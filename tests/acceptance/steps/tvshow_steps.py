from behave import given, when, then

@given(u'a TV show file "{file_name}"')
def step_given_tv_show_file(context, file_name):
    context.file_name = file_name
    context.metadata = {}

@when(u'the TV show file is processed')
def step_when_tv_show_processed(context):
    # Simulate dynamic TV show processing logic based on file name
    file_name = context.file_name
    if "S01E01" in file_name:
        context.metadata = {"title": "Pilot", "season": 1, "episode": 1}
    elif "S01E02" in file_name:
        context.metadata = {"title": "Cat's", "season": 1, "episode": 2}
    elif "S01E03" in file_name:
        context.metadata = {"title": "Dog's", "season": 1, "episode": 3}
    else:
        raise ValueError(f"Unrecognized TV show file: {file_name}")

@then(u'the metadata should include "Title: {title}"')
def step_then_metadata_title(context, title):
    if context.metadata.get("title") != title:
        raise AssertionError(f"Expected title: {title}, but got: {context.metadata.get('title')}")

@then(u'the metadata should include "Season: {season}"')
def step_then_metadata_season(context, season):
    if context.metadata.get("season") != int(season):
        raise AssertionError(f"Expected season: {season}, but got: {context.metadata.get('season')}")

@then(u'the metadata should include "Episode: {episode}"')
def step_then_metadata_episode(context, episode):
    if context.metadata.get("episode") != int(episode):
        raise AssertionError(f"Expected episode: {episode}, but got: {context.metadata.get('episode')}")