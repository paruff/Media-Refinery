"""P1 (ebooks to beta): the #101 minors and test gaps, with Calibre mocked."""

import json
import struct
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.verify import verify_ebook
from app.media import ebook
from app.models.media import FileState
from app.pipeline.types.ebook import EbookStrategy
from tests.ebook_helpers import make_epub

pytestmark = [pytest.mark.unit]


# ---- parse_meta -----------------------------------------------------------
def test_parse_meta_keeps_ampersand_names_and_first_value():
    text = (
        "Title               : Q & A\n"
        "Author(s)           : Barnes & Noble & AT&T [Sort]\n"
        "Comments            : Title: not this one\n"
    )
    assert ebook.parse_meta(text) == {
        "title": "Q & A",
        "authors": ["Barnes", "Noble", "AT&T"],
    }
    assert ebook.parse_meta("Title : first\nTitle : second\n")["title"] == "first"


def test_parse_meta_of_garbage_is_empty():
    assert ebook.parse_meta("") == {}
    assert ebook.parse_meta("\x00\x01 no colon here") == {}


# ---- epub_text_length -----------------------------------------------------
def test_epub_text_length_of_a_corrupt_zip_is_zero(tmp_path):
    (tmp_path / "x.epub").write_bytes(b"PK\x03\x04 junk")
    assert ebook.epub_text_length(tmp_path / "x.epub") == 0
    assert ebook.epub_text_length(tmp_path / "missing.epub") == 0


def test_epub_text_length_reads_a_bounded_amount(tmp_path, monkeypatch):
    big = "<p>" + "word " * 1000 + "</p>"
    p = make_epub(tmp_path / "big.epub", "T", "A", {"OEBPS/big.xhtml": big * 50})
    monkeypatch.setattr(ebook, "MAX_HTML_READ", 100)
    assert 0 < ebook.epub_text_length(p, enough=10**9) < 1000


def test_epub_text_length_stops_once_there_is_enough(tmp_path):
    p = make_epub(
        tmp_path / "t.epub", "T", "A", {"OEBPS/a.xhtml": "<p>" + "x" * 500 + "</p>"}
    )
    assert ebook.epub_text_length(p) >= ebook.MIN_PDF_TEXT


# ---- AZW3 DRM -------------------------------------------------------------
def test_drm_azw3_header(tmp_path):
    def azw3(name, encryption):
        header = b"x" * 78 + struct.pack(">I", 86) + b"\0" * 4
        (tmp_path / name).write_bytes(
            header + struct.pack(">HHIHHH", 2, 0, 0, 0, 0, encryption)
        )
        return tmp_path / name

    assert ebook.detect_drm(azw3("a.azw3", 2)) == "mobipocket"
    assert ebook.detect_drm(azw3("b.azw3", 0)) is None
    (tmp_path / "short.azw3").write_bytes(b"tiny")
    assert ebook.detect_drm(tmp_path / "short.azw3") is None


# ---- fetch_meta -----------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_meta_by_title_and_author_and_cover():
    run = AsyncMock(return_value=(0, "Title : Dune\nPublisher : Ace\n", ""))
    with patch("app.media.ebook.run_tool", run):
        got = await ebook.fetch_meta(
            {"title": "Dune", "authors": ["Frank Herbert", "B"]}, Path("/c.jpg")
        )
    assert got == {"title": "Dune", "publisher": "Ace"}
    args = run.await_args.args[0]
    assert args[1:5] == ["--title", "Dune", "--authors", "Frank Herbert & B"]
    assert args[-2:] == ["--cover", "/c.jpg"]


@pytest.mark.asyncio
async def test_fetch_meta_without_isbn_or_title_does_not_call_out():
    run = AsyncMock()
    with patch("app.media.ebook.run_tool", run):
        assert await ebook.fetch_meta({}) == {}
    run.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_meta_miss_and_timeout_are_empty():
    for result in ((1, "", "no results"), (-1, "", "timed out")):
        with patch("app.media.ebook.run_tool", AsyncMock(return_value=result)):
            assert await ebook.fetch_meta({"isbn": "1"}) == {}


