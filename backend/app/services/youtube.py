"""YouTube OAuth (web flow) + resumable upload."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Callable, Optional

from ..config import get_settings

log = logging.getLogger("app.youtube")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
# Google sign-in (login) asks only for basic profile: no sensitive scopes, so no "unverified app" screen.
LOGIN_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"
# Added to every description we post, so "On YouTube" lists only videos made with this app.
APP_MARKER = "Made with What's Cooking? #WhatsCookingApp"


class YouTubeError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def _client_config() -> dict:
    s = get_settings()
    return {
        "web": {
            "client_id": s.google_oauth_client_id,
            "client_secret": s.google_oauth_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": TOKEN_URI,
            "redirect_uris": [s.oauth_redirect_uri],
        }
    }


def _state_key() -> bytes:
    """OAuth state is signed with APP_SECRET; never with a guessable fallback."""
    secret = get_settings().app_secret
    if not secret:
        raise YouTubeError("not_configured", "APP_SECRET is not set on the server.")
    return secret.encode()


def _sign(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    key = _state_key()
    sig = hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{raw}.{sig}"


def _verify(state: str) -> dict:
    try:
        raw, sig = state.rsplit(".", 1)
    except ValueError as e:
        raise YouTubeError("bad_state", "Invalid OAuth state") from e
    key = _state_key()
    want = hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, want):
        raise YouTubeError("bad_state", "Invalid OAuth state")
    payload = json.loads(base64.urlsafe_b64decode(raw.encode()))
    if time.time() - payload.get("t", 0) > 900:
        raise YouTubeError("bad_state", "OAuth state expired, try again")
    return payload


def state_purpose(state: str) -> str:
    """'login' for Google sign-in, 'youtube' for channel connections (both share one redirect URI)."""
    return _verify(state).get("p", "youtube")


def _flow(state: Optional[str] = None, scopes: Optional[list[str]] = None):
    from google_auth_oauthlib.flow import Flow

    s = get_settings()
    flow = Flow.from_client_config(_client_config(), scopes=scopes or SCOPES, state=state, autogenerate_code_verifier=False)
    flow.redirect_uri = s.oauth_redirect_uri
    return flow


def auth_url(restaurant_id: int, nonce: str) -> str:
    """nonce: random value the visitor's browser made and kept. It rides in the signed state and comes back with
    the connection, so the browser only accepts a connection it started (stops someone planting their channel)."""
    if not get_settings().youtube_enabled:
        raise YouTubeError("youtube_not_configured", "YouTube OAuth client is not configured on the server.")
    state = _sign({"r": restaurant_id, "t": int(time.time()), "n": nonce})
    url, _ = _flow(state).authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    return url


def login_url(nonce: str) -> str:
    if not get_settings().youtube_enabled:
        raise YouTubeError("google_not_configured", "Google sign-in is not configured on the server.")
    state = _sign({"p": "login", "t": int(time.time()), "n": nonce})
    url, _ = _flow(state, LOGIN_SCOPES).authorization_url(access_type="online", prompt="select_account")
    return url


def exchange_login(code: str, state: str) -> dict:
    """Finish Google sign-in: returns {sub, email, name, picture, nonce} from a verified ID token."""
    import os

    from google.auth.transport import requests as grequests
    from google.oauth2 import id_token

    payload = _verify(state)
    if payload.get("p") != "login":
        raise YouTubeError("bad_state", "Invalid sign-in state")
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")  # Google may echo scopes in another order
    flow = _flow(state, LOGIN_SCOPES)
    flow.fetch_token(code=code)
    raw = getattr(flow.credentials, "id_token", None)
    if not raw:
        raise YouTubeError("no_id_token", "Google didn't return an identity. Try signing in again.")
    claims = id_token.verify_oauth2_token(raw, grequests.Request(), get_settings().google_oauth_client_id)
    if not claims.get("sub"):
        raise YouTubeError("no_id_token", "Google didn't return an identity. Try signing in again.")
    email = claims.get("email", "") if claims.get("email_verified") else ""  # never trust an unverified address
    return {"sub": claims["sub"], "email": email, "name": claims.get("name", ""),
            "picture": claims.get("picture", ""), "nonce": payload.get("n") or ""}


def exchange_code(code: str, state: str) -> dict:
    payload = _verify(state)
    flow = _flow(state)
    flow.fetch_token(code=code)
    creds = flow.credentials
    if not creds.refresh_token:
        raise YouTubeError("no_refresh_token", "Google did not return a refresh token. Remove the app's access in your Google account and connect again.")
    channel_id, channel_title = None, None
    try:
        yt = _service(creds)
        resp = yt.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items") or []
        if items:
            channel_id = items[0]["id"]
            channel_title = items[0]["snippet"]["title"]
    except Exception as e:  # noqa: BLE001
        log.warning("channels.list failed: %s", e)
    return {
        "restaurant_id": payload["r"],
        "nonce": payload.get("n") or "",
        "refresh_token": creds.refresh_token,
        "channel_id": channel_id,
        "channel_title": channel_title,
    }


def _service(creds):
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def credentials_from_refresh(refresh_token: str):
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    s = get_settings()
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=s.google_oauth_client_id,
        client_secret=s.google_oauth_client_secret,
        scopes=SCOPES,
    )
    try:
        creds.refresh(Request())
    except RefreshError as e:
        raise YouTubeError("youtube_reconnect_required", "YouTube access expired. Reconnect YouTube in Settings.") from e
    return creds


def upload(
    refresh_token: str,
    path: str,
    *,
    title: str,
    description: str,
    tags: list[str],
    privacy: str,
    on_progress: Optional[Callable[[int], None]] = None,
    service=None,
) -> dict:
    """Blocking resumable upload. Returns {id, url, privacy}. Raises YouTubeError."""
    from googleapiclient.errors import HttpError, ResumableUploadError
    from googleapiclient.http import MediaFileUpload

    if service is None:
        service = _service(credentials_from_refresh(refresh_token))
    clean_tags = [t.lstrip("#") for t in tags if t.strip("#")]
    hashtags = " ".join("#" + t for t in clean_tags)
    if "#shorts" not in hashtags.lower():
        hashtags = (hashtags + " #Shorts").strip()
    hashtags += f"\n\n{APP_MARKER}"
    body = {
        "snippet": {
            "title": title[:100] or "New dish",
            "description": (description + "\n\n" + hashtags).strip()[:4900],
            "tags": clean_tags[:15],
            "categoryId": "26",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(path, mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = service.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    retries = 0
    while resp is None:
        try:
            status, resp = req.next_chunk()
            if status and on_progress:
                on_progress(int(status.progress() * 100))
        except HttpError as e:
            reason = ""
            try:
                reason = json.loads(e.content.decode())["error"]["errors"][0]["reason"]
            except Exception:  # noqa: BLE001
                pass
            if reason in ("quotaExceeded", "uploadLimitExceeded"):
                raise YouTubeError("quota_exceeded", "Daily YouTube upload limit reached, try tomorrow.") from e
            if e.resp.status in (500, 502, 503, 504) and retries < 3:
                retries += 1
                time.sleep(2 ** retries)
                continue
            if e.resp.status in (401, 403):
                raise YouTubeError("youtube_forbidden", f"YouTube refused the upload ({reason or e.resp.status}).") from e
            raise YouTubeError("upload_failed", f"YouTube upload failed ({reason or e.resp.status}).", True) from e
        except (ResumableUploadError, ConnectionError, TimeoutError, OSError) as e:
            if retries < 3:
                retries += 1
                time.sleep(2 ** retries)
                continue
            raise YouTubeError("upload_failed", "Upload was interrupted. Retry.", True) from e
    vid = (resp or {}).get("id")
    if not vid:
        raise YouTubeError("upload_failed", "YouTube didn't return a video ID.", True)
    privacy_back = ((resp or {}).get("status") or {}).get("privacyStatus") or privacy
    if on_progress:
        on_progress(100)
    return {"id": vid, "url": f"https://youtube.com/shorts/{vid}", "privacy": privacy_back}


def list_uploads(refresh_token: str, *, max_results: int = 50, known_ids: set | None = None, service=None) -> dict:
    """Videos on the connected channel that were made with this app (newest first), straight from YouTube."""
    known_ids = known_ids or set()
    if service is None:
        service = _service(credentials_from_refresh(refresh_token))
    ch = service.channels().list(part="snippet,contentDetails", mine=True).execute()
    items = ch.get("items") or []
    if not items:
        return {"channel_title": None, "videos": []}
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    pl = service.playlistItems().list(part="snippet,status,contentDetails", playlistId=uploads, maxResults=max_results).execute()
    out = []
    for it in pl.get("items", []):
        vid = it["contentDetails"]["videoId"]
        sn = it.get("snippet", {})
        if "WhatsCookingApp" not in (sn.get("description") or "") and vid not in known_ids:
            continue  # the rest of the channel isn't ours to show
        thumbs = sn.get("thumbnails", {})
        thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")
        out.append({
            "id": vid,
            "title": sn.get("title"),
            "published_at": it["contentDetails"].get("videoPublishedAt") or sn.get("publishedAt"),
            "thumbnail": thumb,
            "url": f"https://youtube.com/shorts/{vid}",
            "privacy": (it.get("status") or {}).get("privacyStatus"),
        })
    return {"channel_title": items[0]["snippet"]["title"], "videos": out}
