"""Tests for smart_mode module."""

from app.media.video.smart_mode import SmartMode, smart_scale


class TestSmartModeClass:
    """Tests for SmartMode class."""

    def test_is_sd_bt470bg(self):
        """Test SD detection with bt470bg color space."""
        sm = SmartMode()
        assert sm.is_sd(720, "bt470bg") is True

    def test_is_sd_low_height(self):
        """Test SD detection with low height."""
        sm = SmartMode()
        assert sm.is_sd(480, "") is True
        assert sm.is_sd(360, "") is True

    def test_is_not_sd(self):
        """Test HD detection."""
        sm = SmartMode()
        assert sm.is_sd(720, "") is False
        assert sm.is_sd(1080, "") is False

    def test_calculate_scale_factor_sd_bt470bg(self):
        """Test scale factor for SD video with bt470bg."""
        sm = SmartMode()
        assert sm.calculate_scale_factor(480, 29.97, "bt470bg") == 1.2

    def test_calculate_scale_factor_sd_low_height(self):
        """Test scale factor for SD video with low height."""
        sm = SmartMode()
        assert sm.calculate_scale_factor(360, 29.97, "") == 1.2

    def test_calculate_scale_factor_low_fps(self):
        """Test scale factor for low FPS video."""
        sm = SmartMode()
        assert sm.calculate_scale_factor(720, 24, "") == 1.3

    def test_calculate_scale_factor_high_fps(self):
        """Test scale factor for high FPS video."""
        sm = SmartMode()
        assert sm.calculate_scale_factor(1080, 30, "") == 1.7

    def test_calculate_scale_factor_medium(self):
        """Test scale factor for medium quality video."""
        sm = SmartMode()
        assert sm.calculate_scale_factor(720, 25, "") == 1.5

    def test_get_codec_adjustment(self):
        """Test codec adjustment (currently neutral)."""
        sm = SmartMode()
        assert sm.get_codec_adjustment("h264") == 1.0
        assert sm.get_codec_adjustment("mpeg1video") == 1.0

    def test_scale_bitrate_basic(self):
        """Test bitrate scaling with basic stream."""
        sm = SmartMode()
        stream = {
            "height": 480,
            "r_frame_rate": "30/1",
            "color_space": "bt470bg",
            "codec_name": "h264",
        }
        # 1200000 * 1.2 = 1440000
        assert sm.scale_bitrate(stream, 1_200_000) == 1_440_000

    def test_scale_bitrate_with_fraction_fps(self):
        """Test bitrate scaling with fractional FPS (no width, so no content adjustment)."""
        sm = SmartMode()
        stream = {
            "height": 1080,
            "r_frame_rate": "30000/1001",  # 29.97 fps
            "color_space": "",
            "codec_name": "h264",
        }
        # Without width, no content adjustment: 1200000 * 1.7 = 2040000
        assert sm.scale_bitrate(stream, 1_200_000) == 2_040_000

    def test_scale_bitrate_with_defaults(self):
        """Test bitrate scaling with missing fields."""
        sm = SmartMode()
        stream = {}
        # Should use defaults: height=480, fps=30, color_space=""
        # Since height <= 480, scale = 1.2
        assert sm.scale_bitrate(stream, 1_200_000) == 1_440_000

    def test_get_bitrate_from_stream(self):
        """Test bitrate extraction from stream."""
        sm = SmartMode()
        stream = {"bit_rate": "2500000", "height": 720}
        assert sm.get_bitrate(stream) == 2_500_000

    def test_get_bitrate_from_format(self):
        """Test bitrate extraction from format when stream has none."""
        sm = SmartMode()
        stream = {"height": 720}
        format_info = {"bit_rate": "3000000"}
        assert sm.get_bitrate(stream, format_info) == 3_000_000

    def test_get_bitrate_fallback_sd(self):
        """Test fallback bitrate for SD resolution."""
        sm = SmartMode()
        stream = {"height": 480}
        # Should use DEFAULT_SD_BITRATE (1200000)
        assert sm.get_bitrate(stream) == 1_200_000

    def test_get_bitrate_fallback_hd(self):
        """Test fallback bitrate for HD resolution."""
        sm = SmartMode()
        stream = {"height": 720}
        # Should use DEFAULT_SD_BITRATE * 2.5 = 3000000
        assert sm.get_bitrate(stream) == 3_000_000

    def test_get_bitrate_fallback_full_hd(self):
        """Test fallback bitrate for Full HD resolution."""
        sm = SmartMode()
        stream = {"height": 1080}
        # Should use DEFAULT_SD_BITRATE * 5 = 6000000
        assert sm.get_bitrate(stream) == 6_000_000

    def test_get_bitrate_invalid_string(self):
        """Test fallback when bitrate string is invalid."""
        sm = SmartMode()
        stream = {"bit_rate": "invalid", "height": 480}
        # Should fallback to SD default
        assert sm.get_bitrate(stream) == 1_200_000


