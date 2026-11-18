"""Videos + YouTube OAuth/publish."""
from __future__ import annotations

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..auth import Actor, get_actor, require_owner
from ..config import get_settings
from ..db import current_restaurant, get_session, session_scope
from ..errors import AppError
from ..models import Video, YouTubeAuth, jdump
from ..serializers import video_out
from ..services import youtube
from ..util import decrypt, encrypt

log = logging.getLogger("app.videos")
router = APIRouter()


@router.get("/videos")
def list_videos(session: Session = Depends(get_session)):
    r = current_restaurant(session)
    rows = session.exec(select(Video).where(Video.restaurant_id == r.id).order_by(Video.created_at.desc())).all()
    return [video_out(session, v) for v in rows]


@router.get("/videos/{video_id}")
def get_video(video_id: int, session: Session = Depends(get_session)):
    v = session.get(Video, video_id)
    if not v:
        raise AppError("not_found", "Video not found", 404)
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
        if e.code == "youtube_reconnect_required":
            with session_scope() as s:
                v = s.get(Video, video_id)
                auth = s.get(YouTubeAuth, v.restaurant_id)
                if auth:
                    s.delete(auth)
                    s.commit()
    except Exception as e:  # noqa: BLE001
        log.exception("publish crashed")
        _set_video(video_id, publish_status="failed", publish_error=f"Upload failed: {e}"[:300])


_tasks: set[asyncio.Task] = set()


@router.post("/videos/{video_id}/publish", status_code=202)
async def publish(video_id: int, body: PublishBody, actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    require_owner(actor)
    v = session.get(Video, video_id)
    if not v:
        raise AppError("not_found", "Video not found", 404)
    if v.publish_status == "publishing":
        raise AppError("already_publishing", "Already publishing.", 409)
    auth = session.get(YouTubeAuth, v.restaurant_id)
    if not auth:
        raise AppError("youtube_not_connected", "Connect YouTube in Settings first.", 409)
    try:
        token = decrypt(auth.refresh_token)
    except RuntimeError as e:
        raise AppError("youtube_reconnect_required", "Reconnect YouTube in Settings.", 409) from e
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


# ------------------------------------------------------------------ YouTube OAuth

@router.get("/youtube/auth/start")
def yt_start(token: str | None = None, session: Session = Depends(get_session)):
    # Browser navigation can't send headers, so the owner token comes as a query param here.
    from ..auth import resolve_actor

    require_owner(resolve_actor(token))
    r = current_restaurant(session)
    try:
        return RedirectResponse(youtube.auth_url(r.id), status_code=302)
    except youtube.YouTubeError as e:
        raise AppError(e.code, e.message, 400) from e


@router.get("/youtube/auth/callback")
def yt_callback(code: str | None = None, state: str | None = None, error: str | None = None,
                session: Session = Depends(get_session)):
    front = get_settings().frontend_origin.rstrip("/")
    if error or not code or not state:
        return RedirectResponse(f"{front}/settings?youtube=error&reason={error or 'missing_code'}", status_code=302)
    try:
        info = youtube.exchange_code(code, state)
    except youtube.YouTubeError as e:
        return RedirectResponse(f"{front}/settings?youtube=error&reason={e.code}", status_code=302)
    except Exception:  # noqa: BLE001
        log.exception("oauth exchange failed")
        return RedirectResponse(f"{front}/settings?youtube=error&reason=exchange_failed", status_code=302)
    auth = session.get(YouTubeAuth, info["restaurant_id"]) or YouTubeAuth(
        restaurant_id=info["restaurant_id"], refresh_token="")
    auth.refresh_token = encrypt(info["refresh_token"])
    auth.channel_id = info["channel_id"]
    auth.channel_title = info["channel_title"]
    session.add(auth)
    session.commit()
    return RedirectResponse(f"{front}/settings?youtube=connected", status_code=302)


@router.post("/youtube/disconnect")
def yt_disconnect(actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    require_owner(actor)
    r = current_restaurant(session)
    auth = session.get(YouTubeAuth, r.id)
    if auth:
        session.delete(auth)
        session.commit()
    return {"ok": True}
