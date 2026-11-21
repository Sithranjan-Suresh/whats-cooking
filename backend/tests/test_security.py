"""Security checklist (docs/SECURITY.md): each item that applies to this app, pinned by a test."""
import io
import json
import time

import pytest
from PIL import Image

from tests.test_api import ADMIN, OWNER, _jpeg, _menu_job, _wait, client  # noqa: F401  (fixture)

# Every route and who may call it. A new route makes test_every_route_was_reviewed fail until it's added here
# (on purpose: checklist #11 "every API route checks who the caller is").
REVIEWED = {
    ("GET", "/health"): "public", ("GET", "/restaurants/me"): "studio", ("PATCH", "/restaurants/me"): "studio",
    ("POST", "/uploads"): "studio", ("GET", "/menu"): "studio", ("POST", "/menu/import"): "studio",
    ("POST", "/menu/{item_id}/photo"): "studio+owned", ("GET", "/usage"): "public (shared budget numbers)",
    ("GET", "/settings"): "admin", ("PATCH", "/settings"): "admin",
    ("POST", "/sales/import"): "studio", ("GET", "/sales/summary"): "studio", ("GET", "/insights"): "studio",
    ("POST", "/insights/refresh"): "studio", ("GET", "/insights/{insight_id}"): "studio+owned",
    ("POST", "/sales/map"): "studio+owned",
    ("POST", "/jobs"): "studio+owned+fair-use", ("GET", "/jobs"): "studio", ("GET", "/jobs/{job_id}"): "studio+owned",
    ("POST", "/jobs/{job_id}/confirm-dish"): "studio+owned", ("POST", "/jobs/{job_id}/retry"): "studio+owned+fair-use",
    ("POST", "/jobs/{job_id}/edit"): "studio+owned+fair-use", ("POST", "/dishes"): "studio",
    ("GET", "/videos"): "studio", ("GET", "/videos/{video_id}"): "studio+owned",
    ("POST", "/videos/{video_id}/publish"): "studio+owned+visitor's YouTube",
    ("GET", "/youtube/auth/url"): "public (signed state + browser nonce)", ("GET", "/youtube/auth/callback"): "Google",
    ("GET", "/youtube/uploads"): "visitor's YouTube", ("POST", "/youtube/disconnect"): "public no-op",
    ("POST", "/director/plan"): "studio+owned+limits", ("POST", "/director/preview"): "studio+owned+limits",
    ("POST", "/mascot/options"): "studio+limits", ("POST", "/mascot/choose"): "studio+owned",
    ("GET", "/auth/google/url"): "public+limits", ("GET", "/auth/me"): "session",
}


def test_every_route_was_reviewed():
    from app.main import create_app

    routes = {(m, r.path) for r in create_app().routes if hasattr(r, "methods") and not r.path.startswith(("/docs", "/openapi", "/redoc"))
              for m in r.methods if m not in ("HEAD", "OPTIONS")}
    assert routes - set(REVIEWED) == set(), "new routes: say who may call them in REVIEWED"


def test_decompression_bomb_is_refused(client):
    big = Image.new("L", (9000, 9000))  # 81 MP of one color compresses to a tiny PNG
    b = io.BytesIO()
    big.save(b, "PNG")
    assert len(b.getvalue()) < 10 * 1024 * 1024
    r = client.post("/uploads", files={"file": ("x.png", b.getvalue(), "image/png")}, data={"kind": "photo"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "image_too_large"


def test_youtube_connection_expires():
    from cryptography.fernet import Fernet

    from app.config import get_settings
    from app.viewer import CONNECTION_DAYS, encode_connection, viewer_youtube

    assert viewer_youtube(encode_connection("rt", "UC1", "Chan"))["rt"] == "rt"
    old = Fernet(get_settings().app_secret.encode()).encrypt_at_time(
        json.dumps({"rt": "rt", "cid": "UC1", "ct": "Chan"}).encode(), int(time.time()) - (CONNECTION_DAYS + 1) * 86400)
    assert viewer_youtube(old.decode()) is None


def test_settings_are_admin_only(client):
    assert client.get("/settings").status_code == 403
    assert client.get("/settings", headers=OWNER).status_code == 403
    assert client.get("/settings", headers=ADMIN).status_code == 200


def test_sign_in_is_rate_limited(client, monkeypatch):
    from app.config import get_settings
    from app.routers import director

    monkeypatch.setattr(get_settings(), "signins_per_hour_per_ip", 2)
    director._hits.clear()
    codes = [client.get("/auth/google/url?nonce=abcdef0123456789abcd").status_code for _ in range(3)]
    assert codes[:2] == [400, 400] and codes[2] == 429  # 400 = Google not configured in tests; 3rd is limited first


def test_failed_youtube_upload_does_not_leak_internals(client, monkeypatch):
    from app.services import youtube
    from app.viewer import encode_connection

    def boom(*a, **k):
        raise RuntimeError("connection reset by 10.0.3.7:/srv/app/secret_internal_path")

    monkeypatch.setattr(youtube, "upload", boom)
    jid = _menu_job(client, headers=OWNER)
    j = _wait(client, jid, until=("done", "failed"), timeout=90)
    yt = {"X-YouTube-Auth": encode_connection("rt", "UC1", "Chan")}
    assert client.post(f"/videos/{j['video']['id']}/publish", json={"title": "t"}, headers={**OWNER, **yt}).status_code == 202
    for _ in range(50):
        v = client.get(f"/videos/{j['video']['id']}").json()
        if v["publish_status"] == "failed":
            break
        time.sleep(0.1)
    assert v["publish_status"] == "failed" and "10.0.3.7" not in v["publish_error"] and "secret" not in v["publish_error"]


def test_production_cors_and_secret(monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    s = get_settings()
    monkeypatch.setattr(s, "public_base_url", "https://api.example.com")
    monkeypatch.setattr(s, "frontend_origin", "https://app.example.com")
    app = create_app()
    with TestClient(app) as c:
        ok = c.get("/health", headers={"Origin": "https://app.example.com"})
        bad = c.get("/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "https://app.example.com"
    assert "access-control-allow-origin" not in bad.headers  # localhost can't call the live API
    monkeypatch.setattr(s, "app_secret", "")
    with pytest.raises(RuntimeError, match="APP_SECRET"):
        with TestClient(create_app()):
            pass


def test_errors_do_not_leak_details(client, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.routers import core

    def explode(*a, **k):
        raise RuntimeError("psycopg.OperationalError at /srv/app/db.py line 42: password=hunter2")

    monkeypatch.setattr(core, "restaurant_out", explode)
    with TestClient(create_app(), raise_server_exceptions=False, headers={"X-Workspace": "a" * 32}) as c:
        r = c.get("/restaurants/me")
    assert r.status_code == 500 and "hunter2" not in r.text and "db.py" not in r.text
    assert r.json()["error"]["code"] == "internal_error"
