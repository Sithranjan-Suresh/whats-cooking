"""FastAPI app entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import ensure_dirs, get_settings
from .db import init_db, restore_media
from .errors import install_error_handlers
from .pipeline import job_queue
from .routers import core, insights, jobs, videos

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_dirs()
    init_db()
    restore_media()
    await job_queue.start(get_settings().workers)
    yield
    await job_queue.stop()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="What's Cooking? API", version="1.0.0", lifespan=lifespan)
    origins = {o.strip().rstrip("/") for o in s.frontend_origin.split(",") if o.strip()}
    origins |= {"http://localhost:3000", "http://127.0.0.1:3000"}
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)

    for r in (core.router, insights.router, jobs.router, videos.router):
        app.include_router(r)
    ensure_dirs()
    app.mount("/media", StaticFiles(directory=str(s.media_dir)), name="media")
    return app


app = create_app()
