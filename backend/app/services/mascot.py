"""Mascot creator: an original cartoon character for the restaurant, generated from a description (4 options),
cut out from its plain background so it can sit on the video's ending."""
from __future__ import annotations

import asyncio
import io
import logging

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from ..config import get_settings
from . import gemini
from .gemini import GeminiError

log = logging.getLogger(__name__)
N_OPTIONS = 4
STYLES = [
    "bold flat vector cartoon, thick dark outlines, bright friendly colors",
    "soft 3D toy style, rounded shapes, glossy",
    "retro 1950s diner mascot, cel-shaded",
    "cute kawaii sticker style, chunky outlines",
]

CHECK_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["ok", "reason"],
}


async def check_description(description: str) -> tuple[bool, str]:
    """Refuse famous/copyrighted characters, real people, brands, and anything not family-friendly."""
    try:
        d = await gemini.generate_json(
            f"DESCRIPTION: {description}\nIs this an ORIGINAL mascot idea (not an existing copyrighted or trademarked "
            "character, brand mascot, celebrity or real person) that is family-friendly? If not, `reason` says why in "
            "one short friendly sentence.", CHECK_SCHEMA, timeout_s=15, temperature=0)
        return bool(d.get("ok")), str(d.get("reason") or "")
    except GeminiError:
        return True, ""  # the image model also refuses; don't block on a flaky check


def _prompt(description: str, style: str) -> str:
    return (f"An original cartoon mascot character for a restaurant: {description}. Style: {style}. Full body, "
            "centered, friendly pose, facing the viewer. Plain solid pure white background. No text, no letters, no "
            "logos, no frame, no shadow on the ground.")


async def _generate_one(description: str, style: str) -> bytes:
    from google.genai import errors as gerrors
    from google.genai import types

    client = gemini._get_client()
    try:
        resp = await asyncio.wait_for(client.aio.models.generate_content(
            model=get_settings().director_image_model, contents=[_prompt(description, style)],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"],
                                               image_config=types.ImageConfig(aspect_ratio="1:1")),
        ), timeout=60)
    except asyncio.TimeoutError as e:
        raise GeminiError("timeout", "mascot took too long") from e
    except gerrors.APIError as e:
        raise GeminiError("rate_limit" if getattr(e, "code", None) == 429 else "api", str(e)) from e
    for cand in resp.candidates or []:
        for part in (cand.content.parts if cand.content else []) or []:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data
    raise GeminiError("blocked", "no image returned")


def cut_out(png: bytes, size: int = 640) -> bytes:
    """Make the plain background transparent, trim, and scale to fit `size`.

    Background = light pixels connected to the image edge. The connectivity flood fill (pure Python in PIL) runs on a
    160px copy; the crisp edge comes from a full-resolution near-white test. Inner whites (a chef hat, eyes) stay.
    """
    im = Image.open(io.BytesIO(png)).convert("RGB")
    im.thumbnail((size, size), Image.LANCZOS)
    w, h = im.size
    small = im.resize((max(1, w // 4), max(1, h // 4)), Image.BILINEAR)
    sw, sh = small.size
    sentinel = (255, 0, 255)
    for xy in [(0, 0), (sw - 1, 0), (0, sh - 1), (sw - 1, sh - 1), (sw // 2, 0), (sw // 2, sh - 1), (0, sh // 2), (sw - 1, sh // 2)]:
        px = small.getpixel(xy)
        if px != sentinel and min(px) > 200:  # light background only
            ImageDraw.floodfill(small, xy, sentinel, thresh=48)
    r, g, b = small.split()
    connected = ImageChops.multiply(ImageChops.multiply(r.point(lambda v: 255 if v == 255 else 0),
                                                        g.point(lambda v: 255 if v == 0 else 0)),
                                    b.point(lambda v: 255 if v == 255 else 0))
    # grow it a little so it covers the anti-aliased rim, then back to full size
    connected = connected.filter(ImageFilter.MaxFilter(3)).resize((w, h), Image.BILINEAR).point(lambda v: 255 if v > 64 else 0)
    light = im.convert("L").point(lambda v: 255 if v > 205 else 0)
    is_bg = ImageChops.multiply(connected, light)
    mask = ImageChops.invert(is_bg).filter(ImageFilter.GaussianBlur(1.2))
    out = im.convert("RGBA")
    out.putalpha(mask)
    bbox = mask.point(lambda v: 255 if v > 20 else 0).getbbox()
    if bbox:
        out = out.crop(bbox)
    buf = io.BytesIO()
    out.save(buf, "PNG", compress_level=6)  # optimize=True was 80% of the time on a slow CPU
    return buf.getvalue()


async def generate(description: str) -> list[bytes]:
    """N_OPTIONS cut-out PNGs (different styles). Raises GeminiError if none came back."""
    results = await asyncio.gather(*[_generate_one(description, st) for st in STYLES[:N_OPTIONS]], return_exceptions=True)
    out = []
    for r in results:
        if isinstance(r, Exception):
            log.info("mascot option failed: %s", r)
            continue
        try:
            out.append(await asyncio.to_thread(cut_out, r))
        except Exception:  # noqa: BLE001
            log.exception("mascot cut-out failed")
    if not out:
        raise GeminiError("blocked", "no mascot options")
    return out
