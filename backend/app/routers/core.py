"""Health, restaurant/brand, menu, uploads, usage and settings routes."""
from __future__ import annotations

import csv
import hmac
import io
import time
from collections import defaultdict, deque
import re
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

# A small file can declare a gigantic image ("decompression bomb") and exhaust a 512 MB server while decoding.
# 40 MP is plenty for any phone photo (a 12 MP shot is 4032x3024).
Image.MAX_IMAGE_PIXELS = 40_000_000
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..auth import Actor, get_actor, require_owner
from ..config import get_settings, media_url
from ..db import asset_usable, current_restaurant, get_app_settings, get_session, keep_asset_bytes, template_restaurant
from ..errors import AppError
from ..models import Asset, MenuItem
from ..serializers import menu_item_out, restaurant_out
from ..services import budget
from ..services.tts import VOICES
from ..util import normalize_name, parse_price_cents, sha256_file
from ..viewer import viewer_youtube

router = APIRouter()

ALLOWED_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@router.get("/health")
def health(actor: Actor = Depends(get_actor)):
    s = get_settings()
    return {
        "ok": True,
        "mock": s.mock_pipeline,
        "demo": s.demo_mode,
        "actor": actor,
        "veo_model": s.veo_model,
        "gemini_model": s.gemini_text_model,
        "gemini_configured": s.gemini_enabled,
        "youtube_configured": s.youtube_enabled,
    }


# ------------------------------------------------------------------ restaurant

class BrandPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    color_primary: Optional[str] = None
    color_accent: Optional[str] = None
    voice_tone: Optional[Literal["friendly", "upbeat", "elegant"]] = None
    tts_voice: Optional[str] = None
    logo_asset_id: Optional[int] = None


@router.get("/restaurants/me")
def get_me(yt: Optional[dict] = Depends(viewer_youtube), session: Session = Depends(get_session)):
    r = current_restaurant(session)
    out = restaurant_out(session, r, yt)
    out["voices"] = [{"id": k, "label": v} for k, v in VOICES.items()]
    return out


@router.patch("/restaurants/me")
def patch_me(body: BrandPatch, actor: Actor = Depends(get_actor), yt: Optional[dict] = Depends(viewer_youtube),
             session: Session = Depends(get_session)):
    require_owner(actor)
    r = current_restaurant(session)
    data = body.model_dump(exclude_unset=True)
    for key in ("color_primary", "color_accent"):
        if key in data and data[key] is not None and not HEX_RE.match(data[key]):
            raise AppError("bad_color", f"{key} must be a hex color like #C49A4A")
    if "tts_voice" in data and data["tts_voice"] not in VOICES:
        raise AppError("bad_voice", "Unknown voice")
    if data.get("logo_asset_id") is not None:
        a = session.get(Asset, data["logo_asset_id"])
        if not asset_usable(session, a, r):
            raise AppError("bad_asset", "Logo asset not found", 404)
    for k, v in data.items():
        if v is not None:
            setattr(r, k, v.upper() if k.startswith("color_") else v)
    session.add(r)
    session.commit()
    session.refresh(r)
    out = restaurant_out(session, r, yt)
    out["voices"] = [{"id": k, "label": v} for k, v in VOICES.items()]
    return out


# ------------------------------------------------------------------ uploads

def save_image_asset(session: Session, restaurant_id: int, data: bytes, mime: str, kind: str) -> Asset:
    s = get_settings()
    if len(data) > s.max_upload_bytes:
        raise AppError("file_too_large", "Use a JPG or PNG under 10 MB.", 413)
    if mime not in ALLOWED_MIME or (kind == "logo" and mime not in ("image/png", "image/webp", "image/jpeg")):
        raise AppError("bad_mime", "Use a JPG or PNG under 10 MB.", 415)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)  # treat "too big" as an error too
            img = Image.open(io.BytesIO(data))
            if img.width * img.height > Image.MAX_IMAGE_PIXELS:
                raise AppError("image_too_large", "That image is too large. Use a photo under 40 megapixels.", 413)
            img = ImageOps.exif_transpose(img)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
        raise AppError("image_too_large", "That image is too large. Use a photo under 40 megapixels.", 413) from e
    except (UnidentifiedImageError, OSError) as e:
        raise AppError("bad_image", "That file isn't a readable image.", 415) from e
    ext = ALLOWED_MIME[mime]
    path = s.media_dir / "assets" / f"{uuid.uuid4().hex}.{ext}"
    if kind == "photo":
        # Normalize: apply EXIF rotation, cap size, store as JPEG (Veo + ffmpeg friendly).
        img = img.convert("RGB")
        img.thumbnail((s.photo_max_px, s.photo_max_px))
        path = path.with_suffix(".jpg")
        img.save(path, quality=88)
        mime = "image/jpeg"
    else:
        if img.mode not in ("RGBA", "RGB"):
            img = img.convert("RGBA")
        img.thumbnail((1024, 1024))
        path = path.with_suffix(".png")
        img.save(path)
        mime = "image/png"
    a = Asset(
        restaurant_id=restaurant_id, kind=kind, path=str(path), mime=mime,
        width=img.width, height=img.height, bytes=path.stat().st_size, sha256=sha256_file(path),
    )
    session.add(a)
    session.commit()
    session.refresh(a)
    keep_asset_bytes(session, a)
    return a


_upload_times: dict[str, deque] = defaultdict(deque)


def upload_limit(request: Request) -> None:
    """Per-visitor cap on uploads (they're stored in the database, which has a size quota)."""
    from .jobs import client_ip

    ip, now = client_ip(request), time.time()
    q = _upload_times[ip]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= get_settings().uploads_per_hour_per_ip:
        raise AppError("rate_limited", "That's a lot of uploads in one hour. Try again a bit later.", 429, retryable=True)
    q.append(now)


