"""Per-visitor YouTube connection.

Each visitor's browser keeps its own encrypted YouTube connection (Fernet, APP_SECRET) and sends it as
X-YouTube-Auth. The server never stores it, so every visitor posts to *their own* channel and nobody can
touch anyone else's connection. It also survives free-host restarts because it lives in the browser.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import Header

from .util import decrypt, encrypt


def encode_connection(refresh_token: str, channel_id: Optional[str], channel_title: Optional[str]) -> str:
    return encrypt(json.dumps({"rt": refresh_token, "cid": channel_id, "ct": channel_title}))


def viewer_youtube(x_youtube_auth: Optional[str] = Header(default=None)) -> Optional[dict]:
    """The calling visitor's YouTube connection, or None (missing, tampered or from an old server secret)."""
    if not x_youtube_auth:
        return None
    try:
        data = json.loads(decrypt(x_youtube_auth))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, dict) or not data.get("rt"):
        return None
    return data
