"""Tiny generated ebooks for the G8 tests: a valid EPUB 3, a MOBI, a fake-DRM EPUB."""

import io
import subprocess
import zipfile
from pathlib import Path

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
            uid=abs(hash(title)), title=title, author=author
        ),
        "OEBPS/nav.xhtml": NAV,
        "OEBPS/c1.xhtml": PAGE.format(title=title, body="<p>Hello, reader.</p>"),
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
