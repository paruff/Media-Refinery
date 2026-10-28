"""JSONL trace events (NF-4, ported from movies2vlib): one line per pipeline event."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict

logger = logging.getLogger(__name__)

Status = Literal[
    "started",
    "passed",
    "failed",
    "success",
    "skipped",
    "included",
    "degraded",
    "dry_run",
    "inconclusive",
    "flagged",
]


class TraceEvent(BaseModel):
    """The schema of one trace line; `TraceEvent.model_json_schema()` is the contract."""

    model_config = ConfigDict(extra="forbid")

    timestamp: AwareDatetime
    run_id: str
    event: str
    item_id: str  # "" for run-level events
    status: Status
    detail: str = ""


class TraceWriter:
    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id

    def emit(self, event: str, item_id: str, status: Status, detail: str = "") -> None:
        """Append one event. A trace that cannot be written is logged, never fatal."""
        line = TraceEvent(
            timestamp=datetime.now(UTC),
            run_id=self.run_id,
            event=event,
            item_id=item_id,
            status=status,
            detail=detail,
        ).model_dump_json()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            logger.exception("Cannot write trace event %s to %s", event, self.path)
