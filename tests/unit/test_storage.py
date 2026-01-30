import pytest
from src.storage.storage import Storage


@pytest.fixture
def storage():
    return Storage()


def test_save_file(storage, tmp_path):
    file_path = tmp_path / "test.txt"
    content = "Hello, World!"

    result = storage.save_file(file_path, content)

    assert result is True
    assert file_path.read_text() == content


def test_delete_file(storage, tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.touch()

    result = storage.delete_file(file_path)

    assert result is True
    assert not file_path.exists()
