import pytest
from app.services.device_profile_service import DeviceProfileService
from app.services.planning_service import PlanningService, FileAttributes


@pytest.fixture(scope="module")
def planning_service():
    profile_service = DeviceProfileService()
    return PlanningService(profile_service)


def test_constraint_solver_transcode_audio(planning_service):
    import asyncio

    attrs = FileAttributes(
        audio="flac", video="h264", width=1920, height=1080, container="mp4"
    )
    plan = asyncio.run(planning_service.plan(attrs, "samsung_tizen"))
    assert plan["transcode_audio"] is True
    assert plan["transcode_video"] is False
    assert plan["resize"] is False
    assert plan["remux"] is False


def test_constraint_solver_resize(planning_service):
    import asyncio

    attrs = FileAttributes(
        audio="aac", video="h264", width=4000, height=3000, container="mp4"
    )
    plan = asyncio.run(planning_service.plan(attrs, "samsung_tizen"))
    assert plan["resize"] is True


def test_constraint_solver_remux(planning_service):
    import asyncio

    attrs = FileAttributes(
        audio="aac", video="h264", width=1920, height=1080, container="avi"
    )
    plan = asyncio.run(planning_service.plan(attrs, "samsung_tizen"))
    assert plan["remux"] is True
