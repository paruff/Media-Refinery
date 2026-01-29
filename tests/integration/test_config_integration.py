import pytest
from pathlib import Path
from src.config.config import ConfigLoader
import yaml

@pytest.fixture
def integration_config_file(tmp_path):
    config_path = tmp_path / "integration_config.yaml"
    config_data = {
        "database": {
            "host": "localhost",
            "port": 5432
        },
        "api": {
            "key": "test_key"
        }
    }
    with config_path.open("w") as file:
        yaml.dump(config_data, file)
    return config_path

def test_integration_load_config(integration_config_file):
    loader = ConfigLoader(integration_config_file)
    config = loader.load_config()

    assert config["database"]["host"] == "localhost"
    assert config["database"]["port"] == 5432
    assert config["api"]["key"] == "test_key"