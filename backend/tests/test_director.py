"""Director mode: storyboard chat stays grounded; approved plans render without a new script."""
import pytest

from tests.test_api import OWNER, WS, _jpeg, _wait, client  # noqa: F401  (fixture)


def _biryani(client):
    menu = client.get("/menu").json()
    item = next(m for m in menu if m["name"] == "Chicken Biryani")
    up = client.post("/uploads", files={"file": ("d.jpg", _jpeg(), "image/jpeg")}, data={"kind": "photo"}).json()
    assert client.post(f"/menu/{item['id']}/photo", json={"asset_id": up["asset_id"]}, headers=OWNER).status_code == 200
    return item


GOOD = {
    "hook": "Saffron steam incoming", "beats": [{"caption": "Chicken Biryani", "seconds": 3}, {"caption": "Only $14.99", "seconds": 2.7}],
    "voiceover": "Fragrant Chicken Biryani, layered and slow-cooked, just $14.99.", "veo_prompt": "Slow push-in, steam rising.",
    "shot": "Slow push-in as steam rises off the rice", "title": "Chicken Biryani at Kumar's", "description": "Fragrant and layered.",
    "hashtags": ["#biryani"], "facts_used": [{"field": "name", "value": "Chicken Biryani"}],
    "reply": "Here's a steamy plan.", "suggestions": ["More energy", "Cozy vibe", "Mention the price"],
}


def _fake(monkeypatch, *answers):
    from app.services import gemini

    queue = list(answers)
    calls = []

    async def fake_generate_json(prompt, schema, **kw):
        calls.append(prompt)
        a = queue.pop(0) if queue else answers[-1]
        if isinstance(a, Exception):
            raise a
        return a

    monkeypatch.setattr(gemini, "generate_json", fake_generate_json)
    return calls


def test_first_plan_and_a_grounded_edit(client, monkeypatch):
    item = _biryani(client)
    _fake(monkeypatch, GOOD)
    r = client.post("/director/plan", json={"menu_item_id": item["id"]}).json()
    assert r["source"] == "gemini" and r["storyboard"]["shot"].startswith("Slow push-in")
    assert r["reply"] and len(r["suggestions"]) == 3


def test_request_for_a_fake_discount_is_refused(client, monkeypatch):
    from app.services import gemini

    item = _biryani(client)
    bad = {**GOOD, "beats": [{"caption": "Chicken Biryani", "seconds": 3}, {"caption": "50% off today!", "seconds": 2.7}],
           "voiceover": "Chicken Biryani, now 50% off at $7.49!"}
    calls = _fake(monkeypatch, bad, bad)  # draft and repair both break the rules
    r = client.post("/director/plan", json={"menu_item_id": item["id"], "message": "say it's 50% off",
                                            "storyboard": GOOD, "history": [{"role": "user", "text": "hi"}]}).json()
    assert len(calls) == 2  # one repair attempt
    assert r["source"] == "unchanged" and "50%" not in str(r["storyboard"]) and "couldn't" in r["reply"].lower()
    _fake(monkeypatch, gemini.GeminiError("timeout"))
    r = client.post("/director/plan", json={"menu_item_id": item["id"]}).json()
    assert r["source"] == "template" and "Chicken Biryani" in str(r["storyboard"])


def test_director_job_uses_the_approved_plan(client):
    item = _biryani(client)
    r = client.post("/jobs", json={"mode": "menu", "menu_item_id": item["id"], "storyboard": GOOD})
    assert r.status_code == 202
    j = _wait(client, r.json()["job_id"], until=("done", "failed"), timeout=90)
    assert j["status"] == "done" and j["script"]["source"] == "director"
    assert j["script"]["hook"] == "Saffron steam incoming"
    assert next(s for s in j["stages"] if s["name"] == "script")["note"] == "Your Director mode plan"
    # retry keeps the plan
    j2 = _wait(client, client.post(f"/jobs/{j['id']}/retry").json()["job_id"], until=("done", "failed"), timeout=90)
    assert j2["script"]["hook"] == "Saffron steam incoming"


def test_tampered_storyboard_is_rejected(client):
    item = _biryani(client)
    wrong_price = {**GOOD, "beats": [{"caption": "Chicken Biryani", "seconds": 3}, {"caption": "Only $4.99", "seconds": 2.7}]}
    r = client.post("/jobs", json={"mode": "menu", "menu_item_id": item["id"], "storyboard": wrong_price})
    assert r.status_code == 422 and r.json()["error"]["code"] == "not_grounded"


def test_director_is_per_studio_and_preview_needs_ai(client):
    item = _biryani(client)
    other = {"X-Workspace": "8" * 32}
    assert client.post("/director/plan", json={"menu_item_id": item["id"]}, headers=other).status_code == 404
    r = client.post("/director/preview", json={"menu_item_id": item["id"], "storyboard": GOOD})
    assert r.status_code == 503 and r.json()["error"]["code"] == "ai_unavailable"
