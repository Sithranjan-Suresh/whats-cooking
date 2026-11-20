"""API + pipeline integration tests (real ffmpeg; Gemini/TTS/Veo faked)."""
import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

OWNER = {"X-Owner-Token": "test-owner"}
ADMIN = {"X-Admin-Token": "test-admin"}
WS = "a" * 32  # this test browser's studio id


@pytest.fixture()
def client(restaurant, monkeypatch):
    from app.services import tts

    async def fake_tts(text, voice, out_path, tone="upbeat"):
        return None  # captions-only path (no network in tests)

    monkeypatch.setattr(tts, "synthesize", fake_tts)
    from app.main import create_app

    with TestClient(create_app(), headers={"X-Workspace": WS}) as c:
        yield c


def _jpeg(w=900, h=1200, color=(200, 120, 40)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (w, h), color).save(b, "JPEG")
    return b.getvalue()


def _wait(client, job_id, until=("done", "failed", "needs_dish"), timeout=60, headers=None):
    t = time.time()
    while time.time() - t < timeout:
        j = client.get(f"/jobs/{job_id}", headers=headers or {}).json()
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
    # budget settings need the admin key, even for the owner
    r = client.patch("/settings", json={"free_mode": True}, headers=OWNER)
    assert r.status_code == 403 and r.json()["error"]["code"] == "admin_required"
    assert client.patch("/settings", json={"free_mode": True}, headers={"X-Admin-Token": "wrong"}).status_code == 403
    assert client.patch("/settings", json={"free_mode": True}, headers=ADMIN).json()["free_mode"] is True


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
    assert u["ai_videos_left"] == 10 and u["ai_videos_total"] == 15  # 10/day limit, $10 cap / 64¢
    assert client.patch("/settings", json={"daily_veo_clip_limit": 99}, headers=ADMIN).status_code == 422
    # the $10 hard cap can't be raised through the API
    assert client.patch("/settings", json={"monthly_cap_cents": 10000}, headers=ADMIN).status_code == 422


def _menu_job(client, name="Chicken Biryani", veo=False, headers=None):
    menu = client.get("/menu", headers=headers or {}).json()
    item = next(m for m in menu if m["name"] == name)
    up = client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"},
                     headers=headers or {}).json()
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


def test_budget_cap_blocks_with_clear_error(client, monkeypatch):
    from app.services import veo

    called = []

    async def never(*a, **k):
        called.append(1)

    monkeypatch.setattr(veo, "generate_clip", never)
    client.patch("/settings", json={"monthly_cap_cents": 50}, headers=ADMIN)  # less than one 64¢ clip
    menu = client.get("/menu").json()
    item = next(m for m in menu if m["name"] == "Chicken Biryani")
    up = client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"}).json()
    r = client.post("/jobs", json={"mode": "menu", "menu_item_id": item["id"], "photo_asset_id": up["asset_id"], "veo": True}, headers=OWNER)
    assert r.status_code == 402
    body = r.json()["error"]
    assert body["code"] == "budget_cap_reached" and "$0.50" in body["message"] and "free photo motion" in body["message"]
    assert not called
    # free mode still works under the cap
    r = client.post("/jobs", json={"mode": "menu", "menu_item_id": item["id"], "photo_asset_id": up["asset_id"], "veo": False}, headers=OWNER)
    assert r.status_code == 202


def test_veo_success_8s_with_ambient_sound(client, monkeypatch, tmp_path):
    """Fake Veo returns an 8s 9:16 clip WITH audio; the Short is 8s, uses Veo, and keeps sound."""
    import subprocess

    from app.services import veo

    async def fake_clip(photo, mime, prompt, out_path, *, seconds=8):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=720x1280:r=24:d=8",
                        "-f", "lavfi", "-i", "anoisesrc=d=8:a=0.2", "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(out_path)], check=True)
        return out_path

    monkeypatch.setattr(veo, "generate_clip", fake_clip)
    jid = _menu_job(client, veo=True, headers=OWNER)
    j = _wait(client, jid, until=("done", "failed"), timeout=120)
    assert j["status"] == "done", j
    assert j["veo_used"] is True and j["cost_cents"] == 64 and j["fallback_reason"] is None
    v = client.get("/videos").json()[0]
    assert v["mode"] == "veo" and abs(v["duration_s"] - 8.0) < 0.2
    u = client.get("/usage", headers=OWNER).json()
    assert u["today"]["clips"] == 1 and u["month"]["est_cents"] == 64


