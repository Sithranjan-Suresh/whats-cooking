"""Budget guard (layer 3 of cost control). Atomic reserve → commit/release on the UsageLedger.

Atomicity: the app runs as ONE process (N asyncio workers + request threads). A process-wide lock
serializes every reserve/commit/release, and the check + insert happen in one DB transaction, so two
jobs can never both take the last clip. (Run a single uvicorn worker; see README.)
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlmodel import Session, select

from ..db import get_app_settings, get_engine
from ..models import AppSettings, UsageLedger

_lock = threading.Lock()

ACTIVE = ("reserved", "committed")

# Hard ceiling on estimated AI-motion spend per month, whatever the settings say. Raising it needs a code change.
HARD_CAP_CENTS = 1000


def _cap(st: AppSettings) -> int:
    return min(st.monthly_cap_cents, HARD_CAP_CENTS)


@dataclass
class Decision:
    allowed: bool
    reason: Optional[str] = None  # free_mode|daily_limit|monthly_cap|demo_mode
    est_cost_cents: int = 0
    ledger_id: Optional[int] = None


def _today() -> date:
    return date.today()


def usage_snapshot(session: Session, restaurant_id: int, today: Optional[date] = None) -> dict:
    today = today or _today()
    st = get_app_settings(session, restaurant_id)
    rows = session.exec(
        select(UsageLedger).where(UsageLedger.restaurant_id == restaurant_id, UsageLedger.state.in_(ACTIVE))
    ).all()
    clips_today = sum(1 for r in rows if r.date == today)
    month_cents = sum(r.est_cost_cents for r in rows if (r.date.year, r.date.month) == (today.year, today.month))
    return {
        "today": {"clips": clips_today, "limit": st.daily_veo_clip_limit},
        "month": {"est_cents": month_cents, "cap_cents": _cap(st)},
        "cost_per_sec_cents": st.veo_cost_per_sec_cents,
        "free_mode": st.free_mode,
    }


def check(session: Session, restaurant_id: int, seconds: int = 8, today: Optional[date] = None) -> Decision:
    """Read-only preview of what reserve_veo would decide (used by the UI)."""
    st = get_app_settings(session, restaurant_id)
    snap = usage_snapshot(session, restaurant_id, today)
    est = seconds * st.veo_cost_per_sec_cents
    if st.free_mode:
        return Decision(False, "free_mode", est)
    if snap["today"]["clips"] >= st.daily_veo_clip_limit:
        return Decision(False, "daily_limit", est)
    if snap["month"]["est_cents"] + est > _cap(st):
        return Decision(False, "monthly_cap", est)
    return Decision(True, None, est)


def reserve_veo(restaurant_id: int, job_id: int, seconds: int = 8, today: Optional[date] = None) -> Decision:
    today = today or _today()
    with _lock:
        with Session(get_engine()) as session:
            st: AppSettings = get_app_settings(session, restaurant_id)
            est = seconds * st.veo_cost_per_sec_cents
            if st.free_mode:
                return Decision(False, "free_mode", est)
            rows = session.exec(
                select(UsageLedger).where(
                    UsageLedger.restaurant_id == restaurant_id, UsageLedger.state.in_(ACTIVE)
                )
            ).all()
            clips_today = sum(1 for r in rows if r.date == today)
            if clips_today >= st.daily_veo_clip_limit:
                return Decision(False, "daily_limit", est)
            month = sum(r.est_cost_cents for r in rows if (r.date.year, r.date.month) == (today.year, today.month))
            if month + est > _cap(st):
                return Decision(False, "monthly_cap", est)
            row = UsageLedger(
                restaurant_id=restaurant_id, date=today, job_id=job_id, seconds=seconds,
                est_cost_cents=est, state="reserved",
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return Decision(True, None, est, row.id)


def _set_state(job_id: int, frm: str, to: str) -> int:
    with _lock:
        with Session(get_engine()) as session:
            rows = session.exec(select(UsageLedger).where(UsageLedger.job_id == job_id, UsageLedger.state == frm)).all()
            for r in rows:
                r.state = to
                session.add(r)
            session.commit()
            return len(rows)


def commit(job_id: int) -> int:
    return _set_state(job_id, "reserved", "committed")


def release(job_id: int) -> int:
    return _set_state(job_id, "reserved", "released")


DENY_MESSAGES = {
    "free_mode": "AI motion is switched off on this server",
    "daily_limit": "Today's AI videos are used up",
    "monthly_cap": "The AI video budget is used up",
    "demo_mode": "AI motion is off in demo mode",
}


def cap_message(session: Session, restaurant_id: int, reason: str, est_cents: int) -> str:
    st = get_app_settings(session, restaurant_id)
    if reason == "daily_limit":
        return (f"Today's {st.daily_veo_clip_limit} AI videos are used up (they reset tomorrow). "
                "You can still make this one with free photo motion.")
    cap = _cap(st)
    money = f"${cap // 100}" if cap % 100 == 0 else f"${cap / 100:.2f}"
    return (f"The {money} AI video budget for this month is used up. "
            "You can still make videos with free photo motion.")
