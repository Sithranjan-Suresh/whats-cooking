"""Videos + YouTube OAuth/publish."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import quote
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..auth import Actor, get_actor, require_owner
from ..config import get_settings
from ..db import current_restaurant, get_session, owned, session_scope
from ..errors import AppError
from ..models import Video, jdump
from ..serializers import video_out
from ..services import youtube
from ..viewer import encode_connection, viewer_youtube

log = logging.getLogger("app.videos")
router = APIRouter()


@router.get("/videos")
def list_videos(session: Session = Depends(get_session)):
    r = current_restaurant(session)
    rows = session.exec(select(Video).where(Video.restaurant_id == r.id).order_by(Video.created_at.desc())).all()
    # Files live on the host's disk and are backed up in the DB (mediastore); hide only ones that are truly gone.
    from ..services import mediastore

    stored = mediastore.stored_keys(mediastore.key_for(Path(v.path)) for v in rows)
    return [video_out(session, v) for v in rows if Path(v.path).exists() or mediastore.key_for(Path(v.path)) in stored]


@router.get("/videos/{video_id}")
def get_video(video_id: int, session: Session = Depends(get_session)):
    v = owned(session, Video, video_id, current_restaurant(session), "Video not found")
    return video_out(session, v)


class PublishBody(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=4500)
    tags: list[str] = Field(default_factory=list)
    privacy: Literal["private", "unlisted", "public"] = "private"


def _set_video(video_id: int, **fields) -> None:
    with session_scope() as s:
        v = s.get(Video, video_id)
        for k, val in fields.items():
            setattr(v, k, val)
        s.add(v)
        s.commit()


async def _publish_task(video_id: int, refresh_token: str, body: PublishBody) -> None:
    with session_scope() as s:
        path = s.get(Video, video_id).path
    last = {"p": -1}

    def progress(p: int) -> None:
        if p != last["p"]:
            last["p"] = p
            _set_video(video_id, publish_progress=p)

    try:
        res = await asyncio.to_thread(
            youtube.upload, refresh_token, path, title=body.title, description=body.description,
            tags=body.tags, privacy=body.privacy, on_progress=progress,
        )
        _set_video(video_id, youtube_id=res["id"], youtube_url=res["url"], youtube_privacy=res["privacy"],
                   publish_status="published", publish_error=None, publish_progress=100)
    except youtube.YouTubeError as e:
        log.warning("publish failed: %s", e.message)
        _set_video(video_id, publish_status="failed", publish_error=e.message)
    except Exception as e:  # noqa: BLE001
        log.exception("publish crashed")
        log.exception("publish %s failed", video_id)  # details stay in the server log
        _set_video(video_id, publish_status="failed", publish_error="Upload to YouTube failed. Try posting again.")


_tasks: set[asyncio.Task] = set()


def _require_youtube(yt: Optional[dict]) -> dict:
    if not yt:
        raise AppError("youtube_not_connected", "Connect your YouTube channel first.", 409)
    return yt


@router.post("/videos/{video_id}/publish", status_code=202)
async def publish(video_id: int, body: PublishBody, actor: Actor = Depends(get_actor),
                  yt: Optional[dict] = Depends(viewer_youtube), session: Session = Depends(get_session)):
    """Posts to the *calling visitor's* channel (their browser's connection)."""
    require_owner(actor)
    v = owned(session, Video, video_id, current_restaurant(session), "Video not found")
    if v.publish_status == "publishing":
        raise AppError("already_publishing", "Already posting this one.", 409)
    token = _require_youtube(yt)["rt"]
    from ..services import mediastore

    if not await asyncio.to_thread(mediastore.restore, Path(v.path)):
        raise AppError("video_gone", "This video's file is no longer available. Make it again to post it.", 410)
    v.publish_status = "publishing"
    v.publish_error = None
    v.publish_progress = 0
    v.title = body.title
    v.description = body.description
    v.hashtags_json = jdump(body.tags)
    session.add(v)
    session.commit()
    t = asyncio.create_task(_publish_task(video_id, token, body))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
    return JSONResponse({"publish_status": "publishing"}, status_code=202)


# ------------------------------------------------------------------ YouTube OAuth (per visitor)

@router.get("/youtube/auth/url")
def yt_auth_url(nonce: str = Query(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
                session: Session = Depends(get_session)):
    """Google consent URL; the frontend navigates to it. Anyone can connect their own channel."""
    r = current_restaurant(session)
    try:
        return {"url": youtube.auth_url(r.id, nonce)}
    except youtube.YouTubeError as e:
        raise AppError(e.code, e.message, 400) from e


@router.get("/youtube/auth/callback")
def yt_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    front = get_settings().frontend_origin.split(",")[0].strip().rstrip("/")
    if error or not code or not state:
        purpose = _purpose(state)
        kind = "signin" if purpose == "login" else "youtube"
        return RedirectResponse(f"{front}/?{kind}=error&reason={error or 'missing_code'}", status_code=302)
    if _purpose(state) == "login":  # Google sign-in shares this redirect URI
        from .director import _limit

        try:
            _limit("signin_cb", request, get_settings().signins_per_hour_per_ip, "sign-in attempts")
        except AppError:
            return RedirectResponse(f"{front}/?signin=error&reason=rate_limited", status_code=302)
        return _finish_login(code, state, front)
    try:
        info = youtube.exchange_code(code, state)
    except youtube.YouTubeError as e:
        return RedirectResponse(f"{front}/?youtube=error&reason={e.code}", status_code=302)
    except Exception:  # noqa: BLE001
        log.exception("oauth exchange failed")
        return RedirectResponse(f"{front}/?youtube=error&reason=exchange_failed", status_code=302)
    # Handed to this visitor's browser only (URL fragment never reaches server logs); not stored server-side.
    blob = encode_connection(info["refresh_token"], info["channel_id"], info["channel_title"])
    # n= echoes the browser's nonce: the page keeps the connection only if it matches the one it started with.
    return RedirectResponse(f"{front}/?youtube=connected#yt={quote(blob)}&n={quote(info.get('nonce') or '')}",
                            status_code=302)


def _purpose(state: Optional[str]) -> str:
    if not state:
        return "youtube"
    try:
        return youtube.state_purpose(state)
    except youtube.YouTubeError:
        return "youtube"


def _finish_login(code: str, state: str, front: str) -> RedirectResponse:
    """Google sign-in: upsert the account, hand the browser an encrypted session (URL fragment) + its nonce."""
    from ..accounts import encode_session
    from ..models import Account, utcnow

    try:
        info = youtube.exchange_login(code, state)
    except youtube.YouTubeError as e:
        return RedirectResponse(f"{front}/?signin=error&reason={e.code}", status_code=302)
    except Exception:  # noqa: BLE001
        log.exception("sign-in exchange failed")
        return RedirectResponse(f"{front}/?signin=error&reason=exchange_failed", status_code=302)
    with session_scope() as s:
        acct = s.exec(select(Account).where(Account.google_sub == info["sub"])).first()
        if acct is None:
            acct = Account(google_sub=info["sub"])
        acct.email, acct.name, acct.picture = info["email"], info["name"], info["picture"]
        acct.last_login_at = utcnow()
        s.add(acct)
        s.commit()
        s.refresh(acct)
        token = encode_session(acct.id)
    return RedirectResponse(f"{front}/?signin=ok#session={quote(token)}&n={quote(info.get('nonce') or '')}",
                            status_code=302)


@router.get("/youtube/uploads")
async def yt_uploads(yt: Optional[dict] = Depends(viewer_youtube), session: Session = Depends(get_session)):
    """This visitor's videos made with What's Cooking?, read live from their channel."""
    token = _require_youtube(yt)["rt"]
    r = current_restaurant(session)
    known = {v.youtube_id for v in session.exec(select(Video).where(Video.restaurant_id == r.id)).all() if v.youtube_id}
    try:
        return await asyncio.to_thread(youtube.list_uploads, token, known_ids=known)
    except youtube.YouTubeError as e:
        raise AppError(e.code, e.message, 409) from e
    except Exception as e:  # noqa: BLE001
        log.warning("list uploads failed: %s", e)
        raise AppError("youtube_error", "Couldn't load your YouTube videos right now.", 502, retryable=True) from e


class Claim(BaseModel):
    connection: str = Field(min_length=20, max_length=4000)


@router.post("/youtube/claim")
def yt_claim(body: Claim, session: Session = Depends(get_session)):
    """Signed in: save a connection this browser holds (fresh from connect, or from before signing in) to the account."""
    from ..db import account_var
    from ..models import Account
    from ..viewer import decode_connection, encode_connection

    acct_id = account_var.get()
    if not acct_id:
        raise AppError("signin_required", "Sign in to save YouTube to your account.", 401)
    data = decode_connection(body.connection)
    if data is None:
        raise AppError("youtube_reconnect_required", "That YouTube connection expired. Connect again.", 400)
    acct = session.get(Account, acct_id)
    if acct is None:
        raise AppError("signin_required", "Sign in again.", 401)
    acct.youtube_conn = encode_connection(data["rt"], data.get("cid"), data.get("ct"))
    session.add(acct)
    session.commit()
    return {"ok": True, "channel_title": data.get("ct")}


@router.post("/youtube/disconnect")
def yt_disconnect(yt: Optional[dict] = Depends(viewer_youtube), session: Session = Depends(get_session)):
    """Revoke the connection at Google and forget it (account copy deleted; the browser drops its own copy)."""
    from ..db import account_var
    from ..models import Account

    if yt:
        youtube.revoke(yt["rt"])  # best effort: the token stops working even if someone copied it
    acct_id = account_var.get()
    if acct_id:
        acct = session.get(Account, acct_id)
        if acct and acct.youtube_conn:
            acct.youtube_conn = None
            session.add(acct)
            session.commit()
    return {"ok": True}