def test_quick_take_dish_upload(client):
    up = client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"}).json()
    r = client.post("/dishes", json={"name": "Masala Dosa", "price": "11.50", "description": "Crispy rice crepe with potato masala", "photo_asset_id": up["asset_id"]}, headers=OWNER)
    assert r.status_code == 200, r.json()
    d = r.json()
    assert d["price"] == "$11.50" and d["photo_url"]
    assert client.post("/dishes", json={"name": "X", "price": "abc", "photo_asset_id": up["asset_id"]}, headers=OWNER).status_code == 422
    jid = client.post("/jobs", json={"mode": "menu", "menu_item_id": d["id"]}).json()["job_id"]
    j = _wait(client, jid, until=("done", "failed"), timeout=90)
    assert j["status"] == "done" and j["length_s"] == 8
    assert "Masala Dosa" in j["script"]["voiceover"] and "$11.50" in j["script"]["voiceover"]


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
    r = client.post("/sales/import?create_missing=false", files={"file": ("s.csv", csv_text, "text/csv")}, headers=OWNER).json()
    assert r["unmatched_items"] == ["House Biryani Special"]
    menu = client.get("/menu").json()
    bid = next(m["id"] for m in menu if m["name"] == "Chicken Biryani")
    out = client.post("/sales/map", json={"raw_item_name": "House Biryani Special", "menu_item_id": bid}, headers=OWNER).json()
    assert out["mapped"] == 1 and out["unmatched_items"] == []
    cards = client.get("/insights").json()["cards"]
    assert cards[0]["menu_item"]["name"] == "Chicken Biryani" and cards[0]["metric"]["qty_7d"] == 12


def test_any_restaurant_csv_creates_dishes_and_picks_one(client):
    """A CSV with dishes not on the menu: they're created with the typical price paid, junk lines skipped."""
    rows = ["date,item_name,quantity,revenue"]
    from datetime import date, timedelta

    end = date(2026, 11, 15)
    for d in range(21):
        day = (end - timedelta(days=20 - d)).isoformat()
        rows.append(f"{day},MASALA DOSA,{6 if d < 14 else 9},{(6 if d < 14 else 9) * 11.5:.2f}")
        rows.append(f"{day},Filter Coffee,{4},{4 * 3.25:.2f}")
        rows.append(f"{day},Gift Card,1,25.00")
        rows.append(f"{day},Delivery Fee,2,7.98")
    r = client.post("/sales/import", files={"file": ("s.csv", "\n".join(rows).encode(), "text/csv")}, headers=OWNER).json()
    assert sorted(r["dishes_created"]) == ["Filter Coffee", "Masala Dosa"]
    assert set(r["unmatched_items"]) == {"Gift Card", "Delivery Fee"}
    menu = {m["name"]: m for m in client.get("/menu").json()}
    assert menu["Masala Dosa"]["price"] == "$11.50" and menu["Filter Coffee"]["price"] == "$3.25"
    cards = client.get("/insights").json()["cards"]
    names = {c["angle"]: c["menu_item"]["name"] for c in cards}
    assert names["top_seller"] == "Masala Dosa"


