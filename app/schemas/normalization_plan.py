from pydantic import BaseModel
from typing import Optional


class NormalizationPlanSchema(BaseModel):
    id: str
    media_item_id: str
    target_path: str
    needs_transcode: bool = False
    needs_rename: bool = False
    needs_tagging: bool = False
    surround: Optional[bool] = False
    # Add any other fields required for execution

    class Config:
        orm_mode = True
