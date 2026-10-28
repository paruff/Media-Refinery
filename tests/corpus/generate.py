"""Generated "messy library" corpus (G15). Nothing here is committed media: every file is
synthesised with ffmpeg (or mutagen for the bulk filler) into a caller-supplied directory."""

from __future__ import annotations

import shutil
import unicodedata
from pathlib import Path

from tests.pipeline_helpers import _ffmpeg, make_mkv


def tone(
    path: Path,
    codec: str = "libmp3lame",
    seconds: int = 1,
    freq: int = 440,
    rate: int = 44100,
    extra: tuple[str, ...] = (),
    **tags: str,
) -> Path:
    """One short sine file; `extra` carries encoder flags (e.g. VBR), `tags` are -metadata."""
    meta = [a for k, v in tags.items() for a in ("-metadata", f"{k}={v}")]
    path.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg(
        *("-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}"),
        *("-ar", str(rate), *meta, "-c:a", codec, *extra, str(path)),
    )
    return path


def messy(root: Path) -> dict[str, list[Path]]:
    """Write the hand-built messy library under `root`; return {category: [paths]}."""
    made: dict[str, list[Path]] = {}

    def add(kind: str, p: Path) -> Path:
        made.setdefault(kind, []).append(p)
        return p

    # a clean, fully tagged album: the control group
    for n in (1, 2, 3):
        add("clean", tone(root / "Clean/Album One" / f"{n:02d}.mp3", freq=300 + n,
            artist="Artist A", album="Album One", title=f"One {n}", track=str(n), date="2019"))  # fmt: skip

    # multi-disc with overlapping track numbers
    for disc in (1, 2):
        for n in (1, 2):
            add("multidisc", tone(root / f"Multi/Disc {disc}" / f"{n:02d}.mp3", freq=400 + disc * 10 + n,
                artist="Artist B", album="Album Two", title=f"Two {disc}.{n}",
                track=f"{n}/2", disc=f"{disc}/2", date="2015"))  # fmt: skip

    # missing tags: no tags at all, and a track with only a title
    add("untagged", tone(root / "Misc/track01.mp3", freq=500))
    add("untagged", tone(root / "Misc/only title.mp3", freq=501, title="Only A Title"))

    # contradictory tags inside one folder (artist/album disagree between tracks)
    add("contradictory", tone(root / "Contradictory/a.mp3", freq=510,
        artist="Artist C", album="Album Three", title="C1", track="1", date="2001"))  # fmt: skip
    add("contradictory", tone(root / "Contradictory/b.mp3", freq=511,
        artist="Artist D", album="Album 3 (Remaster)", title="C2", track="1", date="2011"))  # fmt: skip

    # duplicate albums: byte-identical copy, and a re-encode of the same content
    for n in (1, 2):
        add("dupe", tone(root / "Dupes/Album Four" / f"{n:02d}.mp3", freq=600 + n,
            artist="Artist E", album="Album Four", title=f"Four {n}", track=str(n), date="2005"))  # fmt: skip
    shutil.copytree(root / "Dupes/Album Four", root / "Dupes/Album Four (copy)")
    add("dupe", root / "Dupes/Album Four (copy)/01.mp3")
    add("dupe", tone(root / "Dupes/Album Four (re-encode)/01.mp3", freq=601, rate=48000,
        artist="Artist E", album="Album Four", title="Four 1", track="1", date="2005"))  # fmt: skip

    # lossy next to lossless, same track
    for codec, ext in (("flac", "flac"), ("libmp3lame", "mp3")):
        add("lossy_lossless", tone(root / f"Both/Album Five/01.{ext}", codec=codec, freq=700,
            artist="Artist F", album="Album Five", title="Five 1", track="1", date="2020"))  # fmt: skip

    # odd filenames and unicode: NFC and NFD of the same name, CJK, emoji, long, trailing dot
    name = "Björk – Jóga (日本語) ♪"  # noqa: RUF001 (the odd characters are the point)
    add("unicode", tone(root / "Unicode" / f"{unicodedata.normalize('NFC', name)}.mp3", freq=710,
        artist="Björk", album="Homogenic", title="Jóga", track="3", date="1997"))  # fmt: skip
    add("unicode", tone(root / "Unicode" / f"{unicodedata.normalize('NFD', name)} 2.mp3", freq=711,
        artist="Björk", album="Homogenic", title="Bachelorette", track="4", date="1997"))  # fmt: skip
    add("unicode", tone(root / "Unicode" / ("long " * 40 + ".mp3"), freq=712,
        artist="Long Name", album="Long", title="L" * 120, track="1"))  # fmt: skip
    add("unicode", tone(root / "Unicode/we:ird*na?me|.mp3", freq=713,
        artist="A/C D/C", album="Back In Black", title="What/Ever", track="1", date="1980"))  # fmt: skip

    # mixed sample rates and VBR vs CBR in one album
    for i, (rate, extra) in enumerate(
        [(22050, ()), (44100, ("-q:a", "2")), (48000, ("-b:a", "320k"))], start=1
    ):
        add("mixed_rates", tone(root / "Mixed/Album Six" / f"{i:02d}.mp3", freq=720 + i, rate=rate,
            extra=extra, artist="Artist G", album="Album Six", title=f"Six {i}", track=str(i), date="2012"))  # fmt: skip

    # broken files: truncated, zero-byte, garbage with a media extension
    good = tone(root / "Broken/src.flac", codec="flac", seconds=2, freq=730,
        artist="Artist H", album="Album Seven", title="Seven 1", track="1")  # fmt: skip
    add("truncated", good.rename(root / "Broken/truncated.flac"))
    trunc = root / "Broken/truncated.flac"
    trunc.write_bytes(trunc.read_bytes()[: trunc.stat().st_size // 3])
    add("zero_byte", _write(root / "Broken/empty.mp3", b""))
    add("garbage", _write(root / "Broken/garbage.mp3", b"this is not audio " * 50))

    # a movie, and non-media clutter beside the music
    add("movie", make_mkv(_mk(root / "Movies/Messy Movie (2018).mkv"), seconds=1))
    _write(root / "Clean/Album One/notes.txt", b"ripped by hand\n")
    return made


def bulk(root: Path, files: int, template_dir: Path) -> int:
    """Add filler tracks until `root` holds `files` files in total; return how many were added.

    Copies a tagged template and rewrites its tags with mutagen, so each file is unique
    without paying for one ffmpeg run per file.
    """
    from mutagen.easyid3 import EasyID3

    template = tone(template_dir / "filler.mp3", seconds=1)
    have = sum(1 for p in root.rglob("*") if p.is_file())
    for i in range(max(0, files - have)):
        dest = (
            root
            / f"Bulk/Artist {i // 100:02d}/Album {i // 10:03d}/{i % 10 + 1:02d}.mp3"
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template, dest)
        tags = EasyID3()
        tags.update({
            "artist": f"Bulk Artist {i // 100:02d}", "album": f"Bulk Album {i // 10:03d}",
            "title": f"Bulk Track {i}", "tracknumber": str(i % 10 + 1), "date": "2010",
        })  # fmt: skip
        tags.save(dest)
    return max(0, files - have)


def _mk(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write(path: Path, data: bytes) -> Path:
    _mk(path).write_bytes(data)
    return path
