"""Job queue + stage machine.

queued → analyze → [needs_dish?] → script → visuals → voice → assemble → done
Any hard failure → failed (with stage + error). Visuals and voice degrade instead of failing.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import secrets
import shutil
import time
from pathlib import Path
from typing import Any, Optional

from sqlmodel import select

from .config import get_settings
from .db import session_scope
from .models import Asset, Insight, Job, MenuItem, Restaurant, Video, jdump, jload, utcnow
from .services import formats, budget, gemini, render, scripts, tts, veo
from .services.insights import top_matches
from .services.media import FFmpegError, probe_video
from .util import fmt_price

log = logging.getLogger("app.pipeline")

STAGES = ["analyze", "script", "visuals", "voice", "assemble"]


def initial_stages() -> list[dict]:
    return [{"name": n, "status": "pending", "started_at": None, "ended_at": None, "note": None} for n in STAGES]


class StageFailed(Exception):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.message = message


class Paused(Exception):
    pass


# ------------------------------------------------------------------ DB helpers

def _update_job(job_id: int, **fields: Any) -> None:
    with session_scope() as s:
        job = s.get(Job, job_id)
        if job is None:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        s.add(job)
        s.commit()


def _get_stages(job_id: int) -> list[dict]:
    with session_scope() as s:
        job = s.get(Job, job_id)
        return jload(job.stages_json, initial_stages()) if job else initial_stages()


def set_stage(job_id: int, name: str, status: str, note: Optional[str] = None) -> None:
    with session_scope() as s:
        job = s.get(Job, job_id)
        if job is None:
            return
        stages = jload(job.stages_json, initial_stages())
        now = utcnow().isoformat() + "Z"
        for st in stages:
            if st["name"] == name:
                if status == "running":
                    st["started_at"] = now
                    st["ended_at"] = None
                elif status in ("done", "failed", "skipped"):
                    st["started_at"] = st["started_at"] or now
                    st["ended_at"] = now
                st["status"] = status
                if note is not None:
                    st["note"] = note
        job.stages_json = jdump(stages)
        if job.status == "queued":
            job.status = "running"
        s.add(job)
        s.commit()


def stage_status(job_id: int, name: str) -> str:
    for st in _get_stages(job_id):
        if st["name"] == name:
            return st["status"]
    return "pending"


def _flags(job: Job) -> dict:
    return jload(job.flags_json, {}) or {}


# ------------------------------------------------------------------ queue

class JobQueue:
    def __init__(self) -> None:
        self.queue: Optional[asyncio.Queue[int]] = None
        self.workers: list[asyncio.Task] = []

    async def start(self, n: int) -> None:
        self.queue = asyncio.Queue()
        self.workers = [asyncio.create_task(self._worker(i)) for i in range(n)]
        self._recover()

    async def stop(self) -> None:
        for w in self.workers:
            w.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers = []

    def enqueue(self, job_id: int) -> None:
        assert self.queue is not None, "queue not started"
        self.queue.put_nowait(job_id)

    def _recover(self) -> None:
        with session_scope() as s:
            for job in s.exec(select(Job).where(Job.status.in_(("running", "queued")))).all():
                if job.status == "running":
                    job.status = "failed"
                    job.error = "The server restarted while this video was rendering. Retry."
                    job.error_stage = next(
                        (st["name"] for st in jload(job.stages_json, []) if st["status"] == "running"), None
                    )
                    s.add(job)
                else:
                    self.queue.put_nowait(job.id)  # type: ignore[union-attr]
            s.commit()

    async def _worker(self, idx: int) -> None:
        assert self.queue is not None
        while True:
            job_id = await self.queue.get()
            try:
                await run_job(job_id)
            except Exception:  # noqa: BLE001
                log.exception("worker %s: job %s crashed", idx, job_id)
                _update_job(job_id, status="failed", error="Unexpected error. Retry.", finished_at=utcnow())
            finally:
                self.queue.task_done()


job_queue = JobQueue()


# ------------------------------------------------------------------ context

class Ctx:
    def __init__(self, job_id: int):
        with session_scope() as s:
            job = s.get(Job, job_id)
            if job is None:
                raise LookupError(job_id)
            self.job_id = job_id
            self.mode = job.mode
            self.angle = job.angle
            self.style = job.style if job.style in render.STYLE_PRESETS else "bold"
            self.length_s = job.length_s if job.length_s in (8, 15, 30) else 8
            self.veo_requested = job.veo_requested
            self.flags = _flags(job)
            self.fmt = formats.get(self.flags.get("format"))
            self.analyze = jload(job.analyze_json, {}) or {}
            self.script = jload(job.script_json, None)
            r = s.get(Restaurant, job.restaurant_id)
            self.restaurant_id = r.id
            self.restaurant = {
                "name": r.name, "color_primary": r.color_primary, "color_accent": r.color_accent,
                "voice_tone": r.voice_tone, "tts_voice": r.tts_voice,
            }
            logo = s.get(Asset, r.logo_asset_id) if r.logo_asset_id else None
            self.logo_path = Path(logo.path) if logo else None
            music = s.exec(select(Asset).where(Asset.restaurant_id == r.id, Asset.kind == "music")).first()
            self.music_path = Path(music.path) if music else None
            self.menu_item_id = job.menu_item_id
            item = s.get(MenuItem, job.menu_item_id) if job.menu_item_id else None
            self.item = (
                {"id": item.id, "name": item.name, "price_cents": item.price_cents,
                 "description": item.description, "name_norm": item.name_norm}
                if item else None
            )
            self.menu_row = scripts.menu_row_for(item) if item else {"name": None, "price": None, "description": None}
            photo = s.get(Asset, job.photo_asset_id) if job.photo_asset_id else None
            self.photo_path = Path(photo.path) if photo else None
            self.photo_mime = photo.mime if photo else "image/jpeg"
            self.insight_metric = None
            if job.insight_id:
                ins = s.get(Insight, job.insight_id)
                if ins:
                    self.insight_metric = jload(ins.metric_json, {})
            self.menu_list = [
                {"id": m.id, "name": m.name, "price": fmt_price(m.price_cents),
                 "description": m.description}
                for m in s.exec(select(MenuItem).where(MenuItem.restaurant_id == r.id)).all()
            ]
        self.card_task: "Optional[asyncio.Task[Path]]" = None
        # formats without a slate use the whole length for motion
        self.main_len = float(self.length_s) if self.fmt.overlay_end else self.length_s - render.END_CARD_S
        self.work = get_settings().media_dir / "work" / f"job_{job_id}"
        self.work.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------ entry

async def run_job(job_id: int) -> None:
    s = get_settings()
    ctx = Ctx(job_id)
    _update_job(job_id, status="running")
    try:
        if s.mock_pipeline:
            await run_mock(ctx)
        else:
            await run_real(ctx)
    except Paused:
        return
    except StageFailed as e:
        set_stage(job_id, e.stage, "failed", e.message)
        _update_job(job_id, status="failed", error=e.message, error_stage=e.stage, finished_at=utcnow())
        budget.release(job_id)
    finally:
        if ctx.card_task and not ctx.card_task.done():
            ctx.card_task.cancel()
        if not s.mock_pipeline:
            _cleanup_work(ctx)


def _cleanup_work(ctx: Ctx) -> None:
    with session_scope() as s:
        job = s.get(Job, ctx.job_id)
        if job and job.status in ("done", "failed"):
            shutil.rmtree(ctx.work, ignore_errors=True)


def _angle_metric(ctx: Ctx) -> Optional[str]:
    # Qualitative only: keeps numbers out of scripts so the grounding validator stays strict.
    return {
        "rising": "orders for this dish climbed sharply this week",
        "top_seller": "this is the most-ordered dish this week",
        "slow_mover": "regulars who try it love it, but few people know about it yet",
    }.get(ctx.angle or "", None)


# ------------------------------------------------------------------ real pipeline

async def run_real(ctx: Ctx) -> None:
    jid = ctx.job_id
    if ctx.photo_path is None or not ctx.photo_path.exists():
        raise StageFailed("analyze", "No photo for this dish. Upload one and retry.")

    # ---- Analyze
    if stage_status(jid, "analyze") != "done":
        set_stage(jid, "analyze", "running")
        await _analyze(ctx)
    # ---- Script
    if stage_status(jid, "script") != "done" or not ctx.script:
        set_stage(jid, "script", "running")
        await _script(ctx)
    # ---- Visuals (the logo ending is painted meanwhile)
    set_stage(jid, "visuals", "running")
    if not ctx.fmt.overlay_end:
        _start_end_card(ctx)
    visuals = await _visuals(ctx)
    # ---- Voice
    set_stage(jid, "voice", "running")
    voice = await _voice(ctx)
    # ---- Assemble
    set_stage(jid, "assemble", "running")
    await _assemble(ctx, visuals, voice)


async def _analyze(ctx: Ctx) -> None:
    jid = ctx.job_id
    photo = (ctx.photo_path.read_bytes(), ctx.photo_mime)
    if ctx.menu_item_id or ctx.flags.get("not_on_menu"):
        notes, warn = "", None
        try:
            d = await gemini.describe_photo(photo, ctx.menu_row.get("name") or "a dish")
            notes = d["visual_notes"]
            if not d["is_food"]:
                warn = "This doesn't look like a dish photo"
            elif d["quality"] != "good":
                warn = f"Photo looks {d['quality']}"
        except gemini.GeminiError as e:
            log.info("describe_photo failed (%s); continuing without visual notes", e.kind)
        ctx.analyze.update({"visual_notes": notes, "menu_item_id": ctx.menu_item_id, "confidence": 1.0, "warning": warn})
        _update_job(jid, analyze_json=jdump(ctx.analyze))
        set_stage(jid, "analyze", "done", warn or ("Dish confirmed" if ctx.menu_item_id else "Not on menu"))
        return

    # Photo mode: match to the menu.
    menu_pairs = [(m["id"], m["name"]) for m in ctx.menu_list]
    try:
        a = await gemini.analyze_photo(photo, ctx.menu_list)
    except gemini.GeminiError as e:
        msg = {"rate_limit": "AI is busy", "timeout": "Couldn't read the photo in time"}.get(e.kind, "Couldn't read the photo")
        ctx.analyze = {"is_food": True, "dish_guess": "", "menu_item_id": None, "confidence": 0,
                       "visual_notes": "", "quality": "good", "reason": "analyze_failed",
                       "candidates": [m for m in top_matches("", menu_pairs, 3)]}
        _pause_for_dish(ctx, f"{msg}. Pick the dish.")
        return
    ctx.analyze = dict(a)
    cands = top_matches(a["dish_guess"], menu_pairs, 3)
    if a["menu_item_id"] and a["menu_item_id"] in cands:
        cands.remove(a["menu_item_id"])
    if a["menu_item_id"]:
        cands = [a["menu_item_id"], *cands][:3]
    ctx.analyze["candidates"] = cands
    if not a["is_food"] and not ctx.flags.get("continue_anyway"):
        ctx.analyze["reason"] = "not_food"
        _pause_for_dish(ctx, "This doesn't look like a dish photo")
        return
    if a["menu_item_id"] and a["confidence"] >= 0.6:
        ctx.menu_item_id = a["menu_item_id"]
        _update_job(ctx.job_id, analyze_json=jdump(ctx.analyze), menu_item_id=ctx.menu_item_id)
        _reload_item(ctx)
        note = f"Matched {ctx.menu_row['name']} ({round(a['confidence'] * 100)}%)"
        if a["quality"] != "good":
            note += f" · photo looks {a['quality']}"
        set_stage(ctx.job_id, "analyze", "done", note)
        return
    ctx.analyze["reason"] = "low_confidence"
    _pause_for_dish(ctx, "Not sure which dish this is. Pick it.")


def _pause_for_dish(ctx: Ctx, note: str) -> None:
    _update_job(ctx.job_id, analyze_json=jdump(ctx.analyze), status="needs_dish")
    set_stage(ctx.job_id, "analyze", "running", note)
    _update_job(ctx.job_id, status="needs_dish")
    raise Paused()


def _reload_item(ctx: Ctx) -> None:
    with session_scope() as s:
        item = s.get(MenuItem, ctx.menu_item_id)
        if item:
            ctx.item = {"id": item.id, "name": item.name, "price_cents": item.price_cents,
                        "description": item.description, "name_norm": item.name_norm}
            ctx.menu_row = scripts.menu_row_for(item)


async def _script(ctx: Ctx) -> None:
    jid = ctx.job_id
    script, source, note = await scripts.write_script(
        menu_row=ctx.menu_row,
        restaurant_name=ctx.restaurant["name"],
        angle=ctx.angle,
        tone=ctx.restaurant["voice_tone"],
        style=ctx.style,
        length_s=ctx.length_s,
        visual_notes=ctx.analyze.get("visual_notes", ""),
        angle_metric=_angle_metric(ctx),
        not_on_menu=bool(ctx.flags.get("not_on_menu")),
        fmt=ctx.fmt.key,
    )
    script["source"] = source
    ctx.script = script
    _update_job(jid, script_json=jdump(script))
    set_stage(jid, "script", "done", note or ("Grounded in your menu" if source != "template" else None))


def _start_end_card(ctx: Ctx) -> "asyncio.Task[Path]":
    """Paint the animated logo ending in the background (overlaps the slow AI-motion wait)."""
    ctx.card_task = asyncio.create_task(render.animated_end_card(
        ctx.work, restaurant_name=ctx.restaurant["name"],
        dish_name=None if ctx.flags.get("not_on_menu") else ctx.menu_row.get("name"),
        price=None if ctx.flags.get("not_on_menu") else ctx.menu_row.get("price"),
        color_primary=ctx.restaurant["color_primary"], color_accent=ctx.restaurant["color_accent"],
        logo_path=ctx.logo_path,
    ))
    return ctx.card_task


async def _visuals(ctx: Ctx) -> Path:
    jid = ctx.job_id
    main_len = ctx.main_len
    fallback = None
    if ctx.veo_requested:
        if ctx.flags.get("demo"):
            fallback = "demo_mode"
        else:
            decision = budget.reserve_veo(ctx.restaurant_id, jid, seconds=8)
            if not decision.allowed and decision.reason in ("daily_limit", "monthly_cap"):
                with session_scope() as s:
                    msg = budget.cap_message(s, ctx.restaurant_id, decision.reason, decision.est_cost_cents)
                raise StageFailed("visuals", msg)
            if not decision.allowed:
                fallback = decision.reason
            else:
                clip = ctx.work / "veo.mp4"
                try:
                    set_stage(jid, "visuals", "running", "Generating AI motion (about a minute)…")
                    await veo.generate_clip(ctx.photo_path, ctx.photo_mime,
                                            ctx.script.get("veo_prompt") or scripts.default_veo_prompt(), clip)
                except veo.VeoError as e:
                    budget.release(jid)
                    fallback = veo.FALLBACK_REASONS.get(e.kind, "veo_error")
                    log.warning("veo failed (%s): %s", e.kind, e)
                else:
                    budget.commit(jid)  # the clip exists, so it was billed
                    _update_job(jid, cost_cents=decision.est_cost_cents, veo_used=True)
                    try:
                        out = await render.veo_plus_tail(clip, ctx.photo_path, main_len, ctx.work, style=ctx.style)
                        set_stage(jid, "visuals", "done", "AI motion")
                        return out
                    except FFmpegError as e:
                        fallback = "veo_error"
                        log.error("veo compose failed: %s", e.stderr_tail[-300:])
                        _update_job(jid, veo_used=False)
    try:
        out = await render.kenburns(ctx.photo_path, main_len, ctx.work, style=ctx.style)
    except FFmpegError as e:
        raise StageFailed("visuals", "Couldn't animate the photo. Retry.") from e
    note = "Free mode (Ken Burns)"
    if fallback:
        note = "Free mode (" + {
            "free_mode": "free mode is on", "daily_limit": "daily Veo limit reached",
            "monthly_cap": "monthly cap reached", "demo_mode": "demo mode",
        }.get(fallback, "Veo unavailable") + ")"
        _update_job(jid, fallback_reason=fallback)
    set_stage(jid, "visuals", "done", note)
    return out


async def _voice(ctx: Ctx) -> Optional[dict]:
    jid = ctx.job_id
    if not ctx.fmt.narrated or not (ctx.script.get("voiceover") or "").strip():
        set_stage(jid, "voice", "skipped", "No narrator in this format: the food does the talking")
        return None
    v = await tts.synthesize(ctx.script.get("voiceover", ""), ctx.restaurant["tts_voice"],
                             ctx.work / "voice.mp3", tone=ctx.restaurant["voice_tone"])
    if v is None:
        set_stage(jid, "voice", "done", "Captions only (voice unavailable)")
        flags = dict(ctx.flags, captions_only=True)
        _update_job(jid, flags_json=jdump(flags))
    else:
        set_stage(jid, "voice", "done", "Voice: " + ("neural" if v["engine"] == "edge-tts" else "fallback engine"))
    return v


async def _assemble(ctx: Ctx, visuals: Path, voice: Optional[dict]) -> None:
    if ctx.fmt.overlay_end:
        return await _assemble_loop(ctx, visuals)
    jid = ctx.job_id
    main_len = ctx.main_len
    speech = None
    if voice and voice.get("timings"):
        speech = (voice["timings"][0]["start"] + 0.3, voice["timings"][-1]["end"] + 0.3)
    ass = render.build_ass(ctx.script, main_len, color_primary=ctx.restaurant["color_primary"],
                           color_accent=ctx.restaurant["color_accent"], style=ctx.style, speech=speech)
    card = await (ctx.card_task or _start_end_card(ctx))
    media = get_settings().media_dir
    out = media / "videos" / f"job_{jid}_{secrets.token_hex(8)}.mp4"  # unguessable: /media is public
    try:
        await render.assemble_with_retry(work=ctx.work, visuals=visuals, main_len=main_len, ass_text=ass,
                                         end_card_png=card, voice=voice, music=ctx.music_path, out_path=out,
                                         ambient=ctx.work / "ambient.m4a")
        poster = await render.extract_poster(out, media / "posters" / (out.stem + ".jpg"))
        info = await probe_video(out)
    except FFmpegError as e:
        raise StageFailed("assemble", "Render failed. Retry.") from e
    _finish(ctx, out, poster, info)
    set_stage(jid, "assemble", "done", f"{info['duration_s']:.0f}s · {info['bytes'] / 1e6:.1f} MB")


async def _assemble_loop(ctx: Ctx, visuals: Path) -> None:
    """Formats without a slate (money shot, chef POV): corner logo, name at the end, loops."""
    jid = ctx.job_id
    dish = None if ctx.flags.get("not_on_menu") else ctx.menu_row.get("name")
    outro = ctx.restaurant["name"] + (f" · {dish}" if dish else "")
    # captions and the name line finish before the last moment blends back into the first (clean loop)
    ass = render.build_ass(ctx.script, ctx.main_len - render.LOOP_XFADE, color_primary=ctx.restaurant["color_primary"],
                           color_accent=ctx.restaurant["color_accent"], style=ctx.fmt.caption_style, outro=outro)
    media = get_settings().media_dir
    out = media / "videos" / f"job_{jid}_{secrets.token_hex(8)}.mp4"
    try:
        await render.assemble_loop_with_retry(work=ctx.work, visuals=visuals, total=ctx.main_len, ass_text=ass,
                                              logo=ctx.logo_path, music=ctx.music_path,
                                              ambient=ctx.work / "ambient.m4a", out_path=out)
        poster = await render.extract_poster(out, media / "posters" / (out.stem + ".jpg"))
        info = await probe_video(out)
    except FFmpegError as e:
        raise StageFailed("assemble", "Render failed. Retry.") from e
    _finish(ctx, out, poster, info)
    sound = "kitchen sound" if (ctx.work / "ambient.m4a").exists() else "music"
    set_stage(jid, "assemble", "done", f"{info['duration_s']:.0f}s loop · {sound} · {info['bytes'] / 1e6:.1f} MB")


def _finish(ctx: Ctx, out: Path, poster: Optional[Path], info: dict, *, mode: Optional[str] = None,
            cost_cents: Optional[int] = None) -> None:
    with session_scope() as s:
        job = s.get(Job, ctx.job_id)
        script = ctx.script or {}
        v = Video(
            job_id=job.id, restaurant_id=job.restaurant_id, menu_item_id=job.menu_item_id,
            path=str(out), poster_path=str(poster) if poster else None,
            duration_s=info["duration_s"], width=info["width"], height=info["height"], bytes=info["bytes"],
            mode=mode or ("veo" if job.veo_used else "free"),
            cost_cents=job.cost_cents if cost_cents is None else cost_cents,
            title=script.get("title"), description=script.get("description"),
            hashtags_json=jdump(script.get("hashtags", [])),
        )
        s.add(v)
        job.status = "done"
        job.finished_at = utcnow()
        if cost_cents is not None:
            job.cost_cents = cost_cents
        s.add(job)
        s.commit()


# ------------------------------------------------------------------ mock + demo cache

MOCK_TIMELINE = [("analyze", 1.5), ("script", 3.0), ("visuals", 6.0), ("voice", 1.5), ("assemble", 2.0)]


async def _timeline(ctx: Ctx, times: list[tuple[str, float]], *, fail_rate: float = 0.0, script: Optional[dict] = None,
                    notes: Optional[dict] = None) -> None:
    jid = ctx.job_id
    notes = notes or {}
    for name, secs in times:
        if stage_status(jid, name) == "done":
            continue
        set_stage(jid, name, "running", notes.get(name + "_running"))
        await asyncio.sleep(secs)
        if fail_rate and random.random() < fail_rate:
            raise StageFailed(name, f"Mock failure in {name} (MOCK_FAIL_RATE). Retry.")
        if name == "analyze" and ctx.mode == "photo" and not ctx.menu_item_id and not ctx.flags.get("not_on_menu"):
            if get_settings().mock_needs_dish:
                ctx.analyze = {"is_food": True, "dish_guess": "curry", "menu_item_id": None, "confidence": 0.4,
                               "visual_notes": "", "quality": "good", "reason": "low_confidence",
                               "candidates": [m["id"] for m in ctx.menu_list[:3]]}
                _pause_for_dish(ctx, "Not sure which dish this is. Pick it.")
            ctx.menu_item_id = ctx.menu_list[0]["id"] if ctx.menu_list else None
            _update_job(jid, menu_item_id=ctx.menu_item_id)
            _reload_item(ctx)
        if name == "script":
            ctx.script = script or scripts.template_script(ctx.menu_row, ctx.angle, ctx.restaurant["name"], ctx.length_s)
            ctx.script.setdefault("source", "template")
            _update_job(jid, script_json=jdump(ctx.script))
        set_stage(jid, name, "done", notes.get(name))


def _copy_video(src: Path, jid: int, tag: str) -> tuple[Path, Optional[Path]]:
    media = get_settings().media_dir
    out = media / "videos" / f"{tag}_{jid}_{secrets.token_hex(8)}.mp4"
    shutil.copyfile(src, out)
    poster_src = src.with_suffix(".jpg")
    poster = None
    if poster_src.exists():
        poster = media / "posters" / (out.stem + ".jpg")
        shutil.copyfile(poster_src, poster)
    return out, poster


async def run_mock(ctx: Ctx) -> None:
    s = get_settings()
    times = [(n, t * 2 if (n == "visuals" and ctx.veo_requested) else t) for n, t in MOCK_TIMELINE]
    await _timeline(ctx, times, fail_rate=s.mock_fail_rate, notes={"visuals": "Free mode (mock)"})
    src = s.seed_dir / "mock_short.mp4"
    if not src.exists():
        raise StageFailed("assemble", "seed/mock_short.mp4 is missing. Run `make seed`.")
    out, poster = _copy_video(src, ctx.job_id, "mock")
    if poster is None:
        poster = await render.extract_poster(out, s.media_dir / "posters" / (out.stem + ".jpg"))
    _finish(ctx, out, poster, await probe_video(out), mode="free", cost_cents=0)
