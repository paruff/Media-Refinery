from pydantic import BaseModel
from typing import List


class Resolution(BaseModel):
    width: int
    height: int


class DeviceProfile(BaseModel):
    id: str
    name: str
    supported_audio: List[str]
    supported_video: List[str]
    max_resolution: Resolution
    container: List[str]

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceProfile":
        if "max_resolution" in data and not isinstance(
            data["max_resolution"], Resolution
        ):
            data["max_resolution"] = Resolution(**data["max_resolution"])
        return cls(**data)
