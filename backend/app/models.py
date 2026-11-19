"""SQLModel tables (engineering spec §2.1)."""
import json
import datetime as dt
from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Restaurant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(index=True, unique=True)
    logo_asset_id: Optional[int] = Field(default=None, foreign_key="asset.id")
    color_primary: str = "#C49A4A"
    color_accent: str = "#F3EBDD"
    voice_tone: str = "upbeat"  # friendly|upbeat|elegant
    tts_voice: str = "en-US-AriaNeural"
    created_at: datetime = Field(default_factory=utcnow)


class Asset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    restaurant_id: int = Field(foreign_key="restaurant.id", index=True)
    kind: str  # photo|logo|music
    path: str
    mime: str
    width: int = 0
    height: int = 0
    bytes: int = 0
    sha256: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class MenuItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    restaurant_id: int = Field(foreign_key="restaurant.id", index=True)
    name: str
    name_norm: str = Field(index=True)
    price_cents: Optional[int] = None
    description: Optional[str] = None
    category: Optional[str] = None
    photo_asset_id: Optional[int] = Field(default=None, foreign_key="asset.id")


class SalesRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    restaurant_id: int = Field(foreign_key="restaurant.id", index=True)
    date: dt.date = Field(index=True)
    menu_item_id: Optional[int] = Field(default=None, foreign_key="menuitem.id")
    raw_item_name: str
    quantity: int
    revenue_cents: Optional[int] = None


class Insight(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    restaurant_id: int = Field(foreign_key="restaurant.id", index=True)
    menu_item_id: int = Field(foreign_key="menuitem.id")
    angle: str  # top_seller|rising|slow_mover
    metric_json: str = "{}"
    reason: str = ""
    reason_source: str = "rule"  # gemini|rule
    created_at: datetime = Field(default_factory=utcnow)
    batch_id: str = Field(index=True)
    rank: int = 0


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    restaurant_id: int = Field(foreign_key="restaurant.id", index=True)
    mode: str  # photo|insight|menu
    menu_item_id: Optional[int] = Field(default=None, foreign_key="menuitem.id")
    photo_asset_id: Optional[int] = Field(default=None, foreign_key="asset.id")
    insight_id: Optional[int] = Field(default=None, foreign_key="insight.id")
    angle: Optional[str] = None
    style: str = "bold"
    length_s: int = 8
    veo_requested: bool = False
    veo_used: bool = False
    fallback_reason: Optional[str] = None
    status: str = "queued"  # queued|running|needs_dish|done|failed
    stages_json: str = "[]"
    analyze_json: Optional[str] = None
    script_json: Optional[str] = None
    flags_json: str = "{}"
    cost_cents: int = 0
    error: Optional[str] = None
    error_stage: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    finished_at: Optional[datetime] = None


class Video(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: Optional[int] = Field(default=None, foreign_key="job.id")
    restaurant_id: int = Field(foreign_key="restaurant.id", index=True)
    menu_item_id: Optional[int] = Field(default=None, foreign_key="menuitem.id")
    path: str
    poster_path: Optional[str] = None
    duration_s: float = 0
    width: int = 0
    height: int = 0
    bytes: int = 0
    mode: str = "free"  # veo|free
    cost_cents: int = 0
    title: Optional[str] = None
    description: Optional[str] = None
    hashtags_json: str = "[]"
    youtube_id: Optional[str] = None
    youtube_url: Optional[str] = None
    youtube_privacy: Optional[str] = None
    publish_status: str = "draft"  # draft|publishing|published|failed
    publish_error: Optional[str] = None
    publish_progress: int = 0
    created_at: datetime = Field(default_factory=utcnow, index=True)


class UsageLedger(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    restaurant_id: int = Field(foreign_key="restaurant.id", index=True)
    date: dt.date = Field(index=True)
    job_id: int = Field(foreign_key="job.id")
    kind: str = "veo_clip"
    seconds: int
    est_cost_cents: int
    state: str = "reserved"  # reserved|committed|released
    created_at: datetime = Field(default_factory=utcnow)


class AppSettings(SQLModel, table=True):
    __tablename__ = "settings"
    restaurant_id: int = Field(primary_key=True, foreign_key="restaurant.id")
    daily_veo_clip_limit: int = 10
    monthly_cap_cents: int = 1000
    free_mode: bool = False
    veo_cost_per_sec_cents: int = 8


# ---------- JSON helpers ----------

def jload(s: Optional[str], default: Any = None) -> Any:
    if not s:
        return default
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return default


def jdump(v: Any) -> str:
    return json.dumps(v, default=str)
