import pytest
from app.services.vmaf_guardrail_service import VMAFGuardrailService
from app.models.media import NormalizationPlan, PlanStatus
from pydantic import BaseModel


class DummyDB:
    async def execute(self, *args, **kwargs):
        return None

    async def commit(self):
        return None


class DummyMetrics(BaseModel):
    vmaf: float = 88.0
    psnr: float = 39.0

    def dict(self):
        return {"vmaf": self.vmaf, "psnr": self.psnr}


@pytest.mark.asyncio
async def test_vmaf_guardrail_integration(monkeypatch):
    plan = NormalizationPlan(id="integration", ffmpeg_args={"bitrate": "1200"})
    db = DummyDB()

    async def dummy_vmaf(src, dst):
        return DummyMetrics()

    service = VMAFGuardrailService(db, vmaf_func=dummy_vmaf)
    result = await service.check_and_update_quality(plan, "src.mp4", "out.mp4")
    assert result.failed_quality_check is True
    assert result.plan_status == PlanStatus.failed
    assert result.quality_metrics["vmaf"] == 88.0
    assert result.ffmpeg_args["bitrate"] == "2400"
