"""Pipeline configuration: roots, limits and per-type switches."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings
from app.models.media import MediaType


@dataclass
class PipelineConfig:
    input_dir: Path
    work_dir: Path
    archive_dir: Path
    quarantine_dir: Path
    music_root: Path
    movies_root: Path
    tv_root: Path
    audiobooks_root: Path
    ebooks_root: Path  # the Calibre library
    ebook_fetch: bool = False
    dry_run: bool = False
    auto_approve_types: frozenset[str] = field(default_factory=frozenset)
    # types processed; a disabled type's files stay untouched in the input folder (G16)
    enabled_types: frozenset[str] = frozenset(
        {"music", "movie", "series", "audiobook", "ebook"}
    )
    ffmpeg_timeout: float = 6 * 3600
    max_concurrent_execute: int = 2  # CPU-heavy stage bounded separately (R-PIPE-5)
    max_concurrent_io: int = 5
    throttle_after_failures: int = 2  # consecutive EXECUTE failures that halve workers
    trace_path: Path | None = None  # JSONL trace (NF-4); default work/trace.jsonl

    @classmethod
    def from_settings(cls) -> PipelineConfig:
        return cls(
            input_dir=Path(settings.INPUT_DIR),
            work_dir=Path(settings.WORK_DIR),
            archive_dir=Path(settings.ARCHIVE_DIR),
            quarantine_dir=Path(settings.QUARANTINE_DIR),
            music_root=Path(settings.MUSIC_ROOT),
            movies_root=Path(settings.MOVIES_ROOT),
            tv_root=Path(settings.TV_ROOT),
            audiobooks_root=Path(settings.AUDIOBOOKS_ROOT),
            ebooks_root=Path(settings.CALIBRE_LIBRARY),
            ebook_fetch=settings.EBOOK_FETCH_METADATA,
            trace_path=Path(settings.LOG_DIR) / "trace.jsonl",
            dry_run=settings.DRY_RUN,
            auto_approve_types=frozenset(settings.AUTO_APPROVE_TYPES),
            enabled_types=frozenset(settings.ENABLED_TYPES),
        )

    @property
    def roots(self) -> dict[str, str]:
        return {
            "music": str(self.music_root),
            "movie": str(self.movies_root),
            "series": str(self.tv_root),
            "audiobook": str(self.audiobooks_root),
            "ebook": str(self.ebooks_root),
        }

    def root_for(self, media_type) -> Path:
        return {
            MediaType.music: self.music_root,
            MediaType.movie: self.movies_root,
            MediaType.series: self.tv_root,
            MediaType.audiobook: self.audiobooks_root,
            MediaType.ebook: self.ebooks_root,
        }[MediaType(media_type)]
