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
