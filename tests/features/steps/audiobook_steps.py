import asyncio
import io
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import mutagen
from behave import given, then  # type: ignore[import-untyped]
from mutagen.id3 import APIC
from PIL import Image

from app.core.orchestrator import PipelineOrchestrator
from tests.pipeline_helpers import (
    import_input,
    make_config,
    make_mp3,
    make_session_factory,
)

FFPROBE = [
    *("ffprobe", "-v", "error", "-show_format", "-show_streams"),
    *("-show_chapters", "-of", "json"),
]
TITLES = ["Chapter One", "Chapter Two", "Chapter Three"]


def _run(context, coro):
    return context.spine_loop.run_until_complete(coro)


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (600, 600), "green").save(buf, "PNG")
    return buf.getvalue()


@given("an audiobook workspace")
def step_workspace(context):
    if not shutil.which("ffmpeg"):
        context.scenario.skip("ffmpeg not installed (see `make docker-test`)")
        return
    tmp = tempfile.TemporaryDirectory()
    context.add_cleanup(tmp.cleanup)
    base = Path(tmp.name)
    context.spine_loop = asyncio.new_event_loop()
    context.add_cleanup(context.spine_loop.close)
    context.cfg = make_config(base, auto_approve_types=frozenset({"audiobook"}))
    engine, context.factory = _run(context, make_session_factory(base))
    context.add_cleanup(lambda: _run(context, engine.dispose()))
    context.orch = PipelineOrchestrator(context.factory, context.cfg)


def _book(context, title, names, series=None, mono=False, kbps=None, titles=None):
    titles = titles or dict(zip(names, TITLES, strict=False))
    folder = context.cfg.input_dir / title
    folder.mkdir()
    context.seconds = []
    for n, name in enumerate(names):
        path = folder / name
        tags = {
            "title": titles[name],
            "album": title,
            "artist": "Test Author",
            "composer": "Test Narrator",
            "genre": "Audiobook",
            "date": "2019",
            "comment": "A generated test book.",
        }
        if series:
            tags.update(series=series[0], **{"series-part": series[1]})
        # distinct audio per chapter, or duplicate detection skips the later ones
        make_mp3(path, seconds=2 + n, freq=330 + 110 * n, **tags)
        if mono or kbps:
            _reencode(path, mono, kbps, tags)
        context.seconds.append(2 + n)
        if n == 0:
            audio = mutagen.File(path)
            audio.tags.add(APIC(encoding=3, mime="image/png", type=3, data=_png()))
            audio.save()
    _run(context, import_input(context.cfg, context.factory))


def _reencode(path, mono, kbps, tags):
    tmp = path.with_name("re.mp3")
    meta = [a for k, v in tags.items() for a in ("-metadata", f"{k}={v}")]
    args = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(path), *meta]
    args += ["-c:a", "libmp3lame", *(["-ac", "1"] if mono else [])]
    args += ["-b:a", f"{kbps or 64}k", str(tmp)]
    subprocess.run(args, check=True)
    tmp.replace(path)


@given('a generated book "{title}" of 3 MP3 chapters in series "{series}" book {part}')
def step_series_book(context, title, series, part):
    _book(context, title, ["01.mp3", "02.mp3", "03.mp3"], (series, part))


@given('a generated book "{title}" of 3 MP3 chapters named "{a}", "{b}", "{c}"')
def step_named_book(context, title, a, b, c):
    by_number = sorted([a, b, c], key=lambda name: int(name.split(".")[0]))
    _book(context, title, [a, b, c], titles=dict(zip(by_number, TITLES, strict=True)))


@given('a generated book "{title}" of {count:d} MP3 chapters')
def step_plain_book(context, title, count):
    _book(context, title, [f"{n + 1:02d}.mp3" for n in range(count)])


@given('a generated book "{title}" of 2 mono MP3 chapters at {kbps:d} kbps')
def step_mono_book(context, title, kbps):
    _book(context, title, ["01.mp3", "02.mp3"], mono=True, kbps=kbps)


def _m4b(context) -> Path:
    books = list(context.cfg.audiobooks_root.rglob("*.m4b"))
    assert len(books) == 1, (books, list(context.cfg.audiobooks_root.rglob("*")))
    return books[0]


def _probe(path: Path) -> dict:
    out = subprocess.run(
        [*FFPROBE, str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(out)


@then('the book is published at "{rel}"')
def step_path(context, rel):
    assert _m4b(context) == (context.cfg.audiobooks_root / rel).resolve()


@then("it is a single AAC file")
def step_aac(context):
    audio = [s for s in _probe(_m4b(context))["streams"] if s["codec_type"] == "audio"]
    assert [s["codec_name"] for s in audio] == ["aac"], audio
    assert int(audio[0]["channels"]) <= 2


@then('it has 3 chapters titled "{a}", "{b}", "{c}"')
@then('the chapter titles in order are "{a}", "{b}", "{c}"')
def step_chapters(context, a, b, c):
    chapters = _probe(_m4b(context))["chapters"]
    assert [ch["tags"]["title"] for ch in chapters] == [a, b, c], chapters


@then("its duration matches the 3 sources within 0.5 s")
def step_duration(context):
    got = float(_probe(_m4b(context))["format"]["duration"])
    assert abs(got - sum(context.seconds)) <= 0.5, (got, context.seconds)


@then("it carries the R-BOOK-3 tags")
def step_tags(context):
    tags = mutagen.File(_m4b(context)).tags
    text = lambda key: tags[key][0]  # noqa: E731
    assert text("\xa9nam") == "The Test Book" and text("\xa9ART") == "Test Author"
    assert text("\xa9wrt") == "Test Narrator" and text("\xa9day") == "2019"
    assert text("desc") == "A generated test book."
    free = lambda name: bytes(tags[f"----:com.apple.iTunes:{name}"][0]).decode()  # noqa: E731
    assert free("SERIES") == "Test Saga" and free("SERIES-PART") == "2"


@then("it embeds a cover")
def step_cover(context):
    covr = mutagen.File(_m4b(context)).tags["covr"]
    assert min(Image.open(io.BytesIO(bytes(covr[0]))).size) >= 500


@then("the source chapters are archived")
def step_archived(context):
    assert not list(context.cfg.input_dir.rglob("*.mp3"))
    assert len(list(context.cfg.archive_dir.rglob("*.mp3"))) == 3


@then("the published bitrate is at most {kbps:d} kbps")
def step_bitrate(context, kbps):
    audio = [s for s in _probe(_m4b(context))["streams"] if s["codec_type"] == "audio"]
    assert int(audio[0]["bit_rate"]) <= kbps * 1000, audio
    assert int(audio[0]["channels"]) == 1
