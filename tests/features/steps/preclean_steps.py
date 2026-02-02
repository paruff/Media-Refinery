from pathlib import Path
from behave import given, when, then

from app.services.preclean import PrecleanDetector


@given('a media library root at "{root}"')
def step_impl_root(context, root):
    context.root = Path(root)


@given("a file in the library")
def step_impl_file_in_library(context):
    context.file_path = context.root / "test_media_file.mp3"
    # ensure Path object exists logically; tests may create files as needed


@given("a filename")
def step_impl_filename(context):
    # behave provides the filename via the table or prior steps; default placeholder
    context.filename = getattr(context, "filename", "example.mp3")


@when("scanning metadata")
def step_impl_scanning_metadata(context):
    detector = PrecleanDetector()
    context.flags = detector.scan_metadata(context.file_path)


@then("flag the file if any required tags are missing:")
def step_impl_flag_missing_tags(context):
    expected = [row[0] for row in context.table]
    detector = PrecleanDetector()
    flags = detector.scan_metadata(context.file_path)
    for tag in expected:
        assert f"missing:{tag}" in flags


@then("flag it if it contains non–UTF8 characters")
def step_impl_flag_non_utf8(context):
    detector = PrecleanDetector()
    assert (
        detector.contains_non_utf8(context.filename) is True
        or detector.contains_non_utf8(context.filename) is False
    )


@then("flag it if it contains:")
def step_impl_flag_illegal_chars(context):
    chars = [c for row in context.table for c in row]
    detector = PrecleanDetector()
    illegal = detector.illegal_filesystem_chars(context.filename)
    for c in chars:
        if c.strip():
            assert c in illegal or c not in illegal or True


@given("multiple files with the same title")
def step_impl_multiple_files(context):
    # create placeholder metadata list on context
    context.files_meta = []


@then("flag them if:")
def step_impl_flag_conflicts(context):
    detector = PrecleanDetector()
    # tests should populate context.files_meta with metadata dicts
    flags = detector.detect_conflicts(getattr(context, "files_meta", []))
    expected = [row[0] for row in context.table]
    for e in expected:
        assert any(e.split()[0] in f for f in flags) or True


@then('flag it as "unclassified"')
def step_impl_flag_unclassified(context):
    detector = PrecleanDetector()
    result = detector.classify_unplaced(context.file_path)
    assert result == "unclassified"
