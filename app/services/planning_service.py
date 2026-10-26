import logging
from typing import Any

from pydantic import BaseModel

from app.services.device_profile_service import DeviceProfileService

logger = logging.getLogger("PlanningService")


class FileAttributes(BaseModel):
    audio: str
    video: str
    width: int
    height: int
    container: str


class PlanningService:
    def __init__(self, profile_service: DeviceProfileService):
        self.profile_service = profile_service

    async def plan(self, file_attrs: FileAttributes, device_id: str) -> dict[str, Any]:
        """Constraint solver: returns plan actions for given file and device."""
        try:
            profile = self.profile_service.get_profile(device_id)
        except Exception as e:
            logger.exception("Device profile error")
            return {"error": str(e)}

        plan = {
            "transcode_audio": False,
            "transcode_video": False,
            "resize": False,
            "remux": False,
        }

        if file_attrs.audio not in profile.supported_audio:
            plan["transcode_audio"] = True
        if file_attrs.video not in profile.supported_video:
            plan["transcode_video"] = True
        if (
            file_attrs.width > profile.max_resolution.width
            or file_attrs.height > profile.max_resolution.height
        ):
            plan["resize"] = True
        if file_attrs.container not in profile.container:
            plan["remux"] = True
        return plan
