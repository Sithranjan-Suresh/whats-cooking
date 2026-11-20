"""Keep rendered media (videos, posters, AI clips) in the database so free-host restarts don't lose them.

Files are still served from the local disk (cheap: no database egress per view). After a restart a missing file is
written back from the database the first time it's requested (main.MediaRestoreMiddleware). The total is capped
(MEDIA_DB_CAP_MB): AI clips go first (only needed for free caption edits), then videos already on YouTube, then the
oldest. Swap this module for an S3/R2 client later without touching the callers.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import delete
from sqlmodel import Session, select

from ..config import get_settings
from ..db import get_engine
from ..models import MediaBlob, Video

log = logging.getLogger(__name__)
KINDS = {"videos": "video", "posters": "poster", "clips": "clip"}


def key_for(path: Path) -> Optional[str]:
    try:
        rel = Path(path).resolve().relative_to(get_settings().media_dir.resolve())
    except ValueError:
        return None
    return rel.as_posix() if rel.parts and rel.parts[0] in KINDS else None


def keep(path: Path) -> None:
    """Store a file (best effort: never fails the caller)."""
    key = key_for(path)
    if not key or not Path(path).exists():
        return
    try:
        data = Path(path).read_bytes()
        with Session(get_engine()) as s:
            s.merge(MediaBlob(key=key, kind=KINDS[key.split("/", 1)[0]], size=len(data), data=data))
            s.commit()
        evict()
    except Exception:  # noqa: BLE001
        log.exception("couldn't keep %s in the database", key)


def restore(path: Path) -> bool:
    """Write a missing file back from the database. True if the file exists afterwards."""
    p = Path(path)
    if p.exists():
        return True
    key = key_for(p)
    if not key:
        return False
    with Session(get_engine()) as s:
        blob = s.get(MediaBlob, key)
        if blob is None:
            return False
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + f".{os.getpid()}.part")
        tmp.write_bytes(blob.data)
        tmp.replace(p)  # atomic: a parallel request never sees half a file
    return True


def stored_keys(keys: Iterable[str]) -> set[str]:
    keys = [k for k in keys if k]
    if not keys:
        return set()
    with Session(get_engine()) as s:
        return set(s.exec(select(MediaBlob.key).where(MediaBlob.key.in_(keys))).all())


def evict() -> None:
    cap = get_settings().media_db_cap_mb * 1024 * 1024
    with Session(get_engine()) as s:
        rows = s.exec(select(MediaBlob.key, MediaBlob.kind, MediaBlob.size, MediaBlob.created_at)).all()
        total = sum(r[2] for r in rows)
        if total <= cap:
            return
        posted = {
            key_for(Path(v.path)) for v in s.exec(select(Video).where(Video.youtube_id.is_not(None))).all()
        }
        rank = {"clip": 0, "video": 2, "poster": 2}
        order = sorted(rows, key=lambda r: (rank[r[1]] - (1 if r[0] in posted else 0), r[3]))
        victims = []
        for key, kind, size, _ in order:
            if total <= cap:
                break
            victims.append(key)
            total -= size
        if victims:
            s.exec(delete(MediaBlob).where(MediaBlob.key.in_(victims)))
            s.commit()
            log.info("media store over cap: cleared %d files", len(victims))
