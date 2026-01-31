from pydantic import BaseModel
from typing import Optional


class QualityMetricsSchema(BaseModel):
    vmaf: Optional[float] = None
    psnr: Optional[float] = None
