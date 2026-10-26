from pathlib import Path


class Validator:
    """
    Validates files and directories based on predefined rules.
    """

    def __init__(self, allowed_extensions: list[str] = None):  # noqa: RUF013
        self.allowed_extensions = allowed_extensions or [
            ".mp3",
            ".flac",
            ".aac",
            ".m4a",
            ".ogg",
            ".wav",
        ]

    def validate_file(self, file_path: Path) -> bool:
        """
        Validates a single file based on its extension and existence.

        Args:
            file_path (Path): The path to the file to validate.

        Returns:
            bool: True if the file is valid, False otherwise.
        """
        if not file_path.exists():
            print(f"File does not exist: {file_path}")  # noqa: T201
            return False

        if file_path.suffix.lower() not in self.allowed_extensions:
            print(f"Invalid file extension: {file_path.suffix}")  # noqa: T201
            return False

        return True

    def validate_directory(self, directory_path: Path) -> list[Path]:
        """
        Validates all files in a directory.

        Args:
            directory_path (Path): The path to the directory to validate.

        Returns:
            List[Path]: A list of valid file paths.
        """
        if not directory_path.is_dir():
            print(f"Not a directory: {directory_path}")  # noqa: T201
            return []

        valid_files = []
        for file_path in directory_path.iterdir():
            if self.validate_file(file_path):
                valid_files.append(file_path)

        return valid_files
