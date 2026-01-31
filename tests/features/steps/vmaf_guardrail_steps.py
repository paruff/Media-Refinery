from behave import given, when, then
from app.models.media import NormalizationPlan, PlanStatus
from app.services.vmaf_guardrail_service import VMAFGuardrailService
from pydantic import BaseModel
import asyncio


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


@given('a normalization plan with bitrate "{bitrate}"')
def step_given_plan(context, bitrate):
    context.plan = NormalizationPlan(id="bdd", ffmpeg_args={"bitrate": bitrate})
    context.db = DummyDB()
    context.dummy_vmaf = None


@when("the VMAF score is {score:f}")
def step_when_vmaf(context, score):
    async def dummy_vmaf(src, dst):
        return DummyMetrics(vmaf=score, psnr=40.0)

    context.service = VMAFGuardrailService(context.db, vmaf_func=dummy_vmaf)
    context.result = asyncio.run(
        context.service.check_and_update_quality(context.plan, "src.mp4", "out.mp4")
    )


@then("the plan should be marked as failed_quality_check")
def step_then_failed_quality(context):
    assert context.result.failed_quality_check is True
    assert context.result.plan_status == PlanStatus.failed


@then('the bitrate should be bumped to "{bitrate}"')
def step_then_bitrate_bumped(context, bitrate):
    assert context.result.ffmpeg_args["bitrate"] == bitrate


@then("the plan should not be marked as failed_quality_check")
def step_then_not_failed_quality(context):
    assert context.result.failed_quality_check is False
    assert context.result.plan_status == PlanStatus.completed


@then('the bitrate should remain "{bitrate}"')
def step_then_bitrate_remain(context, bitrate):
    assert context.result.ffmpeg_args["bitrate"] == bitrate
