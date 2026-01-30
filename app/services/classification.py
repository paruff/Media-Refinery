import re
import logging
from guessit import guessit
from mutagen import File as MutagenFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.media import MediaItem

SCENE_TAGS = [
    'REPACK', 'PROPER', 'DTS-HD', 'DTSHD', 'REMUX', 'WEB-DL', 'WEBRip', 'BluRay', 'HDRip', 'DVDRip',
    '1080p', '720p', '2160p', '4K', 'HEVC', 'x264', 'x265', 'AAC', 'AC3', 'H264', 'H265', 'HDTV', 'NF', 'AMZN', 'DDP', 'Atmos'
]
SCENE_TAGS_RE = re.compile(r'\\b(?:' + '|'.join(SCENE_TAGS) + r')\\b', re.IGNORECASE)
YEAR_RE = re.compile(r'(19|20)\\d{2}')
AUDIO_EXTS = {'flac', 'mp3', 'wav', 'm4a'}

logger = logging.getLogger("media_refinery.classification")

class ClassificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def classify_file(self, media_id: int):
        # Fetch media item
        result = await self.db.execute(select(MediaItem).where(MediaItem.id == media_id))
        item = result.scalar_one_or_none()
        if not item:
            logger.warning(f"Media item {media_id} not found.")
            return
        filename = item.source_path.split('/')[-1]
        ext = filename.split('.')[-1].lower()
        enrichment_data = {}
        media_type = None
        # Video classification
        if ext not in AUDIO_EXTS:
            guess = guessit(filename)
            # Clean title
            title = guess.get('title')
            if title:
                title = SCENE_TAGS_RE.sub('', title).replace('.', ' ').strip()
            # Stricter unknown detection
            if guess.get('type') == 'movie':
                year = guess.get('year')
                # If no title or year, treat as unknown
                if not title or not year:
                    media_type = 'unknown'
                else:
                    media_type = 'movie'
                    enrichment_data = {
                        'title': title,
                        'year': year
                    }
            # Series
            elif guess.get('type') == 'episode':
                media_type = 'series'
                enrichment_data = {
                    'series_title': title,
                    'season_number': guess.get('season'),
                    'episode_number': guess.get('episode')
                }
            else:
                # Unknown video
                media_type = 'unknown'
        # Audio classification
        if ext in AUDIO_EXTS:
            media_type = 'music'
            try:
                audio = MutagenFile(item.source_path, easy=True)
                tags = audio.tags or {}
                enrichment_data = {
                    'artist': tags.get('artist', [None])[0],
                    'album': tags.get('album', [None])[0],
                    'track_title': tags.get('title', [None])[0],
                    'track_number': None
                }
                # Track number
                track_num = tags.get('tracknumber', [None])[0]
                if track_num:
                    try:
                        enrichment_data['track_number'] = int(str(track_num).split('/')[0])
                    except Exception:
                        enrichment_data['track_number'] = track_num
            except Exception as e:
                logger.warning(f"Mutagen failed for {item.source_path}: {e}")
        # Unknown fallback
        if not media_type:
            media_type = 'unknown'
        if media_type == 'unknown':
            logger.warning(f"Could not classify file: {filename}")
        # Update DB
        import json
        await self.db.execute(
            update(MediaItem)
            .where(MediaItem.id == media_id)
            .values(
                media_type=media_type,
                enrichment_data=json.dumps(enrichment_data),
                state='enriched'
            )
        )
        await self.db.commit()
        return media_type, enrichment_data
