from pathlib import Path

from pydantic import AliasChoices, Field
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
    AUDIOBOOKS_ROOT: str = str(_ROOT / "output" / "Audiobooks")
    CALIBRE_LIBRARY: str = str(_ROOT / "output" / "Books")  # R-EBOOK-3
    EBOOK_FETCH_METADATA: bool = True  # R-EBOOK-2: fetch-ebook-metadata, non-fatal
    WORK_DIR: str = str(_ROOT / "work")
    ARCHIVE_DIR: str = str(_ROOT / "archive")
    QUARANTINE_DIR: str = str(_ROOT / "quarantine")
    DRY_RUN: bool = False
    TMDB_API_KEY: str = ""  # movie enrichment; empty = guessit names only
    TVDB_API_KEY: str = ""  # TV enrichment
    ACOUSTID_API_KEY: str = ""  # music identification; empty = embedded tags only
    ACOUSTID_MIN_SCORE: float = 0.85  # below this a music plan needs manual approval
    # Opt-in approval rules: media types ("music", "movie", "series", "audiobook", "ebook") that skip review.
    AUTO_APPROVE_TYPES: list[str] = []

    # R-API-1: loopback needs no token; any other bind host requires MR_API_TOKEN.
    API_HOST: str = Field(
        "127.0.0.1", validation_alias=AliasChoices("MR_API_HOST", "API_HOST")
    )
    API_TOKEN: str = Field(
        "", validation_alias=AliasChoices("MR_API_TOKEN", "API_TOKEN")
    )

    class Config:
        env_file = ".env"


settings = Settings()  # type: ignore[call-arg]  # API_* are env-only aliases
