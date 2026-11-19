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
    veo_cost_per_sec_cents: int = 8          # Veo video only (food close-up)
    veo_audio_cost_per_sec_cents: int = 15   # Veo video + native audio (star-host format)
    gemini_image_model: str = "gemini-2.5-flash-image"
    veo_timeout_s: int = 180
    veo_poll_s: int = 5

    # YouTube OAuth
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    oauth_redirect_uri: str = "http://localhost:8000/youtube/auth/callback"

    # Security
    app_secret: str = ""  # Fernet key (urlsafe base64, 32 bytes)
    owner_token: str = ""

    # Modes
    demo_mode: bool = True
    mock_pipeline: bool = False
    demo_cache: bool = True
    mock_fail_rate: float = 0.0
    mock_needs_dish: bool = False

    # Web
    frontend_origin: str = "http://localhost:3000"
    public_base_url: str = "http://localhost:8000"  # used to build absolute media URLs

    # Storage
    data_dir: Path = BACKEND_ROOT / "data"
    seed_dir: Path = REPO_ROOT / "seed"
    fonts_dir: Path = BACKEND_ROOT / "assets" / "fonts"

    # Limits
    max_upload_bytes: int = 10 * 1024 * 1024
    ffmpeg_timeout_s: int = 90
    # Low-CPU hosts (e.g. Render free): RENDER_PRESET=ultrafast, KB_OVERSAMPLE=1
    render_preset: str = "veryfast"
    kb_oversample: float = 2.0
    workers: int = 2
    demo_jobs_per_hour_per_ip: int = 12

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
