# Watcher-specific step definitions for BDD tests
from behave import given, when, then
from behave.api.pending_step import StepNotImplementedError

@given('a file "test_song.mp3" exists in the input directory')
def step_impl(context):
    raise StepNotImplementedError(u'Given a file "test_song.mp3" exists in the input directory')

@when('the watcher scans for new files')
def step_impl(context):
    raise StepNotImplementedError(u'When the watcher scans for new files')

@then('the database should show the file "test_song.mp3" in "scanned" state')
def step_impl(context):
    raise StepNotImplementedError(u'Then the database should show the file "test_song.mp3" in "scanned" state')