class TestSmartScaleLegacy:
    """Tests for legacy smart_scale function (backward compatibility)."""

    def test_scale_sd_bt470bg(self):
        """Test scaling for SD video with bt470bg color space."""
        info = {"video": {"height": 480, "fps": 29.97, "color_space": "bt470bg"}}
        assert smart_scale(info) == 1.2

    def test_scale_sd_low_height(self):
        """Test scaling for SD video with low height."""
        info = {"video": {"height": 360, "fps": 29.97, "color_space": ""}}
        assert smart_scale(info) == 1.2

    def test_scale_low_fps(self):
        """Test scaling for low FPS video."""
        info = {"video": {"height": 720, "fps": 24, "color_space": ""}}
        assert smart_scale(info) == 1.3

    def test_scale_high_fps(self):
        """Test scaling for high FPS video."""
        info = {"video": {"height": 1080, "fps": 30, "color_space": ""}}
        assert smart_scale(info) == 1.7

    def test_scale_medium(self):
        """Test scaling for medium quality video."""
        info = {"video": {"height": 720, "fps": 25, "color_space": ""}}
        assert smart_scale(info) == 1.5

    def test_scale_missing_color_space(self):
        """Test scaling with missing color space."""
        info = {"video": {"height": 720, "fps": 29.97}}
        assert smart_scale(info) == 1.7


