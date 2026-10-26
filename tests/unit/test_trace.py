import json

import pytest
from pydantic import ValidationError

from app.core.trace import TraceEvent, TraceWriter


def test_emitted_lines_validate_against_schema(tmp_path):
    w = TraceWriter(tmp_path / "logs" / "trace.jsonl", "run-1")
    w.emit("healthcheck", "item-1", "failed", "ffprobe_unreadable")
    w.emit("workers.throttle", "", "degraded", "new_workers=1")
    lines = w.path.read_text().splitlines()
    assert len(lines) == 2
    events = [TraceEvent.model_validate_json(line) for line in lines]
    assert [e.run_id for e in events] == ["run-1", "run-1"]
    assert set(json.loads(lines[0])) == {
        "timestamp",
        "run_id",
        "event",
        "item_id",
        "status",
        "detail",
    }
    assert events[0].timestamp.tzinfo is not None


@pytest.mark.parametrize(
    "bad",
    [
        {"timestamp": "2026-01-01T00:00:00", "run_id": "r", "event": "e", "item_id": "i", "status": "success"},  # naive ts
        {"timestamp": "2026-01-01T00:00:00Z", "run_id": "r", "event": "e", "item_id": "i", "status": "bogus"},
        {"timestamp": "2026-01-01T00:00:00Z", "run_id": "r", "event": "e", "item_id": "i", "status": "success", "file": "x"},
    ],
)  # fmt: skip
def test_schema_rejects_malformed_lines(bad):
    with pytest.raises(ValidationError):
        TraceEvent.model_validate(bad)


def test_unwritable_trace_is_logged_not_fatal(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    TraceWriter(blocker / "trace.jsonl", "r").emit("e", "i", "started")
