"""Veo image-to-video (paid, capped). Raises VeoError(kind) on any failure so the caller can fall back."""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from ..config import get_settings
from .media import probe_video

log = logging.getLogger("app.veo")


class VeoError(Exception):
    def __init__(self, kind: str, message: str = ""):
        super().__init__(message or kind)
        self.kind = kind  # unavailable|timeout|blocked|api|corrupt|rate_limit


FALLBACK_REASONS = {
    "unavailable": "veo_unavailable",
    "timeout": "veo_timeout",
    "blocked": "veo_blocked",
    "api": "veo_error",
    "corrupt": "veo_error",
    "rate_limit": "veo_rate_limit",
}


async def generate_clip(photo: Path, mime: str, prompt: str, out_path: Path, *, seconds: int = 8) -> Path:
    s = get_settings()
    if not s.gemini_api_key:
        raise VeoError("unavailable", "GEMINI_API_KEY is not set")
    from google import genai
    from google.genai import errors as gerrors
    from google.genai import types

    client = genai.Client(api_key=s.gemini_api_key)
    image = types.Image(image_bytes=Path(photo).read_bytes(), mime_type=mime)
    cfg = types.GenerateVideosConfig(
        aspect_ratio="9:16",
        duration_seconds=seconds,
        resolution="720p",
        number_of_videos=1,
        negative_prompt="text, captions, watermark, logos, faces, distorted food, extra limbs",
    )
    t0 = time.monotonic()
    try:
        op = await client.aio.models.generate_videos(model=s.veo_model, prompt=prompt, image=image, config=cfg)
        while not op.done:
            if time.monotonic() - t0 > s.veo_timeout_s:
                raise VeoError("timeout", f"Veo took longer than {s.veo_timeout_s}s")
            await asyncio.sleep(s.veo_poll_s)
            op = await client.aio.operations.get(op)
    except VeoError:
        raise
    except gerrors.APIError as e:
        code = getattr(e, "code", None)
        if code == 429:
            raise VeoError("rate_limit", str(e)) from e
        raise VeoError("api", f"Veo API error {code}: {e}") from e
    except Exception as e:  # noqa: BLE001
        raise VeoError("api", str(e)) from e

    if op.error:
        msg = str(op.error)
        kind = "blocked" if any(k in msg.lower() for k in ("safety", "filter", "policy", "rai")) else "api"
        raise VeoError(kind, msg)
    resp = op.response or op.result
    vids = getattr(resp, "generated_videos", None) or []
    if not vids:
        reasons = getattr(resp, "rai_media_filtered_reasons", None)
        raise VeoError("blocked", f"no video returned {reasons or ''}")
    video = vids[0].video
    try:
        data = None
        if getattr(video, "video_bytes", None):
            data = video.video_bytes
        else:
            data = await client.aio.files.download(file=video)
        if not data:
            raise VeoError("corrupt", "empty download")
        out_path.write_bytes(data)
    except VeoError:
        raise
    except Exception as e:  # noqa: BLE001
        raise VeoError("api", f"download failed: {e}") from e
    try:
        info = await probe_video(out_path)
        if info["duration_s"] < 1 or info["width"] == 0:
            raise VeoError("corrupt", "clip too short or unreadable")
    except VeoError:
        raise
    except Exception as e:  # noqa: BLE001
        raise VeoError("corrupt", str(e)) from e
    log.info("veo clip ok in %.1fs", time.monotonic() - t0)
    return out_path
