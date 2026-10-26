from pydantic import BaseModel


class NormalizationPlanSchema(BaseModel):
    id: str
    media_item_id: str
    source_path: str | None = None
    target_path: str
    needs_transcode: bool = False
    needs_rename: bool = False
    needs_tagging: bool = False
    surround: bool | None = False
    # Add any other fields required for execution

    class Config:
        from_attributes = True
