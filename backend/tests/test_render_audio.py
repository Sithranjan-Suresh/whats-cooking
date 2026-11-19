"""Regression: a long narration (sped up with atempo) mixed with music must not come out silent."""
import asyncio
import re
import subprocess
from pathlib import Path

from app.services import render


def _mean_db(path: Path) -> float:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"mean_volume: (-?[\d.]+) dB", out)
    return float(m.group(1)) if m else -999.0


def test_long_voice_plus_music_is_audible(tmp_path, fresh_db):
    w = tmp_path
    sh = lambda *a: subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *a], check=True, cwd=w)  # noqa: E731
    sh("-f", "lavfi", "-i", "sine=f=300:d=7", "-ac", "1", "-ar", "24000", "voice.mp3")  # longer than the 5.7s slot → atempo
    sh("-f", "lavfi", "-i", "sine=f=500:d=20", "-ac", "2", "music.mp3")
    sh("-f", "lavfi", "-i", "color=c=red:s=720x1280:r=30:d=5.7", "-pix_fmt", "yuv420p", "vis.mp4")
    main_len = 8 - render.END_CARD_S

    async def go():
        card = await render.animated_end_card(w, restaurant_name="K", dish_name="D", price="$1.00",
                                              color_primary="#C49A4A", color_accent="#F3EBDD", logo_path=None)
        ass = render.build_ass({"hook": "hi", "beats": [{"caption": "a", "seconds": 2}]}, main_len,
                               color_primary="#C49A4A", color_accent="#F3EBDD")
        return await render.assemble(work=w, visuals=w / "vis.mp4", main_len=main_len, ass_text=ass, end_card_png=card,
                                     voice={"path": str(w / "voice.mp3"), "duration_s": 7.0}, music=w / "music.mp3",
                                     out_path=w / "out.mp4")

    out = asyncio.run(go())
    assert _mean_db(out) > -45, "final video audio is silent"
