"""Jobs: create, poll, confirm dish, list active, retry."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from ..auth import Actor, get_actor
from ..config import get_settings
from ..db import current_restaurant, get_session
from ..errors import AppError
from ..models import Asset, Insight, Job, MenuItem, jdump
from ..pipeline import initial_stages, job_queue
from ..serializers import job_out

router = APIRouter()

_recent: dict[str, deque] = defaultdict(deque)


def _rate_limit(ip: str) -> None:
    limit = get_settings().demo_jobs_per_hour_per_ip
    q = _recent[ip]
    now = time.time()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= limit:
        raise AppError("rate_limited", "Demo limit reached for now. Try again later.", 429, retryable=True)
    q.append(now)


class JobCreate(BaseModel):
    mode: Literal["photo", "insight", "menu"]
    photo_asset_id: Optional[int] = None
    menu_item_id: Optional[int] = None
    insight_id: Optional[int] = None
    style: Literal["bold", "warm", "minimal"] = "bold"
    length_s: Literal[15, 30] = 15
    veo: bool = False


@router.post("/jobs", status_code=202)
def create_job(body: JobCreate, request: Request, actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    r = current_restaurant(session)
    if actor != "owner":
        _rate_limit(request.client.host if request.client else "unknown")
    menu_item_id = body.menu_item_id
    photo_asset_id = body.photo_asset_id
    angle = None
    if body.mode == "insight":
        ins = session.get(Insight, body.insight_id) if body.insight_id else None
        if not ins or ins.restaurant_id != r.id:
            raise AppError("not_found", "That insight is gone. Refresh Insights.", 404)
        menu_item_id = ins.menu_item_id
        angle = ins.angle
    if body.mode in ("insight", "menu"):
        item = session.get(MenuItem, menu_item_id) if menu_item_id else None
        if not item or item.restaurant_id != r.id:
            raise AppError("not_found", "Menu item not found", 404)
        photo_asset_id = photo_asset_id or item.photo_asset_id
        if not photo_asset_id:
            raise AppError("photo_required", f"{item.name} has no photo yet. Upload one first.", 400)
    if body.mode == "photo" and not photo_asset_id:
        raise AppError("photo_required", "Add a dish photo first.", 400)
    a = session.get(Asset, photo_asset_id)
    if not a or a.restaurant_id != r.id or a.kind != "photo":
        raise AppError("not_found", "Photo not found. Upload it again.", 404)
    flags = {"demo": actor != "owner"}
    job = Job(
        restaurant_id=r.id, mode=body.mode, menu_item_id=menu_item_id if body.mode != "photo" else body.menu_item_id,
        photo_asset_id=photo_asset_id, insight_id=body.insight_id if body.mode == "insight" else None,
        angle=angle, style=body.style, length_s=body.length_s,
        veo_requested=bool(body.veo), status="queued", stages_json=jdump(initial_stages()),
        flags_json=jdump(flags),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    job_queue.enqueue(job.id)
    return JSONResponse({"job_id": job.id}, status_code=202)


@router.get("/jobs")
def list_jobs(status: Optional[str] = None, session: Session = Depends(get_session)):
    r = current_restaurant(session)
    q = select(Job).where(Job.restaurant_id == r.id).order_by(Job.created_at.desc()).limit(30)
    if status == "active":
        q = select(Job).where(Job.restaurant_id == r.id, Job.status.in_(("queued", "running", "needs_dish"))).order_by(
            Job.created_at.desc())
    return [job_out(session, j) for j in session.exec(q).all()]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)):
    j = session.get(Job, job_id)
    if not j:
        raise AppError("not_found", "Job not found", 404)
    return job_out(session, j)


class ConfirmDish(BaseModel):
    menu_item_id: Optional[int] = None
    continue_anyway: bool = True


@router.post("/jobs/{job_id}/confirm-dish")
def confirm_dish(job_id: int, body: ConfirmDish, session: Session = Depends(get_session)):
    from ..models import jload

    j = session.get(Job, job_id)
    if not j:
        raise AppError("not_found", "Job not found", 404)
    if j.status != "needs_dish":
        raise AppError("not_waiting", "This job isn't waiting for a dish.", 409)
    flags = jload(j.flags_json, {}) or {}
    flags["continue_anyway"] = body.continue_anyway
    if body.menu_item_id is None:
        flags["not_on_menu"] = True
        j.menu_item_id = None
    else:
        item = session.get(MenuItem, body.menu_item_id)
        if not item or item.restaurant_id != j.restaurant_id:
            raise AppError("not_found", "Menu item not found", 404)
        j.menu_item_id = item.id
        flags.pop("not_on_menu", None)
    stages = jload(j.stages_json, initial_stages())
    for st in stages:
        if st["name"] == "analyze":
            st["status"] = "pending"
            st["note"] = None
    j.stages_json = jdump(stages)
    j.flags_json = jdump(flags)
    j.status = "queued"
    session.add(j)
    session.commit()
    job_queue.enqueue(j.id)
    return {"ok": True}


@router.post("/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: int, request: Request, actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    from ..models import jload

    old = session.get(Job, job_id)
    if not old:
        raise AppError("not_found", "Job not found", 404)
    if actor != "owner":
        _rate_limit(request.client.host if request.client else "unknown")
    flags = {k: v for k, v in (jload(old.flags_json, {}) or {}).items() if k in ("not_on_menu", "continue_anyway")}
    flags["demo"] = actor != "owner"
    job = Job(
        restaurant_id=old.restaurant_id, mode=old.mode, menu_item_id=old.menu_item_id,
        photo_asset_id=old.photo_asset_id, insight_id=old.insight_id, angle=old.angle, style=old.style,
        length_s=old.length_s, veo_requested=old.veo_requested, status="queued",
        stages_json=jdump(initial_stages()), flags_json=jdump(flags),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    job_queue.enqueue(job.id)
    return JSONResponse({"job_id": job.id}, status_code=202)
