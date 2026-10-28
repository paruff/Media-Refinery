import logging
import re

from guessit import guessit
from mutagen import File as MutagenFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem

SCENE_TAGS = [
    "REPACK",
    "PROPER",
    "DTS-HD",
    "DTSHD",
    "REMUX",
    "WEB-DL",
    "WEBRip",
    "BluRay",
    "HDRip",
    "DVDRip",
    "1080p",
    "720p",
    "2160p",
    "4K",
    "HEVC",
    "x264",
    "x265",
    "AAC",
    "AC3",
    "H264",
    "H265",
    "HDTV",
    "NF",
    "AMZN",
    "DDP",
    "Atmos",
]
SCENE_TAGS_RE = re.compile(r"\\b(?:" + "|".join(SCENE_TAGS) + r")\\b", re.IGNORECASE)
YEAR_RE = re.compile(r"(19|20)\\d{2}")
AUDIO_EXTS = {"flac", "mp3", "wav", "m4a", "m4b"}
AUDIOBOOK_GENRES = {"audiobook", "audiobooks", "audio book", "spoken word", "speech"}

logger = logging.getLogger("media_refinery.classification")


<<<<<<< HEAD
def parse_disc(disc, total=None) -> tuple[int | None, int | None]:
    """(disc number, disc total) from embedded tags like "2/3", or "2" + a DISCTOTAL tag."""
    number, _, of = str(disc or "").partition("/")
    number, of = number.strip(), (of or str(total or "")).strip()
    return (
        int(number) if number.isdigit() else None,
        int(of) if of.isdigit() else None,
    )
=======
AUDIOBOOK_FOLDERS = {"audiobook", "audiobooks"}
AUDIOBOOK_SECONDS = 3600


def audiobook_by_rule(path: str, duration: float | None, input_dir=None) -> bool:
    """R-PIPE-4: audio in an `audiobooks/` folder, or running an hour or more, is an audiobook."""
    parts = [p.lower() for p in path.split("/")[:-1]]
    if input_dir is not None:  # only folders below the drop folder count
        base = str(input_dir).rstrip("/")
        parts = [p.lower() for p in path.removeprefix(base).split("/")[:-1]]
    return bool(AUDIOBOOK_FOLDERS & set(parts)) or (duration or 0) >= AUDIOBOOK_SECONDS
>>>>>>> origin/main


class ClassificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def classify_file(self, media_id: int):
        # Fetch media item
        result = await self.db.execute(
            select(MediaItem).where(MediaItem.id == media_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            logger.warning(f"Media item {media_id} not found.")
            return
        filename = item.source_path.split("/")[-1]
        ext = filename.split(".")[-1].lower()
        enrichment_data = {}
        media_type = None
        # Video classification
        if ext not in AUDIO_EXTS:
            guess = guessit(filename)
            # Clean title
            title = guess.get("title")
            if title:
                title = SCENE_TAGS_RE.sub("", title).replace(".", " ").strip()
            # Stricter unknown detection
            if guess.get("type") == "movie":
                year = guess.get("year")
                # If no title or year, treat as unknown
                if not title or not year:
                    media_type = "unknown"
                else:
                    media_type = "movie"
                    enrichment_data = {"title": title, "year": year}
                    if guess.get("part"):  # multi-part movie (R-VIDEO-4)
                        enrichment_data["part"] = guess["part"]
            # Series
            elif guess.get("type") == "episode":
                media_type = "series"
                episodes = guess.get("episode")
                episodes = episodes if isinstance(episodes, list) else [episodes]
                enrichment_data = {
                    "series_title": title,
                    "year": guess.get("year"),
                    # unknown stays None (reviewed); 0 only for an explicit S00 / special marker
                    "season_number": guess.get(
                        "season",
                        0
                        if guess.get("episode_details") in ("Special", "OVA")
                        else None,
                    ),
                    "episode_number": min(episodes) if episodes[0] else None,
                    "episode_end": max(episodes) if episodes[0] else None,
                }
            else:
                # Unknown video
                media_type = "unknown"
        # Audio classification
        if ext in AUDIO_EXTS:
            media_type = "audiobook" if ext == "m4b" else "music"
            try:
                audio = MutagenFile(item.source_path, easy=True)
                tags = audio.tags or {}
                if str((tags.get("genre") or [""])[0]).lower() in AUDIOBOOK_GENRES:
                    media_type = "audiobook"  # R-BOOK-1: classify by genre or .m4b
                enrichment_data = {
                    "artist": tags.get("artist", [None])[0],
                    "album": tags.get("album", [None])[0],
                    "track_title": tags.get("title", [None])[0],
                    "track_number": None,
                }
                disc, disc_total = parse_disc(
                    (tags.get("discnumber") or [None])[0],
                    (tags.get("disctotal") or tags.get("totaldiscs") or [None])[0],
                )
                if disc:
                    enrichment_data.update(disc_number=disc, disc_total=disc_total)
                # Track number
                track_num = tags.get("tracknumber", [None])[0]
                if track_num:
                    try:
                        enrichment_data["track_number"] = int(
                            str(track_num).split("/")[0]
                        )
                    except Exception:
                        enrichment_data["track_number"] = track_num
            except Exception as e:
                logger.warning(f"Mutagen failed for {item.source_path}: {e}")
        # Unknown fallback
        if not media_type:
            media_type = "unknown"
        if media_type == "unknown":
            logger.warning(f"Could not classify file: {filename}")
        # Update DB
        import json

        await self.db.execute(
            update(MediaItem)
            .where(MediaItem.id == media_id)
            .values(
                media_type=media_type,
                enrichment_data=json.dumps(enrichment_data),
                state="enriched",
            )
        )
        await self.db.commit()
        return media_type, enrichment_data
