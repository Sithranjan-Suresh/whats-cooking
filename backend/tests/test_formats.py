"""Formats: money shot / chef POV render a full-length loop with no narrator and no logo slate."""
import json
import subprocess

from tests.test_api import OWNER, _jpeg, _wait, client  # noqa: F401  (fixture)


def _job(client, fmt, veo=False):
    menu = client.get("/menu").json()
    item = next(m for m in menu if m["name"] == "Chicken Biryani")
    up = client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"}).json()
    r = client.post("/jobs", json={"mode": "menu", "menu_item_id": item["id"], "photo_asset_id": up["asset_id"],
                                   "veo": veo, "format": fmt}, headers=OWNER)
    assert r.status_code == 202, r.text
    return _wait(client, r.json()["job_id"], until=("done", "failed"), timeout=150)


def _streams(url: str, client) -> dict:
    from app.config import get_settings

    path = get_settings().media_dir / url.split("/media/", 1)[1]
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type:format=duration", "-of", "json",
                          str(path)], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    return {"types": sorted(s["codec_type"] for s in d["streams"]), "duration": float(d["format"]["duration"])}


def test_money_shot_free_mode_is_a_full_length_loop_without_narrator(client):
    j = _job(client, "money_shot")
    assert j["status"] == "done", j
    voice = next(s for s in j["stages"] if s["name"] == "voice")
    assert voice["status"] == "skipped" and "no narrator" in voice["note"].lower()
    assert j["script"]["voiceover"] == "" and "chicken biryani" in json.dumps(j["script"]["beats"]).lower()
    info = _streams(j["video"]["url"], client)
    assert info["types"] == ["audio", "video"] and abs(info["duration"] - 8.0) < 0.2  # all 8s are motion, no slate
    assert "loop" in next(s for s in j["stages"] if s["name"] == "assemble")["note"]


def test_chef_pov_with_ai_clip_uses_the_kitchen_sound(client, monkeypatch):
    from app.services import veo

    async def fake_clip(photo, mime, prompt, out_path, *, seconds=8):
        assert "first-person" in prompt.lower() or "pov" in prompt.lower()  # the format shaped the AI-motion prompt
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=720x1280:r=24:d=8",
                        "-f", "lavfi", "-i", "anoisesrc=d=8:a=0.2", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(out_path)], check=True)
        return out_path

    monkeypatch.setattr(veo, "generate_clip", fake_clip)
    j = _job(client, "chef_pov", veo=True)
    assert j["status"] == "done", j
    assert "kitchen sound" in next(s for s in j["stages"] if s["name"] == "assemble")["note"]
    assert j["script"]["hook"].startswith("pov")
    assert abs(_streams(j["video"]["url"], client)["duration"] - 8.0) < 0.2


def test_classic_is_unchanged(client):
    j = _job(client, "classic")
    assert j["status"] == "done" and next(s for s in j["stages"] if s["name"] == "voice")["status"] != "skipped"


def test_retry_keeps_the_format(client):
    j = _job(client, "money_shot")
    j2 = _wait(client, client.post(f"/jobs/{j['id']}/retry", headers=OWNER).json()["job_id"], until=("done", "failed"), timeout=150)
    assert next(s for s in j2["stages"] if s["name"] == "voice")["status"] == "skipped"


def _fake_clip_with(monkeypatch, audio_src):
    from app.services import veo

    async def fake_clip(photo, mime, prompt, out_path, *, seconds=8):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=720x1280:r=24:d=8",
                        "-f", "lavfi", "-i", audio_src, "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(out_path)], check=True)
        return out_path

    monkeypatch.setattr(veo, "generate_clip", fake_clip)


def _lufs(url):
    import asyncio

    from app.config import get_settings
    from app.services import render

    return asyncio.run(render.integrated_loudness(get_settings().media_dir / url.split("/media/", 1)[1]))


def test_quiet_kitchen_sound_is_brought_up_to_a_consistent_loudness(client, monkeypatch):
    _fake_clip_with(monkeypatch, "anoisesrc=d=8:a=0.004")  # very quiet, like the real money-shot clip (-40 LUFS)
    j = _job(client, "money_shot", veo=True)
    assert j["status"] == "done", j
    assert "kitchen sound" in next(s for s in j["stages"] if s["name"] == "assemble")["note"]
    assert -19 < _lufs(j["video"]["url"]) < -13


def test_silent_ai_clip_falls_back_to_music(client, monkeypatch):
    _fake_clip_with(monkeypatch, "anullsrc=r=44100:cl=stereo:d=8")
    j = _job(client, "money_shot", veo=True)
    assert j["status"] == "done", j
    note = next(s for s in j["stages"] if s["name"] == "assemble")["note"]
    assert "kitchen sound" not in note and ("music" in note or "silent" in note)  # test studio has no music asset


def test_new_studio_videos_get_the_demo_music(client):
    """Studios are copies of the demo; its music track is shared (free money shot = music)."""
    import shutil

    from sqlmodel import Session, select

    from app.config import get_settings
    from app.db import get_engine, template_restaurant
    from app.models import Asset

    with Session(get_engine()) as s:
        tpl = template_restaurant(s)
        dst = get_settings().media_dir / "assets" / "music_test.mp3"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=440:d=10", str(dst)], check=True)
        s.add(Asset(restaurant_id=tpl.id, kind="music", path=str(dst), mime="audio/mpeg"))
        s.commit()
    j = _job(client, "money_shot")  # the test client is a studio, not the template
    assert j["status"] == "done", j
    assert "music" in next(st for st in j["stages"] if st["name"] == "assemble")["note"]
