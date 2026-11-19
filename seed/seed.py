"""Load the Kumar's demo restaurant into the DB (idempotent).

Run from the repo root:  make seed   (= backend/.venv/bin/python seed/seed.py)

Steps: restaurant + brand kit → menu → photos → music + logo assets → sales → insights →
settings → mock_short.mp4 (real free-mode render) → 2 historical videos → mock_insights.json.
Optional: seed/published.json  {"dish": "Chicken Biryani", "youtube_url": "...", "youtube_id": "..."}
marks one seeded video as already published (shown to demo viewers).
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlmodel import Session, select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import get_app_settings, get_engine, has_restaurant, init_db, keep_asset_bytes  # noqa: E402
from app.models import Asset, Job, MenuItem, Restaurant, Video, jdump  # noqa: E402
from app.pipeline import initial_stages  # noqa: E402
from app.routers.core import import_menu_csv  # noqa: E402
from app.routers.insights import _cards, compute_insights, import_sales_text  # noqa: E402
from app.services import render, scripts, tts  # noqa: E402
from app.services.media import probe_video  # noqa: E402
from app.util import sha256_file, slugify  # noqa: E402

SEED = ROOT / "seed"


def copy_asset(session: Session, rid: int, src: Path, kind: str, mime: str) -> Asset:
    s = get_settings()
    digest = sha256_file(src)
    existing = session.exec(select(Asset).where(Asset.restaurant_id == rid, Asset.sha256 == digest, Asset.kind == kind)).first()
    if existing and Path(existing.path).exists():
        return existing
    dst = s.media_dir / "assets" / f"seed_{kind}_{src.stem}{src.suffix.lower()}"
    shutil.copyfile(src, dst)
    w = h = 0
    if kind in ("photo", "logo"):
        from PIL import Image, ImageOps

        with Image.open(dst) as im:
            im = ImageOps.exif_transpose(im)
            w, h = im.size
    a = Asset(restaurant_id=rid, kind=kind, path=str(dst), mime=mime, width=w, height=h,
              bytes=dst.stat().st_size, sha256=digest)
    session.add(a)
    session.commit()
    session.refresh(a)
    keep_asset_bytes(session, a)
    return a


async def render_free(session: Session, r: Restaurant, item: MenuItem, out: Path, *, angle=None) -> tuple[Path, Path, dict, dict]:
    """Real free-mode render (template script, so it works without an API key)."""
    s = get_settings()
    work = s.media_dir / "work" / f"seed_{item.id}_{int(time.time())}"
    work.mkdir(parents=True, exist_ok=True)
    photo = Path(session.get(Asset, item.photo_asset_id).path)
    row = scripts.menu_row_for(item)
    script = scripts.template_script(row, angle, r.name, 8)
    script["source"] = "template"
    main_len = 8 - render.END_CARD_S
    visuals = await render.kenburns(photo, main_len, work)
    voice = await tts.synthesize(script["voiceover"], r.tts_voice, work / "voice.mp3", tone=r.voice_tone)
    speech = (voice["timings"][0]["start"] + 0.3, voice["timings"][-1]["end"] + 0.3) if voice and voice.get("timings") else None
    ass = render.build_ass(script, main_len, color_primary=r.color_primary, color_accent=r.color_accent, speech=speech)
    logo = session.get(Asset, r.logo_asset_id) if r.logo_asset_id else None
    card = await render.animated_end_card(work, restaurant_name=r.name, dish_name=item.name, price=row["price"],
                                  color_primary=r.color_primary, color_accent=r.color_accent,
                                  logo_path=Path(logo.path) if logo else None)
    music = session.exec(select(Asset).where(Asset.restaurant_id == r.id, Asset.kind == "music")).first()
    await render.assemble_with_retry(work=work, visuals=visuals, main_len=main_len, ass_text=ass, end_card_png=card,
                                     voice=voice, music=Path(music.path) if music else None, out_path=out)
    poster = out.with_suffix(".jpg")
    await render.extract_poster(out, poster)
    shutil.rmtree(work, ignore_errors=True)
    return out, poster, await probe_video(out), script


async def main() -> None:
    s = get_settings()
    init_db()
    if "--if-empty" in sys.argv and has_restaurant():
        # A persistent DB (DATABASE_URL) already holds the owner's restaurant: never overwrite their branding.
        print("seed: restaurant already exists, skipping")
        return
    with Session(get_engine()) as session:
        r = session.exec(select(Restaurant).where(Restaurant.slug == "kumars")).first()
        if r is None:
            r = Restaurant(name="Kumar's", slug=slugify("kumars"), color_primary="#C49A4A", color_accent="#F3EBDD",
                           voice_tone="upbeat", tts_voice="en-US-AriaNeural")
            session.add(r)
            session.commit()
            session.refresh(r)
        print("restaurant:", r.id, r.name)

        print("menu:", import_menu_csv(session, r.id, (SEED / "kumars_menu.csv").read_text()))

        logo_src = SEED / "logo.png"
        if logo_src.exists():
            r.logo_asset_id = copy_asset(session, r.id, logo_src, "logo", "image/png").id
            session.add(r)
            session.commit()
        music_src = SEED / "music_upbeat.mp3"
        if music_src.exists():
            copy_asset(session, r.id, music_src, "music", "audio/mpeg")

        items = {m.name_norm: m for m in session.exec(select(MenuItem).where(MenuItem.restaurant_id == r.id)).all()}
        n_photos = 0
        for p in sorted((SEED / "photos").iterdir()):
            if p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue
            norm = p.stem.replace("-", " ").replace("_", " ").lower()
            item = items.get(norm)
            if not item:
                print("  ! no menu item for photo", p.name)
                continue
            mime = {"png": "image/png", "webp": "image/webp"}.get(p.suffix.lower().lstrip("."), "image/jpeg")
            if mime != "image/jpeg":  # normalize to JPEG like uploads do
                from PIL import Image

                jp = s.media_dir / "work" / (p.stem + ".jpg")
                Image.open(p).convert("RGB").save(jp, quality=92)
                p, mime = jp, "image/jpeg"
            item.photo_asset_id = copy_asset(session, r.id, p, "photo", mime).id
            session.add(item)
            n_photos += 1
        session.commit()
        print("photos linked:", n_photos)

        print("sales:", import_sales_text(session, r.id, (SEED / "kumars_sales_8w.csv").read_text()))
        await compute_insights(session, r.id, r.name)
        cards = _cards(session, r.id)
        for c in cards["cards"]:
            print(f"  insight {c['angle']:<11} {c['menu_item']['name']:<18} {c['metric_label']}  [{c['reason_source']}]")
        (SEED / "mock_insights.json").write_text(json.dumps(cards, indent=1))

        st = get_app_settings(session, r.id)
        st.veo_cost_per_sec_cents = s.veo_cost_per_sec_cents
        session.add(st)
        session.commit()

        # SEED_RENDER=0 (low-CPU hosts): skip the sample renders; the library starts empty.
        render_samples = os.environ.get("SEED_RENDER", "1") != "0"

        # mock_short.mp4: a real free-mode render of the biryani.
        bir = items.get("chicken biryani")
        if render_samples and bir and bir.photo_asset_id and not (SEED / "mock_short.mp4").exists():
            print("rendering seed/mock_short.mp4 …")
            await render_free(session, r, bir, SEED / "mock_short.mp4", angle="rising")

        # Historical library videos (only once).
        have = session.exec(select(Video).where(Video.restaurant_id == r.id)).first()
        published = json.loads((SEED / "published.json").read_text()) if (SEED / "published.json").exists() else {}
        if have is None and render_samples:
            for name in ("Butter Chicken", "Tandoori Chicken"):
                item = items.get(name.lower())
                if not item or not item.photo_asset_id:
                    continue
                stem = f"seed_{slugify(name)}"
                out = s.media_dir / "videos" / f"{stem}.mp4"
                print("rendering library video:", name)
                out, poster, info, script = await render_free(session, r, item, out, angle="top_seller" if name == "Butter Chicken" else None)
                poster_dst = s.media_dir / "posters" / poster.name
                shutil.move(poster, poster_dst)
                job = Job(restaurant_id=r.id, mode="menu", menu_item_id=item.id, photo_asset_id=item.photo_asset_id,
                          status="done", stages_json=jdump([{**st_, "status": "done"} for st_ in initial_stages()]),
                          script_json=jdump(script), flags_json=jdump({"seed": True}))
                session.add(job)
                session.commit()
                session.refresh(job)
                v = Video(job_id=job.id, restaurant_id=r.id, menu_item_id=item.id, path=str(out),
                          poster_path=str(poster_dst), duration_s=info["duration_s"], width=info["width"],
                          height=info["height"], bytes=info["bytes"], mode="free", cost_cents=0,
                          title=script["title"], description=script["description"],
                          hashtags_json=jdump(script["hashtags"]))
                session.add(v)
                session.commit()
        if published.get("youtube_url"):
            dish = (published.get("dish") or "Butter Chicken").lower()
            item = items.get(dish)
            v = session.exec(select(Video).where(Video.restaurant_id == r.id, Video.menu_item_id == (item.id if item else -1))).first()
            if v:
                v.youtube_url = published["youtube_url"]
                v.youtube_id = published.get("youtube_id")
                v.youtube_privacy = published.get("privacy", "unlisted")
                v.publish_status = "published"
                session.add(v)
                session.commit()
                print("marked published:", v.id, v.youtube_url)
    print("seed done ✓")


if __name__ == "__main__":
    asyncio.run(main())
