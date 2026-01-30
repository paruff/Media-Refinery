import pytest
from app.models.media import MediaItem, FileState, MediaType
from app.services.auditor import IssueDetectorService


@pytest.mark.asyncio
async def test_movies_full_integration(async_session):
    # Simulate a movie library with several movies
    movies = [
        MediaItem(
            id=f"mov{i}",
            source_path=f"/movies/Movie {i} (2020)/Movie {i} (2020).mkv",
            state=FileState.enriched,
            media_type=MediaType.movie,
            video_codec="h264",
            audio_codec="aac",
            subtitle_format="srt",
            year="2020",
        )
        for i in range(1, 4)
    ]
    for item in movies:
        async_session.add(item)
    await async_session.commit()
    auditor = IssueDetectorService(async_session)
    for item in movies:
        issues, _ = await auditor.audit(item.id)
        assert not issues  # All should be compliant


@pytest.mark.asyncio
async def test_movies_with_issues(async_session):
    # Simulate a movie with bad codecs and image-based subtitles
    item = MediaItem(
        id="badmov1",
        source_path="/movies/BadMovie (2019)/BadMovie (2019).mkv",
        state=FileState.enriched,
        media_type=MediaType.movie,
        video_codec="mpeg2",
        audio_codec="mp2",
        subtitle_format="pgs",
        year="2019",
    )
    async_session.add(item)
    await async_session.commit()
    auditor = IssueDetectorService(async_session)
    issues, _ = await auditor.audit("badmov1")
    codes = {i["code"] for i in issues}
    assert "UNSUPPORTED_VIDEO_CODEC" in codes
    assert "UNSUPPORTED_AUDIO_CODEC" in codes
    assert "IMAGE_BASED_SUBTITLE" in codes
