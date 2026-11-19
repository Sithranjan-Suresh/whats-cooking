"""YouTube upload failure paths with a fake API client."""
import json

import pytest

from app.services import youtube


class FakeResp(dict):
    def __init__(self, status):
        super().__init__()
        self.status = status
        self.reason = "x"


def http_error(status, reason):
    from googleapiclient.errors import HttpError

    body = json.dumps({"error": {"errors": [{"reason": reason}], "message": reason}}).encode()
    return HttpError(FakeResp(status), body)


class Status:
    def __init__(self, p):
        self.p = p

    def progress(self):
        return self.p


class FakeRequest:
    def __init__(self, script):
        self.script = list(script)

    def next_chunk(self):
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class FakeService:
    def __init__(self, script):
        self.req = FakeRequest(script)
        self.body = None

    def videos(self):
        return self

    def insert(self, part, body, media_body):
        self.body = body
        return self.req


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch, tmp_path):
    monkeypatch.setattr(youtube.time, "sleep", lambda s: None)
    (tmp_path / "v.mp4").write_bytes(b"\x00" * 100)
    return tmp_path


def _up(svc, tmp_path, **kw):
    return youtube.upload("rt", str(tmp_path / "v.mp4"), title="T", description="D", tags=["#biryani"],
                          privacy="public", service=svc, **kw)


def test_success_reads_back_privacy(no_sleep):
    prog = []
    svc = FakeService([(Status(0.5), None), (None, {"id": "abc123", "status": {"privacyStatus": "private"}})])
    out = _up(svc, no_sleep, on_progress=prog.append)
    assert out == {"id": "abc123", "url": "https://youtube.com/shorts/abc123", "privacy": "private"}
    assert "#Shorts" in svc.body["snippet"]["description"]
    assert prog[-1] == 100


def test_quota_exceeded(no_sleep):
    svc = FakeService([http_error(403, "quotaExceeded")])
    with pytest.raises(youtube.YouTubeError) as e:
        _up(svc, no_sleep)
    assert e.value.code == "quota_exceeded"


def test_transient_errors_retry_then_succeed(no_sleep):
    svc = FakeService([http_error(503, "backendError"), ConnectionError(), (None, {"id": "x1"})])
    assert _up(svc, no_sleep)["id"] == "x1"


def test_interrupted_upload_gives_up_after_3(no_sleep):
    svc = FakeService([ConnectionError()] * 4)
    with pytest.raises(youtube.YouTubeError) as e:
        _up(svc, no_sleep)
    assert e.value.code == "upload_failed" and e.value.retryable


def test_missing_video_id(no_sleep):
    svc = FakeService([(None, {"status": {}})])
    with pytest.raises(youtube.YouTubeError) as e:
        _up(svc, no_sleep)
    assert e.value.code == "upload_failed"


def test_oauth_state_roundtrip_and_tamper():
    s = youtube._sign({"r": 1, "t": __import__("time").time()})
    assert youtube._verify(s)["r"] == 1
    with pytest.raises(youtube.YouTubeError):
        youtube._verify(s[:-2] + "00")


class _Exec:
    def __init__(self, v):
        self.v = v

    def execute(self):
        return self.v


class FakeListService:
    def channels(self):
        return self

    def playlistItems(self):  # noqa: N802
        return self

    def list(self, **kw):
        if "mine" in kw:
            return _Exec({"items": [{"snippet": {"title": "Chan"}, "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
        mk = lambda vid, desc: {"contentDetails": {"videoId": vid}, "snippet": {"title": vid, "description": desc}, "status": {}}  # noqa: E731
        return _Exec({"items": [mk("app1", "Yum " + youtube.APP_MARKER), mk("personal", "my vlog"), mk("old", "posted before the tag")]})


def test_list_uploads_only_shows_app_videos():
    out = youtube.list_uploads("rt", known_ids={"old"}, service=FakeListService())
    assert [v["id"] for v in out["videos"]] == ["app1", "old"]


def test_upload_description_carries_marker(no_sleep):
    svc = FakeService([(None, {"id": "z"})])
    _up(svc, no_sleep)
    assert youtube.APP_MARKER in svc.body["snippet"]["description"]
