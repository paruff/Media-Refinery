# Common step definitions for BDD tests

from behave import given, when, then
from behave.api.pending_step import StepNotImplementedError

@given('a media library root at "/Media"')
def step_impl(context):
    raise StepNotImplementedError(u'Given a media library root at "/Media"')

@given('a file in the library')
def step_impl(context):
    raise StepNotImplementedError(u'Given a file in the library')

@when('scanning metadata')
def step_impl(context):
    raise StepNotImplementedError(u'When scanning metadata')

@then('flag the file if any required tags are missing:')
def step_impl(context):
    raise StepNotImplementedError(u'Then flag the file if any required tags are missing:')

@given('a filename')
def step_impl(context):
    raise StepNotImplementedError(u'Given a filename')

@then('flag it if it contains non–UTF8 characters')
def step_impl(context):
    raise StepNotImplementedError(u'Then flag it if it contains non–UTF8 characters')

@then('flag it if it contains:')
def step_impl(context):
    raise StepNotImplementedError(u'Then flag it if it contains:')

@given('multiple files with the same title')
def step_impl(context):
    raise StepNotImplementedError(u'Given multiple files with the same title')

@then('flag them if:')
def step_impl(context):
    raise StepNotImplementedError(u'Then flag them if:')

@given('a file not inside a recognized movie, series, or music structure')
def step_impl(context):
    raise StepNotImplementedError(u'Given a file not inside a recognized movie, series, or music structure')

@then('flag it as "unclassified"')
def step_impl(context):
    raise StepNotImplementedError(u'Then flag it as "unclassified"')

@given('a movie file with messy naming')
def step_impl(context):
    raise StepNotImplementedError(u'Given a movie file with messy naming')

@then('rename it to:')
def step_impl(context):
    raise StepNotImplementedError(u'Then rename it to:')

@given('a series episode file')
def step_impl(context):
    raise StepNotImplementedError(u'Given a series episode file')

@given('a track file')
def step_impl(context):
    raise StepNotImplementedError(u'Given a track file')

@given('a movie, series, or album')
def step_impl(context):
    raise StepNotImplementedError(u'Given a movie, series, or album')

@then('move it into the correct canonical directory:')
def step_impl(context):
    raise StepNotImplementedError(u'Then move it into the correct canonical directory:')

@given('a file with incomplete metadata')
def step_impl(context):
    raise StepNotImplementedError(u'Given a file with incomplete metadata')

@then('enrich metadata using:')
def step_impl(context):
    raise StepNotImplementedError(u'Then enrich metadata using:')

@given('a TV library root at "/TV"')
def step_impl(context):
    raise StepNotImplementedError(u'Given a TV library root at "/TV"')

@given('a show titled "Show Name"')
def step_impl(context):
    raise StepNotImplementedError(u'Given a show titled "Show Name"')

@then('the directory MUST be:')
def step_impl(context):
    raise StepNotImplementedError(u'Then the directory MUST be:')

@given('season 1 of a show')
def step_impl(context):
    raise StepNotImplementedError(u'Given season 1 of a show')

@given('an episode with season 1 and episode 2')
def step_impl(context):
    raise StepNotImplementedError(u'Given an episode with season 1 and episode 2')

@then('the filename MUST be:')
def step_impl(context):
    raise StepNotImplementedError(u'Then the filename MUST be:')

@given('a file containing episodes 1 and 2')
def step_impl(context):
    raise StepNotImplementedError(u'Given a file containing episodes 1 and 2')

@then('the video codec MUST be:')
def step_impl(context):
    raise StepNotImplementedError(u'Then the video codec MUST be:')

@then('audio MUST be:')
def step_impl(context):
    raise StepNotImplementedError(u'Then audio MUST be:')

@then('subtitles MUST be:')
def step_impl(context):
    raise StepNotImplementedError(u'Then subtitles MUST be:')

@then('MUST NOT be:')
def step_impl(context):
    raise StepNotImplementedError(u'Then MUST NOT be:')

@given('a movie directory')
def step_impl(context):
    raise StepNotImplementedError(u'Given a movie directory')

