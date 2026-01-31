from unittest.mock import AsyncMock
from app.services.reporting_service import ReportingService


def test_reporting_service_summary(monkeypatch):
    db = AsyncMock()
    # Patch SQLAlchemy queries to return fake data
    db.scalar.return_value = 5

    class FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

        def scalars(self):
            return self

        def first(self):
            return self._rows[0] if self._rows else None

    execute_results = [
        FakeResult([("validated", 3), ("error", 2)]),  # by_state
        FakeResult([("music", 2), ("movie", 3)]),  # by_media_type
        FakeResult(["Error 1", "Error 2", "Error 1"]),  # error_log
        FakeResult(["missing metadata warning"]),  # warnings
        FakeResult([(123456789,)]),  # storage_bytes
    ]
    service = ReportingService(db)

    # Patch methods to return expected values
    async def fake_execute(*args, **kwargs):
        return execute_results.pop(0)

    db.execute = fake_execute
    import asyncio

    summary = asyncio.run(service.get_summary())
    assert summary.total == 5
    assert summary.by_state[0].state == "validated"
    assert summary.by_media_type[1].media_type == "movie"
    assert summary.validated_success_rate == 60.0
    assert "Error 1" in summary.error_log
    assert summary.storage_bytes == 123456789
