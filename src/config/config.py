from pathlib import Path
import yaml
from typing import Any, Dict

class ConfigLoader:
    """
    Handles loading and parsing configuration files.
    """

    def __init__(self, config_path: Path):
        self.config_path = config_path

    def load_config(self) -> Dict[str, Any]:
        """
        Loads the configuration file and parses it as a dictionary.

        Returns:
            Dict[str, Any]: The parsed configuration data.
        """
        try:
            with self.config_path.open("r") as file:
                return yaml.safe_load(file)
        except Exception as e:
            print(f"Failed to load configuration: {e}")
            return {}