# ---- calibredb add: failure and duplicate ---------------------------------
@pytest.mark.asyncio
async def test_calibredb_add_failure_returns_the_error():
    run = AsyncMock(return_value=(1, "", "Invalid EPUB"))
    with patch("app.media.ebook.run_tool", run):
        book_id, err = await ebook.calibredb_add(Path("/l"), Path("/b.epub"), {}, None)
    assert (book_id, err) == (None, "Invalid EPUB")


@pytest.mark.asyncio
async def test_calibredb_add_duplicate_skipped_by_calibre_has_no_id():
    out = "The following books were not added as they already exist in the database"
    with patch("app.media.ebook.run_tool", AsyncMock(return_value=(0, out, ""))):
        assert await ebook.calibredb_add(Path("/l"), Path("/b.epub"), {}, None) == (
            None,
            "",
        )


# ---- publisher / pubdate --------------------------------------------------
@pytest.mark.asyncio
async def test_publisher_and_pubdate_are_written_after_the_add():
    run = AsyncMock(return_value=(0, "", ""))
    meta = {"publisher": "Ace", "published": "1990-09-01T19:11:44+00:00"}
    with patch("app.media.ebook.run_tool", run):
        await ebook.set_extra_fields(Path("/l"), 7, meta)
    args = run.await_args.args[0]
    assert args[:2] == ["calibredb", "set_metadata"] and "7" in args
    assert "publisher:Ace" in args and "pubdate:1990-09-01" in args


@pytest.mark.asyncio
async def test_nothing_to_set_means_no_call():
    run = AsyncMock()
    with patch("app.media.ebook.run_tool", run):
        await ebook.set_extra_fields(Path("/l"), 7, {"title": "T"})
    run.assert_not_awaited()


# ---- epubcheck failure ----------------------------------------------------
@pytest.mark.asyncio
async def test_epubcheck_failure_fails_verification(tmp_path):
    book = make_epub(tmp_path / "b.epub", "T", "A")
    with patch(
        "app.media.ebook.run_tool", AsyncMock(return_value=(1, "ERROR(RSC-005)", ""))
    ):
        checks, _, reason = await verify_ebook(str(book))
    assert reason is not None
    assert next(c for c in checks if c["name"] == "epubcheck")["passed"] is False


@pytest.mark.asyncio
async def test_missing_epubcheck_is_skipped_not_failed(tmp_path):
    book = make_epub(tmp_path / "b.epub", "T", "A")
    with patch(
        "app.media.ebook.run_tool", AsyncMock(return_value=(127, "", "missing"))
    ):
        _, _, reason = await verify_ebook(str(book))
    assert reason is None


# ---- strategy: classify (fetch outcome), build (PDF), publish (duplicate) --
def _orch(tmp_path, fetch=True):
    o = MagicMock()
    o.cfg = SimpleNamespace(
        ebook_fetch=fetch, quarantine_dir=tmp_path / "q", ebooks_root=tmp_path / "lib"
    )
    o._calibre_lock = __import__("asyncio").Lock()
    o._quarantine = AsyncMock()
    return o


def _item(path, **kw):
    return SimpleNamespace(
        id="abcdef1234",
        source_path=str(path),
        state=None,
        enrichment_data=None,
        error_log=None,
        **kw,
    )


@pytest.mark.asyncio
async def test_classify_reports_the_fetch_outcome(tmp_path):
    book = make_epub(tmp_path / "b.epub", "Embedded", "Auth")
    for fetched, outcome in (({"publisher": "Ace"}, "success"), ({}, "skipped")):
        o, item, session = _orch(tmp_path), _item(book), AsyncMock()
        with (
            patch(
                "app.media.ebook.read_meta",
                AsyncMock(return_value={"title": "Embedded"}),
            ),
            patch("app.media.ebook.fetch_meta", AsyncMock(return_value=fetched)),
        ):
            await EbookStrategy().classify(o, session, item)
        o._emit.assert_any_call("enrich", "abcdef1234", outcome)
        meta = json.loads(item.enrichment_data)["ebook"]
        assert meta["title"] == "Embedded" and item.state == FileState.enriched
        assert meta.get("publisher") == fetched.get("publisher")


