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
    vmaf: float = 85.0
    psnr: float = 40.0

    def dict(self):
        return {"vmaf": self.vmaf, "psnr": self.psnr}


@pytest.mark.asyncio
async def test_vmaf_guardrail_fail(monkeypatch):
    plan = NormalizationPlan(id="test", ffmpeg_args={"bitrate": "1000"})
    db = DummyDB()

    async def dummy_vmaf(src, dst):
        return DummyMetrics()

    service = VMAFGuardrailService(db, vmaf_func=dummy_vmaf)
    result = await service.check_and_update_quality(plan, "src.mp4", "out.mp4")
    assert result.failed_quality_check is True
    assert result.plan_status == PlanStatus.failed
    assert result.quality_metrics["vmaf"] == 85.0
    assert result.ffmpeg_args["bitrate"] == "2000"


@pytest.mark.asyncio
async def test_vmaf_guardrail_pass(monkeypatch):
    plan = NormalizationPlan(id="test", ffmpeg_args={"bitrate": "1000"})
    db = DummyDB()

    async def dummy_vmaf(src, dst):
        return DummyMetrics(vmaf=95.0, psnr=42.0)

    service = VMAFGuardrailService(db, vmaf_func=dummy_vmaf)
    result = await service.check_and_update_quality(plan, "src.mp4", "out.mp4")
    assert result.failed_quality_check is False
    assert result.plan_status == PlanStatus.completed
    assert result.quality_metrics["vmaf"] == 95.0
    assert result.ffmpeg_args["bitrate"] == "1000"
