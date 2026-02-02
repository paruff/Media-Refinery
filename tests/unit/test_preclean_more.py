from pathlib import Path

from app.services.preclean import PrecleanDetector


def test_detect_conflicts_all_flags():
    detector = PrecleanDetector()
    files_meta = [
        {
            "Title": "Movie A",
            "Year": "1999",
            "Resolution": "1080p",
            "Cut": "theatrical",
            "AudioCodec": "aac",
        },
        {
            "Title": "Movie A",
            "Year": "2001",
            "Resolution": "720p",
            "Cut": "director's cut",
            "AudioCodec": "dts",
        },
        {
            "Title": "Movie A",
            "Year": "1999",
            "Resolution": "4k",
            "Cut": "theatrical",
            "AudioCodec": "aac",
        },
    ]

    flags = detector.detect_conflicts(files_meta)

    assert "Different years" in flags
    assert "Different resolutions" in flags
    assert "Different cuts" in flags
    assert "Different audio codecs" in flags


def test_contains_non_utf8_surrogate():
    detector = PrecleanDetector()
    # Include a lone low surrogate which cannot be encoded to UTF-8
    bad = "bad" + chr(0xDC00) + "name"
    assert detector.contains_non_utf8(bad) is True


def test_illegal_filesystem_chars():
    detector = PrecleanDetector()
    filename = "fi<le>name?.mp3"
    illegal = detector.illegal_filesystem_chars(filename)
    for c in ["<", ">", "?"]:
        assert c in illegal


def test_classify_unplaced():
    detector = PrecleanDetector()
    p = Path("/Media/Random/file.mp3")
    assert detector.classify_unplaced(p) == "unclassified"
    p2 = Path("/Media/Movies/Film.mp4")
    assert detector.classify_unplaced(p2) == "classified"