def test_youtube_is_per_visitor(client, monkeypatch):
    """Each browser holds its own encrypted connection; the server stores none, so visitors never share a channel."""
    from urllib.parse import unquote

    from app.services import youtube

    monkeypatch.setattr(youtube, "exchange_code", lambda code, state: {
        "restaurant_id": 1, "nonce": "browser-nonce-123456", "refresh_token": "rt-raj", "channel_id": "UC1",
        "channel_title": "Raj Eats"})
    r = client.get("/youtube/auth/callback?code=x&state=y", follow_redirects=False)
    assert r.status_code == 302 and "youtube=connected#yt=" in r.headers["location"]
    frag = r.headers["location"].split("#yt=", 1)[1]
    raj, nonce = (unquote(x) for x in frag.split("&n=", 1))
    assert nonce == "browser-nonce-123456"  # echoed so the browser can check it started this connection
    assert "rt-raj" not in raj  # encrypted

    # Raj sees his channel; another visitor (no header) sees nothing connected; garbage is ignored.
    assert client.get("/restaurants/me", headers={"X-YouTube-Auth": raj}).json()["youtube_channel_title"] == "Raj Eats"
    assert client.get("/restaurants/me").json()["youtube_connected"] is False
    assert client.get("/restaurants/me", headers={"X-YouTube-Auth": "nope"}).json()["youtube_connected"] is False

    seen = {}

    def fake_list(token, max_results=50, known_ids=None, service=None):
        seen["token"] = token
        return {"channel_title": "Raj Eats", "videos": []}

    monkeypatch.setattr(youtube, "list_uploads", fake_list)
    assert client.get("/youtube/uploads", headers={"X-YouTube-Auth": raj}).status_code == 200 and seen["token"] == "rt-raj"
    assert client.get("/youtube/uploads").status_code == 409
    # posting without your own connection is refused
    vids = client.get("/videos").json()
    if vids:
        r = client.post(f"/videos/{vids[0]['id']}/publish", json={"title": "t"}, headers=OWNER)
        assert r.json()["error"]["code"] == "youtube_not_connected"



# ------------------------------------------------------------------ hardening (public app, no login)

def _limits(monkeypatch, **kw):
    from app.config import get_settings
    from app.routers import jobs

    for k, v in kw.items():
        monkeypatch.setattr(get_settings(), k, v)
    jobs._hourly.clear()
    jobs._ip_jobs.clear()


def _hold_queue(monkeypatch):
    """Keep new jobs queued (no worker picks them up) so 'in progress' limits can be observed."""
    from app.pipeline import job_queue

    monkeypatch.setattr(job_queue, "enqueue", lambda job_id: None)


def test_one_video_in_progress_per_visitor(client, monkeypatch):
    _limits(monkeypatch, active_jobs_per_ip=1, jobs_per_hour_per_ip=100, max_queued_jobs=100)
    _hold_queue(monkeypatch)
    _menu_job(client)
    up = client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"}).json()
    item = next(m for m in client.get("/menu").json() if m["name"] == "Chicken Biryani")
    r = client.post("/jobs", json={"mode": "menu", "menu_item_id": item["id"], "photo_asset_id": up["asset_id"]})
    assert r.status_code == 429 and "in progress" in r.json()["error"]["message"]
    # a real owner token is exempt
    r = client.post("/jobs", json={"mode": "menu", "menu_item_id": item["id"], "photo_asset_id": up["asset_id"]}, headers=OWNER)
    assert r.status_code == 202


def test_hourly_limit_and_busy_studio(client, monkeypatch):
    _limits(monkeypatch, active_jobs_per_ip=100, jobs_per_hour_per_ip=2, max_queued_jobs=100)
    _hold_queue(monkeypatch)
    _menu_job(client)
    _menu_job(client)
    up = client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"}).json()
    item = next(m for m in client.get("/menu").json() if m["name"] == "Chicken Biryani")
    body = {"mode": "menu", "menu_item_id": item["id"], "photo_asset_id": up["asset_id"]}
    r = client.post("/jobs", json=body)
    assert r.status_code == 429 and "in the last hour" in r.json()["error"]["message"]
    # another visitor isn't affected by the first one's hourly count, but the whole queue has a ceiling
    _limits(monkeypatch, jobs_per_hour_per_ip=100, max_queued_jobs=2)
    r = client.post("/jobs", json=body, headers={"CF-Connecting-IP": "203.0.113.9"})
    assert r.status_code == 429 and "studio is busy" in r.json()["error"]["message"]


