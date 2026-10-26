import logging
import os
from typing import Any

from mutagen import File, MutagenError
from mutagen.flac import FLAC, Picture
from mutagen.id3 import (
    APIC,
    ID3,
    TALB,
    TCON,
    TDRC,
    TIT2,
    TPE1,
    TPE2,
    TPOS,
    TRCK,
    TXXX,
    ID3NoHeaderError,
)
from mutagen.mp4 import MP4, MP4Cover

# R-MUSIC-2 keys without a native frame/atom: Vorbis names, ID3 TXXX, MP4 freeform
EXTRA_KEYS = (
    "musicbrainz_trackid",
    "musicbrainz_albumid",
    "musicbrainz_artistid",
    "musicbrainz_albumartistid",
    "replaygain_track_gain",
    "replaygain_track_peak",
    "replaygain_album_gain",
    "replaygain_album_peak",
)


class TaggingService:
    """
    Service to apply canonical music metadata to FLAC, MP3, and M4A files using mutagen.
    """

    def __init__(self):
        self.logger = logging.getLogger("TaggingService")

    def apply_tags(
        self, file_path: str, metadata: dict[str, Any], clean_tags: bool = True
    ) -> bool:
        """
        Detect file type and apply tags from metadata dict. Returns True if successful.
        """
        try:
            audio = File(file_path, easy=False)
        except MutagenError as e:
            self.logger.error(f"Unreadable file {file_path}: {e}")
            return False
        if audio is None:
            self.logger.error(f"Unsupported or unreadable file: {file_path}")
            return False
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == ".flac" or isinstance(audio, FLAC):
                return self._tag_flac(audio, metadata, clean_tags)
            elif ext == ".mp3" or (
                hasattr(audio, "tags") and isinstance(audio.tags, ID3)
            ):
                try:
                    tags = ID3(file_path)
                except ID3NoHeaderError:
                    tags = ID3()
                    tags.filename = file_path  # a fresh ID3 needs to know where to save
                return self._tag_mp3(tags, metadata, clean_tags)
            elif ext in (".m4a", ".mp4") or isinstance(audio, MP4):
                return self._tag_mp4(audio, metadata, clean_tags)
            else:
                self.logger.error(f"Unsupported file type: {file_path}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to tag {file_path}: {e}")
            return False

    def _tag_flac(self, audio: FLAC, meta: dict[str, Any], clean: bool) -> bool:
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
            "genre": "GENRE",
            **{k: k.upper() for k in EXTRA_KEYS},
        }
        for k, v in tag_map.items():
            if k in meta and meta[k] is not None:
                audio[v] = [str(meta[k])]
        if meta.get("cover"):
            audio.clear_pictures()
            audio.add_picture(self._flac_picture(meta["cover"]))
        audio.save()
        return True

    @staticmethod
    def _flac_picture(jpeg: bytes) -> Picture:
        pic = Picture()
        pic.type, pic.mime, pic.data = 3, "image/jpeg", jpeg  # 3 = front cover
        return pic

    def _tag_mp3(self, audio: ID3, meta: dict[str, Any], clean: bool) -> bool:
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
        if "genre" in meta:
            audio.add(TCON(encoding=3, text=meta["genre"]))
        for key in EXTRA_KEYS:
            if key in meta:
                audio.add(TXXX(encoding=3, desc=key.upper(), text=str(meta[key])))
        if meta.get("cover"):
            audio.delall("APIC")
            audio.add(
                APIC(encoding=3, mime="image/jpeg", type=3, desc="", data=meta["cover"])
            )
        audio.save()
        return True

    def _tag_mp4(self, audio: MP4, meta: dict[str, Any], clean: bool) -> bool:
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
            "genre": "\xa9gen",
            **{k: f"----:com.apple.iTunes:{k.upper()}" for k in EXTRA_KEYS},
        }
        for k, v in tag_map.items():
            if k in meta and meta[k] is not None:
                if v.startswith("----"):
                    audio[v] = [str(meta[k]).encode("utf-8")]
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
        if meta.get("cover"):
            audio["covr"] = [MP4Cover(meta["cover"], imageformat=MP4Cover.FORMAT_JPEG)]
        audio.save()
        return True
