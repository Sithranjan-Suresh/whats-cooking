"""Typed configuration, read from environment variables / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), str(BACKEND_ROOT / ".env")),
        extra="ignore",
    )

    # AI
    gemini_api_key: str = ""
    gemini_text_model: str = "gemini-3.5-flash"
    veo_model: str = "gemini-omni-1.2-flash"  # Veo's successor (Interactions API); veo-* ids still work
    veo_cost_per_sec_cents: int = 8          # estimated AI-motion cost per second (8s clip ≈ $0.64)
    veo_timeout_s: int = 180
    veo_poll_s: int = 5

    # YouTube OAuth
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    oauth_redirect_uri: str = "http://localhost:8000/youtube/auth/callback"

    # Security
    app_secret: str = ""  # Fernet key (urlsafe base64, 32 bytes)
    owner_token: str = ""
    admin_token: str = ""  # required to change budget settings (PATCH /settings); unset = settings locked

    # Modes
    demo_mode: bool = True
    mock_pipeline: bool = False
    mock_fail_rate: float = 0.0
    mock_needs_dish: bool = False

    # Web
    frontend_origin: str = "http://localhost:3000"
    public_base_url: str = "http://localhost:8000"  # used to build absolute media URLs

    # Storage
    # DATABASE_URL (Postgres, e.g. Neon) keeps branding, budget and history across restarts of hosts with
    # no persistent disk. Unset = SQLite at $DATA_DIR/app.db.
    database_url: str = ""
    data_dir: Path = BACKEND_ROOT / "data"
    seed_dir: Path = REPO_ROOT / "seed"
    fonts_dir: Path = BACKEND_ROOT / "assets" / "fonts"

    # Limits
    max_upload_bytes: int = 10 * 1024 * 1024
    ffmpeg_timeout_s: int = 90
    # Low-CPU hosts (e.g. Render free): RENDER_PRESET=ultrafast, KB_OVERSAMPLE=1
    render_preset: str = "veryfast"
    kb_oversample: float = 2.0
    ffmpeg_threads: int = 0      # 0 = ffmpeg's default; 2 keeps a 1080x1920 encode near 100 MB on small hosts
    ffmpeg_parallel: int = 1     # concurrent ffmpeg processes per server
    workers: int = 2
    demo_jobs_per_hour_per_ip: int = 12
    # Fair use for everyone (the live app has no login): per-IP hourly limit, one video in progress per IP,
    # and a cap on the whole queue so one visitor can't stall the studio.
    jobs_per_hour_per_ip: int = 6
    active_jobs_per_ip: int = 1
    max_queued_jobs: int = 4

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def youtube_enabled(self) -> bool:
        return bool(self.google_oauth_client_id and self.google_oauth_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()


MEDIA_SUBDIRS = ("assets", "clips", "audio", "videos", "posters", "work")


def ensure_dirs() -> None:
    s = get_settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    for sub in MEDIA_SUBDIRS:
        (s.media_dir / sub).mkdir(parents=True, exist_ok=True)


def media_url(path: str | Path | None) -> str | None:
    """Convert an absolute media path into a public URL under /media."""
    if not path:
        return None
    s = get_settings()
    p = Path(path)
    try:
        rel = p.resolve().relative_to(s.media_dir.resolve())
    except ValueError:
        return None
    return f"{s.public_base_url.rstrip('/')}/media/{rel.as_posix()}"
