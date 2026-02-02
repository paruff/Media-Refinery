from app.services.preclean import PrecleanDetector


def test_scan_metadata_flags_missing_tags(mock_ffprobe, tmp_path, mocker):
    """Red test: with empty metadata, detector must flag required missing tags."""
    f = tmp_path / "song.mp3"
    f.write_bytes(b"dummy")

    detector = PrecleanDetector()

    # Force no metadata returned (simulate missing tags)
    mocker.patch.object(PrecleanDetector, "_read_metadata", return_value={})

    flags = detector.scan_metadata(f)

    assert "missing:Title" in flags
    assert "missing:Year" in flags
    assert "missing:Artist/Album" in flags
