import pytest
from unittest.mock import AsyncMock
from app.services.reporting_service import ReportingService


@pytest.mark.asyncio
def test_reporting_service_summary(monkeypatch):
    db = AsyncMock()
    # Patch SQLAlchemy queries to return fake data
    db.scalar.return_value = 5
    db.execute.side_effect = [
        AsyncMock(return_value=[("validated", 3), ("error", 2)]),  # by_state
        AsyncMock(return_value=[("music", 2), ("movie", 3)]),  # by_media_type
        AsyncMock(return_value=["Error 1", "Error 2", "Error 1"]),  # error_log
        AsyncMock(return_value=["missing metadata warning"]),  # warnings
        AsyncMock(return_value=[(123456789,)]),  # storage_bytes
    ]
    service = ReportingService(db)

    # Patch methods to return expected values
    async def fake_execute(*args, **kwargs):
        return await db.execute.side_effect.pop(0)

    db.execute = fake_execute
    summary = pytest.run(service.get_summary())
    assert summary.total == 5
    assert summary.by_state[0].state == "validated"
    assert summary.by_media_type[1].media_type == "movie"
    assert summary.validated_success_rate == 60.0
    assert "Error 1" in summary.error_log
    assert summary.storage_bytes == 123456789
