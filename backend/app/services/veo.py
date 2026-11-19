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
    if s.veo_model.startswith("gemini-omni"):
        return await _omni_clip(photo, mime, prompt, out_path, seconds=seconds)
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


async def _omni_clip(photo: Path, mime: str, prompt: str, out_path: Path, *, seconds: int = 8) -> Path:
    """Gemini Omni (Veo's successor on the Gemini API): image-to-video via the Interactions API (v1beta)."""
    import base64

    s = get_settings()
    from google import genai

    client = genai.Client(api_key=s.gemini_api_key)
    img = base64.b64encode(Path(photo).read_bytes()).decode()
    body = dict(
        api_version="v1beta",
        model=s.veo_model,
        input=[{"type": "text", "text": prompt}, {"type": "image", "data": img, "mime_type": mime or "image/jpeg"}],
        response_modalities=["video"],
        generation_config={"video_config": {"task": "image_to_video"}},
        response_format={"type": "video", "aspect_ratio": "9:16", "resolution": "720p", "duration": f"{seconds}s",
                         "delivery": "inline"},
        background=True,
    )
    t0 = time.monotonic()
    try:
        r = await asyncio.to_thread(lambda: client.interactions.create(**body))
        iid = r.id
        while getattr(r, "status", None) not in ("completed", "failed", "cancelled", "incomplete"):
            if time.monotonic() - t0 > s.veo_timeout_s:
                raise VeoError("timeout", f"Video model took longer than {s.veo_timeout_s}s")
            await asyncio.sleep(s.veo_poll_s)
            r = await asyncio.to_thread(lambda: client.interactions.get(iid, api_version="v1beta"))
    except VeoError:
        raise
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        low = msg.lower()
        if "429" in msg or "resource_exhausted" in low or "quota" in low:
            raise VeoError("rate_limit", msg[:300]) from e
        if any(k in low for k in ("safety", "blocked", "policy", "prohibited")):
            raise VeoError("blocked", msg[:300]) from e
        raise VeoError("api", msg[:300]) from e
    if r.status != "completed":
        detail = str(getattr(r, "error", "") or r.status)
        kind = "blocked" if any(k in detail.lower() for k in ("safety", "blocked", "policy")) else "api"
        raise VeoError(kind, f"video {r.status}: {detail[:200]}")
    video = getattr(r, "output_video", None)
    data = getattr(video, "data", None) if video is not None else None
    if not data:
        raise VeoError("blocked", "no video returned")
    out_path.write_bytes(base64.b64decode(data))
    try:
        info = await probe_video(out_path)
        if info["duration_s"] < 1 or info["width"] == 0:
            raise VeoError("corrupt", "clip too short or unreadable")
    except VeoError:
        raise
    except Exception as e:  # noqa: BLE001
        raise VeoError("corrupt", str(e)) from e
    log.info("omni clip ok in %.1fs", time.monotonic() - t0)
    return out_path
