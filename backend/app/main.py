"""FastAPI app entrypoint."""
from __future__ import annotations

import hmac
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import ensure_dirs, get_settings
from .db import WORKSPACE_RE, init_db, restore_media, workspace_var
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


class WorkspaceMiddleware:
    """Ties each request to the visitor's studio (X-Workspace) for current_restaurant().

    Writes without a workspace would change the shared demo template every new studio is copied from, so they
    need an owner or admin token.
    """

    WRITE = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode(errors="replace") for k, v in scope["headers"]}
        ws = headers.get("x-workspace", "").strip().lower()
        ws = ws if WORKSPACE_RE.match(ws) else None
        if ws is None and scope["method"] in self.WRITE and not self._privileged(headers):
            body = json.dumps({"error": {"code": "workspace_required", "retryable": False,
                                         "message": "Refresh the page and try again (missing studio id)."}}).encode()
            await send({"type": "http.response.start", "status": 400,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})
            return
        token = workspace_var.set(ws)
        try:
            await self.app(scope, receive, send)
        finally:
            workspace_var.reset(token)

    @staticmethod
    def _privileged(headers: dict) -> bool:
        s = get_settings()
        for header, real in (("x-owner-token", s.owner_token), ("x-admin-token", s.admin_token)):
            given = headers.get(header)
            if real and given and hmac.compare_digest(given, real):
                return True
        return False


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="What's Cooking? API", version="1.0.0", lifespan=lifespan)
    origins = {o.strip().rstrip("/") for o in s.frontend_origin.split(",") if o.strip()}
    origins |= {"http://localhost:3000", "http://127.0.0.1:3000"}
    app.add_middleware(WorkspaceMiddleware)  # inside CORS, so its errors still carry CORS headers
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
