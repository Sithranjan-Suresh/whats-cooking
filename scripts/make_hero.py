"""Generate the DEMO_CACHE hero video ONCE for real (task 125). COSTS ONE VEO CLIP.

Runs the real pipeline (Gemini script + Veo + TTS + render) for the seeded Chicken Biryani with the
'rising' angle, then saves seed/hero_veo_short.mp4 (+ .jpg poster, + .json with the script and cost).

    backend/.venv/bin/python scripts/make_hero.py
"""
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["DEMO_CACHE"] = "0"
os.environ["MOCK_PIPELINE"] = "0"

from sqlmodel import Session, select  # noqa: E402

from app.db import get_engine, init_db  # noqa: E402
from app.models import Insight, Job, MenuItem, Video, jdump, jload  # noqa: E402
from app.pipeline import initial_stages, run_job  # noqa: E402


async def main():
    init_db()
    with Session(get_engine()) as s:
        item = s.exec(select(MenuItem).where(MenuItem.name_norm == "chicken biryani")).first()
        if not item or not item.photo_asset_id:
            sys.exit("Seed first (make seed) and make sure seed/photos/chicken-biryani.jpg is a real photo.")
        ins = s.exec(select(Insight).where(Insight.menu_item_id == item.id, Insight.angle == "rising")).first()
        job = Job(restaurant_id=item.restaurant_id, mode="insight" if ins else "menu", menu_item_id=item.id,
                  photo_asset_id=item.photo_asset_id, insight_id=ins.id if ins else None, angle="rising",
                  veo_requested=True, stages_json=jdump(initial_stages()), flags_json=jdump({"demo": False}))
        s.add(job)
        s.commit()
        s.refresh(job)
        jid = job.id
    print("running job", jid, "(this calls Veo; ~1-3 min)…")
    await run_job(jid)
    with Session(get_engine()) as s:
        job = s.get(Job, jid)
        v = s.exec(select(Video).where(Video.job_id == jid)).first()
        if job.status != "done" or not v:
            sys.exit(f"job failed: {job.error}")
        if not job.veo_used:
            sys.exit(f"Veo was not used (fallback: {job.fallback_reason}). Fix Veo first; not saving a hero.")
        shutil.copyfile(v.path, ROOT / "seed" / "hero_veo_short.mp4")
        if v.poster_path:
            shutil.copyfile(v.poster_path, ROOT / "seed" / "hero_veo_short.jpg")
        meta = {"job_id": jid, "cost_cents": job.cost_cents, "script": jload(job.script_json, {}),
                "created_at": job.created_at.isoformat()}
        (ROOT / "seed" / "hero_veo_short.json").write_text(json.dumps(meta, indent=1))
        print(f"saved seed/hero_veo_short.mp4 (cost {job.cost_cents}¢). DEMO_CACHE=1 will now replay it.")


asyncio.run(main())
