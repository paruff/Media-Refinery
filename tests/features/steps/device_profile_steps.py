from behave import given, when, then
from app.services.device_profile_service import DeviceProfileService
from app.services.planning_service import PlanningService, FileAttributes


@given(
    'a file with audio "{audio}", video "{video}", width {width:d}, height {height:d}, container "{container}"'
)
def step_given_file_attrs(context, audio, video, width, height, container):
    context.file_attrs = FileAttributes(
        audio=audio, video=video, width=width, height=height, container=container
    )


@given('a device profile "{profile_id}"')
def step_given_device_profile(context, profile_id):
    context.device_id = profile_id
    context.profile_service = DeviceProfileService()
    context.planning_service = PlanningService(context.profile_service)


@when("I plan for the device")
def step_when_plan(context):
    import asyncio

    context.plan = asyncio.run(
        context.planning_service.plan(context.file_attrs, context.device_id)
    )


@then("the plan should not require transcode_audio")
def step_then_no_transcode_audio(context):
    assert context.plan["transcode_audio"] is False


@then("the plan should not require transcode_video")
def step_then_no_transcode_video(context):
    assert context.plan["transcode_video"] is False


@then("the plan should not require resize")
def step_then_no_resize(context):
    assert context.plan["resize"] is False


@then("the plan should not require remux")
def step_then_no_remux(context):
    assert context.plan["remux"] is False


@then("the plan should require transcode_audio")
def step_then_require_transcode_audio(context):
    assert context.plan["transcode_audio"] is True
