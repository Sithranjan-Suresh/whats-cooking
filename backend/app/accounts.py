"""Signed-in sessions (Google sign-in). Stateless: the browser keeps an encrypted token (APP_SECRET) and sends it
as X-Session; the server stores only the Account row. Signing out = the browser forgets the token."""
from __future__ import annotations

import json
import time
from typing import Optional

from .util import decrypt, encrypt

SESSION_DAYS = 90


def encode_session(account_id: int) -> str:
    return encrypt(json.dumps({"a": account_id, "t": int(time.time())}))


def decode_session(token: Optional[str]) -> Optional[int]:
    """Account id for a valid, unexpired token; None otherwise (tampered, old secret, expired)."""
    if not token:
        return None
    try:
        data = json.loads(decrypt(token))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, dict) or not isinstance(data.get("a"), int):
        return None
    if time.time() - float(data.get("t", 0)) > SESSION_DAYS * 86400:
        return None
    return data["a"]