class TestSmartModeEdgeCases:
    """Tests for Smart Mode edge cases and boundary conditions."""

    def test_is_sd_boundary_480(self):
        """Test SD detection at 480p boundary."""
        sm = SmartMode()
        assert sm.is_sd(480, "") is True
        assert sm.is_sd(481, "") is False

    def test_is_sd_hd_boundary(self):
        """Test SD/HD boundary - SD is only up to 480p."""
        sm = SmartMode()
        # 480 and below are SD
        assert sm.is_sd(480, "") is True
        # Above 480 is not SD (even if below 720)
        assert sm.is_sd(481, "") is False
        assert sm.is_sd(719, "") is False
        assert sm.is_sd(720, "") is False

    def test_calculate_scale_factor_fps_boundaries(self):
        """Test scale factor at FPS boundaries."""
        sm = SmartMode()
        # Low FPS boundary (< 25)
        assert sm.calculate_scale_factor(720, 24.9, "") == 1.3
        assert sm.calculate_scale_factor(720, 25.0, "") == 1.5
        # High FPS boundary (>= 29.5)
        assert sm.calculate_scale_factor(720, 29.4, "") == 1.5
        assert sm.calculate_scale_factor(720, 29.5, "") == 1.7

    def test_scale_bitrate_very_low_fps(self):
        """Test bitrate scaling with very low FPS (e.g., stop motion)."""
        sm = SmartMode()
        stream = {
            "height": 1080,
            "width": 1920,
            "r_frame_rate": "12/1",
            "color_space": "",
            "codec_name": "h264",
        }
        # Low FPS (< 24) triggers low-complexity: 1200000 * 1.3 * 0.85 = 1326000
        assert sm.scale_bitrate(stream, 1_200_000) == 1_326_000

    def test_scale_bitrate_very_high_fps(self):
        """Test bitrate scaling with very high FPS (e.g., 60fps)."""
        sm = SmartMode()
        stream = {
            "height": 1080,
            "width": 1920,
            "r_frame_rate": "60/1",
            "color_space": "",
            "codec_name": "h264",
        }
        # 1920x1080@60 with 1.2Mbps = 0.010 bpp/s (low complexity)
        # 1200000 * 1.7 * 0.85 = 1733999
        assert sm.scale_bitrate(stream, 1_200_000) == 1_733_999

    def test_scale_bitrate_ntsc_fps(self):
        """Test bitrate scaling with NTSC fractional FPS (29.97)."""
        sm = SmartMode()
        stream = {
            "height": 720,
            "width": 1280,
            "r_frame_rate": "30000/1001",  # 29.97 fps
            "color_space": "",
            "codec_name": "h264",
        }
        # 1280x720@29.97 with 1.2Mbps = 0.043 bpp/s (< 0.08, low complexity)
        # 29.97 >= 29.5, so scale = 1.7, content = 0.85
        # 1200000 * 1.7 * 0.85 = 1733999
        assert sm.scale_bitrate(stream, 1_200_000) == 1_733_999

    def test_scale_bitrate_pal_fps(self):
        """Test bitrate scaling with PAL FPS (25)."""
        sm = SmartMode()
        stream = {
            "height": 720,
            "r_frame_rate": "25/1",
            "color_space": "",
            "codec_name": "h264",
        }
        # 25 fps, scale = 1.5
        assert sm.scale_bitrate(stream, 1_200_000) == 1_800_000

    def test_scale_bitrate_film_fps(self):
        """Test bitrate scaling with film FPS (23.976)."""
        sm = SmartMode()
        stream = {
            "height": 1080,
            "width": 1920,
            "r_frame_rate": "24000/1001",  # 23.976 fps
            "color_space": "",
            "codec_name": "h264",
        }
        # < 24 fps triggers low complexity, scale = 1.3, content = 0.85
        # 1200000 * 1.3 * 0.85 = 1326000
        assert sm.scale_bitrate(stream, 1_200_000) == 1_326_000

    def test_get_bitrate_fallback_4k(self):
        """Test fallback bitrate for 4K resolution."""
        sm = SmartMode()
        stream = {"height": 2160}  # 4K
        # Should use DEFAULT_SD_BITRATE * 5 = 6000000
        assert sm.get_bitrate(stream) == 6_000_000

    def test_get_bitrate_fallback_ultra_low_res(self):
        """Test fallback bitrate for very low resolution (e.g., 240p)."""
        sm = SmartMode()
        stream = {"height": 240}
        # Should use DEFAULT_SD_BITRATE = 1200000
        assert sm.get_bitrate(stream) == 1_200_000

    def test_get_bitrate_with_zero_value(self):
        """Test fallback when bitrate is zero or empty string."""
        sm = SmartMode()
        stream = {"bit_rate": "0", "height": 720}
        # Zero bitrate should be treated as valid (even if unusual)
        assert sm.get_bitrate(stream) == 0

        stream = {"bit_rate": "", "height": 720}
        # Empty string should trigger fallback
        assert sm.get_bitrate(stream) == 3_000_000

    def test_get_bitrate_with_none_value(self):
        """Test fallback when bitrate is None."""
        sm = SmartMode()
        stream = {"bit_rate": None, "height": 1080}
        # None should trigger fallback
        assert sm.get_bitrate(stream) == 6_000_000

    def test_scale_bitrate_missing_all_fields(self):
        """Test bitrate scaling with all fields missing (complete fallback)."""
        sm = SmartMode()
        stream = {}
        # Should use defaults: height=480, fps=30, color_space=""
        # height <= 480, so SD -> scale = 1.2
        result = sm.scale_bitrate(stream, 1_200_000)
        assert result == 1_440_000

    def test_scale_bitrate_with_integer_fps(self):
        """Test bitrate scaling when FPS is already an integer (no width, no content adjustment)."""
        sm = SmartMode()
        stream = {
            "height": 1080,
            "r_frame_rate": 30,
            "color_space": "",
            "codec_name": "h264",
        }
        # FPS 30 >= 29.5, scale = 1.7, no content adjustment without width
        # 1200000 * 1.7 = 2040000
        assert sm.scale_bitrate(stream, 1_200_000) == 2_040_000

    def test_scale_bitrate_with_float_fps(self):
        """Test bitrate scaling when FPS is a float (no width, no content adjustment)."""
        sm = SmartMode()
        stream = {
            "height": 1080,
            "r_frame_rate": 29.97,
            "color_space": "",
            "codec_name": "h264",
        }
        # FPS 29.97 >= 29.5, scale = 1.7, no content adjustment without width
        # 1200000 * 1.7 = 2040000
        assert sm.scale_bitrate(stream, 1_200_000) == 2_040_000

    def test_sd_with_bt470bg_overrides_height(self):
        """Test that bt470bg color space forces SD even for HD resolution."""
        sm = SmartMode()
        # Even at 1080p, bt470bg should be classified as SD
        assert sm.is_sd(1080, "bt470bg") is True
        scale = sm.calculate_scale_factor(1080, 30, "bt470bg")
        assert scale == 1.2  # SD scale factor

    def test_get_bitrate_format_fallback_when_stream_invalid(self):
        """Test format bitrate is used when stream bitrate is invalid."""
        sm = SmartMode()
        stream = {"bit_rate": "not_a_number", "height": 720}
        format_info = {"bit_rate": "2000000"}
        assert sm.get_bitrate(stream, format_info) == 2_000_000

    def test_get_bitrate_both_sources_invalid(self):
        """Test fallback when both stream and format bitrates are invalid."""
        sm = SmartMode()
        stream = {"bit_rate": "invalid", "height": 720}
        format_info = {"bit_rate": "also_invalid"}
        # Should fallback to height-based calculation
        assert sm.get_bitrate(stream, format_info) == 3_000_000

    def test_scale_bitrate_edge_case_zero_base(self):
        """Test scaling with zero base bitrate."""
        sm = SmartMode()
        stream = {
            "height": 1080,
            "r_frame_rate": "30/1",
            "color_space": "",
            "codec_name": "h264",
        }
        # 0 * 1.7 = 0
        assert sm.scale_bitrate(stream, 0) == 0

    def test_codec_adjustment_future_enhancement(self):
        """Test codec adjustment for various codecs (currently all 1.0)."""
        sm = SmartMode()
        # All should currently return 1.0 (neutral)
        assert sm.get_codec_adjustment("h264") == 1.0
        assert sm.get_codec_adjustment("h265") == 1.0
        assert sm.get_codec_adjustment("mpeg1video") == 1.0
        assert sm.get_codec_adjustment("vp9") == 1.0
        assert sm.get_codec_adjustment("av1") == 1.0


