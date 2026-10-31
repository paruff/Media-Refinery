import importlib
import json
import logging
import shutil
import subprocess

from app.media.video._run import run
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
    def require_video_support() -> None:
        """Fail fast (startup) when video duplicate detection cannot work at all."""
        try:
            for module in ("cv2", "imagehash", "PIL.Image"):
                importlib.import_module(module)
        except ImportError as exc:
            raise RuntimeError(
                f"video fingerprinting needs opencv, Pillow and imagehash: {exc}"
            ) from exc

    @staticmethod
    def _container_duration(file_path: str) -> float:
        """Seconds from ffprobe, 0.0 when unknown (used when the frame count is unusable)."""
        try:
            result = run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file_path],
                timeout=FPCALC_TIMEOUT,
            )  # fmt: skip
            return float(result.stdout.strip()) if result else 0.0
        except ValueError:
            return 0.0

    @staticmethod
    def fingerprint_video(file_path: str) -> str | None:
        """Fingerprint = rounded duration + pHash of frames spread over the runtime.

        A single (often black) first frame collides across unrelated videos. A variable-
        frame-rate file reports no usable frame count, so its frames are sought by time.
        """
        try:
            import cv2
            import imagehash
            from PIL import Image

            cap = cv2.VideoCapture(file_path)
            try:
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                seconds = (
                    total / fps
                    if total >= 1 and fps > 0
                    else FingerprintService._container_duration(file_path)
                )
                if total < 1 and seconds <= 0:
                    return None
                hashes = []
                for i in range(VIDEO_FRAME_SAMPLES):
                    at = (i + 0.5) / VIDEO_FRAME_SAMPLES
                    if total >= 1:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, int(at * total))
                    else:
                        cap.set(cv2.CAP_PROP_POS_MSEC, at * seconds * 1000)
                    success, frame = cap.read()
                    if not success:
                        return None
                    # OpenCV frames are BGR; PIL expects RGB.
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    hashes.append(str(imagehash.phash(Image.fromarray(rgb))))
            finally:
                cap.release()
            return "-".join([str(round(seconds)), *hashes])
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
