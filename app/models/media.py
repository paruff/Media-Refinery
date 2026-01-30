import enum
import uuid
from sqlalchemy import Column, String, DateTime, Enum
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class FileState(str, enum.Enum):
    pending = "pending"
    scanned = "scanned"
    enriched = "enriched"
    planned = "planned"
    executed = "executed"
    validated = "validated"
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
