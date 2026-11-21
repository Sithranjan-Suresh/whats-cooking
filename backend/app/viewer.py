"""YouTube connection for the caller.

Guests: the browser keeps an encrypted connection (Fernet, APP_SECRET) and sends it as X-YouTube-Auth; the server
stores nothing. Signed-in accounts: the connection is saved, encrypted, on the Account (so it works on every
device and survives clearing the browser). The account's connection wins over a browser one.

Linking a connection to an account always goes through the browser that started the connect (POST
/youtube/claim with its own session), never straight from Google's redirect: otherwise someone could get a victim
to link the victim's channel to the attacker's account.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import Header

from .util import decrypt, encrypt

CONNECTION_DAYS = 90  # browser-held connections: a stolen one can't be used forever


def encode_connection(refresh_token: str, channel_id: Optional[str], channel_title: Optional[str]) -> str:
    return encrypt(json.dumps({"rt": refresh_token, "cid": channel_id, "ct": channel_title}))


def decode_connection(blob: Optional[str], ttl_days: Optional[int] = CONNECTION_DAYS) -> Optional[dict]:
    if not blob:
        return None
    try:
        data = json.loads(decrypt(blob, ttl=ttl_days * 86400 if ttl_days else None))
    except Exception:  # noqa: BLE001  (tampered, old secret, or expired: reconnect)
        return None
    if not isinstance(data, dict) or not data.get("rt"):
        return None
    return data


def account_connection(account_id: Optional[int]) -> Optional[dict]:
    """The signed-in account's saved connection (no age limit: it lives server-side, revocable on disconnect)."""
    if not account_id:
        return None
    from sqlmodel import Session

    from .db import get_engine
    from .models import Account

    with Session(get_engine()) as s:
        acct = s.get(Account, account_id)
        blob = acct.youtube_conn if acct else None
    data = decode_connection(blob, ttl_days=None)
    if data is not None:
        data["source"] = "account"
    return data


def viewer_youtube(x_youtube_auth: Optional[str] = Header(default=None)) -> Optional[dict]:
    """The caller's YouTube connection: the account's if signed in and linked, else this browser's, else None."""
    from .db import account_var

    data = account_connection(account_var.get())
    if data is not None:
        return data
    data = decode_connection(x_youtube_auth)
    if data is not None:
        data["source"] = "browser"
    return data
