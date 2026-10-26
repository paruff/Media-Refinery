import json
import logging
import shutil
import subprocess

from app.models.media import MediaItem

logger = logging.getLogger("FingerprintService")

VIDEO_FRAME_SAMPLES = 5  # R-PIPE-7: >=5 frames spread over the runtime
FPCALC_TIMEOUT = 120  # seconds (R-SAFE-5)


class FingerprintService:
    """
    Service for generating and comparing perceptual and acoustic fingerprints for media files.
    Uses fpcalc (Chromaprint) for audio and multi-frame pHash for video.
    """

    @staticmethod
    def fingerprint_audio(file_path: str) -> str | None:
        """Generate an acoustic fingerprint for an audio file using fpcalc (Chromaprint)."""
        fpcalc = shutil.which("fpcalc")
        if fpcalc is None:
            logger.warning("fpcalc not installed; cannot fingerprint %s", file_path)
            return None
        try:
            result = subprocess.run(
                [fpcalc, "-json", file_path],
                capture_output=True,
                text=True,
                check=True,
                timeout=FPCALC_TIMEOUT,
            )
            return json.loads(result.stdout).get("fingerprint")
        except Exception:
            logger.exception("Failed to fingerprint audio %s", file_path)
            return None

    @staticmethod
    def fingerprint_video(file_path: str) -> str | None:
        """Fingerprint = rounded duration + pHash of frames spread over the runtime.

        A single (often black) first frame collides across unrelated videos.
        """
        try:
            import cv2
            import imagehash
            from PIL import Image

            cap = cv2.VideoCapture(file_path)
            try:
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total < 1:
                    return None
                fps = cap.get(cv2.CAP_PROP_FPS)
                hashes = []
                for i in range(VIDEO_FRAME_SAMPLES):
                    cap.set(
                        cv2.CAP_PROP_POS_FRAMES,
                        int((i + 0.5) * total / VIDEO_FRAME_SAMPLES),
                    )
                    success, frame = cap.read()
                    if not success:
                        return None
                    # OpenCV frames are BGR; PIL expects RGB.
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    hashes.append(str(imagehash.phash(Image.fromarray(rgb))))
            finally:
                cap.release()
            duration = round(total / fps) if fps > 0 else 0
            return "-".join([str(duration), *hashes])
        except Exception:
            logger.exception("Failed to fingerprint video %s", file_path)
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
