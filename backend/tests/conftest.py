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
        "ADMIN_TOKEN": "test-admin",
        # never let a developer's DATABASE_URL (e.g. Neon in .env) point the tests at a real database
        "DATABASE_URL": "",
        "DATABASE_URL_UNPOOLED": "",
        "JOBS_PER_HOUR_PER_IP": "1000",
        "ACTIVE_JOBS_PER_IP": "1000",
        "MAX_QUEUED_JOBS": "1000",
        "DEMO_JOBS_PER_HOUR_PER_IP": "1000",
    }
)

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    """A brand-new DB + media dir per test (SQLite, or Postgres when TEST_DATABASE_URL is set)."""
    from app import db

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    pg = os.environ.get("TEST_DATABASE_URL")  # e.g. postgresql://postgres@127.0.0.1:5433/wctest
    if pg:
        monkeypatch.setenv("DATABASE_URL", pg)
    get_settings.cache_clear()
    db.reset_engine()
    if pg:
        from sqlalchemy import text

        with db.get_engine().begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
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
