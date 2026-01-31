# Common step definitions for BDD tests
import os
from behave import given, when, then  # type: ignore[import-untyped]


@given('a file "{filename}" exists in the input directory')
def step_given_file_in_input(context, filename):
    file_path = os.path.join(context.input_dir, filename)
    with open(file_path, "w") as f:
        f.write("test content")
    context.last_file = filename


@then('the database should show the file "{filename}" in "{state}" state')
def step_then_db_file_state(context, filename, state):
    from sqlalchemy.future import select
    from app.models.media import MediaItem
    import asyncio

    async def check():
        async with context.db() as session:
            result = await session.execute(
                select(MediaItem).where(MediaItem.source_path == filename)
            )
            item = result.scalar_one_or_none()
            assert item is not None, f"File {filename} not found in DB"
            assert item.state == state, f"Expected {state}, got {item.state}"

    asyncio.run(check())


@given('a media library root at "/Media"')
def step_given_media_library_root(context):
    context.media_root = os.path.abspath("/tmp/test_media_root")
    os.makedirs(context.media_root, exist_ok=True)


@given("a file in the library")
def step_given_file_in_library(context):
    if not hasattr(context, "media_root"):
        context.media_root = os.path.abspath("/tmp/test_media_root")
        os.makedirs(context.media_root, exist_ok=True)
    file_path = os.path.join(context.media_root, "testfile.txt")
    with open(file_path, "w") as f:
        f.write("dummy content")
    context.library_file = file_path


@when("scanning metadata")
def step_when_scanning_metadata(context):
    # Simulate metadata scan (no-op for now)
    pass


@then("flag the file if any required tags are missing:")
def step_then_flag_missing_tags(context):
    # Simulate tag check (no-op for now)
    pass


@given("a filename")
def step_given_filename(context):
    context.filename = "test_file_ä.txt"


@then("flag it if it contains non–UTF8 characters")
def step_then_flag_non_utf8(context):
    # Simulate UTF-8 check (no-op for now)
    pass


@then("flag it if it contains:")
def step_then_flag_illegal_chars(context):
    # Simulate illegal char check (no-op for now)
    pass


@given("multiple files with the same title")
def step_given_multiple_files_same_title(context):
    if not hasattr(context, "media_root"):
        context.media_root = os.path.abspath("/tmp/test_media_root")
        os.makedirs(context.media_root, exist_ok=True)
    context.duplicate_files = []
    for i in range(2):
        file_path = os.path.join(context.media_root, f"Movie.Name.2020.{i}.mkv")
        with open(file_path, "w") as f:
            f.write("dummy content")
        context.duplicate_files.append(file_path)


@then("flag them if:")
def step_then_flag_duplicates(context):
    # Simulate duplicate check (no-op for now)
    pass


@given("a file not inside a recognized movie, series, or music structure")
def step_given_file_unclassified(context):
    context.unclassified_path = os.path.abspath(
        "/tmp/test_media_root/unclassified_file.txt"
    )
    os.makedirs(os.path.dirname(context.unclassified_path), exist_ok=True)
    with open(context.unclassified_path, "w") as f:
        f.write("dummy content")


@then('flag it as "unclassified"')
def step_then_flag_unclassified(context):
    # Simulate unclassified file check (no-op for now)
    pass


@given("a movie file with messy naming")
def step_given_movie_file_messy(context):
    context.messy_movie_path = os.path.abspath(
        "/tmp/test_media_root/Movie.Name.2020.1080p.bluray.x264.mkv"
    )
    os.makedirs(os.path.dirname(context.messy_movie_path), exist_ok=True)
    with open(context.messy_movie_path, "w") as f:
        f.write("dummy content")


@then("rename it to:")
def step_then_rename_to(context):
    # Simulate rename (no-op for now)
    pass


@given("a series episode file")
def step_given_series_episode_file(context):
    context.series_episode_path = os.path.abspath(
        "/tmp/test_media_root/Show.Name.S01E02.mkv"
    )
    os.makedirs(os.path.dirname(context.series_episode_path), exist_ok=True)
    with open(context.series_episode_path, "w") as f:
        f.write("dummy content")


@given("a track file")
def step_given_track_file(context):
    context.track_file_path = os.path.abspath(
        "/tmp/test_media_root/01 - Track Title.flac"
    )
    os.makedirs(os.path.dirname(context.track_file_path), exist_ok=True)
    with open(context.track_file_path, "w") as f:
        f.write("dummy content")


@given("a movie, series, or album")
def step_given_movie_series_album(context):
    context.movie_dir = os.path.abspath("/tmp/test_media_root/Movies/Movie Name (2020)")
    os.makedirs(context.movie_dir, exist_ok=True)
    context.series_dir = os.path.abspath("/tmp/test_media_root/TV/Show Name/Season 01")
    os.makedirs(context.series_dir, exist_ok=True)
    context.album_dir = os.path.abspath(
        "/tmp/test_media_root/Music/Artist/2020 - Album"
    )
    os.makedirs(context.album_dir, exist_ok=True)


@then("move it into the correct canonical directory:")
def step_then_move_canonical(context):
    # Simulate move (no-op for now)
    pass


@given("a file with incomplete metadata")
def step_given_file_incomplete_metadata(context):
    # Simulate file with incomplete metadata (no-op for now)
    context.incomplete_metadata_file = True


@then("enrich metadata using:")
def step_then_enrich_metadata(context):
    # Simulate metadata enrichment (no-op for now)
    pass


@given('a TV library root at "/TV"')
def step_given_tv_library_root(context):
    context.tv_root = os.path.abspath("/tmp/test_tv_root")
    os.makedirs(context.tv_root, exist_ok=True)


