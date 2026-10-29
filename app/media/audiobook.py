"""Audiobooks (R-BOOK-1..5): natural-order merge, chapters, AAC M4B, Audiobookshelf tags."""

import json
import re
from pathlib import Path

from mutagen.mp4 import MP4, MP4Cover

from app.core.tools import run_tool

MIN_CHAPTER = 60.0  # seconds; silence-detected chapters shorter than this are merged
SILENCE = "silencedetect=noise=-35dB:d=2"
CAPS_KBPS = {1: 64, 2: 128}  # R-BOOK-1: mono / stereo ceilings
FFPROBE = [
    "ffprobe",
    "-v",
    "error",
    "-show_format",
    "-show_streams",
    "-show_chapters",
    "-of",
    "json",
]
NULL = ["-f", "null", "-"]
FREEFORM = "----:com.apple.iTunes:"


def natural_key(path: Path | str) -> list:
    """'2.mp3' < '10.mp3': digit runs compare as numbers (R-BOOK-5)."""
    parts = re.split(r"(\d+)", str(path).lower())
    return [int(p) if p.isdigit() else p for p in parts]


DISC_FOLDER = re.compile(r"^(cd|disc|disk|part)[\s._-]*\d+$", re.IGNORECASE)


def book_dir(path: str | Path, input_dir: Path) -> Path:
    """The unit merged into one book: the folder holding the audio, with a CD1/Disc 2/Part 3
    folder folded into its parent. Loose files directly in input/ stand alone."""
    path = Path(path)
    try:
        rel = path.resolve().relative_to(input_dir.resolve())
    except ValueError:
        return path
    folders = rel.parts[:-1]
    if not folders:
        return path
    if len(folders) > 1 and DISC_FOLDER.match(folders[-1]):
        folders = folders[:-1]
    return input_dir.joinpath(*folders)


def _stamp(text: str) -> float:
    minutes, seconds, frames = (int(x) for x in text.split(":"))
    return minutes * 60 + seconds + frames / 75


def parse_cue(text: str, total: float) -> list[dict]:
    """Chapters from a single-file CUE sheet; INDEX 01 starts a track. A sheet naming more than
    one FILE has per-file timestamps we would misread, so it yields no chapters."""
    if sum(raw.strip().startswith("FILE ") for raw in text.splitlines()) > 1:
        return []
    starts: list[tuple[str, float]] = []
    title = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("TRACK"):
            title = f"Chapter {len(starts) + 1}"
        elif line.startswith("TITLE") and title:
            title = line[5:].strip().strip('"') or title
        elif line.startswith("INDEX 01"):
            starts.append((title, _stamp(line.split()[-1])))
    return _close(starts, total)


def _close(starts: list[tuple[str, float]], total: float) -> list[dict]:
    ends = [s for _, s in starts[1:]] + [total]
    return [
        {"title": t, "start": s, "end": e}
        for (t, s), e in zip(starts, ends, strict=True)
    ]


def chapters_from_silence(stderr: str, total: float) -> list[dict]:
    """Cut at the middle of each silence; chapters under MIN_CHAPTER are merged forward."""
    begins = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", stderr)]
    cuts = [0.0]
    for a, b in zip(begins, ends, strict=False):
        mid = (a + b) / 2
        if mid - cuts[-1] >= MIN_CHAPTER and total - mid >= MIN_CHAPTER:
            cuts.append(mid)
    return _close([(f"Chapter {n}", s) for n, s in enumerate(cuts, 1)], total)


def ffmetadata(chapters: list[dict]) -> str:
    esc = lambda s: re.sub(r"([=;#\\\n])", r"\\\1", s)  # noqa: E731
    out = [";FFMETADATA1"]
    for c in chapters:
        out += ["[CHAPTER]", "TIMEBASE=1/1000"]
        out += [f"START={round(c['start'] * 1000)}", f"END={round(c['end'] * 1000)}"]
        out.append(f"title={esc(c['title'])}")
    return "\n".join(out) + "\n"


