"""Ebooks (R-EBOOK-1..4): DRM detection, Calibre metadata/convert, epubcheck, calibredb add."""

import asyncio
import re
import shutil
import struct
import zipfile
from pathlib import Path

from app.core.tools import run_tool

EBOOK_EXTS = {"epub", "mobi", "azw", "azw3", "pdf"}
CALIBRE_TIMEOUT = 600
FETCH_TIMEOUT = 60
MIN_PDF_TEXT = 200  # characters in the converted EPUB; less means a scanned-image PDF
# Font obfuscation is not DRM; everything else listed in encryption.xml is.
FONT_OBFUSCATION = (
    "http://www.idpf.org/2008/embedding",
    "http://ns.adobe.com/pdf/enc#RC",
)
LINE = re.compile(r"^(\w[\w()\s]*?)\s*:\s(.*)$")


def is_ebook(path: str | Path) -> bool:
    return Path(path).suffix.lstrip(".").lower() in EBOOK_EXTS


def _epub_drm(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            if "META-INF/rights.xml" in names:
                return "adobe_adept"
            if "META-INF/encryption.xml" in names:
                xml = z.read("META-INF/encryption.xml").decode(errors="replace")
                algorithms = re.findall(r'Algorithm="([^"]+)"', xml)
                if any(not a.startswith(FONT_OBFUSCATION) for a in algorithms):
                    return "encrypted_content"
    except zipfile.BadZipFile:
        return None  # not DRM; the convert/verify steps reject a corrupt file
    return None


def _mobi_drm(path: Path) -> str | None:
    """PalmDOC header, record 0 offset 12: 0 = none, 1 = old MOBI, 2 = Mobipocket DRM."""
    with open(path, "rb") as f:
        head = f.read(86)
        if len(head) < 86:
            return None
        (offset,) = struct.unpack(">I", head[78:82])
        f.seek(offset + 12)
        raw = f.read(2)
    return "mobipocket" if len(raw) == 2 and struct.unpack(">H", raw)[0] else None


def detect_drm(path: str | Path) -> str | None:
    """R-EBOOK-4: a short reason when the file is DRM-protected, else None."""
    path = Path(path)
    ext = path.suffix.lstrip(".").lower()
    if ext == "epub":
        return _epub_drm(path)
    if ext in ("mobi", "azw", "azw3"):
        return _mobi_drm(path)
    return None


def parse_meta(text: str) -> dict:
    """Parse the 'Key  : value' listing of ebook-meta / fetch-ebook-metadata."""
    fields = {}
    for raw in text.splitlines():
        if m := LINE.match(raw):
            fields[m.group(1).strip().lower()] = m.group(2).strip()
    out: dict = {}
    if title := fields.get("title"):
        out["title"] = title
    if authors := fields.get("author(s)"):
        out["authors"] = [
            a.strip() for a in re.sub(r"\[.*?\]", "", authors).split("&") if a.strip()
        ]
    if series := re.match(r"(.+?) #([\d.]+)$", fields.get("series", "")):
        out["series"], out["series_index"] = series.group(1), series.group(2)
    for key in ("publisher", "published"):
        if fields.get(key):
            out[key] = fields[key]
    if isbn := re.search(r"isbn:(\w+)", fields.get("identifiers", "")):
        out["isbn"] = isbn.group(1)
    return out


async def read_meta(path: Path) -> dict:
    rc, out, _ = await run_tool(["ebook-meta", str(path)], CALIBRE_TIMEOUT)
    return parse_meta(out) if rc == 0 else {}


async def extract_cover(path: Path, dest: Path) -> Path | None:
    rc, _, _ = await run_tool(
        ["ebook-meta", str(path), "--get-cover", str(dest)], CALIBRE_TIMEOUT
    )
    return dest if rc == 0 and await asyncio.to_thread(dest.exists) else None


async def fetch_meta(meta: dict) -> dict:
    """R-EBOOK-2: Calibre's metadata sources by ISBN, else title+author. A miss is empty."""
    args = ["fetch-ebook-metadata"]
    if meta.get("isbn"):
        args += ["--isbn", meta["isbn"]]
    elif meta.get("title"):
        args += ["--title", meta["title"]]
        if meta.get("authors"):
            args += ["--authors", " & ".join(meta["authors"])]
    else:
        return {}
    rc, out, _ = await run_tool(args, FETCH_TIMEOUT)
    return parse_meta(out) if rc == 0 else {}


def epub_text_length(path: Path) -> int:
    """Visible-ish text in an EPUB's (x)html files; markup is stripped crudely."""
    total = 0
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.lower().endswith((".xhtml", ".html", ".htm")):
                html = z.read(name).decode(errors="replace")
                html = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.S)
                total += len(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip())
    return total


async def to_epub(source: Path, out: Path) -> tuple[int, str]:
    """R-EBOOK-1: EPUB 3 via ebook-convert; an EPUB source is copied as is."""
    if source.suffix.lower() == ".epub":
        await asyncio.to_thread(shutil.copyfile, source, out)
        return 0, ""
    rc, _, err = await run_tool(
        ["ebook-convert", str(source), str(out), "--epub-version", "3"],
        CALIBRE_TIMEOUT,
    )
    return rc, err


JAR = Path(
    "/usr/share/java/epubcheck.jar"
)  # Debian/Ubuntu ship a jar without a launcher


async def epubcheck(path: Path) -> tuple[bool | None, str]:
    """True/False, or None when epubcheck is not installed."""
    for cmd in (["epubcheck"], ["java", "-jar", str(JAR)]):
        try:
            rc, out, err = await run_tool([*cmd, str(path)], CALIBRE_TIMEOUT)
        except OSError:  # missing, or a launcher-less jar that cannot be exec'd
            continue
        return rc == 0, (err or out).strip()[:500]
    return None, "epubcheck not installed"


def add_args(library: Path, book: Path, meta: dict, cover: Path | None) -> list[str]:
    """R-EBOOK-3: calibredb owns the library layout; we only hand it the book + metadata."""
    args = ["calibredb", "add", "--with-library", str(library), str(book)]
    if meta.get("title"):
        args += ["--title", meta["title"]]
    if meta.get("authors"):
        args += ["--authors", " & ".join(meta["authors"])]
    if meta.get("series"):
        args += ["--series", meta["series"]]
        args += ["--series-index", str(meta.get("series_index") or 1)]
    if meta.get("isbn"):
        args += ["--isbn", meta["isbn"]]
    if cover is not None:
        args += ["--cover", str(cover)]
    return args


async def calibredb_add(library: Path, book: Path, meta: dict, cover: Path | None):
    """Return (book id or None when Calibre skipped a duplicate, error text)."""
    rc, out, err = await run_tool(add_args(library, book, meta, cover), CALIBRE_TIMEOUT)
    if rc != 0:
        return None, (err or out).strip()[:500]
    found = re.search(r"Added book ids: (\d+)", out)
    return (int(found.group(1)) if found else None), ""