@pytest.mark.asyncio
async def test_pdf_input_is_converted_and_a_text_pdf_becomes_epub(tmp_path):
    src, tmp = tmp_path / "in.pdf", tmp_path / "out.tmp.epub"
    src.write_bytes(b"%PDF")
    plan = SimpleNamespace(target_path=str(tmp_path / "x.epub"))

    async def convert(source, out, retitle=None):
        make_epub(out, "T", "A", {"OEBPS/c1.xhtml": "<p>" + "text " * 100 + "</p>"})
        return 0, ""

    with (
        patch("app.media.ebook.extract_cover", AsyncMock(return_value=None)),
        patch("app.media.ebook.to_epub", convert),
    ):
        rc, _, out = await EbookStrategy().build(
            _orch(tmp_path, fetch=False), _item(src), plan, src, tmp
        )
    assert rc == 0 and out.suffix == ".epub" and plan.target_path.endswith("x.epub")


@pytest.mark.asyncio
async def test_scanned_pdf_stays_pdf_and_the_retarget_cannot_collide(tmp_path):
    """#188: an epub plan and a pdf plan share a name; the kept-as-PDF target stays unique."""
    src = tmp_path / "scan.pdf"
    src.write_bytes(b"%PDF")

    async def convert(source, out, retitle=None):
        make_epub(out, "T", "A", {"OEBPS/c1.xhtml": "<p></p>"})
        return 0, ""

    async def build(item_id):
        plan = SimpleNamespace(target_path=str(tmp_path / "Same Title.epub"))
        tmp = tmp_path / f"{item_id}.tmp.epub"
        with (
            patch("app.media.ebook.extract_cover", AsyncMock(return_value=None)),
            patch("app.media.ebook.to_epub", convert),
        ):
            item = _item(src)
            item.id = item_id
            await EbookStrategy().build(
                _orch(tmp_path, fetch=False), item, plan, src, tmp
            )
        return plan.target_path

    a, b = await build("aaaaaaaa1"), await build("bbbbbbbb2")
    assert a != b and a.endswith(".pdf") and b.endswith(".pdf")
    assert a != str(tmp_path / "Same Title.epub")  # never the epub plan's name
    assert not zipfile.is_zipfile(src)


@pytest.mark.asyncio
async def test_publish_skips_a_duplicate_that_appeared_since_planning(tmp_path):
    meta = {"title": "Dune", "authors": ["Frank Herbert"], "isbn": "9780441172719"}
    work = tmp_path / "work.epub"
    work.write_bytes(b"x")
    item = _item(work)
    item.enrichment_data = json.dumps({"ebook": meta})
    plan = SimpleNamespace(execution_log="")
    add = AsyncMock()
    with (
        patch("app.media.ebook.find_duplicate", AsyncMock(return_value=3)),
        patch("app.media.ebook.calibredb_add", add),
    ):
        done = await EbookStrategy().publish(
            _orch(tmp_path), AsyncMock(), item, plan, work
        )
    assert done is True and item.state == FileState.published
    add.assert_not_awaited()
    assert "duplicate of calibre id 3" in plan.execution_log


