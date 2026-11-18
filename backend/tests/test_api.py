"""API + pipeline integration tests (real ffmpeg; Gemini/TTS/Veo faked)."""
import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

OWNER = {"X-Owner-Token": "test-owner"}


@pytest.fixture()
def client(restaurant, monkeypatch):
    from app.services import tts

    async def fake_tts(text, voice, out_path, tone="upbeat"):
        return None  # captions-only path (no network in tests)

    monkeypatch.setattr(tts, "synthesize", fake_tts)
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def _jpeg(w=900, h=1200, color=(200, 120, 40)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (w, h), color).save(b, "JPEG")
    return b.getvalue()


def _wait(client, job_id, until=("done", "failed", "needs_dish"), timeout=60):
    t = time.time()
    while time.time() - t < timeout:
        j = client.get(f"/jobs/{job_id}").json()
        if j["status"] in until:
            return j
        time.sleep(0.3)
    raise AssertionError(f"job {job_id} stuck: {j}")


def test_health_and_error_shape(client):
    h = client.get("/health").json()
    assert h["ok"] and h["demo"] and h["actor"] == "demo"
    r = client.get("/jobs/999")
    assert r.status_code == 404
    assert set(r.json()["error"]) == {"code", "message", "retryable"}


def test_bad_owner_token(client):
    r = client.get("/health", headers={"X-Owner-Token": "nope"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "bad_owner_token"


def test_upload_rejections(client):
    r = client.post("/uploads", files={"file": ("x.gif", b"GIF89a", "image/gif")}, data={"kind": "photo"})
    assert r.status_code == 415 and r.json()["error"]["code"] == "bad_mime"
    big = b"\xff" * (10 * 1024 * 1024 + 10)
    r = client.post("/uploads", files={"file": ("x.jpg", big, "image/jpeg")}, data={"kind": "photo"})
    assert r.status_code == 413
    r = client.post("/uploads", files={"file": ("x.jpg", b"notanimage", "image/jpeg")}, data={"kind": "photo"})
    assert r.status_code == 415


def test_demo_mode_blocks_owner_actions(client):
    assert client.patch("/settings", json={"free_mode": True}).status_code == 403
    assert client.patch("/restaurants/me", json={"name": "X"}).json()["error"]["code"] == "demo_mode"
    assert client.patch("/settings", json={"free_mode": True}, headers=OWNER).json()["free_mode"] is True


def test_menu_and_brand(client):
    menu = client.get("/menu").json()
    assert len(menu) == 20
    thali = next(m for m in menu if m["name"] == "Chef's Thali")
    assert thali["price"] is None
    r = client.patch("/restaurants/me", json={"color_primary": "#112233"}, headers=OWNER)
    assert r.json()["color_primary"] == "#112233"
    assert client.patch("/restaurants/me", json={"color_primary": "red"}, headers=OWNER).status_code == 400


def test_photo_job_end_to_end_free_mode(client):
    up = client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"}).json()
    jid = client.post("/jobs", json={"mode": "photo", "photo_asset_id": up["asset_id"], "veo": True}).json()["job_id"]
    j = _wait(client, jid)
    # No Gemini key → analyze can't read the photo → asks for the dish
    assert j["status"] == "needs_dish"
    assert len(j["analyze"]["candidates"]) == 3
    menu = client.get("/menu").json()
    biryani = next(m for m in menu if m["name"] == "Chicken Biryani")
    assert client.post(f"/jobs/{jid}/confirm-dish", json={"menu_item_id": biryani["id"]}).json() == {"ok": True}
    j = _wait(client, jid, until=("done", "failed"), timeout=90)
    assert j["status"] == "done", j
    assert j["fallback_reason"] == "demo_mode"  # viewers never spend Veo money
    assert j["script"]["source"] == "template"
    assert "$14.99" in j["script"]["voiceover"]
    assert j["video"]["url"].endswith(".mp4")
    vids = client.get("/videos").json()
    assert vids[0]["dish"] == "Chicken Biryani" and vids[0]["mode"] == "free"
    # publishing is owner-only
    assert client.post(f"/videos/{vids[0]['id']}/publish", json={"title": "t"}).status_code == 403
    r = client.post(f"/videos/{vids[0]['id']}/publish", json={"title": "t"}, headers=OWNER)
    assert r.json()["error"]["code"] == "youtube_not_connected"


def test_not_on_menu_omits_price(client):
    up = client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"}).json()
    jid = client.post("/jobs", json={"mode": "photo", "photo_asset_id": up["asset_id"]}).json()["job_id"]
    _wait(client, jid)
    client.post(f"/jobs/{jid}/confirm-dish", json={"menu_item_id": None})
    j = _wait(client, jid, until=("done", "failed"), timeout=90)
    assert j["status"] == "done"
    assert "$" not in j["script"]["voiceover"]


def test_sales_import_and_insight_job(client):
    from pathlib import Path

    csv_text = (Path(__file__).resolve().parents[2] / "seed" / "kumars_sales_8w.csv").read_bytes()
    assert client.post("/sales/import", files={"file": ("s.csv", csv_text, "text/csv")}).status_code == 403
    r = client.post("/sales/import", files={"file": ("s.csv", csv_text, "text/csv")}, headers=OWNER).json()
    assert r["rows"] > 1000 and r["unmatched_items"] == ["Gift Card"]
    cards = client.get("/insights").json()["cards"]
    by = {c["angle"]: c for c in cards}
    assert by["rising"]["menu_item"]["name"] == "Chicken Biryani"
    assert by["rising"]["metric"]["wow_pct"] == 32
    assert by["top_seller"]["menu_item"]["name"] == "Butter Chicken"
    # no photos in this test DB → insight job asks for one
    r = client.post("/jobs", json={"mode": "insight", "insight_id": by["rising"]["id"]})
    assert r.status_code == 400 and r.json()["error"]["code"] == "photo_required"


def test_bad_sales_csv(client):
    r = client.post("/sales/import", files={"file": ("s.csv", b"a,b\n1,2\n", "text/csv")}, headers=OWNER)
    assert r.status_code == 400 and "Missing column" in r.json()["error"]["message"]


def test_usage_and_settings_validation(client):
    u = client.get("/usage").json()
    assert u["veo"]["allowed"] is False and u["veo"]["reason"] == "demo_mode"
    u = client.get("/usage", headers=OWNER).json()
    assert u["veo"]["allowed"] is True
    assert client.patch("/settings", json={"daily_veo_clip_limit": 99}, headers=OWNER).status_code == 422


def _menu_job(client, name="Chicken Biryani", veo=False, headers=None):
    menu = client.get("/menu").json()
    item = next(m for m in menu if m["name"] == name)
    up = client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"}).json()
    r = client.post("/jobs", json={"mode": "menu", "menu_item_id": item["id"], "photo_asset_id": up["asset_id"], "veo": veo},
                    headers=headers or {})
    return r.json()["job_id"]


def test_owner_veo_failure_falls_back_and_releases_budget(client, monkeypatch):
    from app.services import veo

    async def boom(*a, **k):
        raise veo.VeoError("timeout", "simulated")

    monkeypatch.setattr(veo, "generate_clip", boom)
    jid = _menu_job(client, veo=True, headers=OWNER)
    j = _wait(client, jid, until=("done", "failed"), timeout=90)
    assert j["status"] == "done"
    assert j["fallback_reason"] == "veo_timeout" and j["veo_used"] is False and j["cost_cents"] == 0
    u = client.get("/usage", headers=OWNER).json()
    assert u["today"]["clips"] == 0  # reservation released


def test_owner_veo_daily_limit_falls_back(client, monkeypatch):
    from app.services import veo

    called = []

    async def never(*a, **k):
        called.append(1)

    monkeypatch.setattr(veo, "generate_clip", never)
    client.patch("/settings", json={"daily_veo_clip_limit": 0}, headers=OWNER)
    jid = _menu_job(client, veo=True, headers=OWNER)
    j = _wait(client, jid, until=("done", "failed"), timeout=90)
    assert j["fallback_reason"] == "daily_limit" and not called


def test_edit_rerender_enforces_grounding(client):
    jid = _menu_job(client)
    j = _wait(client, jid, until=("done", "failed"), timeout=90)
    assert j["status"] == "done"
    bad = client.post(f"/jobs/{jid}/edit", json={"beats": [{"caption": "Chicken Biryani"}, {"caption": "Now $9.99!"}]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "not_grounded"
    ok = client.post(f"/jobs/{jid}/edit", json={"beats": [{"caption": "Chicken Biryani"}, {"caption": "Saffron and fried onions"}, {"caption": "Only $14.99"}]})
    assert ok.status_code == 202
    j2 = _wait(client, ok.json()["job_id"], until=("done", "failed"), timeout=90)
    assert j2["status"] == "done" and j2["script"]["source"] == "edited"
    assert [b["caption"] for b in j2["script"]["beats"]][1] == "Saffron and fried\nonions"


def test_map_unmatched_sales_item(client):
    csv_text = b"date,item_name,quantity\n2026-11-01,Chicken Biryani,5\n2026-11-02,House Biryani Special,7\n"
    r = client.post("/sales/import", files={"file": ("s.csv", csv_text, "text/csv")}, headers=OWNER).json()
    assert r["unmatched_items"] == ["House Biryani Special"]
    menu = client.get("/menu").json()
    bid = next(m["id"] for m in menu if m["name"] == "Chicken Biryani")
    out = client.post("/sales/map", json={"raw_item_name": "House Biryani Special", "menu_item_id": bid}, headers=OWNER).json()
    assert out["mapped"] == 1 and out["unmatched_items"] == []
    cards = client.get("/insights").json()["cards"]
    assert cards[0]["menu_item"]["name"] == "Chicken Biryani" and cards[0]["metric"]["qty_7d"] == 12
