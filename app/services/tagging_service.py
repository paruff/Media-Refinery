import logging
from typing import Dict, Any
from mutagen import File
from mutagen.flac import FLAC
from mutagen.id3 import ID3, TPE1, TALB, TDRC, TIT2, TPE2, TRCK, TPOS, TXXX
from mutagen.mp4 import MP4
import os


class TaggingService:
    """
    Service to apply canonical music metadata to FLAC, MP3, and M4A files using mutagen.
    """

    def __init__(self):
        self.logger = logging.getLogger("TaggingService")

    def apply_tags(
        self, file_path: str, metadata: Dict[str, Any], clean_tags: bool = True
    ) -> bool:
        """
        Detect file type and apply tags from metadata dict. Returns True if successful.
        """
        audio = File(file_path, easy=False)
        if audio is None:
            self.logger.error(f"Unsupported or unreadable file: {file_path}")
            return False
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == ".flac" or isinstance(audio, FLAC):
                return self._tag_flac(audio, metadata, clean_tags)
            elif (
                ext == ".mp3" or hasattr(audio, "tags") and isinstance(audio.tags, ID3)
            ):
                return self._tag_mp3(audio, metadata, clean_tags)
            elif ext in (".m4a", ".mp4") or isinstance(audio, MP4):
                return self._tag_mp4(audio, metadata, clean_tags)
            else:
                self.logger.error(f"Unsupported file type: {file_path}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to tag {file_path}: {e}")
            return False

    def _tag_flac(self, audio: FLAC, meta: Dict[str, Any], clean: bool) -> bool:
        if clean:
            audio.delete()
        # Vorbis comments are case-insensitive but usually uppercase
        tag_map = {
            "artist": "ARTIST",
            "album_artist": "ALBUMARTIST",
            "album": "ALBUM",
            "title": "TITLE",
            "track_number": "TRACKNUMBER",
            "track_total": "TRACKTOTAL",
            "disc_number": "DISCNUMBER",
            "disc_total": "DISCTOTAL",
            "year": "DATE",
            "release_date": "DATE",
            "musicbrainz_trackid": "MUSICBRAINZ_TRACKID",
            "musicbrainz_albumid": "MUSICBRAINZ_ALBUMID",
        }
        for k, v in tag_map.items():
            if k in meta and meta[k] is not None:
                audio[v] = [str(meta[k])]
        audio.save()
        return True

    def _tag_mp3(self, audio: ID3, meta: Dict[str, Any], clean: bool) -> bool:
        if clean:
            audio.delete()
        # Standard ID3v2.4 frames
        if "artist" in meta:
            audio.add(TPE1(encoding=3, text=meta["artist"]))
        if "album_artist" in meta:
            audio.add(TPE2(encoding=3, text=meta["album_artist"]))
        if "album" in meta:
            audio.add(TALB(encoding=3, text=meta["album"]))
        if "title" in meta:
            audio.add(TIT2(encoding=3, text=meta["title"]))
        if "year" in meta:
            audio.add(TDRC(encoding=3, text=str(meta["year"])))
        if "track_number" in meta:
            track = str(meta["track_number"])
            if "track_total" in meta:
                track += f"/{meta['track_total']}"
            audio.add(TRCK(encoding=3, text=track))
        if "disc_number" in meta:
            disc = str(meta["disc_number"])
            if "disc_total" in meta:
                disc += f"/{meta['disc_total']}"
            audio.add(TPOS(encoding=3, text=disc))
        # MusicBrainz IDs
        if "musicbrainz_trackid" in meta:
            audio.add(
                TXXX(
                    encoding=3,
                    desc="MUSICBRAINZ_TRACKID",
                    text=meta["musicbrainz_trackid"],
                )
            )
        if "musicbrainz_albumid" in meta:
            audio.add(
                TXXX(
                    encoding=3,
                    desc="MUSICBRAINZ_ALBUMID",
                    text=meta["musicbrainz_albumid"],
                )
            )
        audio.save()
        return True

    def _tag_mp4(self, audio: MP4, meta: Dict[str, Any], clean: bool) -> bool:
        if clean:
            audio.delete()
        tag_map = {
            "artist": "\xa9ART",
            "album_artist": "aART",
            "album": "\xa9alb",
            "title": "\xa9nam",
            "year": "\xa9day",
            "track_number": "trkn",
            "disc_number": "disk",
            "musicbrainz_trackid": "----:com.apple.iTunes:MUSICBRAINZ_TRACKID",
            "musicbrainz_albumid": "----:com.apple.iTunes:MUSICBRAINZ_ALBUMID",
        }
        for k, v in tag_map.items():
            if k in meta and meta[k] is not None:
                if v.startswith("----"):
                    audio[v] = [meta[k].encode("utf-8")]
                elif v in ("trkn", "disk"):
                    # MP4 expects tuples for track/disc
                    if k == "track_number":
                        total = meta.get("track_total", 0)
                        audio[v] = [(int(meta[k]), int(total))]
                    elif k == "disc_number":
                        total = meta.get("disc_total", 0)
                        audio[v] = [(int(meta[k]), int(total))]
                else:
                    audio[v] = [str(meta[k])]
        audio.save()
        return True
