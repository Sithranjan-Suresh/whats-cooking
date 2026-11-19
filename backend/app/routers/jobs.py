"""Jobs: create, poll, confirm dish, list active, retry."""
from __future__ import annotations

import hmac
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
_hourly: dict[str, deque] = defaultdict(deque)
_ip_jobs: dict[str, list[int]] = defaultdict(list)


def _rate_limit(ip: str) -> None:
    limit = get_settings().demo_jobs_per_hour_per_ip
    q = _recent[ip]
    now = time.time()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= limit:
        raise AppError("rate_limited", "Demo limit reached for now. Try again later.", 429, retryable=True)
    q.append(now)


def client_ip(request: Request) -> str:
    """The visitor's address. Render sits behind Cloudflare, which sets CF-Connecting-IP itself."""
    for h in ("cf-connecting-ip", "true-client-ip"):
        v = request.headers.get(h)
        if v:
            return v.strip()
    return request.client.host if request.client else "unknown"


def _has_owner_token(request: Request) -> bool:
    tok, real = request.headers.get("x-owner-token"), get_settings().owner_token
    return bool(tok and real and hmac.compare_digest(tok, real))


def _admit(request: Request, actor: Actor, session: Session) -> str:
    """Fair use: the public app has no login, so limit each visitor and the queue as a whole.

    A real owner token skips this. Raises 429 rate_limited. Returns the visitor's IP for _track().
    """
    ip = client_ip(request)
    if actor != "owner":
        _rate_limit(ip)
    if _has_owner_token(request):
        return ip
    s = get_settings()
    active = ("queued", "running")
    mine = [j for j in _ip_jobs[ip][-20:] if (job := session.get(Job, j)) and job.status in active]
    if len(mine) >= s.active_jobs_per_ip:
        raise AppError("rate_limited", "You already have a video in progress. Wait for it to finish, then make the next one.",
                       429, retryable=True)
    busy = len(session.exec(select(Job.id).where(Job.status.in_(active))).all())
    if busy >= s.max_queued_jobs:
        raise AppError("rate_limited", "The studio is busy with other videos right now. Try again in a couple of minutes.",
                       429, retryable=True)
    q, now = _hourly[ip], time.time()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= s.jobs_per_hour_per_ip:
        wait = max(1, int((3600 - (now - q[0])) // 60) + 1)
        raise AppError("rate_limited", f"You've made {s.jobs_per_hour_per_ip} videos in the last hour. "
                       f"Try again in about {wait} minute{'s' if wait != 1 else ''}.", 429, retryable=True)
    q.append(now)
    return ip


def _track(ip: str, job_id: int) -> None:
    _ip_jobs[ip] = [*_ip_jobs[ip][-19:], job_id]


class JobCreate(BaseModel):
    mode: Literal["photo", "insight", "menu"]
    photo_asset_id: Optional[int] = None
    menu_item_id: Optional[int] = None
    insight_id: Optional[int] = None
    style: Literal["bold", "warm", "minimal"] = "bold"
    length_s: Literal[8, 15, 30] = 8
    veo: bool = False


@router.post("/jobs", status_code=202)
def create_job(body: JobCreate, request: Request, actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    r = current_restaurant(session)
    ip = _admit(request, actor, session)
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
    if body.veo and actor == "owner":
        from ..services import budget

        d = budget.check(session, r.id, 8)
        if not d.allowed and d.reason in ("daily_limit", "monthly_cap"):
            raise AppError("budget_cap_reached", budget.cap_message(session, r.id, d.reason, d.est_cost_cents), 402)
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
    _track(ip, job.id)
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
    ip = _admit(request, actor, session)
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
    _track(ip, job.id)
    return JSONResponse({"job_id": job.id}, status_code=202)


class BeatEdit(BaseModel):
    caption: str


class ScriptEdit(BaseModel):
    hook: Optional[str] = None
    beats: list[BeatEdit]
    voiceover: Optional[str] = None


@router.post("/jobs/{job_id}/edit", status_code=202)
def edit_and_rerender(job_id: int, body: ScriptEdit, request: Request, actor: Actor = Depends(get_actor),
                      session: Session = Depends(get_session)):
    """Edit captions (and optionally hook/voiceover) of a finished job and re-render.

    Edits go through the same grounding validator as AI drafts, so a typo'd price can't ship.
    """
    from ..models import jload
    from ..services import scripts as sc
    from ..pipeline import initial_stages as stages0

    old = session.get(Job, job_id)
    if not old or not old.script_json:
        raise AppError("not_found", "Job or script not found", 404)
    ip = _admit(request, actor, session)
    script = jload(old.script_json, {})
    if not body.beats or len(body.beats) > 8:
        raise AppError("validation_error", "Give 1 to 8 caption beats.", 422)
    old_beats = script.get("beats", [])
    new_beats = []
    for i, b in enumerate(body.beats):
        secs = old_beats[i]["seconds"] if i < len(old_beats) else 3.0
        new_beats.append({"caption": b.caption.strip(), "seconds": secs})
    script["beats"] = new_beats
    if body.hook is not None:
        script["hook"] = body.hook.strip()
    if body.voiceover is not None:
        script["voiceover"] = body.voiceover.strip()
    script = sc.normalize_script({**script, "facts_used": script.get("facts_used", [])}, old.length_s)
    flags = jload(old.flags_json, {}) or {}
    item = session.get(MenuItem, old.menu_item_id) if old.menu_item_id else None
    row = sc.menu_row_for(item) if item else {"name": None, "price": None, "description": None}
    problems = sc.validate_script(script, row, old.length_s, not_on_menu=bool(flags.get("not_on_menu")) or item is None)
    if problems:
        raise AppError("not_grounded", "Edit breaks a grounding rule: " + "; ".join(problems), 422)
    script = sc.annotate_beats(script, row)
    script["source"] = "edited"
    stages = stages0()
    for st in stages:
        if st["name"] in ("analyze", "script"):
            st["status"] = "done"
            st["note"] = "Reused" if st["name"] == "analyze" else "Edited by you · grounding checked"
    new_flags = {k: v for k, v in flags.items() if k in ("not_on_menu", "continue_anyway")}
    new_flags["demo"] = actor != "owner"
    job = Job(
        restaurant_id=old.restaurant_id, mode=old.mode, menu_item_id=old.menu_item_id,
        photo_asset_id=old.photo_asset_id, insight_id=old.insight_id, angle=old.angle, style=old.style,
        length_s=old.length_s, veo_requested=old.veo_requested, status="queued", stages_json=jdump(stages),
        analyze_json=old.analyze_json, script_json=jdump(script), flags_json=jdump(new_flags),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    job_queue.enqueue(job.id)
    _track(ip, job.id)
    return JSONResponse({"job_id": job.id}, status_code=202)


class DishCreate(BaseModel):
    name: str
    price: Optional[str] = None
    description: Optional[str] = None
    photo_asset_id: int


@router.post("/dishes")
def create_dish(body: DishCreate, actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    """Quick-take dashboard: add (or update) a dish by name with its photo, so scripts stay grounded in what you typed."""
    from ..auth import require_owner
    from ..serializers import menu_item_out
    from ..util import normalize_name, parse_price_cents

    require_owner(actor)
    r = current_restaurant(session)
    name = " ".join(body.name.split())[:80]
    if not name:
        raise AppError("validation_error", "Give the dish a name.", 422)
    price_cents = None
    if body.price and body.price.strip():
        price_cents = parse_price_cents(body.price)
        if price_cents is None:
            raise AppError("validation_error", "Price should look like 14.99", 422)
    a = session.get(Asset, body.photo_asset_id)
    if not a or a.restaurant_id != r.id or a.kind != "photo":
        raise AppError("not_found", "Photo not found. Upload it again.", 404)
    norm = normalize_name(name)
    item = session.exec(select(MenuItem).where(MenuItem.restaurant_id == r.id, MenuItem.name_norm == norm)).first()
    if item is None:
        item = MenuItem(restaurant_id=r.id, name=name, name_norm=norm, category="Specials")
    item.name = name
    if body.price is not None:
        item.price_cents = price_cents
    if body.description is not None:
        item.description = " ".join(body.description.split())[:240] or None
    item.photo_asset_id = a.id
    session.add(item)
    session.commit()
    session.refresh(item)
    return menu_item_out(session, item)
