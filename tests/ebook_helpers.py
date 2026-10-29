"""Tiny generated ebooks for the G8 tests: a valid EPUB 3, a MOBI, a fake-DRM EPUB."""

import io
import subprocess
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

CONTAINER = (
    '<?xml version="1.0"?><container version="1.0" '
    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
    '<rootfile full-path="OEBPS/content.opf" '
    'media-type="application/oebps-package+xml"/></rootfiles></container>'
)
OPF = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="id">urn:uuid:{uid}</dc:identifier>
<dc:title>{title}</dc:title><dc:creator>{author}</dc:creator>
<dc:language>en</dc:language>
<meta property="dcterms:modified">2024-01-01T00:00:00Z</meta>
</metadata>
<manifest>
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>
<item id="cover" href="cover.png" media-type="image/png" properties="cover-image"/>
</manifest>
<spine><itemref idref="c1"/></spine>
</package>"""
PAGE = (
    '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" '
    'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>{title}</title></head>'
    "<body>{body}</body></html>"
)
NAV = PAGE.format(
    title="Contents",
    body='<nav epub:type="toc"><ol><li><a href="c1.xhtml">One</a></li></ol></nav>',
)


def make_epub(path: Path, title: str, author: str, extra: dict | None = None) -> Path:
    cover = io.BytesIO()
    Image.new("RGB", (600, 800), "navy").save(cover, "PNG")
    files = {
        "META-INF/container.xml": CONTAINER,
        "OEBPS/content.opf": OPF.format(
            uid=uuid.uuid5(uuid.NAMESPACE_URL, title),
            title=escape(title),
            author=escape(author),
        ),
        "OEBPS/nav.xhtml": NAV,
        "OEBPS/c1.xhtml": PAGE.format(
            title=escape(title), body="<p>Hello, reader.</p>"
        ),
        "OEBPS/cover.png": cover.getvalue(),
        **(extra or {}),
    }
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", zipfile.ZIP_STORED)
        for name, data in files.items():
            z.writestr(name, data, zipfile.ZIP_DEFLATED)
    return path


def make_drm_epub(path: Path, title: str, author: str) -> Path:
    """Adobe ADEPT marker: META-INF/rights.xml (content itself need not be encrypted)."""
    return make_epub(
        path,
        title,
        author,
        {"META-INF/rights.xml": "<rights xmlns='http://ns.adobe.com/adept'/>"},
    )


def make_mobi(path: Path, title: str, author: str) -> Path:
    src = make_epub(path.with_suffix(".src.epub"), title, author)
    subprocess.run(
        ["ebook-convert", str(src), str(path)], check=True, capture_output=True
    )
    src.unlink()
    return path


def make_isbn_epub(path: Path, title: str, author: str, isbn: str) -> Path:
    """An EPUB whose OPF carries a dc:identifier ISBN (Calibre reads it as isbn:...)."""
    tag = f"<dc:identifier>urn:isbn:{isbn}</dc:identifier>"
    p = make_epub(path, title, author)
    _patch_opf(p, lambda opf: opf.replace("<dc:language>", f"{tag}<dc:language>"))
    return p


def make_bare_epub(path: Path) -> Path:
    """An EPUB with no title and no author at all (epubcheck rejects it: dc:title is required)."""
    p = make_epub(path, "x", "x")
    _patch_opf(
        p,
        lambda opf: opf.replace("<dc:title>x</dc:title>", "").replace(
            "<dc:creator>x</dc:creator>", ""
        ),
    )
    return p


def _patch_opf(path: Path, fn) -> None:
    with zipfile.ZipFile(path) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    with zipfile.ZipFile(path, "w") as z:
        for info, data in items:
            is_opf = info.filename == "OEBPS/content.opf"
            z.writestr(info, fn(data.decode()).encode() if is_opf else data)


def make_text_pdf(path: Path, text: str = "Hello, reader. " * 40) -> Path:
    """A one-page PDF with a real text layer (hand-written; no PDF library needed)."""
    body = f"BT /F1 10 Tf 20 100 Td ({text}) Tj ET".encode()
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 2000 200]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length %d>>\nstream\n%s\nendstream" % (len(body), body),
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for n, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (n, obj)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objs) + 1,
        xref,
    )
    path.write_bytes(bytes(out))
    return path


def make_scanned_pdf(path: Path) -> Path:
    """An image-only PDF: no text layer, so conversion yields (almost) no text."""
    Image.new("RGB", (400, 600), "white").save(path, "PDF")
    return path


def make_azw3(path: Path, title: str, author: str) -> Path:
    src = make_epub(path.with_suffix(".src.epub"), title, author)
    subprocess.run(
        ["ebook-convert", str(src), str(path)], check=True, capture_output=True
    )
    src.unlink()
    return path


def make_drm_azw3(path: Path, title: str, author: str) -> Path:
    """A real AZW3 with the MOBI encryption-type field (record 0, offset 12) set to 2."""
    make_azw3(path, title, author)
    data = bytearray(path.read_bytes())
    rec0 = int.from_bytes(data[78:82], "big")
    data[rec0 + 12 : rec0 + 14] = (2).to_bytes(2, "big")
    path.write_bytes(bytes(data))
    return path


def make_corrupt_epub(path: Path) -> Path:
    path.write_bytes(b"PK\x03\x04 this is not really a zip" * 20)
    return path
