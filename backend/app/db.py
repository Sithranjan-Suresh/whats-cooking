"""Database engine + session helpers. Postgres when DATABASE_URL is set, otherwise SQLite."""
import contextvars
import logging
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import event, inspect, text
from sqlalchemy.exc import IntegrityError
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
MIGRATIONS: list[tuple[str, str, str]] = [
    ("restaurant", "account_id", "INTEGER REFERENCES account(id)"),  # studios owned by a signed-in account
    ("restaurant", "mascot_asset_id", "INTEGER REFERENCES asset(id)"),  # mascot shown on the video's ending
    ("settings", "spent_outside_cents", "INTEGER NOT NULL DEFAULT 0"),  # AI spend from before/outside the ledger
    ("account", "youtube_conn", "TEXT"),  # YouTube connection saved to a signed-in account (encrypted)
]


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
            "CREATE INDEX IF NOT EXISTS ix_restaurant_account ON restaurant(account_id)",
        ):
            conn.execute(text(stmt))


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


# ------------------------------------------------------------------ workspaces (one studio per browser)
#
# The public app has no login. Each browser makes a random workspace id (X-Workspace, 32 hex) and gets its own
# restaurant, cloned on first use from the template (the seeded demo, slug without "ws-"). Requests without a
# workspace see the template read-only (writes need an owner/admin token, enforced in main.WorkspaceMiddleware).

workspace_var: "contextvars.ContextVar[Optional[str]]" = contextvars.ContextVar("workspace", default=None)
account_var: "contextvars.ContextVar[Optional[int]]" = contextvars.ContextVar("account", default=None)
WORKSPACE_RE = re.compile(r"^[0-9a-f]{32}$")
WS_PREFIX = "ws-"      # guest studio, keyed by the browser's id
ACCT_PREFIX = "acct-"  # studio owned by a signed-in account


def is_studio(slug: str) -> bool:
    return slug.startswith(WS_PREFIX) or slug.startswith(ACCT_PREFIX)


def template_restaurant(session: Session) -> models.Restaurant:
    r = session.exec(
        select(models.Restaurant)
        .where(~models.Restaurant.slug.startswith(WS_PREFIX), ~models.Restaurant.slug.startswith(ACCT_PREFIX))
        .order_by(models.Restaurant.id)
    ).first()
    if r is None:
        raise AppError("not_seeded", "No restaurant yet. Run `make seed`.", 409)
    return r


def _create_workspace(session: Session, tpl: models.Restaurant, slug: str) -> models.Restaurant:
    """A new studio: the template's branding and menu (sharing its photos), no sales, no videos."""
    r = models.Restaurant(name=tpl.name, slug=slug, logo_asset_id=tpl.logo_asset_id, mascot_asset_id=tpl.mascot_asset_id,
                          color_primary=tpl.color_primary,
                          color_accent=tpl.color_accent, voice_tone=tpl.voice_tone, tts_voice=tpl.tts_voice)
    session.add(r)
    try:
        session.flush()
        for m in session.exec(select(models.MenuItem).where(models.MenuItem.restaurant_id == tpl.id)).all():
            session.add(models.MenuItem(restaurant_id=r.id, name=m.name, name_norm=m.name_norm, price_cents=m.price_cents,
                                        description=m.description, category=m.category, photo_asset_id=m.photo_asset_id))
        session.commit()
    except IntegrityError:  # the same browser's parallel first requests: the other one created it
        session.rollback()
        r = session.exec(select(models.Restaurant).where(models.Restaurant.slug == slug)).one()
    session.refresh(r)
    return r


def _account_restaurant(session: Session, tpl: models.Restaurant, account_id: int) -> models.Restaurant:
    """The signed-in account's studio. First sign-in claims this browser's guest studio (so nothing is lost);
    otherwise a fresh copy of the demo. Claimed studios get a new slug, so the browser id no longer opens them."""
    r = session.exec(select(models.Restaurant).where(models.Restaurant.account_id == account_id)
                     .order_by(models.Restaurant.id)).first()
    if r:
        return r
    ws = workspace_var.get()
    guest = session.exec(select(models.Restaurant).where(models.Restaurant.slug == WS_PREFIX + ws)).first() if ws else None
    if guest is not None and guest.account_id is None:
        guest.account_id, guest.slug = account_id, f"{ACCT_PREFIX}{account_id}"
        session.add(guest)
        try:
            session.commit()
        except IntegrityError:  # a parallel request claimed it first
            session.rollback()
            return _account_restaurant(session, tpl, account_id)
        session.refresh(guest)
        return guest
    r = _create_workspace(session, tpl, f"{ACCT_PREFIX}{account_id}")
    if r.account_id is None:
        r.account_id = account_id
        session.add(r)
        session.commit()
        session.refresh(r)
    return r


def current_restaurant(session: Session) -> models.Restaurant:
    tpl = template_restaurant(session)
    acct = account_var.get()
    if acct:
        return _account_restaurant(session, tpl, acct)
    ws = workspace_var.get()
    if not ws:
        return tpl
    slug = WS_PREFIX + ws
    r = session.exec(select(models.Restaurant).where(models.Restaurant.slug == slug)).first()
    return r or _create_workspace(session, tpl, slug)


def owned(session: Session, model, obj_id: int, r: models.Restaurant, what: str = "Not found"):
    """Fetch a row by id only if it belongs to this studio (404 otherwise, so ids from other studios leak nothing)."""
    obj = session.get(model, obj_id)
    if obj is None or getattr(obj, "restaurant_id", None) != r.id:
        raise AppError("not_found", what, 404)
    return obj


def asset_usable(session: Session, asset: Optional[models.Asset], r: models.Restaurant) -> bool:
    """A studio may use its own assets and the template's (the shared demo photos and logo)."""
    return bool(asset) and asset.restaurant_id in (r.id, template_restaurant(session).id)


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
