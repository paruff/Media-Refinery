from pydantic import BaseModel


class Resolution(BaseModel):
    width: int
    height: int


class DeviceProfile(BaseModel):
    id: str
    name: str
    supported_audio: list[str]
    supported_video: list[str]
    max_resolution: Resolution
    container: list[str]

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceProfile":
        if "max_resolution" in data and not isinstance(
            data["max_resolution"], Resolution
        ):
            data["max_resolution"] = Resolution(**data["max_resolution"])
        return cls(**data)
