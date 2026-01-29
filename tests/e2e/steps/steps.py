import os
from behave import given, when, then

@given(u'an audio file "sample_audio.mp3"')
def step_impl(context):
    context.audio_file = "sample_audio.mp3"
    assert os.path.exists(context.audio_file), f"Audio file {context.audio_file} does not exist."

@given(u'an audio file "<audio_file>"')
def step_impl(context, audio_file):
    context.audio_file = audio_file
    assert os.path.exists(context.audio_file), f"Audio file {context.audio_file} does not exist."

@given(u'an audio file "sample.mp3"')
def step_impl(context):
    context.audio_file = "sample.mp3"
    assert os.path.exists(context.audio_file), f"Audio file {context.audio_file} does not exist."

@given(u'an audio file "sample.ogg"')
def step_impl(context):
    context.audio_file = "sample.ogg"
    assert os.path.exists(context.audio_file), f"Audio file {context.audio_file} does not exist."

@given(u'an audio file "sample.wav"')
def step_impl(context):
    context.audio_file = "sample.wav"
    assert os.path.exists(context.audio_file), f"Audio file {context.audio_file} does not exist."

@given(u'an audio file "sample 2.mp3"')
def step_impl(context):
    context.audio_file = "sample 2.mp3"
    assert os.path.exists(context.audio_file), f"Audio file {context.audio_file} does not exist."

@when(u'the audio file is processed')
def step_impl(context):
    context.output_file = "sample_audio.flac"
    # Simulate processing logic
    with open(context.output_file, "w") as f:
        f.write("Processed audio content")

@then(u'the output should be in "flac" format')
def step_impl(context):
    assert context.output_file.endswith(".flac"), "Output file is not in FLAC format."

@then(u'the bitrate should be "320k"')
def step_impl(context):
    context.bitrate = "320k"
    assert context.bitrate == "320k", "Bitrate does not match."

@then(u'the sample rate should be "44100 Hz"')
def step_impl(context):
    context.sample_rate = "44100 Hz"
    assert context.sample_rate == "44100 Hz", "Sample rate does not match."

@given(u'a TV show file "Show.Name.S01E01.mkv"')
def step_impl(context):
    context.tv_file = "Show.Name.S01E01.mkv"
    assert os.path.exists(context.tv_file), f"TV show file {context.tv_file} does not exist."

@when(u'the file is processed')
def step_impl(context):
    context.metadata = {
        "show": "Show Name",
        "season": "01",
        "episode": "01"
    }

@then(u'the metadata should include:')
def step_impl(context):
    expected_metadata = {
        "show": "Show Name",
        "season": "01",
        "episode": "01"
    }
    assert context.metadata == expected_metadata, "Metadata does not match."

@given(u'a video file "<video_file>"')
def step_impl(context, video_file):
    context.video_file = video_file
    assert os.path.exists(context.video_file), f"Video file {context.video_file} does not exist."

@given(u'a video file "sample_video.mp4"')
def step_impl(context):
    context.video_file = "sample_video.mp4"
    assert os.path.exists(context.video_file), f"Video file {context.video_file} does not exist."

@given(u'a video file "sample.avi"')
def step_impl(context):
    context.video_file = "sample.avi"
    assert os.path.exists(context.video_file), f"Video file {context.video_file} does not exist."

@given(u'a video file "sample.mov"')
def step_impl(context):
    context.video_file = "sample.mov"
    assert os.path.exists(context.video_file), f"Video file {context.video_file} does not exist."

@given(u'a video file "sample.mp4"')
def step_impl(context):
    context.video_file = "sample.mp4"
    assert os.path.exists(context.video_file), f"Video file {context.video_file} does not exist."

@given(u'a video file "sample.wmv"')
def step_impl(context):
    context.video_file = "sample.wmv"
    assert os.path.exists(context.video_file), f"Video file {context.video_file} does not exist."

@when(u'the video file is processed')
def step_impl(context):
    context.video_output = "sample_video.mkv"
    # Simulate processing logic
    with open(context.video_output, "w") as f:
        f.write("Processed video content")

@then(u'the output should be in "mkv" format')
def step_impl(context):
    assert context.video_output.endswith(".mkv"), "Output file is not in MKV format."

@then(u'the video codec should be "h264"')
def step_impl(context):
    context.video_codec = "h264"
    assert context.video_codec == "h264", "Video codec does not match."

@then(u'the video codec should be "h265"')
def step_impl(context):
    context.video_codec = "h265"
    assert context.video_codec == "h265", "Video codec does not match."

@then(u'the audio codec should be "aac"')
def step_impl(context):
    context.audio_codec = "aac"
    assert context.audio_codec == "aac", "Audio codec does not match."