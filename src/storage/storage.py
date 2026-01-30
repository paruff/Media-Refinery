from pathlib import Path
from typing import Union


class Storage:
    """
    Handles file storage operations such as saving and deleting files.
    """

    def save_file(self, file_path: Path, content: Union[str, bytes]) -> bool:
        """
        Saves content to a file.

        Args:
            file_path (Path): The path to the file to save.
            content (Union[str, bytes]): The content to write to the file.

        Returns:
            bool: True if the file was saved successfully, False otherwise.
        """
        try:
            with file_path.open("wb" if isinstance(content, bytes) else "w") as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Failed to save file {file_path}: {e}")
            return False

    def delete_file(self, file_path: Path) -> bool:
        """
        Deletes a file.

        Args:
            file_path (Path): The path to the file to delete.

        Returns:
            bool: True if the file was deleted successfully, False otherwise.
        """
        try:
            if file_path.exists():
                file_path.unlink()
                return True
            else:
                print(f"File does not exist: {file_path}")
                return False
        except Exception as e:
            print(f"Failed to delete file {file_path}: {e}")
            return False
