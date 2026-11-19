"""Database engine + session helpers. Postgres when DATABASE_URL is set, otherwise SQLite."""
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import event, inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from .config import ensure_dirs, get_settings
from .errors import AppError
from . import models  # noqa: F401  (register tables)

log = logging.getLogger(__name__)
_engine = None


def _pg_url(url: str) -> str:
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _pg_engine(url: str):
    # Neon's pooler (PgBouncer, transaction mode) can't keep psycopg's automatic server-side prepared
    # statements, so turn them off there. Neon also suspends idle compute: ping connections before use.
    connect_args = {"prepare_threshold": None} if "-pooler." in url else {}
    return create_engine(_pg_url(url), pool_pre_ping=True, pool_recycle=240, pool_size=5, max_overflow=5,
                         connect_args=connect_args)


def get_engine():
    global _engine
    if _engine is None:
        ensure_dirs()
        s = get_settings()
        if s.database_url:
            _engine = _pg_engine(s.database_url)
        else:
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


# Lightweight forward-only migrations for columns added after the first deploy: (table, column, DDL).
MIGRATIONS: list[tuple[str, str, str]] = []


def init_db() -> None:
    s = get_settings()
    # Schema changes go over the direct connection when there is one (Neon: DATABASE_URL_UNPOOLED).
    ddl = _pg_engine(s.database_url_unpooled) if (s.database_url and s.database_url_unpooled) else get_engine()
    try:
        _create_schema(ddl)
    finally:
        if ddl is not get_engine():
            ddl.dispose()


def _create_schema(eng) -> None:
    SQLModel.metadata.create_all(eng)
    with eng.begin() as conn:
        for table, col, ddl in MIGRATIONS:
            cols = {c["name"] for c in inspect(conn).get_columns(table)}
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
        )
        session.add(st)
        session.commit()
        session.refresh(st)
    return st


# ------------------------------------------------------------------ media that survives disk wipes

def keep_asset_bytes(session: Session, asset: models.Asset) -> None:
    """Store an asset's file in the DB (call after the Asset row exists). Restored by restore_media()."""
    data = Path(asset.path).read_bytes()
    session.merge(models.AssetBlob(asset_id=asset.id, data=data))
    session.commit()


def restore_media() -> int:
    """Write back asset files that are in the DB but missing on disk (e.g. after a free-host restart).

    One blob at a time, so a large library never has to fit in memory.
    """
    restored = 0
    with Session(get_engine()) as session:
        rows = session.exec(
            select(models.Asset.id, models.Asset.path).join(models.AssetBlob, models.AssetBlob.asset_id == models.Asset.id)
        ).all()
        for asset_id, path in rows:
            p = Path(path)
            if p.exists():
                continue
            blob = session.get(models.AssetBlob, asset_id)
            if blob is None:
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(blob.data)
            session.expunge(blob)
            restored += 1
    if restored:
        log.info("restored %d media files from the database", restored)
    return restored


def has_restaurant() -> bool:
    with Session(get_engine()) as session:
        return session.exec(select(models.Restaurant.id)).first() is not None
