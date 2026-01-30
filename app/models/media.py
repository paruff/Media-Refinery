import enum
import uuid
from sqlalchemy import Column, String, DateTime, Enum, Boolean, Integer, Text
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

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
    state = Column(Enum(FileState), default=FileState.pending, nullable=False)
    media_type = Column(Enum(MediaType), default=MediaType.unknown, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    # Technical metadata fields
    container = Column(String, nullable=True)
    video_codec = Column(String, nullable=True)
    video_width = Column(Integer, nullable=True)
    video_height = Column(Integer, nullable=True)
    video_bitrate = Column(Integer, nullable=True)
    # TMDB enrichment fields
    canonical_title = Column(String, nullable=True)
    release_year = Column(Integer, nullable=True)
    tmdb_id = Column(Integer, nullable=True)
    poster_path = Column(String, nullable=True)
    enrichment_failed = Column(Boolean, default=False)
    # MusicBrainz enrichment fields
    album_artist = Column(String, nullable=True)
    album_name = Column(String, nullable=True)
    release_year = Column(Integer, nullable=True)
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
    album = Column(String, nullable=True)
    title = Column(String, nullable=True)
    year = Column(String, nullable=True)
    is_standard_compliant = Column(Boolean, default=False)
    error_log = Column(Text, nullable=True)
    enrichment_data = Column(Text, nullable=True)  # JSON-encoded dict for classification tokens
    detected_issues = Column(Text, nullable=True)  # JSON-encoded list of audit issues
