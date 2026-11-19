import threading
from datetime import date

from sqlmodel import Session

from app.db import get_app_settings, get_engine
from app.models import Job
from app.services import budget

TODAY = date(2026, 11, 18)


def _job(rid):
    with Session(get_engine()) as s:
        j = Job(restaurant_id=rid, mode="photo")
        s.add(j)
        s.commit()
        s.refresh(j)
        return j.id


def _settings(rid, **kw):
    with Session(get_engine()) as s:
        st = get_app_settings(s, rid)
        for k, v in kw.items():
            setattr(st, k, v)
        s.add(st)
        s.commit()


def test_blocks_11th_clip_when_limit_is_10(restaurant):
    _settings(restaurant, daily_veo_clip_limit=10, monthly_cap_cents=100000, veo_cost_per_sec_cents=8)
    results = [budget.reserve_veo(restaurant, _job(restaurant), 8, today=TODAY) for _ in range(11)]
    assert all(r.allowed for r in results[:10])
    assert not results[10].allowed and results[10].reason == "daily_limit"


def test_monthly_cap(restaurant):
    _settings(restaurant, daily_veo_clip_limit=50, monthly_cap_cents=150, veo_cost_per_sec_cents=8)  # 64¢ per clip
    a = budget.reserve_veo(restaurant, _job(restaurant), 8, today=TODAY)
    b = budget.reserve_veo(restaurant, _job(restaurant), 8, today=TODAY)
    c = budget.reserve_veo(restaurant, _job(restaurant), 8, today=TODAY)
    assert a.allowed and b.allowed
    assert not c.allowed and c.reason == "monthly_cap"


def test_release_frees_capacity_commit_keeps_it(restaurant):
    _settings(restaurant, daily_veo_clip_limit=1, monthly_cap_cents=100000)
    j1 = _job(restaurant)
    assert budget.reserve_veo(restaurant, j1, 8, today=TODAY).allowed
    assert not budget.reserve_veo(restaurant, _job(restaurant), 8, today=TODAY).allowed
    budget.release(j1)
    j3 = _job(restaurant)
    assert budget.reserve_veo(restaurant, j3, 8, today=TODAY).allowed
    budget.commit(j3)
    assert not budget.reserve_veo(restaurant, _job(restaurant), 8, today=TODAY).allowed


def test_free_mode_denies(restaurant):
    _settings(restaurant, free_mode=True)
    d = budget.reserve_veo(restaurant, _job(restaurant), 8, today=TODAY)
    assert not d.allowed and d.reason == "free_mode"


def test_concurrent_reservations_at_limit_minus_one(restaurant):
    _settings(restaurant, daily_veo_clip_limit=3, monthly_cap_cents=100000)
    for _ in range(2):
        assert budget.reserve_veo(restaurant, _job(restaurant), 8, today=TODAY).allowed
    jobs = [_job(restaurant) for _ in range(8)]
    out = []
    barrier = threading.Barrier(len(jobs))

    def go(j):
        barrier.wait()
        out.append(budget.reserve_veo(restaurant, j, 8, today=TODAY).allowed)

    threads = [threading.Thread(target=go, args=(j,)) for j in jobs]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert out.count(True) == 1


def test_usage_snapshot(restaurant):
    _settings(restaurant, daily_veo_clip_limit=10, monthly_cap_cents=1500, veo_cost_per_sec_cents=8)
    budget.reserve_veo(restaurant, _job(restaurant), 8, today=TODAY)
    with Session(get_engine()) as s:
        snap = budget.usage_snapshot(s, restaurant, today=TODAY)
    assert snap["today"] == {"clips": 1, "limit": 10}
    assert snap["month"] == {"est_cents": 64, "cap_cents": 1000}  # settings above the $10 hard cap are clamped
