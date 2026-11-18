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
TOKEN_URI = "https://oauth2.googleapis.com/token"


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


def _sign(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    key = (get_settings().app_secret or "dev").encode()
    sig = hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{raw}.{sig}"


def _verify(state: str) -> dict:
    try:
        raw, sig = state.rsplit(".", 1)
    except ValueError as e:
        raise YouTubeError("bad_state", "Invalid OAuth state") from e
    key = (get_settings().app_secret or "dev").encode()
    want = hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, want):
        raise YouTubeError("bad_state", "Invalid OAuth state")
    payload = json.loads(base64.urlsafe_b64decode(raw.encode()))
    if time.time() - payload.get("t", 0) > 900:
        raise YouTubeError("bad_state", "OAuth state expired, try again")
    return payload


def _flow(state: Optional[str] = None):
    from google_auth_oauthlib.flow import Flow

    s = get_settings()
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state, autogenerate_code_verifier=False)
    flow.redirect_uri = s.oauth_redirect_uri
    return flow


def auth_url(restaurant_id: int) -> str:
    if not get_settings().youtube_enabled:
        raise YouTubeError("youtube_not_configured", "YouTube OAuth client is not configured on the server.")
    state = _sign({"r": restaurant_id, "t": int(time.time())})
    url, _ = _flow(state).authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    return url


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
