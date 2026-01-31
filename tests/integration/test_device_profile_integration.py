from app.services.device_profile_service import DeviceProfileService
from app.services.planning_service import PlanningService, FileAttributes


def test_device_profile_integration():
    import asyncio

    service = DeviceProfileService()
    planning = PlanningService(service)
    attrs = FileAttributes(
        audio="aac", video="h264", width=1920, height=1080, container="mp4"
    )
    plan = asyncio.run(planning.plan(attrs, "samsung_tizen"))
    assert plan["transcode_audio"] is False
    assert plan["transcode_video"] is False
    assert plan["resize"] is False
    assert plan["remux"] is False
    # Add a new profile file and verify reload
    import os
    import json

    new_profile = {
        "id": "test_device",
        "name": "Test Device",
        "supported_audio": ["aac"],
        "supported_video": ["h264"],
        "max_resolution": {"width": 1280, "height": 720},
        "container": ["mp4"],
    }
    path = os.path.join(os.path.dirname(__file__), "../../profiles/test_device.json")
    with open(path, "w") as f:
        json.dump(new_profile, f)
    service = DeviceProfileService()  # reload
    assert any(p.id == "test_device" for p in service.profiles)
    os.remove(path)
