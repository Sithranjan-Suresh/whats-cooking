"""DB rows → contract JSON."""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from .config import get_settings, media_url
from .models import Asset, Insight, Job, MenuItem, Restaurant, Video, jload
from .services.insights import metric_label
from .util import fmt_price


def asset_url(session: Session, asset_id: Optional[int]) -> Optional[str]:
    if not asset_id:
        return None
    a = session.get(Asset, asset_id)
    return media_url(a.path) if a else None


def restaurant_out(session: Session, r: Restaurant, yt: Optional[dict] = None) -> dict:
    """yt = the calling visitor's YouTube connection (per browser), if any."""
    from sqlalchemy import func

    from .models import SalesRecord

    menu_count = session.exec(select(func.count()).select_from(MenuItem).where(MenuItem.restaurant_id == r.id)).one()
    has_sales = session.exec(select(SalesRecord.id).where(SalesRecord.restaurant_id == r.id).limit(1)).first() is not None
    return {
        "id": r.id,
        "name": r.name,
        "slug": r.slug,
        "logo_asset_id": r.logo_asset_id,
        "logo_url": asset_url(session, r.logo_asset_id),
        "color_primary": r.color_primary,
        "color_accent": r.color_accent,
        "voice_tone": r.voice_tone,
        "tts_voice": r.tts_voice,
        "menu_count": menu_count,
        "has_sales": has_sales,
        "youtube_connected": yt is not None,
        "youtube_configured": get_settings().youtube_enabled,
        "youtube_channel_title": yt.get("ct") if yt else None,
    }


def menu_item_out(session: Session, m: MenuItem) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "price_cents": m.price_cents,
        "price": fmt_price(m.price_cents),
        "description": m.description,
        "category": m.category,
        "photo_asset_id": m.photo_asset_id,
        "photo_url": asset_url(session, m.photo_asset_id),
    }


def insight_card(session: Session, ins: Insight) -> dict:
    m = session.get(MenuItem, ins.menu_item_id)
    metric = jload(ins.metric_json, {})
    return {
        "id": ins.id,
        "angle": ins.angle,
        "menu_item": {
            "id": m.id if m else None,
            "name": m.name if m else "?",
            "price": fmt_price(m.price_cents) if m else None,
            "photo_url": asset_url(session, m.photo_asset_id) if m else None,
        },
        "metric": metric,
        "metric_label": metric_label(ins.angle, metric),
        "reason": ins.reason,
        "reason_source": ins.reason_source,
    }


def video_out(session: Session, v: Video) -> dict:
    item = session.get(MenuItem, v.menu_item_id) if v.menu_item_id else None
    return {
        "id": v.id,
        "job_id": v.job_id,
        "url": media_url(v.path),
        "poster_url": media_url(v.poster_path),
        "dish": item.name if item else None,
        "menu_item_id": v.menu_item_id,
        "duration_s": round(v.duration_s, 1),
        "width": v.width,
        "height": v.height,
        "bytes": v.bytes,
        "mode": v.mode,
        "cost_cents": v.cost_cents,
        "title": v.title,
        "description": v.description,
        "hashtags": jload(v.hashtags_json, []),
        "youtube_id": v.youtube_id,
        "youtube_url": v.youtube_url,
        "youtube_privacy": v.youtube_privacy,
        "publish_status": v.publish_status,
        "publish_error": v.publish_error,
        "publish_progress": v.publish_progress,
        "created_at": v.created_at.isoformat() + "Z",
    }


def job_out(session: Session, j: Job) -> dict:
    video = session.exec(select(Video).where(Video.job_id == j.id)).first()
    analyze = jload(j.analyze_json, None)
    candidates = []
    if analyze and analyze.get("candidates") is not None and j.status == "needs_dish":
        for mid in analyze.get("candidates") or []:
            m = session.get(MenuItem, mid)
            if m:
                candidates.append(menu_item_out(session, m))
    item = session.get(MenuItem, j.menu_item_id) if j.menu_item_id else None
    return {
        "id": j.id,
        "status": j.status,
        "mode": j.mode,
        "angle": j.angle,
        "style": j.style,
        "length_s": j.length_s,
        "veo_requested": j.veo_requested,
        "stages": jload(j.stages_json, []),
        "analyze": ({**analyze, "candidates": candidates} if analyze else None),
        "script": jload(j.script_json, None),
        "menu_item": menu_item_out(session, item) if item else None,
        "photo_url": asset_url(session, j.photo_asset_id),
        "veo_used": j.veo_used,
        "fallback_reason": j.fallback_reason,
        "flags": jload(j.flags_json, {}),
        "video": (
            {"id": video.id, "url": media_url(video.path), "poster_url": media_url(video.poster_path)} if video else None
        ),
        "cost_cents": j.cost_cents,
        "error": j.error,
        "error_stage": j.error_stage,
        "created_at": j.created_at.isoformat() + "Z",
        "finished_at": (j.finished_at.isoformat() + "Z") if j.finished_at else None,
    }
