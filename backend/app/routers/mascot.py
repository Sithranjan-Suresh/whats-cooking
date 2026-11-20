"""Mascot creator: describe → 4 options → pick one → it appears on the video's ending."""
from __future__ import annotations

import secrets
import shutil
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..config import get_settings, media_url
from ..db import current_restaurant, get_session, keep_asset_bytes, owned
from ..errors import AppError
from ..models import Asset
from ..serializers import restaurant_out
from ..services import gemini, mascot
from ..viewer import viewer_youtube
from .director import _limit

router = APIRouter()
_batches_today: dict[str, int] = {}


class MascotIdea(BaseModel):
    description: str = Field(min_length=3, max_length=200)


@router.post("/mascot/options")
async def options(body: MascotIdea, request: Request, session: Session = Depends(get_session)):
    """Four original mascot options (cut out, PNG). A few cents each; capped per visitor and per day."""
    s = get_settings()
    if not s.gemini_enabled:
        raise AppError("ai_unavailable", "Mascots need the AI service, which isn't set up on this server.", 503)
    r = current_restaurant(session)
    today = date.today().isoformat()
    if _batches_today.get(today, 0) >= s.mascot_batches_per_day:
        raise AppError("rate_limited", "Today's mascot designs are used up. Try again tomorrow.", 429)
    _limit("mascot", request, s.mascot_batches_per_hour_per_ip, "mascot designs")
    ok, reason = await mascot.check_description(body.description)
    if not ok:
        raise AppError("mascot_refused", reason or "Let's make an original character instead of an existing one.", 422)
    if today not in _batches_today:
        _batches_today.clear()
    _batches_today[today] = _batches_today.get(today, 0) + 1
    try:
        pngs = await mascot.generate(body.description.strip())
    except gemini.GeminiError as e:
        msg = "The AI is busy. Try again in a minute." if e.kind in ("rate_limit", "timeout") \
            else "Couldn't draw that one. Try describing it a little differently."
        raise AppError("mascot_failed", msg, 502, retryable=True) from e
    out = []
    for png in pngs:
        path = s.media_dir / "assets" / f"mascot_option_{secrets.token_hex(8)}.png"
        path.write_bytes(png)
        a = Asset(restaurant_id=r.id, kind="mascot_option", path=str(path), mime="image/png", bytes=len(png))
        session.add(a)
        session.commit()
        session.refresh(a)
        out.append({"option_id": a.id, "url": media_url(path)})
    return {"options": out}


class Choice(BaseModel):
    option_id: Optional[int] = None  # null = remove the mascot


@router.post("/mascot/choose")
def choose(body: Choice, session: Session = Depends(get_session), yt: Optional[dict] = Depends(viewer_youtube)):
    r = current_restaurant(session)
    if body.option_id is None:
        r.mascot_asset_id = None
    else:
        opt = owned(session, Asset, body.option_id, r, "That mascot option is gone. Make new ones.")
        if opt.kind != "mascot_option" or not Path(opt.path).exists():
            raise AppError("not_found", "That mascot option is gone. Make new ones.", 404)
        dst = get_settings().media_dir / "assets" / f"mascot_{secrets.token_hex(8)}.png"
        shutil.copyfile(opt.path, dst)
        a = Asset(restaurant_id=r.id, kind="mascot", path=str(dst), mime="image/png", bytes=dst.stat().st_size)
        session.add(a)
        session.commit()
        session.refresh(a)
        keep_asset_bytes(session, a)  # survives restarts
        r.mascot_asset_id = a.id
    session.add(r)
    session.commit()
    session.refresh(r)
    return restaurant_out(session, r, yt)
