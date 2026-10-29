"""Ebooks (R-EBOOK-1..4): DRM detection, Calibre metadata/convert, epubcheck, calibredb add."""

import asyncio
import json
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
AUTHOR_SPLIT = re.compile(
    r"\s&\s"
)  # Calibre joins authors with " & "; "AT&T" is one name
MAX_HTML_READ = 2_000_000  # bytes per (x)html member; bounds memory on a zip bomb


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
    fields: dict[str, str] = {}
    for raw in text.splitlines():
        if m := LINE.match(raw):  # first wins: a Comments body can contain "Title: x"
            fields.setdefault(m.group(1).strip().lower(), m.group(2).strip())
    out: dict = {}
    if title := fields.get("title"):
        out["title"] = title
    if authors := fields.get("author(s)"):
        out["authors"] = [
            a.strip()
            for a in AUTHOR_SPLIT.split(re.sub(r"\[.*?\]", "", authors))
            if a.strip()
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


async def fetch_meta(meta: dict, cover: Path | None = None) -> dict:
    """R-EBOOK-2: Calibre's metadata sources by ISBN, else title+author. A miss is empty.

    With `cover`, a fetched cover image is saved there (absent on a miss)."""
    args = ["fetch-ebook-metadata"]
    if meta.get("isbn"):
        args += ["--isbn", meta["isbn"]]
    elif meta.get("title"):
        args += ["--title", meta["title"]]
        if meta.get("authors"):
            args += ["--authors", " & ".join(meta["authors"])]
    else:
        return {}
    if cover is not None:
        args += ["--cover", str(cover)]
    rc, out, _ = await run_tool(args, FETCH_TIMEOUT)
    return parse_meta(out) if rc == 0 else {}


def epub_text_length(path: Path, enough: int = MIN_PDF_TEXT) -> int:
    """Visible-ish text in an EPUB's (x)html files; markup is stripped crudely.

    Reads at most MAX_HTML_READ bytes per member and stops once `enough` is reached; a
    corrupt zip counts as no text."""
    total = 0
    try:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if not name.lower().endswith((".xhtml", ".html", ".htm")):
                    continue
                with z.open(name) as f:
                    html = f.read(MAX_HTML_READ).decode(errors="replace")
                html = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.S)
                total += len(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip())
                if total >= enough:
                    break
    except zipfile.BadZipFile, OSError, RuntimeError:
        return 0
    return total


async def to_epub(source: Path, out: Path) -> tuple[int, str]:
    """R-EBOOK-1: EPUB 3 (else Calibre default) via ebook-convert; an EPUB source is copied as is."""
    if source.suffix.lower() == ".epub":
        await asyncio.to_thread(shutil.copyfile, source, out)
        return 0, ""
    cmd = ["ebook-convert", str(source), str(out)]
    rc, _, err = await run_tool([*cmd, "--epub-version", "3"], CALIBRE_TIMEOUT)
    if rc != 0:  # EPUB 3 is preferred, not required: Calibre 7.6 crashes in its upgrade
        rc, _, err = await run_tool(cmd, CALIBRE_TIMEOUT)
    return rc, err


JAR = Path(
    "/usr/share/java/epubcheck.jar"
)  # Debian/Ubuntu ship a jar without a launcher


async def epubcheck(path: Path) -> tuple[bool | None, str]:
    """True/False, or None when epubcheck is not installed."""
    for cmd in (["epubcheck"], ["java", "-jar", str(JAR)]):
        rc, out, err = await run_tool([*cmd, str(path)], CALIBRE_TIMEOUT)
        if rc == 127:  # missing, or a launcher-less jar that cannot be exec'd
            continue
        return rc == 0, (err or out).strip()[:500]
    return None, "epubcheck not installed"


def merge_meta(embedded: dict, fetched: dict) -> dict:
    """Fetched metadata fills gaps; a non-empty embedded value is never overwritten."""
    return {**fetched, **{k: v for k, v in embedded.items() if v}}


async def find_duplicate(library: Path, meta: dict) -> int | None:
    """R-PIPE-7: Calibre id of a book already in the library (by ISBN, else exact title+author)."""
    if meta.get("isbn"):
        query = f"identifier:isbn:{meta['isbn']}"
    elif meta.get("title") and meta.get("authors"):
        query = f'title:"={meta["title"]}" and authors:"={meta["authors"][0]}"'
    else:
        return None
    rc, out, _ = await run_tool(
        ["calibredb", "list", "--with-library", str(library), "--for-machine",
         "--fields", "id", "--search", query],
        CALIBRE_TIMEOUT,
    )  # fmt: skip
    try:
        rows = json.loads(out) if rc == 0 else []
    except ValueError:
        return None
    return int(rows[0]["id"]) if rows else None


def add_args(library: Path, book: Path, meta: dict, cover: Path | None) -> list[str]:
    """R-EBOOK-3: calibredb owns the library layout; we only hand it the book + metadata."""
    args = ["calibredb", "add", "--with-library", str(library), str(book)]
    if meta.get("allow_duplicate"):  # a human approved keeping both (R-PIPE-7)
        args.append("--duplicates")
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


def _pubdate(published: str) -> str | None:
    """Calibre prints 'published' as an ISO timestamp; keep the date part."""
    m = re.match(r"\d{4}(-\d{2}(-\d{2})?)?", published or "")
    return m.group(0) if m else None


async def set_extra_fields(library: Path, book_id: int, meta: dict) -> None:
    """`calibredb add` cannot take publisher or pubdate, so set them after. Best effort: the
    book is already in the library, so a failure here must not quarantine it."""
    fields = {
        "publisher": meta.get("publisher"),
        "pubdate": _pubdate(meta.get("published", "")),
    }
    pairs = [f"{name}:{value}" for name, value in fields.items() if value]
    if not pairs:
        return
    args = ["calibredb", "set_metadata", "--with-library", str(library), str(book_id)]
    for pair in pairs:
        args += ["--field", pair]
    await run_tool(args, CALIBRE_TIMEOUT)


BUSY_PREFIX = "busy:"
BUSY_RE = re.compile(
    r"another calibre program|database is locked|library .* in use", re.I
)
BUSY_RETRIES = (
    5,
    15,
    45,
)  # seconds between attempts while the library is held elsewhere


async def calibredb_add(
    library: Path, book: Path, meta: dict, cover: Path | None, sleep=asyncio.sleep
):
    """Return (book id or None when Calibre skipped a duplicate, error text).

    A library held by the Calibre GUI/content server is retried with backoff and then reported
    as `busy:` so the caller can try again later instead of quarantining a good book."""
    for wait in (*BUSY_RETRIES, None):
        rc, out, err = await run_tool(
            add_args(library, book, meta, cover), CALIBRE_TIMEOUT
        )
        if rc == 0:
            found = re.search(r"Added book ids: (\d+)", out)
            return (int(found.group(1)) if found else None), ""
        text = (err or out).strip()
        if not BUSY_RE.search(text):
            return None, text[:500]
        if wait is None:
            return None, f"{BUSY_PREFIX} {text}"[:500]
        await sleep(wait)
    raise AssertionError("unreachable")  # pragma: no cover
