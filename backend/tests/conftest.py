import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

_tmp = tempfile.mkdtemp(prefix="wc_test_")
os.environ.update(
    {
        "DATA_DIR": _tmp,
        "GEMINI_API_KEY": "",
        "OWNER_TOKEN": "test-owner",
        "DEMO_MODE": "1",
        "MOCK_PIPELINE": "0",
        "DEMO_CACHE": "0",
        "APP_SECRET": "ZmRkZmRkZmRkZmRkZmRkZmRkZmRkZmRkZmRkZmRkZmQ=",
        "GOOGLE_OAUTH_CLIENT_ID": "",
    }
)

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    """A brand-new SQLite DB + media dir per test."""
    from app import db

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    db.reset_engine()
    db.init_db()
    yield tmp_path
    db.reset_engine()
    get_settings.cache_clear()


@pytest.fixture()
def restaurant(fresh_db):
    from sqlmodel import Session

    from app.db import get_engine
    from app.models import Restaurant
    from app.routers.core import import_menu_csv

    with Session(get_engine()) as s:
        r = Restaurant(name="Kumar's", slug="kumars")
        s.add(r)
        s.commit()
        s.refresh(r)
        import_menu_csv(s, r.id, (ROOT / "seed" / "kumars_menu.csv").read_text())
        return r.id
