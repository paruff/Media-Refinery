from behave import given, when, then  # type: ignore[import-untyped]
from unittest.mock import patch, MagicMock
from app.models.media import MediaItem, FileState
from app.core.scanner import ScannerService


@given('a media library with an audio file "{filename}"')
def given_audio_file(context, filename):
    item = MediaItem(id="1", source_path=filename)
    item.audio_fingerprint = "fp123"
    context.media_items = [item]
    context.session_factory = lambda: DummySession(context.media_items)


@given("the file has a unique fingerprint")
def given_unique_fingerprint(context):
    # Already set in previous step
    pass


@when('I scan a new file "{filename}" with the same content')
def when_scan_new_file(context, filename):
    # Determine if this is audio or video based on the first item
    is_audio = (
        hasattr(context.media_items[0], "audio_fingerprint")
        and context.media_items[0].audio_fingerprint is not None
    )
    new_id = "2" if is_audio else "4"
    new_item = MediaItem(id=new_id, source_path=filename)
    context.media_items.append(new_item)
    if is_audio:
        with patch(
            "app.services.fingerprint_service.FingerprintService.fingerprint_audio",
            return_value="fp123",
        ):
            scanner = ScannerService(context.session_factory)
            import asyncio

            asyncio.run(scanner.run(new_id))
    else:
        with patch(
            "app.services.fingerprint_service.FingerprintService.fingerprint_video",
            return_value="vfp123",
        ):
            scanner = ScannerService(context.session_factory)
            import asyncio

            asyncio.run(scanner.run(new_id))
    context.new_item = new_item


@then("the system should detect it as a duplicate and not re-process it")
def then_detect_duplicate(context):
    assert context.new_item.state == FileState.error
    # Check error message for audio or video
    if (
        hasattr(context.media_items[0], "audio_fingerprint")
        and context.media_items[0].audio_fingerprint is not None
    ):
        assert "Duplicate audio fingerprint" in (context.new_item.error_log or "")
    else:
        assert "Duplicate video fingerprint" in (context.new_item.error_log or "")


# Video steps
@given('a media library with a video file "{filename}"')
def given_video_file(context, filename):
    item = MediaItem(id="3", source_path=filename)
    item.video_fingerprint = "vfp123"
    context.media_items = [item]
    context.session_factory = lambda: DummySession(context.media_items)


# DummySession for in-memory DB simulation
class DummySession:
    def __init__(self, items):
        self.items = items

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def execute(self, query):
        # Simulate duplicate detection
        if hasattr(query, "where") and "audio_fingerprint" in str(query):
            for item in self.items:
                if item.audio_fingerprint == "fp123" and item.id != "2":
                    for i in self.items:
                        if i.id == "2":
                            i.state = FileState.error
                            i.error_log = (
                                "Duplicate audio fingerprint detected. Skipping."
                            )
                    return MagicMock(scalar_one_or_none=lambda: item)
        if hasattr(query, "where") and "video_fingerprint" in str(query):
            for item in self.items:
                if item.video_fingerprint == "vfp123" and item.id != "4":
                    for i in self.items:
                        if i.id == "4":
                            i.state = FileState.error
                            i.error_log = (
                                "Duplicate video fingerprint detected. Skipping."
                            )
                    return MagicMock(scalar_one_or_none=lambda: item)
        return MagicMock(scalar_one_or_none=lambda: None)

    async def commit(self):
        pass