def test_settings_locked_without_admin_token(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "admin_token", "")
    r = client.patch("/settings", json={"monthly_cap_cents": 100}, headers={"X-Admin-Token": ""})
    assert r.status_code == 403 and r.json()["error"]["code"] == "settings_locked"


def test_youtube_connect_carries_browser_nonce(client, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from app.config import get_settings
    from app.services import youtube

    assert client.get("/youtube/auth/url").status_code == 422  # a nonce is required
    s = get_settings()
    monkeypatch.setattr(s, "google_oauth_client_id", "cid")
    monkeypatch.setattr(s, "google_oauth_client_secret", "secret")
    url = client.get("/youtube/auth/url?nonce=abcdef0123456789abcd").json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    assert youtube._verify(state)["n"] == "abcdef0123456789abcd"
    # tampering with the nonce breaks the signature
    raw, sig = state.rsplit(".", 1)
    import base64
    import json as _json

    forged = base64.urlsafe_b64encode(_json.dumps({**youtube._verify(state), "n": "attacker"}).encode()).decode()
    with pytest.raises(youtube.YouTubeError):
        youtube._verify(f"{forged}.{sig}")


def test_media_restored_from_db_after_disk_wipe(client):
    from pathlib import Path

    from app.db import restore_media

    up = client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"}).json()
    rel = up["url"].split("/media/", 1)[1]
    from app.config import get_settings

    path = Path(get_settings().media_dir) / rel
    original = path.read_bytes()
    path.unlink()
    assert restore_media() >= 1
    assert path.read_bytes() == original


def test_videos_survive_a_disk_wipe(client):
    """Rendered videos are backed up in the DB: after a restart wipes the disk they're restored on first request."""
    from pathlib import Path

    from sqlmodel import Session

    from app.config import get_settings
    from app.db import get_engine
    from app.models import MediaBlob

    jid = _menu_job(client)
    j = _wait(client, jid, until=("done", "failed"), timeout=90)
    assert j["status"] == "done"
    rel = j["video"]["url"].split("/media/", 1)[1]
    path = Path(get_settings().media_dir, rel)
    original = path.read_bytes()
    path.unlink()  # what a free-host restart does
    assert any(v["job_id"] == jid for v in client.get("/videos").json())  # still listed
    r = client.get("/media/" + rel)
    assert r.status_code == 200 and r.content == original and path.exists()  # restored on first request
    # truly gone (not on disk, not in the DB): hidden
    path.unlink()
    with Session(get_engine()) as s:
        s.delete(s.get(MediaBlob, rel))
        s.commit()
    assert not any(v["job_id"] == jid for v in client.get("/videos").json())


def test_media_store_cap_clears_clips_first(client, monkeypatch):
    from app.config import get_settings
    from app.services import mediastore

    media = get_settings().media_dir
    for name, kind_dir, size in [("old_video.mp4", "videos", 400_000), ("a_clip.mp4", "clips", 400_000), ("new_video.mp4", "videos", 400_000)]:
        p = media / kind_dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * size)
        mediastore.keep(p)
    monkeypatch.setattr(get_settings(), "media_db_cap_mb", 1)  # 1 MB: one of the three must go
    mediastore.evict()
    left = mediastore.stored_keys(["videos/old_video.mp4", "clips/a_clip.mp4", "videos/new_video.mp4"])
    assert left == {"videos/old_video.mp4", "videos/new_video.mp4"}  # the clip went first


# ------------------------------------------------------------------ one studio per browser

def test_each_browser_gets_its_own_studio(client):
    a, b = {"X-Workspace": "1" * 32}, {"X-Workspace": "2" * 32}
    assert client.get("/restaurants/me", headers=a).json()["name"] == "Kumar's"  # starts as the demo
    client.patch("/restaurants/me", json={"name": "Hello"}, headers={**a, **OWNER})
    assert client.get("/restaurants/me", headers=a).json()["name"] == "Hello"
    assert client.get("/restaurants/me", headers=b).json()["name"] == "Kumar's"  # another device: untouched
    tpl = client.get("/restaurants/me", headers={"X-Workspace": ""}).json()
    assert tpl["name"] == "Kumar's"  # the template every new studio copies is untouched
    # the new studio got the demo menu
    assert {m["name"] for m in client.get("/menu", headers=b).json()} >= {"Chicken Biryani"}
    # videos and jobs are per studio
    jid = _menu_job(client, headers={**a, **OWNER})
    assert any(j["id"] == jid for j in client.get("/jobs", headers=a).json())
    assert not any(j["id"] == jid for j in client.get("/jobs", headers=b).json())


