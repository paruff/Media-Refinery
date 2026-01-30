import pytest
from src.config.config import ConfigLoader
import yaml


@pytest.fixture
def config_file(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_data = {"key": "value"}
    with config_path.open("w") as file:
        yaml.dump(config_data, file)
    return config_path


@pytest.fixture
def config_loader(config_file):
    return ConfigLoader(config_file)


def test_load_config(config_loader):
    config = config_loader.load_config()
    assert config == {"key": "value"}


def test_load_config_invalid_file(tmp_path):
    invalid_path = tmp_path / "invalid.yaml"
    loader = ConfigLoader(invalid_path)
    config = loader.load_config()
    assert config == {}
