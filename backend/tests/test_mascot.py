"""Mascot creator: options → choose → it appears on the ending (classic slate and loop formats)."""
import io
import subprocess

from PIL import Image, ImageDraw

from tests.test_api import OWNER, _jpeg, _wait, client  # noqa: F401  (fixture)
from tests.test_formats import _job


def _fake_png(color=(220, 30, 30)) -> bytes:
    im = Image.new("RGB", (512, 512), (255, 255, 255))
    ImageDraw.Draw(im).ellipse((106, 106, 406, 406), fill=color)
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _enable(monkeypatch, ok=True):
    from app.config import get_settings
    from app.services import mascot

    monkeypatch.setattr(get_settings(), "gemini_api_key", "test")

    async def check(desc):
        return (ok, "That's an existing character, so let's make an original one.")

    async def one(desc, style):
        return _fake_png()

    monkeypatch.setattr(mascot, "check_description", check)
    monkeypatch.setattr(mascot, "_generate_one", one)


def test_cut_out_makes_the_background_transparent():
    from app.services.mascot import cut_out

    im = Image.open(io.BytesIO(cut_out(_fake_png()))).convert("RGBA")
    assert im.getpixel((0, 0))[3] == 0  # trimmed to the character; corners outside the circle are clear
    assert im.getpixel((im.width // 2, im.height // 2))[3] == 255


def test_options_choose_and_remove(client, monkeypatch):
    _enable(monkeypatch)
    r = client.post("/mascot/options", json={"description": "a cheerful mango in a chef hat"})
    assert r.status_code == 200, r.text
    opts = r.json()["options"]
    assert len(opts) == 4 and all(o["url"].endswith(".png") for o in opts)
    me = client.post("/mascot/choose", json={"option_id": opts[1]["option_id"]}).json()
    assert me["mascot_url"] and me["mascot_url"].endswith(".png")
    assert client.get("/restaurants/me").json()["mascot_url"] == me["mascot_url"]
    # another studio can't pick this studio's options
    assert client.post("/mascot/choose", json={"option_id": opts[0]["option_id"]}, headers={"X-Workspace": "9" * 32}).status_code == 404
    assert client.post("/mascot/choose", json={"option_id": None}).json()["mascot_url"] is None


def test_famous_characters_are_refused(client, monkeypatch):
    _enable(monkeypatch, ok=False)
    r = client.post("/mascot/options", json={"description": "mickey mouse"})
    assert r.status_code == 422 and "original" in r.json()["error"]["message"]


def _pixel(url, t, xy):
    from app.config import get_settings

    path = get_settings().media_dir / url.split("/media/", 1)[1]
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1", "-f", "image2pipe",
                          "-vcodec", "png", "-"], capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(raw)).convert("RGB").getpixel(xy)


def test_mascot_appears_on_the_ending(client, monkeypatch):
    _enable(monkeypatch)
    opts = client.post("/mascot/options", json={"description": "a happy red tomato"}).json()["options"]
    client.post("/mascot/choose", json={"option_id": opts[0]["option_id"]})
    for fmt, t, xy in [("classic", 7.6, (28 + 125, 1280 - 36 - 125)), ("money_shot", 7.2, (360, 1280 - 230 - 150))]:
        j = _job(client, fmt)
        assert j["status"] == "done", j
        r, g, b = _pixel(j["video"]["url"], t, xy)
        assert r > 150 and g < 110 and b < 110, (fmt, (r, g, b))  # the red mascot is on screen


def test_mascot_inside_the_ai_video(client, monkeypatch):
    from PIL import Image as _Image

    from app.services import veo

    _enable(monkeypatch)
    seen = {}

    async def fake_clip(photo, mime, prompt, out_path, *, seconds=8):
        im = _Image.open(photo).convert("RGB")
        seen.update(size=im.size, prompt=prompt, px=im.getpixel((24 + 120, 1280 - 110 - 120)))
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-i", str(photo), "-f", "lavfi", "-i",
                        "anoisesrc=d=8:a=0.2", "-t", "8", "-r", "24", "-c:v", "libx264", "-preset", "ultrafast",
                        "-threads", "2", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out_path)], check=True)
        return out_path

    monkeypatch.setattr(veo, "generate_clip", fake_clip)
    # no mascot yet -> clear error
    menu = client.get("/menu").json()
    item = next(m for m in menu if m["name"] == "Chicken Biryani")
    up = client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"}).json()
    r = client.post("/jobs", json={"mode": "menu", "menu_item_id": item["id"], "photo_asset_id": up["asset_id"],
                                   "veo": True, "format": "money_shot", "mascot": True}, headers=OWNER)
    assert r.status_code == 400 and r.json()["error"]["code"] == "no_mascot"
    opts = client.post("/mascot/options", json={"description": "a happy red tomato"}).json()["options"]
    client.post("/mascot/choose", json={"option_id": opts[0]["option_id"]})
    r = client.post("/jobs", json={"mode": "menu", "menu_item_id": item["id"], "photo_asset_id": up["asset_id"],
                                   "veo": True, "format": "money_shot", "mascot": True}, headers=OWNER)
    j = _wait(client, r.json()["job_id"], until=("done", "failed"), timeout=150)
    assert j["status"] == "done" and j["veo_used"], j
    assert seen["size"] == (720, 1280)  # the AI animates a 9:16 first frame...
    rr, gg, bb = seen["px"]
    assert rr > 150 and gg < 110 and bb < 110  # ...with the (red) mascot standing in it, lower-left
    assert "Meanwhile" in seen["prompt"] and "same flat 2D cartoon" in seen["prompt"]
    # the loop ending doesn't add a second mascot (it's already in the scene): the centre of the last moment
    r2, g2, b2 = _pixel(j["video"]["url"], 7.2, (360, 1280 - 230 - 150))
    assert not (r2 > 150 and g2 < 110 and b2 < 110)


def test_captions_clear_the_mascot_in_the_shot():
    from app.services import render

    script = {"hook": "", "beats": [{"caption": "Rich & creamy", "seconds": 3.0}]}
    plain = render.build_ass(script, 8.0, color_primary="#111111", color_accent="#EEEEEE")
    raised = render.build_ass(script, 8.0, color_primary="#111111", color_accent="#EEEEEE", clear_mascot=True,
                              outro="Kumar's · Butter Chicken")

    def style(ass, name):
        return next(l for l in ass.splitlines() if l.startswith(f"Style: {name},")).split(",")

    assert int(style(plain, "Beat")[21]) == 300
    # beat captions sit above the mascot's head (mascot top = bottom margin + height)
    assert int(style(raised, "Beat")[21]) > render.MASCOT_IN_SHOT_BOTTOM + render.MASCOT_IN_SHOT_H
    outro = style(raised, "Outro")
    assert outro[18] == "3" and int(outro[19]) >= 360  # bottom-right, right of the mascot
