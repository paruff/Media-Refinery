import pytest
from pathlib import Path
from src.validator.validator import Validator

@pytest.fixture
def validator():
    return Validator()

def test_validate_file(validator, tmp_path):
    valid_file = tmp_path / "test.mp3"
    valid_file.touch()
    invalid_file = tmp_path / "test.txt"
    invalid_file.touch()

    assert validator.validate_file(valid_file) is True
    assert validator.validate_file(invalid_file) is False

def test_validate_directory(validator, tmp_path):
    valid_file = tmp_path / "test.mp3"
    valid_file.touch()
    invalid_file = tmp_path / "test.txt"
    invalid_file.touch()

    valid_files = validator.validate_directory(tmp_path)

    assert valid_file in valid_files
    assert invalid_file not in valid_files