class TestContentAwareScaling:
    """Tests for content-aware bitrate scaling."""

    def test_is_black_and_white_gray(self):
        """Test B&W detection with gray pixel format."""
        sm = SmartMode()
        stream = {"pix_fmt": "gray"}
        assert sm.is_black_and_white(stream) is True

    def test_is_black_and_white_gray8(self):
        """Test B&W detection with gray8 pixel format."""
        sm = SmartMode()
        stream = {"pix_fmt": "gray8"}
        assert sm.is_black_and_white(stream) is True

    def test_is_black_and_white_gray16(self):
        """Test B&W detection with gray16 pixel format."""
        sm = SmartMode()
        stream = {"pix_fmt": "gray16"}
        assert sm.is_black_and_white(stream) is True

    def test_is_not_black_and_white_yuv420p(self):
        """Test that color formats are not detected as B&W."""
        sm = SmartMode()
        stream = {"pix_fmt": "yuv420p"}
        assert sm.is_black_and_white(stream) is False

    def test_is_not_black_and_white_yuvj420p(self):
        """Test that JPEG color formats are not detected as B&W."""
        sm = SmartMode()
        stream = {"pix_fmt": "yuvj420p"}
        assert sm.is_black_and_white(stream) is False

    def test_is_not_black_and_white_missing(self):
        """Test that missing pixel format is not detected as B&W."""
        sm = SmartMode()
        stream = {}
        assert sm.is_black_and_white(stream) is False

    def test_is_low_complexity_by_bitrate(self):
        """Test low-complexity detection via low bitrate per pixel."""
        sm = SmartMode()
        # 640x480@30fps with 700kbps = 0.0763 bpp/s (< 0.08 threshold)
        stream = {
            "height": 480,
            "width": 640,
            "r_frame_rate": "30/1",
        }
        base_bitrate = 700_000  # 700 kbps
        assert sm.is_low_complexity(stream, base_bitrate) is True

    def test_is_low_complexity_by_low_fps(self):
        """Test low-complexity detection via very low fps."""
        sm = SmartMode()
        # 720p at 20fps (very low fps, typical for some documentaries)
        stream = {
            "height": 720,
            "width": 1280,
            "r_frame_rate": "20/1",
        }
        base_bitrate = 1_400_000  # 1.4 Mbps = 0.076 bpp/s
        assert sm.is_low_complexity(stream, base_bitrate) is True

    def test_is_not_low_complexity_high_bitrate(self):
        """Test that high bitrate content is not detected as low-complexity."""
        sm = SmartMode()
        # 640x480@30fps with 1.2Mbps = 0.13 bpp/s (> 0.08 threshold)
        stream = {
            "height": 480,
            "width": 640,
            "r_frame_rate": "30/1",
        }
        base_bitrate = 1_200_000  # 1.2 Mbps
        assert sm.is_low_complexity(stream, base_bitrate) is False

    def test_is_not_low_complexity_high_fps(self):
        """Test that high fps with adequate bitrate prevents low-complexity detection."""
        sm = SmartMode()
        # 720p at 30fps with adequate bitrate
        stream = {
            "height": 720,
            "width": 1280,
            "r_frame_rate": "30/1",
        }
        base_bitrate = 3_000_000  # 3 Mbps = 0.108 bpp/s (> 0.08 threshold)
        assert sm.is_low_complexity(stream, base_bitrate) is False

    def test_is_low_complexity_with_fractional_fps(self):
        """Test low-complexity detection with very low fractional fps."""
        sm = SmartMode()
        # 720p at 20fps (very low)
        stream = {
            "height": 720,
            "width": 1280,
            "r_frame_rate": "20000/1001",  # ~20 fps
        }
        base_bitrate = 1_400_000  # 1.4 Mbps = 0.076 bpp/s
        assert sm.is_low_complexity(stream, base_bitrate) is True

    def test_get_content_adjustment_bw_only(self):
        """Test content adjustment for B&W content only."""
        sm = SmartMode()
        stream = {
            "pix_fmt": "gray",
            "height": 480,
            "width": 640,
            "r_frame_rate": "30/1",
        }
        base_bitrate = 1_200_000
        assert sm.get_content_adjustment(stream, base_bitrate) == 0.75

    def test_get_content_adjustment_low_complexity_only(self):
        """Test content adjustment for low-complexity content only."""
        sm = SmartMode()
        stream = {
            "pix_fmt": "yuv420p",
            "height": 480,
            "width": 640,
            "r_frame_rate": "30/1",
        }
        base_bitrate = 700_000  # Low bitrate triggers low-complexity (0.076 bpp/s)
        assert sm.get_content_adjustment(stream, base_bitrate) == 0.85

    def test_get_content_adjustment_both(self):
        """Test content adjustment for B&W + low-complexity."""
        sm = SmartMode()
        stream = {
            "pix_fmt": "gray",
            "height": 480,
            "width": 640,
            "r_frame_rate": "30/1",
        }
        base_bitrate = 700_000  # Low bitrate + B&W
        assert sm.get_content_adjustment(stream, base_bitrate) == 0.65

    def test_get_content_adjustment_none(self):
        """Test content adjustment for normal content with adequate bitrate."""
        sm = SmartMode()
        stream = {
            "pix_fmt": "yuv420p",
            "height": 1080,
            "width": 1920,
            "r_frame_rate": "30/1",
        }
        base_bitrate = 8_000_000  # High bitrate: 0.129 bpp/s (> 0.08 threshold)
        assert sm.get_content_adjustment(stream, base_bitrate) == 1.0

    def test_scale_bitrate_with_bw_content(self):
        """Test bitrate scaling with B&W content."""
        sm = SmartMode()
        stream = {
            "pix_fmt": "gray",
            "height": 480,
            "width": 640,
            "r_frame_rate": "30/1",
            "color_space": "bt470bg",
            "codec_name": "h264",
        }
        # SD + B&W: 1200000 * 1.2 * 0.75 = 1080000
        assert sm.scale_bitrate(stream, 1_200_000) == 1_080_000

    def test_scale_bitrate_with_low_complexity_content(self):
        """Test bitrate scaling with low-complexity content."""
        sm = SmartMode()
        stream = {
            "pix_fmt": "yuv420p",
            "height": 720,
            "width": 1280,
            "r_frame_rate": "24/1",
            "color_space": "",
            "codec_name": "h264",
        }
        # Low FPS (24) -> scale=1.3, low-complexity -> 0.85
        # 1200000 * 1.3 * 0.85 = 1326000
        assert sm.scale_bitrate(stream, 1_200_000) == 1_326_000

    def test_scale_bitrate_with_bw_and_low_complexity(self):
        """Test bitrate scaling with B&W + low-complexity content."""
        sm = SmartMode()
        stream = {
            "pix_fmt": "gray",
            "height": 480,
            "width": 640,
            "r_frame_rate": "30/1",
            "color_space": "bt470bg",
            "codec_name": "h264",
        }
        base_bitrate = 700_000  # Low enough to trigger low-complexity (0.076 bpp/s)
        # SD + B&W + low-complexity: 700000 * 1.2 * 0.65 = 546000
        assert sm.scale_bitrate(stream, base_bitrate) == 546_000

    def test_scale_bitrate_normal_content_unchanged(self):
        """Test that normal content scaling is not affected."""
        sm = SmartMode()
        stream = {
            "pix_fmt": "yuv420p",
            "height": 1080,
            "width": 1920,
            "r_frame_rate": "30/1",
            "color_space": "",
            "codec_name": "h264",
        }
        base_bitrate = 8_000_000  # High bitrate: 0.129 bpp/s (> 0.08 threshold)
        # High FPS (30) -> scale=1.7, normal content -> 1.0
        # 8000000 * 1.7 * 1.0 = 13600000
        assert sm.scale_bitrate(stream, base_bitrate) == 13_600_000

    def test_is_low_complexity_missing_dimensions(self):
        """Test low-complexity detection with missing width/height."""
        sm = SmartMode()
        stream = {"r_frame_rate": "12/1"}  # Very low fps (< 24)
        base_bitrate = 1_000_000
        # Should detect low fps and return True
        assert sm.is_low_complexity(stream, base_bitrate) is True

    def test_is_low_complexity_zero_pixels(self):
        """Test low-complexity detection with invalid dimensions."""
        sm = SmartMode()
        stream = {
            "height": 0,
            "width": 0,
            "r_frame_rate": "30/1",
        }
        base_bitrate = 1_000_000
        # Should not crash and return False (no valid calculation possible)
        assert sm.is_low_complexity(stream, base_bitrate) is False

    def test_is_low_complexity_zero_fps(self):
        """Test low-complexity detection with zero fps."""
        sm = SmartMode()
        stream = {
            "height": 480,
            "width": 640,
            "r_frame_rate": "0/1",
        }
        base_bitrate = 1_000_000
        # Should not crash and return False
        assert sm.is_low_complexity(stream, base_bitrate) is False
