"""Director mode: storyboard + chat + preview frame before the (paid) render. See services/director.py."""
from __future__ import annotations

import io
import secrets
import time
from collections import defaultdict, deque
from datetime import date
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Request
from PIL import Image
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..config import get_settings, media_url
from ..db import current_restaurant, get_session, owned
from ..errors import AppError
from ..models import Asset, MenuItem
from ..services import director, gemini, scripts
from .jobs import client_ip

router = APIRouter()

_hits: dict[tuple[str, str], deque] = defaultdict(deque)
_previews_today: dict[str, int] = {}
_plans_today: dict[str, int] = {}


def _limit(bucket: str, request: Request, per_hour: int, what: str) -> None:
    q, now = _hits[(bucket, client_ip(request))], time.time()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= per_hour:
        raise AppError("rate_limited", f"That's a lot of {what} for one hour. Try again a bit later.", 429, retryable=True)
    q.append(now)


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=800)


class PlanBody(BaseModel):
    menu_item_id: int
    message: Optional[str] = Field(default=None, max_length=400)
    storyboard: Optional[dict] = None
    history: list[Turn] = Field(default_factory=list, max_length=24)
    format: Literal["classic", "money_shot", "chef_pov"] = "classic"


def _dish(session: Session, menu_item_id: int) -> tuple[MenuItem, Optional[Asset]]:
    r = current_restaurant(session)
    item = owned(session, MenuItem, menu_item_id, r, "Dish not found")
    asset = session.get(Asset, item.photo_asset_id) if item.photo_asset_id else None
    return item, asset if asset and Path(asset.path).exists() else None


async def _visual_notes(item: MenuItem, asset: Optional[Asset]) -> str:
    if asset is None or not get_settings().gemini_enabled:
        return ""
    key = gemini.cache_key("director_notes", asset.id, item.name)
    hit = gemini.cache_get(key)
    if hit is not None:
        return hit
    try:
        d = await gemini.describe_photo((Path(asset.path).read_bytes(), asset.mime), item.name)
        notes = d.get("visual_notes", "")
    except gemini.GeminiError:
        notes = ""
    gemini.cache_put(key, notes)
    return notes


@router.post("/director/plan")
async def plan(body: PlanBody, request: Request, session: Session = Depends(get_session)):
    """First call: the opening storyboard. Later calls: send `message` + the current storyboard + history."""
    s = get_settings()
    today = date.today().isoformat()
    if _plans_today.get(today, 0) >= s.director_plans_per_day:
        raise AppError("rate_limited", "The AI director is resting for today. Try again tomorrow.", 429)
    _limit("plan", request, s.director_plans_per_hour_per_ip, "director messages")
    if today not in _plans_today:
        _plans_today.clear()
    _plans_today[today] = _plans_today.get(today, 0) + 1
    r = current_restaurant(session)
    item, asset = _dish(session, body.menu_item_id)
    out = await director.plan(
        menu_row=scripts.menu_row_for(item), restaurant_name=r.name, tone=r.voice_tone,
        visual_notes=await _visual_notes(item, asset), current=body.storyboard,
        history=[t.model_dump() for t in body.history], message=(body.message or "").strip() or None,
        fmt=body.format,
    )
    out["storyboard"] = director.public_storyboard(out["storyboard"])
    return out


class PreviewBody(BaseModel):
    menu_item_id: int
    storyboard: dict


@router.post("/director/preview")
async def preview(body: PreviewBody, request: Request, session: Session = Depends(get_session)):
    """One still of the planned shot (a few cents), so the owner can judge it before the paid render."""
    s = get_settings()
    if not s.gemini_enabled:
        raise AppError("ai_unavailable", "Previews need the AI service, which isn't set up on this server.", 503)
    item, asset = _dish(session, body.menu_item_id)
    if asset is None:
        raise AppError("photo_required", f"{item.name} has no photo yet. Add one first.", 400)
    today = date.today().isoformat()
    if _previews_today.get(today, 0) >= s.director_previews_per_day:
        raise AppError("rate_limited", "Today's preview frames are used up. You can still make the video.", 429)
    _limit("preview", request, s.director_previews_per_hour_per_ip, "previews")
    if today not in _previews_today:
        _previews_today.clear()  # new day: forget yesterday's count
    _previews_today[today] = _previews_today.get(today, 0) + 1
    try:
        data, _mime = await director.preview_frame((Path(asset.path).read_bytes(), asset.mime), body.storyboard)
    except gemini.GeminiError as e:
        msg = "The AI is busy. Try the preview again in a minute." if e.kind in ("rate_limit", "timeout") \
            else "Couldn't make a preview of that shot. Try describing it differently."
        raise AppError("preview_failed", msg, 502, retryable=True) from e
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((720, 1280))
    out = s.media_dir / "assets" / f"preview_{secrets.token_hex(10)}.jpg"
    img.save(out, quality=85)
    return {"url": media_url(out)}
