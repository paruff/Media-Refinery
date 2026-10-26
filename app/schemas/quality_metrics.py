from pydantic import BaseModel


class QualityMetricsSchema(BaseModel):
    vmaf: float | None = None
    psnr: float | None = None
