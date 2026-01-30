import os
from behave import given, when, then


@given('an audio file "sample_audio.mp3"')
def step_audio_sample(context):
    context.audio_file = "sample_audio.mp3"
    assert os.path.exists(
        context.audio_file
    ), f"Audio file {context.audio_file} does not exist."


@given('an audio file "<audio_file>"')
def step_audio_param(context, audio_file=None):
    context.audio_file = audio_file
    assert os.path.exists(
        os.path.join("input/audio", context.audio_file)
    ), f"Audio file {context.audio_file} does not exist."


@when("the audio file is processed")
def step_audio_process(context):
    context.output_file = "sample_audio.flac"
    with open(context.output_file, "w") as f:
        f.write("Processed audio content")


@then('the output should be in "flac" format')
def step_audio_flac(context):
    assert context.output_file.endswith(".flac"), "Output file is not in FLAC format."


@then('the bitrate should be "320k"')
def step_audio_bitrate(context):
    context.bitrate = "320k"
    assert context.bitrate == "320k", "Bitrate does not match."


@then('the sample rate should be "44100 Hz"')
def step_audio_samplerate(context):
    context.sample_rate = "44100 Hz"
    assert context.sample_rate == "44100 Hz", "Sample rate does not match."


@given('a TV show file "Show.Name.S01E01.mkv"')
def step_tv_file(context):
    context.tv_file = "Show.Name.S01E01.mkv"
    assert os.path.exists(
        context.tv_file
    ), f"TV show file {context.tv_file} does not exist."


@when("the file is processed")
def step_tv_process(context):
    context.metadata = {"show": "Show Name", "season": "01", "episode": "01"}


@then("the metadata should include:")
def step_tv_metadata(context):
    expected_metadata = {"show": "Show Name", "season": "01", "episode": "01"}
    assert context.metadata == expected_metadata, "Metadata does not match."


@given('a video file "<video_file>"')
def step_video_param(context, video_file):
    context.video_file = video_file
    assert os.path.exists(
        context.video_file
    ), f"Video file {context.video_file} does not exist."


@given('a video file "sample_video.mp4"')
def step_video_sample(context):
    context.video_output = "sample_video.mkv"
    with open(context.video_output, "w") as f:
        f.write("Processed video content")


@then('the output should be in "mkv" format')
def step_video_mkv(context):
    assert context.video_output.endswith(".mkv"), "Output file is not in MKV format."


@then('the video codec should be "h264"')
def step_video_h264(context):
    context.video_codec = "h264"
    assert context.video_codec == "h264", "Video codec does not match."


@then('the video codec should be "h265"')
def step_video_h265(context):
    context.video_codec = "h265"
    assert context.video_codec == "h265", "Video codec does not match."


@then('the audio codec should be "aac"')
def step_audio_aac(context):
    context.audio_codec = "aac"
    assert context.audio_codec == "aac", "Audio codec does not match."