def test_writes_without_a_studio_cannot_touch_the_template(client):
    no_ws = {"X-Workspace": ""}
    r = client.patch("/restaurants/me", json={"name": "Hijack"}, headers=no_ws)
    assert r.status_code == 400 and r.json()["error"]["code"] == "workspace_required"
    r = client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"}, headers=no_ws)
    assert r.status_code == 400
    # an owner token may still manage the template
    assert client.patch("/restaurants/me", json={"name": "Kumar's Plano"}, headers={**no_ws, **OWNER}).status_code == 200


def test_new_studio_can_use_the_demo_photos(client):
    no_ws_owner = {"X-Workspace": "", **OWNER}
    up = client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"}, headers=no_ws_owner).json()
    tpl_item = next(m for m in client.get("/menu", headers={"X-Workspace": ""}).json() if m["name"] == "Chicken Biryani")
    client.post(f"/menu/{tpl_item['id']}/photo", json={"asset_id": up["asset_id"]}, headers=no_ws_owner)
    fresh = {"X-Workspace": "3" * 32}
    item = next(m for m in client.get("/menu", headers=fresh).json() if m["name"] == "Chicken Biryani")
    assert item["photo_url"] and item["id"] != tpl_item["id"]
    r = client.post("/jobs", json={"mode": "menu", "menu_item_id": item["id"]}, headers=fresh)
    assert r.status_code == 202


def test_all_studios_share_one_ai_budget(client, monkeypatch):
    from app.services import budget

    _hold_queue(monkeypatch)
    a, b = {"X-Workspace": "4" * 32}, {"X-Workspace": "5" * 32}
    before = client.get("/usage", headers={**b, **OWNER}).json()["ai_videos_left"]
    jid = _menu_job(client, headers={**a, **OWNER})
    rid_a = client.get("/restaurants/me", headers=a).json()["id"]
    assert budget.reserve_veo(rid_a, jid, 8).allowed
    assert client.get("/usage", headers={**b, **OWNER}).json()["ai_videos_left"] == before - 1


def test_studios_cannot_reach_each_others_jobs_and_videos(client):
    import re

    a, b = {"X-Workspace": "6" * 32}, {"X-Workspace": "7" * 32}
    jid = _menu_job(client, headers={**a, **OWNER})
    j = _wait(client, jid, until=("done", "failed"), timeout=90, headers=a)
    assert j["status"] == "done"
    vid = j["video"]["id"]
    assert re.search(r"job_\d+_[0-9a-f]{16}\.mp4$", j["video"]["url"])  # file names can't be guessed
    # the owner studio sees it (the test client's default headers are studio "a…a", so pass the studio explicitly)
    assert client.get(f"/jobs/{jid}", headers=a).status_code == 200
    for method, path, body in [("get", f"/jobs/{jid}", None), ("get", f"/videos/{vid}", None),
                               ("post", f"/jobs/{jid}/retry", {}), ("post", f"/jobs/{jid}/confirm-dish", {"menu_item_id": None}),
                               ("post", f"/jobs/{jid}/edit", {"beats": [{"caption": "x"}]}),
                               ("post", f"/videos/{vid}/publish", {"title": "t"})]:
        r = getattr(client, method)(path, headers={**b, **OWNER}, **({"json": body} if body is not None else {}))
        assert r.status_code == 404, (path, r.status_code)


def test_upload_rate_limit(client, monkeypatch):
    from app.config import get_settings
    from app.routers import core

    monkeypatch.setattr(get_settings(), "uploads_per_hour_per_ip", 2)
    core._upload_times.clear()
    up = lambda: client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"})
    assert up().status_code == 200 and up().status_code == 200
    r = up()
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
