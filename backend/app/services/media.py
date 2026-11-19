"""ffmpeg / ffprobe subprocess helpers."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Sequence

from ..config import get_settings

log = logging.getLogger("app.media")


class FFmpegError(Exception):
    def __init__(self, message: str, stderr_tail: str = ""):
        super().__init__(message)
        self.stderr_tail = stderr_tail


async def run(cmd: Sequence[str], *, cwd: Optional[Path] = None, timeout: Optional[float] = None) -> str:
    timeout = timeout or get_settings().ffmpeg_timeout_s
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError as e:
        proc.kill()
        await proc.wait()
        raise FFmpegError(f"{cmd[0]} timed out after {timeout}s") from e
    if proc.returncode != 0:
        tail = err.decode(errors="replace")[-1500:]
        log.error("%s failed (%s): %s", cmd[0], proc.returncode, tail)
        raise FFmpegError(f"{cmd[0]} exited with {proc.returncode}", tail)
    return out.decode(errors="replace")


_ffmpeg_slots: dict = {}  # event loop → Semaphore (asyncio primitives are bound to one loop)


async def ffmpeg(args: Sequence[str], *, cwd: Optional[Path] = None, timeout: Optional[float] = None) -> None:
    """Run ffmpeg, one at a time per process.

    A 1080x1920 x264 encode can take 300+ MB, so two at once (e.g. end card + AI clip) can blow a 512 MB
    host. FFMPEG_THREADS caps threads per encode (memory grows with threads; containers often see many cores).
    """
    loop = asyncio.get_running_loop()
    slots = _ffmpeg_slots.get(loop)
    if slots is None:
        slots = _ffmpeg_slots[loop] = asyncio.Semaphore(max(1, get_settings().ffmpeg_parallel))
    args = list(args)
    n = get_settings().ffmpeg_threads
    head = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if n > 0:
        head += ["-filter_threads", str(n)]
        args = [*args[:-1], "-threads", str(n), args[-1]]  # output option, placed right before the output file
    async with slots:
        await run([*head, *args], cwd=cwd, timeout=timeout)


async def probe(path: Path) -> dict:
    out = await run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)], timeout=30
    )
    return json.loads(out)


async def probe_duration(path: Path) -> Optional[float]:
    try:
        info = await probe(path)
        return float(info["format"]["duration"])
    except Exception:  # noqa: BLE001
        return None


async def probe_video(path: Path) -> dict:
    info = await probe(path)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if v is None:
        raise FFmpegError("no video stream")
    return {
        "width": int(v.get("width", 0)),
        "height": int(v.get("height", 0)),
        "duration_s": float(info["format"].get("duration", 0) or 0),
        "bytes": int(info["format"].get("size", 0) or 0),
        "has_audio": any(s.get("codec_type") == "audio" for s in info.get("streams", [])),
    }