def has_newline(files: list[str]) -> bool:
    """The concat demuxer list is line based, so such names go through the concat filter."""
    return any("\n" in f or "\r" in f for f in files)


def concat_list(files: list[str]) -> str:
    quote = lambda f: f.replace("'", "'\\''")  # noqa: E731
    return "".join(f"file '{quote(f)}'\n" for f in files)


def concat_inputs(book: dict, listing: str) -> tuple[list[str], int, list[str]]:
    """(ffmpeg input args, number of inputs, audio map). Uniform files use the concat demuxer;
    mixed codecs/rates/channels need the concat filter after resampling to one format."""
    files = book["files"]
    if not book.get("mixed"):
        return ["-f", "concat", "-safe", "0", "-i", listing], 1, ["-map", "0:a"]
    layout = "mono" if int(book.get("channels") or 2) == 1 else "stereo"
    rate = int(book.get("sample_rate") or 44100)
    legs = "".join(
        f"[{i}:a:0]aresample={rate},aformat=sample_fmts=fltp:channel_layouts={layout}[a{i}];"
        for i in range(len(files))
    )
    joined = "".join(f"[a{i}]" for i in range(len(files)))
    graph = f"{legs}{joined}concat=n={len(files)}:v=0:a=1[out]"
    inputs = [arg for f in files for arg in ("-i", f)]
    return [*inputs, "-filter_complex", graph], len(files), ["-map", "[out]"]


def part_gaps(files: list[Path]) -> bool:
    """True when numbered parts (01, 02, 04 ...) skip a number within a folder."""
    by_folder: dict[Path, list[int]] = {}
    for f in files:
        match = re.search(r"\d+", f.stem)
        if match is None:
            return False  # not a numbered set: nothing to check
        by_folder.setdefault(f.parent, []).append(int(match.group(0)))
    return any(
        len(set(nums)) > 1
        and sorted(set(nums)) != list(range(min(nums), max(nums) + 1))
        for nums in by_folder.values()
    )


