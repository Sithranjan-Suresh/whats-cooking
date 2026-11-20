"""Google sign-in. See accounts.py (sessions) and db.current_restaurant (account studios, guest claim)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from ..db import account_var, get_session
from ..errors import AppError
from ..models import Account
from ..services import youtube

router = APIRouter()


@router.get("/auth/google/url")
def google_url(nonce: str = Query(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")):
    """Google consent URL for signing in. The browser keeps `nonce` and accepts only a session that echoes it."""
    try:
        return {"url": youtube.login_url(nonce)}
    except youtube.YouTubeError as e:
        raise AppError(e.code, e.message, 400) from e


@router.get("/auth/me")
def me(session: Session = Depends(get_session)):
    acct_id = account_var.get()
    acct = session.get(Account, acct_id) if acct_id else None
    if acct is None:
        return {"account": None}
    return {"account": {"id": acct.id, "email": acct.email, "name": acct.name, "picture": acct.picture}}
