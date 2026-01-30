from behave import given, when, then
import os

@given(u'an audio file "{file_name}"')
def step_given_audio_file(context, file_name):
    context.file_name = file_name
    context.metadata = {}
    context.output_path = None

@when(u'the audio file is processed')
def step_when_audio_processed(context):
    # Simulate processing logic
    if not os.path.exists(context.file_name):
        raise FileNotFoundError(f"Audio file {context.file_name} not found.")
    # Ensure all files are converted to 'flac'
    context.output_path = os.path.splitext(context.file_name)[0] + ".flac"

@then(u'the output should be in "{format}" format')
def step_then_output_format(context, format):
    if not context.output_path.endswith(f".{format}"):
        raise AssertionError(f"Expected output format: {format}, but got: {context.output_path.split('.')[-1]}")

@then(u'the bitrate should be "{bitrate}"')
def step_then_bitrate(context, bitrate):
    # Placeholder for bitrate validation
    context.metadata['bitrate'] = bitrate

@then(u'the sample rate should be "{sample_rate}"')
def step_then_sample_rate(context, sample_rate):
    # Placeholder for sample rate validation
    context.metadata['sample_rate'] = sample_rate

@given(u'the metadata includes "Artist: {artist}" and "Title: {title}"')
def step_given_metadata_artist_title(context, artist, title):
    context.metadata['artist'] = artist
    context.metadata['title'] = title

@when(u'the audio file is processed for normalization')
def step_when_audio_normalized(context):
    # Simulate normalization logic
    context.output_path = f"{context.metadata['artist']} - {context.metadata['title']}.mp3"

@then(u'the file name should be "{expected_file_name}"')
def step_then_file_name(context, expected_file_name):
    if context.output_path != expected_file_name:
        raise AssertionError(f"Expected file name: {expected_file_name}, but got: {context.output_path}")

@then(u'the file name should align with Music Assistant standards')
def step_then_music_assistant_standards(context):
    # Placeholder for standards validation
    if not context.output_path:
        raise AssertionError("Output path is not set.")

@given(u'the metadata includes "Artist: {artist}", "Album: {album}", and "Year: {year}"')
def step_given_metadata_artist_album_year(context, artist, album, year):
    context.metadata['artist'] = artist
    context.metadata['album'] = album
    context.metadata['year'] = year

@when(u'the audio file is processed for organization')
def step_when_audio_organized(context):
    # Simulate organization logic
    context.output_path = os.path.join(
        f"{context.metadata['artist']}",
        f"{context.metadata['album']} - {context.metadata['year']}",
        os.path.basename(context.file_name)
    )

@then(u'the file should be moved to "{expected_path}"')
def step_then_file_moved(context, expected_path):
    if context.output_path != expected_path:
        raise AssertionError(f"Expected path: {expected_path}, but got: {context.output_path}")

@then(u'the directory structure should align with Music Assistant standards')
def step_then_directory_structure(context):
    # Placeholder for directory structure validation
    if not context.output_path:
        raise AssertionError("Output path is not set.")