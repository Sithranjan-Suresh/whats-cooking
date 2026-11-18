"""SQLite engine + session helpers."""
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import event, text
from sqlmodel import Session, SQLModel, create_engine, select

from .config import ensure_dirs, get_settings
from .errors import AppError
from . import models  # noqa: F401  (register tables)

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        ensure_dirs()
        s = get_settings()
        _engine = create_engine(
            f"sqlite:///{s.db_path}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )

        @event.listens_for(_engine, "connect")
        def _pragmas(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return _engine


def reset_engine() -> None:
    """Used by tests to point at a fresh DB."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


# Lightweight forward-only migrations for columns added after the first deploy.
MIGRATIONS = [
    ("restaurant", "presenter_asset_id", "INTEGER REFERENCES asset(id)"),
    ("settings", "veo_audio_cost_per_sec_cents", "INTEGER NOT NULL DEFAULT 15"),
]


def init_db() -> None:
    eng = get_engine()
    SQLModel.metadata.create_all(eng)
    with eng.begin() as conn:
        for table, col, ddl in MIGRATIONS:
            cols = {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}
            if col not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
        for stmt in (
            "CREATE INDEX IF NOT EXISTS ix_sales_rest_date ON salesrecord(restaurant_id, date)",
            "CREATE INDEX IF NOT EXISTS ix_ledger_rest_date_state ON usageledger(restaurant_id, date, state)",
            "CREATE INDEX IF NOT EXISTS ix_video_rest_created ON video(restaurant_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_menu_rest_norm ON menuitem(restaurant_id, name_norm)",
        ):
            conn.execute(text(stmt))


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


def current_restaurant(session: Session) -> models.Restaurant:
    r = session.exec(select(models.Restaurant).order_by(models.Restaurant.id)).first()
    if r is None:
        raise AppError("not_seeded", "No restaurant yet. Run `make seed`.", 409)
    return r


def get_app_settings(session: Session, restaurant_id: int) -> models.AppSettings:
    st = session.get(models.AppSettings, restaurant_id)
    if st is None:
        cfg = get_settings()
        st = models.AppSettings(
            restaurant_id=restaurant_id,
            veo_cost_per_sec_cents=cfg.veo_cost_per_sec_cents,
            veo_audio_cost_per_sec_cents=cfg.veo_audio_cost_per_sec_cents,
        )
        session.add(st)
        session.commit()
        session.refresh(st)
    return st
