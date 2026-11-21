"""Google sign-in: sessions, studio claim on first sign-in, same studio on every device."""
import time
from urllib.parse import unquote

from tests.test_api import OWNER, client  # noqa: F401  (fixture)


def _sign_in(client, monkeypatch, sub="g-123", name="Raj", nonce="browsernonce123456"):
    from app.services import youtube

    monkeypatch.setattr(youtube, "exchange_login", lambda code, state: {
        "sub": sub, "email": f"{sub}@example.com", "name": name, "picture": "", "nonce": nonce})
    state = youtube._sign({"p": "login", "t": int(time.time()), "n": nonce})
    r = client.get(f"/youtube/auth/callback?code=x&state={state}", follow_redirects=False)
    assert r.status_code == 302 and "signin=ok#session=" in r.headers["location"], r.headers["location"]
    frag = r.headers["location"].split("#session=", 1)[1]
    token, n = (unquote(x) for x in frag.split("&n=", 1))
    assert n == nonce
    return token


def test_sign_in_keeps_the_guest_studio_and_follows_you(client, monkeypatch):
    laptop, phone = {"X-Workspace": "c" * 32}, {"X-Workspace": "d" * 32}
    client.patch("/restaurants/me", json={"name": "Guest Bistro"}, headers={**laptop, **OWNER})
    token = _sign_in(client, monkeypatch)
    me = client.get("/auth/me", headers={**laptop, "X-Session": token}).json()["account"]
    assert me["name"] == "Raj"
    # first sign-in claims this browser's guest studio
    assert client.get("/restaurants/me", headers={**laptop, "X-Session": token}).json()["name"] == "Guest Bistro"
    # the same account on another device sees the same studio
    assert client.get("/restaurants/me", headers={**phone, "X-Session": token}).json()["name"] == "Guest Bistro"
    # signed out, the old browser id no longer opens the claimed studio (shared computers)
    assert client.get("/restaurants/me", headers=laptop).json()["name"] == "Kumar's"
    # writes work with a session and no browser id
    r = client.patch("/restaurants/me", json={"name": "Raj's Bistro"}, headers={"X-Workspace": "", "X-Session": token, **OWNER})
    assert r.status_code == 200 and r.json()["name"] == "Raj's Bistro"


def test_each_account_has_its_own_studio(client, monkeypatch):
    a = _sign_in(client, monkeypatch, sub="g-a", name="A")
    b = _sign_in(client, monkeypatch, sub="g-b", name="B")
    ws = {"X-Workspace": "e" * 32}
    client.patch("/restaurants/me", json={"name": "A's Place"}, headers={**ws, "X-Session": a, **OWNER})
    assert client.get("/restaurants/me", headers={**ws, "X-Session": b}).json()["name"] == "Kumar's"
    # signing in again finds the same account (no duplicate)
    assert _sign_in(client, monkeypatch, sub="g-a", name="A")
    assert client.get("/restaurants/me", headers={"X-Workspace": "f" * 32, "X-Session": a}).json()["name"] == "A's Place"


def test_bad_or_expired_sessions_are_ignored(client, monkeypatch):
    import json

    from app.util import encrypt

    for bad in ["garbage", encrypt(json.dumps({"a": 1, "t": time.time() - 100 * 86400}))]:
        assert client.get("/auth/me", headers={"X-Session": bad}).json()["account"] is None
    r = client.patch("/restaurants/me", json={"name": "x"}, headers={"X-Workspace": "", "X-Session": "garbage"})
    assert r.status_code == 400  # no studio, no valid session


def test_google_url_needs_a_nonce_and_config(client):
    assert client.get("/auth/google/url").status_code == 422
    assert client.get("/auth/google/url?nonce=abcdef0123456789abcd").status_code == 400  # no Google client in tests


def test_youtube_saved_to_the_account_follows_you(client, monkeypatch):
    from app.services import youtube
    from app.viewer import encode_connection

    revoked = []
    monkeypatch.setattr(youtube, "revoke", lambda rt: revoked.append(rt) or True)
    blob = encode_connection("rt-owner", "UC9", "Owner Eats")
    laptop, phone = {"X-Workspace": "1a" * 16}, {"X-Workspace": "2b" * 16}
    # guests can't save to an account
    assert client.post("/youtube/claim", json={"connection": blob}, headers=laptop).status_code == 401
    token = _sign_in(client, monkeypatch, sub="g-yt", name="Owner")
    r = client.post("/youtube/claim", json={"connection": blob}, headers={**laptop, "X-Session": token})
    assert r.status_code == 200 and r.json()["channel_title"] == "Owner Eats"
    # the phone has no browser copy, but the account has it
    me = client.get("/restaurants/me", headers={**phone, "X-Session": token}).json()
    assert me["youtube_connected"] and me["youtube_channel_title"] == "Owner Eats" and me["youtube_saved_to"] == "account"
    # garbage is refused
    assert client.post("/youtube/claim", json={"connection": "x" * 40}, headers={**laptop, "X-Session": token}).status_code == 400
    # disconnect revokes at Google and forgets it everywhere
    assert client.post("/youtube/disconnect", headers={**phone, "X-Session": token}).json()["ok"]
    assert revoked == ["rt-owner"]
    assert client.get("/restaurants/me", headers={**laptop, "X-Session": token}).json()["youtube_connected"] is False


def test_account_connection_does_not_expire_like_browser_ones(client, monkeypatch):
    import json as _json

    from cryptography.fernet import Fernet
    from sqlmodel import Session, select

    from app.config import get_settings
    from app.db import get_engine
    from app.models import Account

    token = _sign_in(client, monkeypatch, sub="g-old", name="Old")
    old = Fernet(get_settings().app_secret.encode()).encrypt_at_time(
        _json.dumps({"rt": "rt", "cid": "UC1", "ct": "Chan"}).encode(), int(time.time()) - 400 * 86400).decode()
    with Session(get_engine()) as s:
        acct = s.exec(select(Account).where(Account.google_sub == "g-old")).one()
        acct.youtube_conn = old
        s.add(acct)
        s.commit()
    me = client.get("/restaurants/me", headers={"X-Workspace": "3c" * 16, "X-Session": token}).json()
    assert me["youtube_connected"] is True  # saved server-side: revoked on disconnect, not by age
    # a guest browser copy that old is rejected
    assert client.get("/restaurants/me", headers={"X-Workspace": "3c" * 16, "X-YouTube-Auth": old}).json()["youtube_connected"] is False


def test_guest_disconnect_revokes_the_browser_connection(client, monkeypatch):
    from app.services import youtube
    from app.viewer import encode_connection

    revoked = []
    monkeypatch.setattr(youtube, "revoke", lambda rt: revoked.append(rt) or True)
    client.post("/youtube/disconnect", headers={"X-YouTube-Auth": encode_connection("rt-guest", "UC2", "G")})
    assert revoked == ["rt-guest"]
