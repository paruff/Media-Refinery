from behave import given, when, then

@given(u'a video file "{file_name}"')
def step_given_video_file(context, file_name):
    context.file_name = file_name
    context.metadata = {}

@when(u'the video file is processed')
def step_when_video_processed(context):
    # Simulate video processing logic
    input_format = context.file_name.split('.')[-1]
    context.metadata = {
        "resolution": "1920x1080",
        "codec": "h264",
        "input_format": input_format
    }
    # Ensure output is always in mkv format
    context.output_path = context.file_name.rsplit('.', 1)[0] + ".mkv"

@then(u'the resolution should be "{resolution}"')
def step_then_resolution(context, resolution):
    if context.metadata.get("resolution") != resolution:
        raise AssertionError(f"Expected resolution: {resolution}, but got: {context.metadata.get('resolution')}")

@then(u'the codec should be "{codec}"')
def step_then_codec(context, codec):
    if context.metadata.get("codec") != codec:
        raise AssertionError(f"Expected codec: {codec}, but got: {context.metadata.get('codec')}")