import struct
import zipfile

import pytest

from app.media import ebook
from tests.ebook_helpers import make_drm_epub, make_epub

META = """Title               : Dune
Author(s)           : Frank Herbert & Brian [Sort]
Publisher           : Chilton
Series              : Dune Saga #1
Identifiers         : isbn:9780441172719
"""


def test_parse_meta():
    assert ebook.parse_meta(META) == {
        "title": "Dune",
        "authors": ["Frank Herbert", "Brian"],
        "publisher": "Chilton",
        "series": "Dune Saga",
        "series_index": "1",
        "isbn": "9780441172719",
    }


def test_drm_epub_rights_xml(tmp_path):
    assert (
        ebook.detect_drm(make_drm_epub(tmp_path / "a.epub", "T", "A")) == "adobe_adept"
    )
    assert ebook.detect_drm(make_epub(tmp_path / "b.epub", "T", "A")) is None


def test_font_obfuscation_is_not_drm(tmp_path):
    enc = '<encryption><EncryptedData><EncryptionMethod Algorithm="http://www.idpf.org/2008/embedding"/></EncryptedData></encryption>'
    p = make_epub(tmp_path / "f.epub", "T", "A", {"META-INF/encryption.xml": enc})
    assert ebook.detect_drm(p) is None
    enc = enc.replace(
        "http://www.idpf.org/2008/embedding",
        "http://www.w3.org/2001/04/xmlenc#aes128-cbc",
    )
    p = make_epub(tmp_path / "g.epub", "T", "A", {"META-INF/encryption.xml": enc})
    assert ebook.detect_drm(p) == "encrypted_content"


def _mobi(path, encryption):
    header = b"x" * 78 + struct.pack(">I", 86) + b"\0" * 4  # one record at offset 86
    path.write_bytes(header + struct.pack(">HHIHHH", 2, 0, 0, 0, 0, encryption))
    return path


def test_drm_mobi_header(tmp_path):
    assert ebook.detect_drm(_mobi(tmp_path / "a.mobi", 2)) == "mobipocket"
    assert ebook.detect_drm(_mobi(tmp_path / "b.mobi", 0)) is None


def test_corrupt_epub_is_not_drm(tmp_path):
    (tmp_path / "x.epub").write_text("nope")
    assert ebook.detect_drm(tmp_path / "x.epub") is None


def test_epub_text_length_ignores_markup(tmp_path):
    p = make_epub(tmp_path / "t.epub", "T", "A")
    assert 0 < ebook.epub_text_length(p) < ebook.MIN_PDF_TEXT
    assert zipfile.is_zipfile(p)


def test_add_args_carry_metadata(tmp_path):
    meta = {"title": "T", "authors": ["A", "B"], "series": "S", "series_index": "2"}
    args = ebook.add_args(tmp_path, tmp_path / "b.epub", meta, tmp_path / "c.jpg")
    assert args[:3] == ["calibredb", "add", "--with-library"]
    assert args[args.index("--authors") : args.index("--authors") + 2] == [
        "--authors",
        "A & B",
    ]
    assert "--cover" in args and "--series-index" in args


@pytest.mark.asyncio
async def test_to_epub_falls_back_when_epub3_upgrade_crashes(tmp_path, monkeypatch):
    """Calibre 7.6 (Ubuntu 24.04) crashes in upgrade_to_epub3; EPUB 3 is only preferred."""
    calls = []

    async def fake_run_tool(args, limit):
        calls.append(args)
        return (1, "", "TypeError") if "--epub-version" in args else (0, "", "")

    monkeypatch.setattr(ebook, "run_tool", fake_run_tool)
    rc, _ = await ebook.to_epub(tmp_path / "a.mobi", tmp_path / "out.epub")
    assert rc == 0 and len(calls) == 2 and "--epub-version" not in calls[1]
