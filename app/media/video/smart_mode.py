import logging
from typing import Any

DEFAULT_SD_BITRATE = 1_200_000  # 1200 kbps


def _fps(value: Any) -> float:
    """ffprobe frame rate ('30000/1001', '25', '0/0') as float; 0 when unknown."""
    if isinstance(value, str) and "/" in value:
        num, denom = value.split("/")
        return float(num) / float(denom) if float(denom) != 0 else 0.0
    return float(value) if value else 0.0


class SmartMode:
    """Smart Mode bitrate scaling with SD/HD heuristics and codec-aware adjustments.

    Provides methods for:
    - Bitrate scaling based on video properties
    - SD/HD classification heuristics
    - Codec-aware adjustments
    - Content-aware adjustments (black & white, low-complexity)
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Initialize SmartMode.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)

    def is_sd(self, height: int, color_space: str = "") -> bool:
        """Determine if video is SD quality.

        Args:
            height: Video height in pixels
            color_space: Color space identifier

        Returns:
            True if video is SD quality
        """
        return color_space == "bt470bg" or height <= 480

    def calculate_scale_factor(
        self, height: int, fps: float, color_space: str = ""
    ) -> float:
        """Calculate bitrate scale factor based on video properties.

        Args:
            height: Video height in pixels
            fps: Frames per second
            color_space: Color space identifier

        Returns:
            Scale factor to apply to base bitrate
        """
        if self.is_sd(height, color_space):
            return 1.2
        if fps < 25:
            return 1.3
        if fps >= 29.5:
            return 1.7
        return 1.5

    def get_codec_adjustment(self, codec_name: str) -> float:
        """Get codec-specific bitrate adjustment factor.

        Args:
            codec_name: Codec name (e.g., 'h264', 'mpeg1video')

        Returns:
            Adjustment factor (1.0 = no adjustment)
        """
        # Future enhancement: codec-specific adjustments
        # For now, return neutral adjustment
        return 1.0

    def is_black_and_white(self, video_stream: dict[str, Any]) -> bool:
        """Detect if video is black & white.

        Black & white detection uses pixel format indicators:
        - gray, gray8, gray16: Grayscale formats (definite B&W)

        Args:
            video_stream: Video stream metadata from ffprobe

        Returns:
            True if video appears to be black & white
        """
        pix_fmt = video_stream.get("pix_fmt", "")

        # Definite black & white pixel formats
        bw_formats = {"gray", "gray8", "gray16", "gray8a", "gray16be", "gray16le"}
        if pix_fmt in bw_formats:
            self.logger.debug(f"Detected B&W content via pixel format: {pix_fmt}")
            return True

        return False

    def is_low_complexity(
        self, video_stream: dict[str, Any], base_bitrate: int
    ) -> bool:
        """Detect if video is low-complexity content.

        Low-complexity content includes:
        - Comedies (often static camera, simple sets)
        - Documentaries (talking heads, minimal motion)
        - Cartoons (limited animation)

        Detection heuristics:
        - Low bitrate relative to resolution (< 0.08 bits per pixel per second)
        - Very low frame rates (< 24 fps) combined with moderate resolution

        Args:
            video_stream: Video stream metadata from ffprobe
            base_bitrate: Base bitrate in bits per second

        Returns:
            True if video appears to be low-complexity
        """
        height = video_stream.get("height")
        width = video_stream.get("width")
        fps = video_stream.get("r_frame_rate", "30/1")

        # Need both width and height for bitrate per pixel calculation
        if width is None or height is None:
            # Fall back to fps-only heuristic
            fps_float = _fps(fps)

            # Only very low fps (< 24) indicates low complexity without bitrate data
            if fps_float > 0 and fps_float < 24:
                self.logger.debug(
                    f"Detected low-complexity content: very low fps ({fps_float:.2f})"
                )
                return True
            return False

        fps_float = _fps(fps)

        # Ignore invalid or zero fps
        if fps_float <= 0:
            return False

        # Calculate bits per pixel per second
        pixels = width * height
        if pixels > 0:
            bits_per_pixel_per_second = base_bitrate / (pixels * fps_float)

            # Low complexity threshold: < 0.08 bits per pixel per second
            # Example: 640x480@30fps with 700kbps = 0.076 bpp/s (low complexity)
            #          1920x1080@30fps with 5Mbps = 0.080 bpp/s (borderline)
            if bits_per_pixel_per_second < 0.08:
                self.logger.debug(
                    f"Detected low-complexity content: "
                    f"{bits_per_pixel_per_second:.3f} bits/pixel/sec "
                    f"(threshold: 0.08)"
                )
                return True

        return False

    def get_content_adjustment(
        self, video_stream: dict[str, Any], base_bitrate: int
    ) -> float:
        """Get content-aware bitrate adjustment factor.

        Applies reductions for:
        - Black & white content: 0.75x (25% reduction)
        - Low-complexity content: 0.85x (15% reduction)
        - Both B&W and low-complexity: 0.65x (35% reduction combined)

        Args:
            video_stream: Video stream metadata from ffprobe
            base_bitrate: Base bitrate in bits per second

        Returns:
            Adjustment factor (< 1.0 = reduction, 1.0 = no adjustment)
        """
        is_bw = self.is_black_and_white(video_stream)
        is_low_comp = self.is_low_complexity(video_stream, base_bitrate)

        if is_bw and is_low_comp:
            self.logger.info("Content: B&W + Low-complexity → 0.65x bitrate")
            return 0.65
        if is_bw:
            self.logger.info("Content: Black & White → 0.75x bitrate")
            return 0.75
        if is_low_comp:
            self.logger.info("Content: Low-complexity → 0.85x bitrate")
            return 0.85

        return 1.0

    def get_bitrate(
        self, video_stream: dict[str, Any], format_info: dict[str, Any] | None = None
    ) -> int:
        """Get bitrate from video stream with fallback to safe defaults.

        Args:
            video_stream: Video stream metadata from ffprobe
            format_info: Optional format metadata from ffprobe

        Returns:
            Bitrate in bits per second
        """
        # Try video stream bitrate first
        bitrate_str = video_stream.get("bit_rate")
        if bitrate_str:
            try:
                bitrate = int(bitrate_str)
                self.logger.debug(f"Using stream bitrate: {bitrate} bps")
                return bitrate
            except (ValueError, TypeError):
                pass

        # Try format bitrate
        if format_info:
            bitrate_str = format_info.get("bit_rate")
            if bitrate_str:
                try:
                    bitrate = int(bitrate_str)
                    self.logger.debug(f"Using format bitrate: {bitrate} bps")
                    return bitrate
                except (ValueError, TypeError):
                    pass

        # Fallback to safe SD default
        height = video_stream.get("height", 480)
        if height <= 480:
            fallback_bitrate = DEFAULT_SD_BITRATE
        elif height <= 720:
            fallback_bitrate = int(DEFAULT_SD_BITRATE * 2.5)  # ~3000 kbps for 720p
        else:
            fallback_bitrate = int(DEFAULT_SD_BITRATE * 5)  # ~6000 kbps for 1080p+

        self.logger.warning(
            f"No bitrate found in metadata. Using fallback: {fallback_bitrate} bps "
            f"(based on height={height}px)"
        )
        return fallback_bitrate

    def scale_bitrate(self, video_stream: dict[str, Any], base_bitrate: int) -> int:
        """Scale bitrate using smart mode heuristics.

        Args:
            video_stream: Video stream metadata from ffprobe
            base_bitrate: Base bitrate in bits per second

        Returns:
            Scaled bitrate in bits per second
        """
        height = video_stream.get("height", 480)
        fps = video_stream.get("r_frame_rate", "30/1")

        fps_float = _fps(fps)

        color_space = video_stream.get("color_space", "")
        codec_name = video_stream.get("codec_name", "")

        scale_factor = self.calculate_scale_factor(height, fps_float, color_space)
        codec_adjustment = self.get_codec_adjustment(codec_name)
        content_adjustment = self.get_content_adjustment(video_stream, base_bitrate)

        final_scale = scale_factor * codec_adjustment * content_adjustment
        scaled_bitrate = int(base_bitrate * final_scale)

        self.logger.debug(
            f"Smart Mode: height={height}px, fps={fps_float:.2f}, "
            f"scale={scale_factor:.1f}, codec_adj={codec_adjustment:.1f}, "
            f"content_adj={content_adjustment:.2f}, final_scale={final_scale:.2f}"
        )

        return scaled_bitrate


# Backward compatibility: maintain the original function interface
def smart_scale(info: dict) -> float:
    """Legacy function for backward compatibility.

    Args:
        info: Dictionary with 'video' key containing stream metadata

    Returns:
        Scale factor to apply to base bitrate
    """
    video = info["video"]
    height = video.get("height", 480)
    fps = video.get("fps", 30.0)
    color_space = video.get("color_space", "")

    sm = SmartMode()
    return sm.calculate_scale_factor(height, fps, color_space)
