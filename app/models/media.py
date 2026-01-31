import enum
import uuid
from sqlalchemy import Column, String, DateTime, Enum, Boolean, Integer, Text
from sqlalchemy import ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()  # type: ignore[misc, valid-type]


class FileState(str, enum.Enum):
    pending = "pending"
    scanning = "scanning"
    scanned = "scanned"
    enriched = "enriched"
    planned = "planned"
    executed = "executed"
    validated = "validated"
    audited = "audited"
    error = "error"


class MediaType(str, enum.Enum):
    movie = "movie"
    series = "series"
    music = "music"
    unknown = "unknown"


class MediaItem(Base):
    __tablename__ = "media_items"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_path = Column(String, unique=True, nullable=False)
    state = Column(Enum(FileState), default=FileState.pending, nullable=False)  # type: ignore[var-annotated]
    media_type = Column(Enum(MediaType), default=MediaType.unknown, nullable=False)  # type: ignore[var-annotated]
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )
    # Technical metadata fields
    container = Column(String, nullable=True)
    video_codec = Column(String, nullable=True)
    video_width = Column(Integer, nullable=True)
    video_height = Column(Integer, nullable=True)
    video_bitrate = Column(Integer, nullable=True)
    size = Column(Integer, nullable=True)  # File size in bytes
    subtitles = Column(
        String, nullable=True
    )  # JSON-encoded list or comma-separated string
    # TMDB enrichment fields
    canonical_title = Column(String, nullable=True)
    release_year = Column(Integer, nullable=True)
    tmdb_id = Column(Integer, nullable=True)
    poster_path = Column(String, nullable=True)
    enrichment_failed = Column(Boolean, default=False)
    # Guessed fields for enrichment
    guessed_title = Column(String, nullable=True)
    guessed_year = Column(Integer, nullable=True)
    # MusicBrainz enrichment fields
    album_artist = Column(String, nullable=True)
    album_name = Column(String, nullable=True)
    disc_number = Column(Integer, nullable=True)
    mbid = Column(String, nullable=True)
    release_mbid = Column(String, nullable=True)
    # TV enrichment fields
    canonical_series_name = Column(String, nullable=True)
    episode_title = Column(String, nullable=True)
    absolute_number = Column(Integer, nullable=True)
    overview = Column(String, nullable=True)
    tmdb_series_id = Column(Integer, nullable=True)
    metadata_mismatch = Column(Boolean, default=False)
    video_fps = Column(String, nullable=True)
    audio_codec = Column(String, nullable=True)
    audio_channels = Column(String, nullable=True)
    audio_language = Column(String, nullable=True)
    has_subtitles = Column(Boolean, default=False)
    subtitle_format = Column(String, nullable=True)
    subtitle_language = Column(String, nullable=True)
    artist = Column(String, nullable=True)
    # Fingerprint fields
    audio_fingerprint = Column(String, nullable=True, unique=False, index=True)
    video_fingerprint = Column(String, nullable=True, unique=False, index=True)
    album = Column(String, nullable=True)
    title = Column(String, nullable=True)
    year = Column(String, nullable=True)
    is_standard_compliant = Column(Boolean, default=False)
    error_log = Column(Text, nullable=True)
    enrichment_data = Column(
        Text, nullable=True
    )  # JSON-encoded dict for classification tokens
    detected_issues = Column(Text, nullable=True)  # JSON-encoded list of audit issues
    normalization_plan = relationship(
        "NormalizationPlan",
        uselist=False,
        back_populates="media_item",
        cascade="all, delete-orphan",
    )


class PlanStatus(enum.Enum):
    draft = "draft"
    approved = "approved"
    executing = "executing"
    completed = "completed"
    failed = "failed"


class NormalizationPlan(Base):
    quality_metrics = Column(JSON, nullable=True)  # Dict with VMAF, PSNR, etc.
    failed_quality_check = Column(Boolean, default=False, nullable=False)
    __tablename__ = "normalization_plans"
    __table_args__ = (
        UniqueConstraint("target_path", name="uq_normalizationplan_target_path"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    media_item_id = Column(
        String, ForeignKey("media_items.id"), unique=True, nullable=False
    )
    media_item = relationship("MediaItem", back_populates="normalization_plan")

    # Action flags
    needs_transcode = Column(Boolean, default=False, nullable=False)
    needs_rename = Column(Boolean, default=False, nullable=False)
    needs_subtitle_conversion = Column(Boolean, default=False, nullable=False)
    needs_tagging = Column(Boolean, default=False, nullable=False)

    # Execution data
    target_path = Column(String, nullable=False)
    ffmpeg_args = Column(JSON, nullable=True)  # List of strings
    original_hash = Column(String, nullable=False)

    # Status management
    plan_status = Column(
        Enum(PlanStatus), default=PlanStatus.draft, nullable=False
    )  # type: ignore[var-annotated]
    execution_log = Column(Text, default="", nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @property
    def is_ready(self):
        # Example: check if all enrichment data is present (placeholder logic)
        # Replace with actual enrichment checks as needed
        return all(
            [
                self.target_path,
                self.ffmpeg_args is not None,
                self.original_hash,
                self.media_item is not None
                and getattr(self.media_item, "enrichment_complete", True),
            ]
        )