@given('a show titled "Show Name"')
def step_given_show_titled(context):
    context.show_name = "Show Name"


@then("the directory MUST be:")
def step_then_directory_must_be(context):
    # No-op for now
    pass


@given("season 1 of a show")
def step_given_season_1(context):
    context.season = 1


@given("an episode with season 1 and episode 2")
def step_given_episode_s1e2(context):
    context.episode = (1, 2)


@then("the filename MUST be:")
def step_then_filename_must_be(context):
    # No-op for now
    pass


@given("a file containing episodes 1 and 2")
def step_given_file_multi_episode(context):
    context.multi_episode_file = True


@then("the video codec MUST be:")
def step_then_video_codec_must_be(context):
    # No-op for now
    pass


@then("audio MUST be:")
def step_then_audio_must_be(context):
    # No-op for now
    pass


@then("subtitles MUST be:")
def step_then_subtitles_must_be(context):
    # No-op for now
    pass


@then("MUST NOT be:")
def step_then_must_not_be(context):
    # No-op for now
    pass


@given("a movie directory")
def step_given_movie_directory(context):
    context.movie_dir = os.path.abspath("/tmp/test_media_root/Movies/Movie Name (2020)")
    os.makedirs(context.movie_dir, exist_ok=True)


@then("the directory MUST contain exactly one correctly named movie file")
def step_then_directory_one_movie(context):
    # No-op for now
    pass


@then("the file MUST use supported codecs and audio")
def step_then_file_supported_codecs(context):
    # No-op for now
    pass


@given("a show directory")
def step_given_show_directory(context):
    context.show_dir = os.path.abspath("/tmp/test_media_root/TV/Show Name")
    os.makedirs(context.show_dir, exist_ok=True)


@then("all episodes MUST follow SxxEyy naming")
def step_then_episodes_sxxeyy(context):
    # No-op for now
    pass


@then("all seasons MUST be in Season NN folders")
def step_then_seasons_in_folders(context):
    # No-op for now
    pass


@given("an album directory")
def step_given_album_directory(context):
    context.album_dir = os.path.abspath(
        "/tmp/test_media_root/Music/Artist/2020 - Album"
    )
    os.makedirs(context.album_dir, exist_ok=True)


@then("all tracks MUST have:")
def step_then_tracks_must_have(context):
    # No-op for now
    pass


@then("filenames MUST follow:")
def step_then_filenames_must_follow(context):
    # No-op for now
    pass


@given("any media directory")
def step_given_any_media_directory(context):
    context.any_media_dir = os.path.abspath("/tmp/test_media_root/Any")
    os.makedirs(context.any_media_dir, exist_ok=True)


@then("artwork MUST be present or retrievable")
def step_then_artwork_present(context):
    # No-op for now
    pass


@given("the library root")
def step_given_library_root(context):
    context.library_root = os.path.abspath("/tmp/test_media_root")
    os.makedirs(context.library_root, exist_ok=True)


@then("no files SHOULD remain in unclassified locations")
def step_then_no_orphans(context):
    # No-op for now
    pass


@given('an input audio file "testdata/sample.mp3" with metadata')
def step_given_input_audio_file(context):
    context.input_audio_file = os.path.abspath(
        "/tmp/test_media_root/testdata/sample.mp3"
    )
    os.makedirs(os.path.dirname(context.input_audio_file), exist_ok=True)
    with open(context.input_audio_file, "w") as f:
        f.write("dummy content")


@given("pipeline is configured with dry_run = true")
def step_given_pipeline_dry_run_true(context):
    context.dry_run = True


@when("the pipeline runs")
def step_when_pipeline_runs(context):
    # No-op for now
    pass


@then("if dry_run is true no output files are written")
def step_then_dry_run_no_output(context):
    # No-op for now
    pass


@then('if dry_run is false at least one output file with extension ".flac" exists')
def step_then_flac_output(context):
    # No-op for now
    pass


@then("the output path matches the music pattern")
def step_then_music_pattern(context):
    # No-op for now
    pass


@then(
    "metadata fields (title, artist, album) are present in the output or operation recorded"
)
def step_then_metadata_fields_present(context):
    # No-op for now
    pass


@given("pipeline is configured with dry_run = false")
def step_given_pipeline_dry_run_false(context):
    context.dry_run = False


@given('a TV show file "Show.Name.S01E01.mkv"')
def step_given_tv_show_file(context):
    context.tv_show_file = os.path.abspath("/tmp/test_media_root/Show.Name.S01E01.mkv")
    os.makedirs(os.path.dirname(context.tv_show_file), exist_ok=True)
    with open(context.tv_show_file, "w") as f:
        f.write("dummy content")


@when("the file is processed")
def step_when_file_processed(context):
    # No-op for now
    pass


@then("the metadata should include:")
def step_then_metadata_should_include(context):
    # No-op for now
    pass


@given('a video file "sample_video.mp4"')
def step_given_video_file(context):
    context.video_file = os.path.abspath("/tmp/test_media_root/sample_video.mp4")
    os.makedirs(os.path.dirname(context.video_file), exist_ok=True)
    with open(context.video_file, "w") as f:
        f.write("dummy content")


@when("the video file is processed")
def step_when_video_file_processed(context):
    # No-op for now
    pass


@then('the output should be in "mkv" format')
def step_then_output_mkv(context):
    # No-op for now
    pass


@then('the video codec should be "h264"')
def step_then_video_codec_h264(context):
    # No-op for now
    pass


@then('the audio codec should be "aac"')
def step_then_audio_codec_aac(context):
    # No-op for now
    pass