@pytest.mark.asyncio
async def test_publish_adds_and_writes_extra_fields(tmp_path):
    meta = {"title": "Dune", "publisher": "Ace"}
    work = tmp_path / "work.epub"
    work.write_bytes(b"x")
    item = _item(work)
    item.enrichment_data = json.dumps({"ebook": meta})
    extra = AsyncMock()
    with (
        patch("app.media.ebook.find_duplicate", AsyncMock(return_value=None)),
        patch("app.media.ebook.calibredb_add", AsyncMock(return_value=(9, ""))),
        patch("app.media.ebook.set_extra_fields", extra),
    ):
        await EbookStrategy().publish(
            _orch(tmp_path), AsyncMock(), item, SimpleNamespace(execution_log=""), work
        )
    extra.assert_awaited_once()
    assert extra.await_args.args[1] == 9


# ---- placeholder titles ---------------------------------------------------
def test_placeholder_title_comes_from_the_file_name():
    assert (
        ebook.placeholder_title(Path("/in/my_great.book_v2.epub")) == "my great book v2"
    )
    assert ebook.placeholder_title(Path("/in/bare.epub")) == "bare"
    assert (
        ebook.is_untitled(None)
        and ebook.is_untitled("Unknown")
        and ebook.is_untitled(" ")
    )
    assert not ebook.is_untitled("Dune")


@pytest.mark.asyncio
async def test_classify_uses_the_file_name_when_calibre_says_unknown(tmp_path):
    book = make_epub(tmp_path / "lost_book.epub", "x", "x")
    item, o = _item(book), _orch(tmp_path, fetch=False)
    with patch(
        "app.media.ebook.read_meta", AsyncMock(return_value={"title": "Unknown"})
    ):
        await EbookStrategy().classify(o, AsyncMock(), item)
    meta = json.loads(item.enrichment_data)["ebook"]
    assert meta["title"] == "lost book" and meta["placeholder_title"] is True
    assert meta["authors"] == ["Unknown"]


@pytest.mark.asyncio
async def test_untitled_epub_gets_a_title_without_ebook_convert(tmp_path):
    from tests.ebook_helpers import make_bare_epub

    run = AsyncMock()
    src = make_bare_epub(tmp_path / "bare.epub")
    with patch("app.media.ebook.run_tool", run):
        rc, _ = await ebook.to_epub(src, tmp_path / "o.epub", {"title": "bare"})
    assert rc == 0 and not ebook.epub_lacks_title(tmp_path / "o.epub")
    run.assert_not_awaited()


@pytest.mark.asyncio
async def test_retitle_of_a_corrupt_epub_is_a_conversion_failure(tmp_path):
    (tmp_path / "x.epub").write_bytes(b"PK\x03\x04junk")
    rc, err = await ebook.to_epub(
        tmp_path / "x.epub", tmp_path / "o.epub", {"title": "x"}
    )
    assert rc == 1 and "cannot retitle" in err


def test_epub_lacks_title_reads_the_opf(tmp_path):
    from tests.ebook_helpers import make_bare_epub

    assert ebook.epub_lacks_title(make_bare_epub(tmp_path / "b.epub"))
    assert not ebook.epub_lacks_title(make_epub(tmp_path / "t.epub", "Dune", "A"))
    (tmp_path / "bad.epub").write_bytes(b"nope")
    assert not ebook.epub_lacks_title(tmp_path / "bad.epub")


def test_retitle_epub_adds_dc_title_and_leaves_the_rest_alone(tmp_path):
    from tests.ebook_helpers import make_bare_epub

    src = make_bare_epub(tmp_path / "bare.epub")
    ebook.retitle_epub(src, tmp_path / "out.epub", "My & Book")
    assert not ebook.epub_lacks_title(tmp_path / "out.epub")
    with zipfile.ZipFile(src) as a, zipfile.ZipFile(tmp_path / "out.epub") as b:
        assert (
            b.namelist()[0] == "mimetype"
            and b.infolist()[0].compress_type == zipfile.ZIP_STORED
        )
        assert a.namelist() == b.namelist()
        same = [n for n in a.namelist() if n != "OEBPS/content.opf"]
        assert all(a.read(n) == b.read(n) for n in same)
        assert b"<dc:title>My &amp; Book</dc:title>" in b.read("OEBPS/content.opf")