@router.post("/uploads")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    kind: Literal["photo", "logo"] = Form("photo"),
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
):
    upload_limit(request)
    if kind == "logo":
        require_owner(actor)
    r = current_restaurant(session)
    data = await file.read(get_settings().max_upload_bytes + 1)
    a = save_image_asset(session, r.id, data, (file.content_type or "").lower(), kind)
    return {"asset_id": a.id, "url": media_url(a.path), "width": a.width, "height": a.height}


# ------------------------------------------------------------------ menu

@router.get("/menu")
def list_menu(session: Session = Depends(get_session)):
    r = current_restaurant(session)
    items = session.exec(select(MenuItem).where(MenuItem.restaurant_id == r.id).order_by(MenuItem.category, MenuItem.name)).all()
    return [menu_item_out(session, m) for m in items]


def import_menu_csv(session: Session, restaurant_id: int, text: str) -> dict:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise AppError("bad_csv", "The menu CSV is empty.")
    fields = {f.strip().lower().lstrip("﻿"): f for f in reader.fieldnames}
    if "name" not in fields:
        raise AppError("bad_csv", "The menu CSV needs a 'name' column (plus price, description, category).")
    existing = {m.name_norm: m for m in session.exec(select(MenuItem).where(MenuItem.restaurant_id == restaurant_id)).all()}
    imported = skipped = 0
    for row in reader:
        name = (row.get(fields["name"]) or "").strip()
        if not name:
            skipped += 1
            continue
        get = lambda k: (row.get(fields[k]) or "").strip() if k in fields else ""  # noqa: E731
        norm = normalize_name(name)
        m = existing.get(norm) or MenuItem(restaurant_id=restaurant_id, name=name, name_norm=norm)
        m.name = name
        m.price_cents = parse_price_cents(get("price"))
        m.description = get("description") or None
        m.category = get("category") or None
        session.add(m)
        existing[norm] = m
        imported += 1
    session.commit()
    return {"imported": imported, "skipped": skipped}


@router.post("/menu/import")
async def menu_import(file: UploadFile = File(...), actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    require_owner(actor)
    r = current_restaurant(session)
    raw = await file.read(2 * 1024 * 1024)
    return import_menu_csv(session, r.id, raw.decode("utf-8-sig", errors="replace"))


class PhotoLink(BaseModel):
    asset_id: int


@router.post("/menu/{item_id}/photo")
def set_menu_photo(item_id: int, body: PhotoLink, actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    require_owner(actor)
    r = current_restaurant(session)
    m = session.get(MenuItem, item_id)
    a = session.get(Asset, body.asset_id)
    if not m or m.restaurant_id != r.id:
        raise AppError("not_found", "Menu item not found", 404)
    if not asset_usable(session, a, r) or a.kind != "photo":
        raise AppError("not_found", "Photo not found", 404)
    m.photo_asset_id = a.id
    session.add(m)
    session.commit()
    session.refresh(m)
    return menu_item_out(session, m)


# ------------------------------------------------------------------ usage & settings

@router.get("/usage")
def usage(actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    r = current_restaurant(session)
    snap = budget.usage_snapshot(session, r.id)
    d = budget.check(session, r.id)
    reason = "demo_mode" if actor != "owner" else d.reason
    message = budget.DENY_MESSAGES.get(reason or "", None)
    if reason in ("daily_limit", "monthly_cap"):
        message = budget.cap_message(session, r.id, reason, d.est_cost_cents)
    snap["veo"] = {"allowed": d.allowed and actor == "owner", "reason": reason, "message": message, "est_cents": d.est_cost_cents}
    # How many more AI-motion videos fit under today's limit and the total cap (shown next to Action!).
    per = max(1, d.est_cost_cents)
    by_cap = max(0, snap["total"]["cap_cents"] - snap["total"]["spent_cents"]) // per
    by_day = max(0, snap["today"]["limit"] - snap["today"]["clips"])
    snap["ai_videos_left"] = 0 if snap["free_mode"] else int(min(by_cap, by_day))
    snap["ai_videos_total"] = int(snap["total"]["cap_cents"] // per)
    return snap


class SettingsPatch(BaseModel):
    daily_veo_clip_limit: Optional[int] = Field(default=None, ge=0, le=20)
    monthly_cap_cents: Optional[int] = Field(default=None, ge=0, le=budget.HARD_CAP_CENTS)  # total cap
    spent_outside_cents: Optional[int] = Field(default=None, ge=0, le=100000)
    free_mode: Optional[bool] = None


def require_admin(x_admin_token: Optional[str] = Header(default=None)) -> None:
    """Budget settings move real money, so they need ADMIN_TOKEN (never sent by the web app)."""
    real = get_settings().admin_token
    if not real:
        raise AppError("settings_locked", "Budget settings are locked on this server (no ADMIN_TOKEN set).", 403)
    if not x_admin_token or not hmac.compare_digest(x_admin_token, real):
        raise AppError("admin_required", "Changing budget settings needs the admin key.", 403)


@router.get("/settings")
def get_settings_route(_: None = Depends(require_admin), session: Session = Depends(get_session)):
    r = template_restaurant(session)  # one shared budget for every studio
    return get_app_settings(session, r.id).model_dump()


@router.patch("/settings")
def patch_settings(body: SettingsPatch, _: None = Depends(require_admin), session: Session = Depends(get_session)):
    r = template_restaurant(session)  # one shared budget for every studio
    st = get_app_settings(session, r.id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(st, k, v)
    session.add(st)
    session.commit()
    session.refresh(st)
    return st.model_dump()
