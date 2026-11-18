"""Voiceover: edge-tts (with word timings) → gTTS fallback → None (captions-only)."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from .media import probe_duration

log = logging.getLogger("app.tts")

VOICES = {
    "en-US-AriaNeural": "Aria (US, female)",
    "en-US-GuyNeural": "Guy (US, male)",
    "en-US-JennyNeural": "Jenny (US, female)",
    "en-US-AndrewNeural": "Andrew (US, male)",
    "en-GB-SoniaNeural": "Sonia (UK, female)",
    "en-IN-NeerjaNeural": "Neerja (India, female)",
    "en-IN-PrabhatNeural": "Prabhat (India, male)",
}

TONE_RATE = {"upbeat": "+8%", "friendly": "+0%", "elegant": "-6%"}


async def _edge(text: str, voice: str, out: Path, rate: str) -> list[dict]:
    import edge_tts

    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or None
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary", proxy=proxy)
    timings: list[dict] = []
    with open(out, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                timings.append({"word": chunk["text"], "start": start, "end": start + chunk["duration"] / 1e7})
    return timings


def _gtts(text: str, out: Path) -> None:
    from gtts import gTTS

    gTTS(text=text, lang="en").save(str(out))


async def synthesize(text: str, voice: str, out_path: Path, tone: str = "upbeat") -> Optional[dict]:
    """Returns {path, duration_s, timings|None, engine} or None for captions-only."""
    text = (text or "").strip()
    if not text:
        return None
    rate = TONE_RATE.get(tone, "+0%")
    for attempt in range(2):
        try:
            timings = await asyncio.wait_for(_edge(text, voice or "en-US-AriaNeural", out_path, rate), timeout=15)
            dur = await probe_duration(out_path)
            if dur and dur > 0.3:
                return {"path": str(out_path), "duration_s": dur, "timings": timings or None, "engine": "edge-tts"}
            log.warning("edge-tts produced empty audio (attempt %s)", attempt + 1)
        except Exception as e:  # noqa: BLE001
            log.warning("edge-tts failed (attempt %s): %s", attempt + 1, e)
    try:
        await asyncio.wait_for(asyncio.to_thread(_gtts, text, out_path), timeout=20)
        dur = await probe_duration(out_path)
        if dur and dur > 0.3:
            return {"path": str(out_path), "duration_s": dur, "timings": None, "engine": "gtts"}
    except Exception as e:  # noqa: BLE001
        log.warning("gTTS failed: %s", e)
    return None
