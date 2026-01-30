import os
import logging


class Config:
    def __init__(
        self,
        input_dir,
        output_dir,
        format,
        preserve_metadata,
        compression_level,
        dry_run,
        state_dir,
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.format = format
        self.preserve_metadata = preserve_metadata
        self.compression_level = compression_level
        self.dry_run = dry_run
        self.state_dir = state_dir


class Result:
    def __init__(self, success, output_path, checksum, format):
        self.success = success
        self.output_path = output_path
        self.checksum = checksum
        self.format = format


class Converter:
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config

    def determine_bitrate(self, genre, is_black_and_white):
        """
        Determine the appropriate bitrate based on genre and whether the source is black and white.

        Args:
            genre (str): The genre of the video (e.g., "documentary", "comedy", "action").
            is_black_and_white (bool): Whether the source video is black and white.

        Returns:
            str: The recommended bitrate (e.g., "2M", "4M").
        """
        base_bitrate = "2M" if is_black_and_white else "4M"

        genre_bitrates = {
            "documentary": "3M",
            "comedy": "4M",
            "action": "6M",
        }

        return genre_bitrates.get(genre, base_bitrate)

    def convert_file(self, input_path, genre, is_black_and_white):
        """
        Convert a file to the desired format with bitrate sensitivity.

        Args:
            input_path (str): Path to the input video file.
            genre (str): The genre of the video.
            is_black_and_white (bool): Whether the source video is black and white.

        Returns:
            Result: The result of the conversion.
        """
        bitrate = self.determine_bitrate(genre, is_black_and_white)
        self.logger.info(f"Converting file: {input_path} with bitrate: {bitrate}")

        # Stub: always return success for now
        return Result(
            success=True, output_path=input_path, checksum="", format=self.config.format
        )

    def validate_input_file(self, path):
        """
        Validate the input file to ensure it exists and is non-empty.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Input file {path} does not exist.")
        if os.path.getsize(path) == 0:
            raise ValueError(f"Input file {path} is empty.")


class VideoConverter:
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config

    def convert_file(self, input_path):
        """
        Convert a file to the desired format.
        This is a stub implementation.
        """
        self.logger.info(f"Converting file: {input_path}")
        # Stub: always return success for now
        return Result(
            success=True, output_path=input_path, checksum="", format=self.config.format
        )

    def convert(self, input_path, output_dir):
        """
        Convert a video file to the desired format.
        """
        output_file = output_dir / f"{input_path.stem}.mkv"
        with open(output_file, "w") as f:
            f.write("mock video content")
        return output_file