@then('the directory MUST contain exactly one correctly named movie file')
def step_impl(context):
    raise StepNotImplementedError(u'Then the directory MUST contain exactly one correctly named movie file')

@then('the file MUST use supported codecs and audio')
def step_impl(context):
    raise StepNotImplementedError(u'Then the file MUST use supported codecs and audio')

@given('a show directory')
def step_impl(context):
    raise StepNotImplementedError(u'Given a show directory')

@then('all episodes MUST follow SxxEyy naming')
def step_impl(context):
    raise StepNotImplementedError(u'Then all episodes MUST follow SxxEyy naming')

@then('all seasons MUST be in Season NN folders')
def step_impl(context):
    raise StepNotImplementedError(u'Then all seasons MUST be in Season NN folders')

@given('an album directory')
def step_impl(context):
    raise StepNotImplementedError(u'Given an album directory')

@then('all tracks MUST have:')
def step_impl(context):
    raise StepNotImplementedError(u'Then all tracks MUST have:')

@then('filenames MUST follow:')
def step_impl(context):
    raise StepNotImplementedError(u'Then filenames MUST follow:')

@given('any media directory')
def step_impl(context):
    raise StepNotImplementedError(u'Given any media directory')

@then('artwork MUST be present or retrievable')
def step_impl(context):
    raise StepNotImplementedError(u'Then artwork MUST be present or retrievable')

@given('the library root')
def step_impl(context):
    raise StepNotImplementedError(u'Given the library root')

@then('no files SHOULD remain in unclassified locations')
def step_impl(context):
    raise StepNotImplementedError(u'Then no files SHOULD remain in unclassified locations')

@given('an input audio file "testdata/sample.mp3" with metadata')
def step_impl(context):
    raise StepNotImplementedError(u'Given an input audio file "testdata/sample.mp3" with metadata')

@given('pipeline is configured with dry_run = true')
def step_impl(context):
    raise StepNotImplementedError(u'Given pipeline is configured with dry_run = true')

@when('the pipeline runs')
def step_impl(context):
    raise StepNotImplementedError(u'When the pipeline runs')

@then('if dry_run is true no output files are written')
def step_impl(context):
    raise StepNotImplementedError(u'Then if dry_run is true no output files are written')

@then('if dry_run is false at least one output file with extension ".flac" exists')
def step_impl(context):
    raise StepNotImplementedError(u'Then if dry_run is false at least one output file with extension ".flac" exists')

@then('the output path matches the music pattern')
def step_impl(context):
    raise StepNotImplementedError(u'Then the output path matches the music pattern')

@then('metadata fields (title, artist, album) are present in the output or operation recorded')
def step_impl(context):
    raise StepNotImplementedError(u'Then metadata fields (title, artist, album) are present in the output or operation recorded')

@given('pipeline is configured with dry_run = false')
def step_impl(context):
    raise StepNotImplementedError(u'Given pipeline is configured with dry_run = false')

@given('a TV show file "Show.Name.S01E01.mkv"')
def step_impl(context):
    raise StepNotImplementedError(u'Given a TV show file "Show.Name.S01E01.mkv"')

@when('the file is processed')
def step_impl(context):
    raise StepNotImplementedError(u'When the file is processed')

@then('the metadata should include:')
def step_impl(context):
    raise StepNotImplementedError(u'Then the metadata should include:')

@given('a video file "sample_video.mp4"')
def step_impl(context):
    raise StepNotImplementedError(u'Given a video file "sample_video.mp4"')

@when('the video file is processed')
def step_impl(context):
    raise StepNotImplementedError(u'When the video file is processed')

@then('the output should be in "mkv" format')
def step_impl(context):
    raise StepNotImplementedError(u'Then the output should be in "mkv" format')

@then('the video codec should be "h264"')
def step_impl(context):
    raise StepNotImplementedError(u'Then the video codec should be "h264"')

@then('the audio codec should be "aac"')
def step_impl(context):
    raise StepNotImplementedError(u'Then the audio codec should be "aac"')
