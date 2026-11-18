"""Sales import + insights."""
from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session, delete, select

from ..auth import Actor, get_actor, require_owner
from ..config import get_settings
from ..db import current_restaurant, get_session
from ..errors import AppError
from ..models import Insight, MenuItem, SalesRecord, jdump
from ..serializers import insight_card
from ..services import gemini
from ..services.insights import CsvFormatError, build_matcher, metric_label, parse_sales_csv, rank, rule_reason

log = logging.getLogger("app.insights")
router = APIRouter()


def import_sales_text(session: Session, restaurant_id: int, text: str) -> dict:
    try:
        parsed = parse_sales_csv(text)
    except CsvFormatError as e:
        raise AppError("bad_csv", str(e)) from e
    if not parsed.rows:
        raise AppError("bad_csv", f"No valid sales rows found ({parsed.dropped} rows dropped).")
    menu = session.exec(select(MenuItem).where(MenuItem.restaurant_id == restaurant_id)).all()
    match = build_matcher([(m.id, m.name) for m in menu])
    # Replace semantics: a new export replaces the previous one (single restaurant, documented in contract.md).
    session.exec(delete(SalesRecord).where(SalesRecord.restaurant_id == restaurant_id))
    session.exec(delete(Insight).where(Insight.restaurant_id == restaurant_id))
    unmatched: dict[str, int] = {}
    for r in parsed.rows:
        mid = match(r.item_name)
        if mid is None:
            unmatched[r.item_name] = unmatched.get(r.item_name, 0) + r.quantity
        session.add(SalesRecord(restaurant_id=restaurant_id, date=r.date, menu_item_id=mid,
                                raw_item_name=r.item_name, quantity=r.quantity, revenue_cents=r.revenue_cents))
    session.commit()
    dates = [r.date for r in parsed.rows]
    return {
        "rows": len(parsed.rows),
        "dropped": parsed.dropped,
        "date_from": min(dates).isoformat(),
        "date_to": max(dates).isoformat(),
        "days": (max(dates) - min(dates)).days + 1,
        "unmatched_items": sorted(unmatched, key=lambda k: -unmatched[k]),
    }


async def compute_insights(session: Session, restaurant_id: int, restaurant_name: str) -> str:
    rows = session.exec(select(SalesRecord).where(SalesRecord.restaurant_id == restaurant_id,
                                                  SalesRecord.menu_item_id.is_not(None))).all()
    items = {m.id: m for m in session.exec(select(MenuItem).where(MenuItem.restaurant_id == restaurant_id)).all()}
    with_photo = {mid for mid, m in items.items() if m.photo_asset_id}
    picks = rank([(r.date, r.menu_item_id, r.quantity) for r in rows], with_photo)
    batch = uuid.uuid4().hex[:12]
    if not picks:
        return batch
    reasons: dict[str, str] = {}
    source = "rule"
    try:
        reasons = await gemini.insight_reasons(
            restaurant_name,
            [{"angle": p.angle, "dish": items[p.menu_item_id].name, "metrics": p.metric,
              "metric_summary": metric_label(p.angle, p.metric)} for p in picks],
        )
        source = "gemini"
    except gemini.GeminiError as e:
        log.info("insight reasons fell back to rules (%s)", e.kind)
    session.exec(delete(Insight).where(Insight.restaurant_id == restaurant_id))
    for i, p in enumerate(picks):
        dish = items[p.menu_item_id].name
        reason = reasons.get(p.angle)
        session.add(Insight(
            restaurant_id=restaurant_id, menu_item_id=p.menu_item_id, angle=p.angle,
            metric_json=jdump(p.metric), reason=reason or rule_reason(p.angle, dish, p.metric),
            reason_source=source if reason else "rule", batch_id=batch, rank=i,
        ))
    session.commit()
    return batch


def _cards(session: Session, restaurant_id: int) -> dict:
    rows = session.exec(select(Insight).where(Insight.restaurant_id == restaurant_id).order_by(Insight.rank)).all()
    batch = rows[0].batch_id if rows else None
    order = {"rising": 0, "top_seller": 1, "slow_mover": 2}
    rows = sorted(rows, key=lambda r: order.get(r.angle, 9))
    return {"batch_id": batch, "cards": [insight_card(session, r) for r in rows]}


def _mock_cards() -> dict:
    p = get_settings().seed_dir / "mock_insights.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"batch_id": None, "cards": []}


@router.post("/sales/import")
async def sales_import(file: UploadFile = File(...), actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    require_owner(actor)
    r = current_restaurant(session)
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise AppError("file_too_large", "Sales CSV must be under 5 MB.", 413)
    out = import_sales_text(session, r.id, raw.decode("utf-8-sig", errors="replace"))
    await compute_insights(session, r.id, r.name)
    return out


@router.get("/sales/summary")
def sales_summary(session: Session = Depends(get_session)):
    r = current_restaurant(session)
    rows = session.exec(select(SalesRecord).where(SalesRecord.restaurant_id == r.id)).all()
    if not rows:
        return {"rows": 0, "date_from": None, "date_to": None, "unmatched_items": []}
    dates = [x.date for x in rows]
    unmatched = sorted({x.raw_item_name for x in rows if x.menu_item_id is None})
    return {"rows": len(rows), "date_from": min(dates).isoformat(), "date_to": max(dates).isoformat(),
            "days": (max(dates) - min(dates)).days + 1, "unmatched_items": unmatched}


@router.get("/insights")
async def get_insights(session: Session = Depends(get_session)):
    if get_settings().mock_pipeline:
        return _mock_cards()
    r = current_restaurant(session)
    out = _cards(session, r.id)
    if not out["cards"]:
        has_sales = session.exec(select(SalesRecord.id).where(SalesRecord.restaurant_id == r.id).limit(1)).first()
        if has_sales:
            await compute_insights(session, r.id, r.name)
            out = _cards(session, r.id)
    return out


@router.post("/insights/refresh")
async def refresh_insights(actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    require_owner(actor)
    if get_settings().mock_pipeline:
        return _mock_cards()
    r = current_restaurant(session)
    await compute_insights(session, r.id, r.name)
    return _cards(session, r.id)


@router.get("/insights/{insight_id}")
def get_insight(insight_id: int, session: Session = Depends(get_session)):
    ins = session.get(Insight, insight_id)
    if not ins:
        raise AppError("not_found", "That insight is gone (sales data was refreshed).", 404)
    return insight_card(session, ins)