def audio_args(streams: list[dict]) -> list[str]:
    """R-BOOK-1: copy when every file is the same AAC, else AAC-LC capped per channel count
    and never above the source bitrate."""
    sig = {
        (s.get("codec_name"), s.get("sample_rate"), s.get("channels")) for s in streams
    }
    if len(sig) == 1 and next(iter(sig))[0] == "aac":
        return ["-vn", "-c:a", "copy"]
    channels = min(int(streams[0].get("channels") or 2), 2)
    rates = [int(s["bit_rate"]) // 1000 for s in streams if s.get("bit_rate")]
    kbps = min([CAPS_KBPS[channels], *rates])
    return ["-vn", "-c:a", "aac", "-ac", str(channels), "-b:a", f"{max(kbps, 16)}k"]


async def _probe(path: Path) -> dict:
    rc, out, _ = await run_tool(
        [*FFPROBE, str(path)],
        120,
    )
    return json.loads(out) if rc == 0 else {}


def _tags(probe: dict) -> dict[str, str]:
    return {k.lower(): v for k, v in probe.get("format", {}).get("tags", {}).items()}


def _first(tags: dict, *keys: str) -> str | None:
    return next(
        (str(tags[k]).strip() for k in keys if str(tags.get(k) or "").strip()), None
    )


def _year(value: str | None) -> str | None:
    match = re.match(r"\d{4}", value or "")
    return match.group(0) if match else None


async def _single_file_chapters(
    path: Path, probe: dict, total: float, title: str
) -> tuple[list[dict], bool]:
    """(chapters, detection_failed): failed means silencedetect timed out or errored."""
    if probe.get("chapters"):
        return [
            {
                "title": c.get("tags", {}).get("title") or f"Chapter {n}",
                "start": float(c["start_time"]),
                "end": float(c["end_time"]),
            }
            for n, c in enumerate(probe["chapters"], 1)
        ], False
    cue = path.with_suffix(".cue")
    if cue.is_file() and (
        chapters := parse_cue(cue.read_text(errors="replace"), total)
    ):
        return chapters, False
    rc, _, err = await run_tool(
        ["ffmpeg", "-nostdin", "-v", "info", "-i", str(path), "-af", SILENCE, *NULL],
        3600,
    )
    chapters = chapters_from_silence(err, total)
    if len(chapters) == 1:
        chapters[0]["title"] = title
    return chapters, rc != 0


async def describe_book(files: list[Path], fallback_title: str) -> dict:
    """Everything the plan, the encode and the tags need, from the sources in natural order."""
    files = sorted(files, key=natural_key)
    probes = [await _probe(f) for f in files]
    streams: list[dict] = [
        next((s for s in p.get("streams", []) if s.get("codec_type") == "audio"), {})
        for p in probes
    ]
    durations = [float(p.get("format", {}).get("duration") or 0) for p in probes]
    tags: dict[str, str] = {}
    for p in reversed(probes):  # the first file wins
        tags.update(_tags(p))
    title = (
        _first(tags, "album")
        or (_first(tags, "title") if len(files) == 1 else None)
        or fallback_title
    )
    total = sum(durations)
    chapters_failed = False
    if len(files) == 1:
        chapters, chapters_failed = await _single_file_chapters(
            files[0], probes[0], total, title
        )
    else:
        starts, at = [], 0.0
        for f, p, d in zip(files, probes, durations, strict=True):
            name = _first(_tags(p), "title")
            starts.append((name or f.stem, at))
            at += d
        chapters = _close(starts, total)
    signatures = {
        (s.get("codec_name"), s.get("sample_rate"), s.get("channels")) for s in streams
    }
    return {
        "mixed": len(signatures) > 1 or has_newline([str(f) for f in files]),
        "chapters_failed": chapters_failed,
        "sample_rate": int(streams[0].get("sample_rate") or 44100),
        "channels": min(int(streams[0].get("channels") or 2), 2),
        "gaps": part_gaps(files),
        "files": [str(f) for f in files],
        "title": title,
        "author": _first(tags, "artist", "album_artist") or "Unknown Author",
        "narrator": _first(tags, "narrator", "composer"),
        "series": _first(tags, "series", "grouping"),
        "sequence": _first(tags, "series-part", "series_part", "seriespart"),
        "year": _year(_first(tags, "date", "year")),
        "description": _first(tags, "description", "synopsis", "comment"),
        "asin": _first(tags, "asin"),
        "isbn": _first(tags, "isbn"),
        "duration": total,
        "chapters": chapters,
        "ffmpeg_args": audio_args(streams),
    }


def tag_m4b(path: Path, book: dict, cover: bytes | None) -> None:
    """R-BOOK-3: title, author (artist), narrator (composer), series + sequence, year,
    description, ASIN/ISBN and the embedded cover."""
    audio = MP4(path)
    audio.delete()  # chapters live in their own atom; only the ilst is replaced
    mapping = {
        "\xa9nam": book["title"],
        "\xa9alb": book["title"],
        "\xa9ART": book["author"],
        "aART": book["author"],
        "\xa9wrt": book.get("narrator"),
        "\xa9day": book.get("year"),
        "desc": book.get("description"),
        "\xa9gen": "Audiobook",
    }
    for key, value in mapping.items():
        if value:
            audio[key] = [str(value)]
    audio["stik"] = [2]  # media kind: audiobook
    for name, key in (
        ("SERIES", "series"),
        ("SERIES-PART", "sequence"),
        ("ASIN", "asin"),
        ("ISBN", "isbn"),
    ):
        if book.get(key):
            audio[FREEFORM + name] = [str(book[key]).encode()]
    if cover:
        png = cover[:4] == b"\x89PNG"
        fmt = MP4Cover.FORMAT_PNG if png else MP4Cover.FORMAT_JPEG
        audio["covr"] = [MP4Cover(cover, imageformat=fmt)]
    audio.save()
