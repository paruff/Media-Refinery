from sqlalchemy import (
    Column,
    String,
    DateTime,
    Enum,
    Text,
    func,
)
from app.core.database import Base
import enum
import uuid


class SagaLogStatus(enum.Enum):
    prepared = "prepared"
    committed = "committed"
    cleaned = "cleaned"
    failed = "failed"


class SagaFileMoveLog(Base):
    __tablename__ = "saga_file_move_log"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id = Column(String, nullable=False)
    src_path = Column(String, nullable=False)
    tmp_path = Column(String, nullable=False)
    dest_path = Column(String, nullable=False)
    status = Column(Enum(SagaLogStatus), default=SagaLogStatus.prepared, nullable=False)
    error = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
