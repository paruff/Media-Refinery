import logging
import subprocess
from pathlib import Path
from typing import List, Optional


class SubtitleService:
    """
    Service for extracting, converting, and OCR-ing subtitles to SRT format.
    Handles both text-based and image-based subtitle streams.
    """

    def __init__(self, ffmpeg_path: str = "ffmpeg", tesseract_path: str = "tesseract"):
        self.ffmpeg_path = ffmpeg_path
        self.tesseract_path = tesseract_path
        self.logger = logging.getLogger("SubtitleService")

    def detect_subtitle_streams(self, input_file: Path) -> List[dict]:
        """
        Use ffprobe to detect subtitle streams and their types.
        Returns a list of dicts with keys: index, codec, lang.
        """
        import json

        cmd = [
            self.ffmpeg_path.replace("ffmpeg", "ffprobe"),
            "-v",
            "error",
            "-select_streams",
            "s",
            "-show_entries",
            "stream=index,codec_name:stream_tags=language",
            "-of",
            "json",
            str(input_file),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, check=True, text=True)
            data = json.loads(result.stdout)
            streams = data.get("streams", [])
            return [
                {
                    "index": s["index"],
                    "codec": s.get("codec_name", "unknown"),
                    "lang": s.get("tags", {}).get("language", "und"),
                }
                for s in streams
            ]
        except Exception as e:
            self.logger.error(f"Failed to probe subtitle streams: {e}")
            return []

    def extract_text_subtitle(
        self, input_file: Path, stream_index: int, out_srt: Path
    ) -> bool:
        """
        Use ffmpeg to extract and convert a text-based subtitle stream to SRT.
        """
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(input_file),
            "-map",
            f"0:s:{stream_index}",
            str(out_srt.with_suffix(".srt")),
        ]
        try:
            subprocess.run(cmd, check=True)
            return True
        except Exception as e:
            self.logger.error(f"Failed to extract text subtitle: {e}")
            return False

    def extract_image_subtitle(
        self, input_file: Path, stream_index: int, out_mks: Path
    ) -> bool:
        """
        Use ffmpeg to extract an image-based subtitle stream as .mks (Matroska subtitle file).
        """
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(input_file),
            "-map",
            f"0:s:{stream_index}",
            str(out_mks),
        ]
        try:
            subprocess.run(cmd, check=True)
            return True
        except Exception as e:
            self.logger.error(f"Failed to extract image subtitle: {e}")
            return False

    def ocr_image_subtitle(self, mks_file: Path, out_srt: Path) -> bool:
        """
        Placeholder for OCR process. Attempts to use tesseract or logs a warning.
        """
        # In production, call Subtitle Edit CLI or tesseract-based OCR here.
        self.logger.warning(
            f"OCR for {mks_file} not implemented. Needs manual intervention."
        )
        return False

    def find_existing_srt(self, input_file: Path, lang: str = "en") -> Optional[Path]:
        """
        Search for an existing .srt sidecar file in the input directory.
        """
        srt_path = input_file.with_suffix(f".{lang}.srt")
        if srt_path.exists():
            return srt_path
        # Fallback: any .srt in the same directory
        for f in input_file.parent.glob("*.srt"):
            return f
        return None

    def mux_srt_into_mkv(
        self, input_mkv: Path, srt_file: Path, output_mkv: Path
    ) -> bool:
        """
        Use ffmpeg to mux the SRT file into the MKV container.
        """
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(input_mkv),
            "-i",
            str(srt_file),
            "-c",
            "copy",
            "-map",
            "0",
            "-map",
            "1",
            "-metadata:s:s:0",
            "language=eng",
            str(output_mkv),
        ]
        try:
            subprocess.run(cmd, check=True)
            return True
        except Exception as e:
            self.logger.error(f"Failed to mux SRT: {e}")
            return False

    def convert_subtitles(self, input_file: Path, output_mkv: Path) -> bool:
        """
        Main entry: Detects, extracts/converts, and muxes subtitles as needed.
        Returns True if SRT is muxed into output.
        """
        streams = self.detect_subtitle_streams(input_file)
        for stream in streams:
            codec = stream["codec"].lower()
            idx = stream["index"]
            lang = stream["lang"]
            srt_path = input_file.with_suffix(f".{lang}.srt")
            if codec in ("srt", "ass", "ssa", "mov_text", "dvb_subtitle"):
                if self.extract_text_subtitle(input_file, idx, srt_path):
                    return self.mux_srt_into_mkv(input_file, srt_path, output_mkv)
            elif codec in ("pgs", "hdmv_pgs_subtitle", "vobsub"):
                mks_path = input_file.with_suffix(f".{lang}.mks")
                if self.extract_image_subtitle(input_file, idx, mks_path):
                    if self.ocr_image_subtitle(mks_path, srt_path):
                        return self.mux_srt_into_mkv(input_file, srt_path, output_mkv)
                    else:
                        self.logger.warning(
                            f"OCR not available for {mks_path}. Searching for sidecar SRT."
                        )
                        sidecar = self.find_existing_srt(input_file, lang)
                        if sidecar:
                            return self.mux_srt_into_mkv(
                                input_file, sidecar, output_mkv
                            )
                        else:
                            self.logger.error(
                                f"No SRT found for {input_file} (lang={lang})"
                            )
                            return False
        self.logger.info(f"No subtitle streams found or converted for {input_file}")
        return False
