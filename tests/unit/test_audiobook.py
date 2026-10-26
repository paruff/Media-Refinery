import json
from pathlib import Path

from app.core.planning import build_plan
from app.media.audiobook import (
    audio_args,
    book_dir,
    chapters_from_silence,
    concat_list,
    ffmetadata,
    natural_key,
    parse_cue,
)
from app.models.media import MediaItem, MediaType


def test_natural_order():
    names = ["10.mp3", "2.mp3", "1.mp3", "Disc 2/01.mp3", "Disc 1/02.mp3"]
    assert sorted(names, key=natural_key) == [
        "1.mp3",
        "2.mp3",
        "10.mp3",
        "Disc 1/02.mp3",
        "Disc 2/01.mp3",
    ]


def test_book_dir_spans_disc_folders_but_loose_files_stand_alone(tmp_path):
    (tmp_path / "Book" / "CD1").mkdir(parents=True)
    deep = tmp_path / "Book" / "CD1" / "01.mp3"
    assert book_dir(deep, tmp_path) == tmp_path / "Book"
    loose = tmp_path / "x.m4b"
    assert book_dir(loose, tmp_path) == loose


def test_cue_chapters():
    cue = (
        'FILE "b.mp3" MP3\n'
        '  TRACK 01 AUDIO\n    TITLE "Intro"\n    INDEX 01 00:00:00\n'
        "  TRACK 02 AUDIO\n    INDEX 01 01:30:37\n"
    )
    chapters = parse_cue(cue, 300.0)
    assert [c["title"] for c in chapters] == ["Intro", "Chapter 2"]
    assert chapters[0]["end"] == chapters[1]["start"] == 90 + 37 / 75
    assert chapters[1]["end"] == 300.0


def test_silence_chapters_skip_short_ones():
    err = (
        "silence_start: 10\nsilence_end: 12\n"  # too early: merged
        "silence_start: 100\nsilence_end: 104\n"
        "silence_start: 290\nsilence_end: 292\n"  # too close to the end
    )
    chapters = chapters_from_silence(err, 300.0)
    assert [(c["start"], c["end"]) for c in chapters] == [(0.0, 102.0), (102.0, 300.0)]


def test_ffmetadata_escapes():
    text = ffmetadata([{"title": "A=B;C", "start": 0, "end": 1.5}])
    assert "END=1500" in text and "title=A\\=B\\;C" in text


def test_concat_list_quotes():
    assert concat_list(["/a/it's.mp3"]) == "file '/a/it'\\''s.mp3'\n"


def test_audio_args():
    aac = {"codec_name": "aac", "sample_rate": "44100", "channels": 2}
    assert audio_args([aac, aac]) == ["-vn", "-c:a", "copy"]
    mp3 = {"codec_name": "mp3", "channels": 2, "bit_rate": "320000"}
    assert audio_args([mp3])[-1] == "128k"  # capped
    mono = {"codec_name": "mp3", "channels": 1, "bit_rate": "32000"}
    assert audio_args([mono]) == ["-vn", "-c:a", "aac", "-ac", "1", "-b:a", "32k"]
    surround = {"codec_name": "ac3", "channels": 6}
    assert audio_args([surround])[4] == "2"


def _item(**book):
    base = {"title": "T: One", "author": "A", "ffmpeg_args": ["-c:a", "aac"]}
    item = MediaItem(media_type=MediaType.audiobook, source_path="/x")
    item.enrichment_data = json.dumps({"book": {**base, **book}})
    return item


def test_layout_with_and_without_series(tmp_path):
    root = str(tmp_path)
    spec = build_plan(_item(series="S", sequence="3"), {"audiobook": root})
    assert Path(spec.target_path) == tmp_path.resolve() / "A/S/3 - T- One/T- One.m4b"
    spec = build_plan(_item(), {"audiobook": root})
    assert Path(spec.target_path) == tmp_path.resolve() / "A/T- One/T- One.m4b"
