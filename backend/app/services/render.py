"""Rendering: Ken Burns visuals, Veo+tail composition, ASS captions, end card, final assembly."""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..config import get_settings
from .media import FFmpegError, ffmpeg, probe_video

log = logging.getLogger("app.render")

W, H, FPS = 720, 1280, 30
SRC_W, SRC_H = 1440, 2560  # 2x oversample to keep zoompan smooth
XFADE = 0.5
END_CARD_S = 1.5
END_XFADE = 0.25

STYLE_PRESETS = {
    "bold": {"size": 78, "outline": 5, "shadow": 2, "pop": True, "fade_in": 90, "fade_out": 60, "chars": 17, "kb": "dynamic"},
    "warm": {"size": 66, "outline": 3, "shadow": 3, "pop": False, "fade_in": 320, "fade_out": 260, "chars": 19, "kb": "slow"},
    "minimal": {"size": 50, "outline": 2, "shadow": 0, "pop": False, "fade_in": 180, "fade_out": 180, "chars": 24, "kb": "slow"},
}


# ------------------------------------------------------------------ helpers

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = (h or "#C49A4A").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return (196, 154, 74)


def ass_color(h: str, alpha: int = 0) -> str:
    r, g, b = _hex_to_rgb(h)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def _luminance(h: str) -> float:
    r, g, b = (c / 255 for c in _hex_to_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def link_fonts(work: Path) -> None:
    dst = work / "fonts"
    if not dst.exists():
        try:
            os.symlink(get_settings().fonts_dir, dst)
        except OSError:
            shutil.copytree(get_settings().fonts_dir, dst)


def _font(name: str, size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    fd = get_settings().fonts_dir
    if name == "oswald":
        f = ImageFont.truetype(str(fd / "Oswald.ttf"), size)
        try:
            f.set_variation_by_name("Bold" if bold else "Regular")
        except Exception:  # noqa: BLE001
            pass
        return f
    return ImageFont.truetype(str(fd / ("Inter-Bold.otf" if bold else "Inter-Regular.otf")), size)


# ------------------------------------------------------------------ photo prep

def load_photo(path: Path) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def crops_for(img: Image.Image, n: int) -> list[Image.Image]:
    """n different 9:16 crops at SRC_W×SRC_H. Landscape photos pan across, portrait ones vary vertically."""
    w, h = img.size
    target = 9 / 16
    out = []
    if w / h > target:  # wider than 9:16 → crop width, vary x
        cw, ch = int(h * target), h
        xs = [0.5, 0.25, 0.75][:n] if n > 1 else [0.5]
        for fx in xs:
            x = int((w - cw) * fx)
            out.append(img.crop((x, 0, x + cw, ch)))
    else:  # taller → crop height, vary y
        cw, ch = w, int(w / target)
        ys = [0.5, 0.35, 0.65][:n] if n > 1 else [0.5]
        for fy in ys:
            y = int((h - ch) * fy)
            out.append(img.crop((0, y, cw, y + ch)))
    return [c.resize((SRC_W, SRC_H), Image.LANCZOS) for c in out]


def _zoompan(kind: str, frames: int, strength: float = 0.12) -> str:
    d = max(frames - 1, 1)
    center = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    if kind == "in":
        z = f"z='1+{strength}*on/{d}'"
        xy = center
    elif kind == "out":
        z = f"z='{1 + strength}-{strength}*on/{d}'"
        xy = center
    elif kind == "pan_right":
        z = f"z='{1 + strength}'"
        xy = f"x='(iw-iw/zoom)*on/{d}':y='ih/2-(ih/zoom/2)'"
    else:  # pan_up
        z = f"z='{1 + strength}'"
        xy = f"x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/{d})'"
    return f"zoompan={z}:{xy}:d={frames}:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p"


async def kenburns(photo: Path, total_s: float, work: Path, *, style: str = "bold", tag: str = "kb") -> Path:
    """Build total_s seconds of 720×1280 motion from one photo (2–3 crossfaded crops)."""
    img = load_photo(photo)
    n = 1 if total_s < 4 else (2 if total_s < 9 else 3)
    crops = crops_for(img, n)
    seg = (total_s + (n - 1) * XFADE) / n
    frames = int(round(seg * FPS))
    preset = STYLE_PRESETS.get(style, STYLE_PRESETS["bold"])
    strength = 0.14 if preset["kb"] == "dynamic" else 0.08
    kinds = ["in", "pan_right", "out"] if n == 3 else (["in", "out"] if n == 2 else ["in"])
    args: list[str] = []
    for i, c in enumerate(crops):
        p = work / f"{tag}_src{i}.jpg"
        c.save(p, quality=92)
        args += ["-i", p.name]
    fc = []
    for i in range(n):
        fc.append(f"[{i}:v]{_zoompan(kinds[i], frames, strength)}[z{i}]")
    last = "z0"
    for i in range(1, n):
        offset = i * (seg - XFADE)
        fc.append(f"[{last}][z{i}]xfade=transition=fade:duration={XFADE}:offset={offset:.3f}[x{i}]")
        last = f"x{i}"
    out = work / f"{tag}.mp4"
    await ffmpeg(
        [*args, "-filter_complex", ";".join(fc), "-map", f"[{last}]", "-t", f"{total_s:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS), out.name],
        cwd=work,
    )
    return out


async def veo_plus_tail(veo_clip: Path, photo: Path, total_s: float, work: Path, *, style: str = "bold") -> Path:
    """Veo clip (normalized, max 8s) + Ken Burns tail on the same photo, crossfaded."""
    info = await probe_video(veo_clip)
    veo_len = min(8.0, info["duration_s"] or 8.0)
    if veo_len >= total_s:
        out = work / "visuals.mp4"
        await ffmpeg(
            ["-i", str(veo_clip), "-an", "-vf",
             f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,format=yuv420p",
             "-t", f"{total_s:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out.name],
            cwd=work,
        )
        return out
    tail_len = total_s - veo_len + XFADE
    tail = await kenburns(photo, tail_len, work, style=style, tag="tail")
    out = work / "visuals.mp4"
    fc = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,format=yuv420p,"
        f"trim=0:{veo_len:.3f},setpts=PTS-STARTPTS,settb=AVTB[a];"
        f"[1:v]setsar=1,format=yuv420p,fps={FPS},settb=AVTB[b];"
        f"[a][b]xfade=transition=fade:duration={XFADE}:offset={veo_len - XFADE:.3f}[v]"
    )
    await ffmpeg(
        ["-i", str(veo_clip), "-i", tail.name, "-filter_complex", fc, "-map", "[v]", "-an", "-t", f"{total_s:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", out.name],
        cwd=work,
    )
    return out


# ------------------------------------------------------------------ captions

def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _ass_text(s: str) -> str:
    return s.replace("{", "(").replace("}", ")").replace("\\", "").replace("\n", "\\N")


def caption_font_size(text: str, base: int, chars: int) -> int:
    longest = max((len(line) for line in text.split("\n")), default=1)
    if longest <= chars:
        return base
    return max(int(base * chars / longest), int(base * 0.55))


def beat_windows(beats: list[dict], main_len: float, speech: Optional[tuple[float, float]] = None) -> list[tuple[float, float]]:
    """Spread beats across the speech span (or the main section) proportionally to their seconds."""
    start, end = (0.15, main_len - 0.1)
    if speech:
        start = max(0.1, min(speech[0], 1.0))
        end = min(main_len - 0.1, max(speech[1] + 0.4, main_len * 0.7))
    total = sum(max(b.get("seconds", 1), 0.1) for b in beats) or 1
    span = end - start
    out = []
    t = start
    for b in beats:
        d = span * max(b.get("seconds", 1), 0.1) / total
        out.append((t, t + d))
        t += d
    return out


def build_ass(
    script: dict,
    main_len: float,
    *,
    color_primary: str,
    color_accent: str,
    style: str = "bold",
    speech: Optional[tuple[float, float]] = None,
) -> str:
    p = STYLE_PRESETS.get(style, STYLE_PRESETS["bold"])
    text_col = ass_color(color_accent)
    hook_col = ass_color(color_primary)
    outline = ass_color("#0B0B0B", 0x10)
    back = ass_color("#000000", 0x80)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Beat,Oswald,{p['size']},{text_col},{text_col},{outline},{back},-1,0,0,0,100,100,1,0,1,{p['outline']},{p['shadow']},2,50,50,300,1
Style: Hook,Oswald,{int(p['size'] * 1.05)},{hook_col},{hook_col},{outline},{back},-1,0,0,0,100,100,1,0,1,{p['outline'] + 1},{p['shadow']},8,50,50,230,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    beats = script.get("beats") or []
    windows = beat_windows(beats, main_len, speech)
    pop = "\\fscx70\\fscy70\\t(0,140,\\fscx104\\fscy104)\\t(140,220,\\fscx100\\fscy100)" if p["pop"] else ""
    for b, (s, e) in zip(beats, windows):
        txt = b["caption"]
        fs = caption_font_size(txt, p["size"], p["chars"])
        tags = f"{{\\fad({p['fade_in']},{p['fade_out']}){pop}\\fs{fs}}}"
        lines.append(f"Dialogue: 0,{_ass_time(s)},{_ass_time(e)},Beat,,0,0,0,,{tags}{_ass_text(txt)}")
    hook = (script.get("hook") or "").strip()
    first = (beats[0]["caption"].replace("\n", " ").strip().lower() if beats else "")
    if hook and hook.lower() != first:
        from .scripts import wrap_caption

        htxt = wrap_caption(hook, 20)
        fs = caption_font_size(htxt, int(p["size"] * 1.05), p["chars"])
        hook_end = min(2.6, windows[0][1] if windows else 2.6)
        tags = f"{{\\fad(120,200){pop}\\fs{fs}}}"
        lines.append(f"Dialogue: 1,{_ass_time(0.05)},{_ass_time(hook_end)},Hook,,0,0,0,,{tags}{_ass_text(htxt)}")
    return header + "\n".join(lines) + "\n"


# ------------------------------------------------------------------ end card

def render_end_card(
    out: Path,
    *,
    restaurant_name: str,
    dish_name: Optional[str],
    price: Optional[str],
    color_primary: str,
    color_accent: str,
    logo_path: Optional[Path],
) -> Path:
    bg = _hex_to_rgb(color_primary)
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    dark_bg = _luminance(color_primary) < 0.5
    fg = _hex_to_rgb(color_accent) if dark_bg else (20, 24, 20)
    if dark_bg and _luminance(color_accent) < 0.45:
        fg = (243, 235, 221)
    y = 300
    if logo_path and Path(logo_path).exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((340, 340), Image.LANCZOS)
            img.paste(logo, ((W - logo.width) // 2, y), logo)
            y += logo.height + 60
        except Exception as e:  # noqa: BLE001
            log.warning("logo load failed: %s", e)
            y += 120
    else:
        y += 160

    def center(text: str, font, yy: int, fill) -> int:
        bbox = d.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((W - tw) // 2 - bbox[0], yy - bbox[1]), text, font=font, fill=fill)
        return yy + th

    def fit(text: str, family: str, size: int, max_w: int = W - 100):
        f = _font(family, size)
        while size > 28 and d.textlength(text, font=f) > max_w:
            size -= 4
            f = _font(family, size)
        return f

    name = restaurant_name.upper()
    y = center(name, fit(name, "oswald", 104), y, fg) + 46
    d.line([(W // 2 - 70, y), (W // 2 + 70, y)], fill=fg, width=4)
    y += 50
    if dish_name:
        y = center(dish_name, fit(dish_name, "inter", 50), y, fg) + 30
    if price:
        center(price, _font("oswald", 84), y, fg)
    center("ORDER TODAY", _font("inter", 30), H - 170, fg)
    img.save(out, quality=94)
    return out


# ------------------------------------------------------------------ assemble

def _audio_graph(has_voice: bool, has_music: bool, total: float, tempo: float, safe: bool) -> tuple[str, str]:
    """Returns (filter_complex_audio_part, output_label). Voice is input 2, music is input 3 (or 2 if no voice)."""
    fmt = "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo"
    parts = []
    vi, mi = 2, (3 if has_voice else 2)
    if has_voice:
        tempo_f = f",atempo={tempo:.3f}" if tempo > 1.001 else ""
        parts.append(f"[{vi}:a]{fmt}{tempo_f},adelay=300|300,apad,atrim=0:{total:.3f}[vraw]")
    if has_music:
        fade_st = max(total - 1.2, 0)
        parts.append(
            f"[{mi}:a]{fmt},atrim=0:{total:.3f},volume=-18dB,afade=t=in:d=0.6,afade=t=out:st={fade_st:.3f}:d=1.2[mus]"
        )
    if has_voice and has_music:
        if safe:
            parts.append("[vraw][mus]amix=inputs=2:duration=first:normalize=0[aout]")
        else:
            parts.append("[vraw]asplit=2[vo][vsc]")
            parts.append("[mus][vsc]sidechaincompress=threshold=0.04:ratio=6:attack=15:release=350[duck]")
            parts.append("[vo][duck]amix=inputs=2:duration=first:normalize=0[aout]")
        return ";".join(parts), "[aout]"
    if has_voice:
        return ";".join(parts), "[vraw]"
    if has_music:
        return ";".join(parts), "[mus]"
    return f"anullsrc=r=44100:cl=stereo,atrim=0:{total:.3f}[aout]", "[aout]"


async def assemble(
    *,
    work: Path,
    visuals: Path,
    main_len: float,
    ass_text: str,
    end_card_png: Path,
    voice: Optional[dict],
    music: Optional[Path],
    out_path: Path,
    safe: bool = False,
) -> Path:
    link_fonts(work)
    (work / "captions.ass").write_text(ass_text, encoding="utf-8")
    total = main_len + END_CARD_S
    has_voice = bool(voice and Path(voice["path"]).exists())
    has_music = bool(music and Path(music).exists())
    tempo = 1.0
    if has_voice:
        room = main_len - 0.5
        if voice["duration_s"] > room:
            tempo = min(1.3, voice["duration_s"] / room)
    inputs = ["-i", str(visuals), "-loop", "1", "-framerate", str(FPS), "-t", f"{END_CARD_S + END_XFADE:.3f}", "-i", str(end_card_png)]
    if has_voice:
        inputs += ["-i", str(voice["path"])]
    if has_music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
    vf = (
        f"[0:v]setsar=1,format=yuv420p,trim=0:{main_len:.3f},setpts=PTS-STARTPTS,ass=captions.ass:fontsdir=fonts,fps=30,settb=AVTB[main];"
        f"[1:v]scale={W}:{H},setsar=1,format=yuv420p,fps={FPS},settb=AVTB[card];"
        f"[main][card]xfade=transition=fade:duration={END_XFADE}:offset={main_len - END_XFADE:.3f}[vout]"
    )
    af, alabel = _audio_graph(has_voice, has_music, total, tempo, safe)
    preset, crf = ("ultrafast", "26") if safe else ("veryfast", "23")
    await ffmpeg(
        [*inputs, "-filter_complex", vf + ";" + af, "-map", "[vout]", "-map", alabel,
         "-t", f"{total:.3f}", "-r", str(FPS),
         "-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p", "-profile:v", "high",
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", str(out_path)],
        cwd=work,
    )
    return out_path


async def assemble_with_retry(**kw) -> Path:
    try:
        return await assemble(**kw, safe=False)
    except FFmpegError as e:
        log.warning("assemble failed, retrying with safe preset: %s", e.stderr_tail[-400:])
        return await assemble(**kw, safe=True)


async def extract_poster(video: Path, out: Path, at: float = 1.0) -> Path:
    await ffmpeg(["-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1", "-q:v", "3", str(out)], timeout=30)
    return out
