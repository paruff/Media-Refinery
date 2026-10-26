import logging
import subprocess

from app.models.media import MediaItem


class FingerprintService:
    """
    Service for generating and comparing perceptual and acoustic fingerprints for media files.
    Uses fpcalc (Chromaprint) for audio and pHash for video.
    """

    @staticmethod
    def fingerprint_audio(file_path: str) -> str | None:
        """Generate an acoustic fingerprint for an audio file using fpcalc (Chromaprint)."""
        try:
            result = subprocess.run(
                ["fpcalc", "-json", file_path],  # noqa: S607
                capture_output=True,
                text=True,
                check=True,
            )
            import json

            data = json.loads(result.stdout)
            return data.get("fingerprint")
        except Exception as e:
            logging.error(f"Failed to fingerprint audio {file_path}: {e}")  # noqa: LOG015
            return None

    @staticmethod
    def fingerprint_video(file_path: str) -> str | None:
        """Generate a perceptual hash for a video file using pHash on a key frame."""
        try:
            import cv2
            import imagehash
            from PIL import Image

            cap = cv2.VideoCapture(file_path)
            success, frame = cap.read()
            if not success:
                return None
            # Convert frame to PIL Image
            img = Image.fromarray(frame)
            phash = imagehash.phash(img)
            return str(phash)
        except Exception as e:
            logging.error(f"Failed to fingerprint video {file_path}: {e}")  # noqa: LOG015
            return None

    @staticmethod
    def fingerprint_file(media_item: MediaItem) -> str | None:
        """Generate a fingerprint for a MediaItem based on its type."""
        if media_item.media_type.value == "music":
            return FingerprintService.fingerprint_audio(str(media_item.source_path))
        elif media_item.media_type.value in ("movie", "series"):
            return FingerprintService.fingerprint_video(str(media_item.source_path))
        else:
            return None
