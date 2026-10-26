from pathlib import Path

from pydantic_settings import BaseSettings

_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    DATABASE_URL: str = (
        f"sqlite+aiosqlite:///{_ROOT / 'data' / 'media_refinery.sqlite'}"
    )
    INPUT_DIR: str = str(_ROOT / "input")
    OUTPUT_DIR: str = str(_ROOT / "output")
    LOG_DIR: str = str(_ROOT / "logs")
    STAGING_DIR: str = str(_ROOT / "staging")
    # Pipeline spine (spec §5): library roots per type, work/archive/quarantine.
    MUSIC_ROOT: str = str(_ROOT / "output" / "Music")
    MOVIES_ROOT: str = str(_ROOT / "output" / "Movies")
    TV_ROOT: str = str(_ROOT / "output" / "TV")
    WORK_DIR: str = str(_ROOT / "work")
    ARCHIVE_DIR: str = str(_ROOT / "archive")
    QUARANTINE_DIR: str = str(_ROOT / "quarantine")
    DRY_RUN: bool = False
    TMDB_API_KEY: str = ""  # movie enrichment; empty = guessit names only
    TVDB_API_KEY: str = ""  # TV enrichment
    # Opt-in approval rules: media types ("music", "movie", "series") that skip review.
    AUTO_APPROVE_TYPES: list[str] = []

    class Config:
        env_file = ".env"


settings = Settings()
