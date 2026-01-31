import logging
from app.services.quality_guard_service import run_vmaf_ffmpeg
from app.models.media import NormalizationPlan, PlanStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update


class VMAFGuardrailService:
    def __init__(self, db: AsyncSession, vmaf_func=None):
        self.db = db
        self.vmaf_func = vmaf_func or run_vmaf_ffmpeg

    async def check_and_update_quality(
        self,
        plan: NormalizationPlan,
        src_path: str,
        out_path: str,
        min_vmaf: float = 90.0,
    ):
        metrics = await self.vmaf_func(src_path, out_path)

        plan.quality_metrics = metrics.dict()
        if metrics.vmaf is not None and metrics.vmaf < min_vmaf:
            plan.failed_quality_check = True
            # Bump bitrate for retry (simulate by updating ffmpeg_args)
            if plan.ffmpeg_args:
                plan.ffmpeg_args["bitrate"] = str(
                    int(plan.ffmpeg_args.get("bitrate", "1000")) * 2
                )
            plan.plan_status = PlanStatus.failed
        else:
            plan.failed_quality_check = False
            plan.plan_status = PlanStatus.completed
        await self.db.execute(
            update(NormalizationPlan)
            .where(NormalizationPlan.id == plan.id)
            .values(
                quality_metrics=plan.quality_metrics,
                failed_quality_check=plan.failed_quality_check,
                plan_status=plan.plan_status,
                ffmpeg_args=plan.ffmpeg_args,
            )
        )
        await self.db.commit()
        logging.info(f"VMAF/PSNR metrics for plan {plan.id}: {plan.quality_metrics}")
        return plan
