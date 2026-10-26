import pytest

from app.core.paths import (
    MAX_COMPONENT_BYTES,
    PathEscapeError,
    confine,
    ensure_inside,
    sanitize_component,
)


def test_sanitize_replaces_illegal_and_leading_dots():
    assert sanitize_component('..AC/DC: "Back" in Black?') == "AC-DC- -Back- in Black-"


def test_sanitize_never_empty_and_no_dotdot():
    assert sanitize_component("..") == "_"
    assert sanitize_component("") == "_"


def test_sanitize_truncates_bytes_keeping_extension():
    out = sanitize_component("é" * 300 + ".flac")
    assert len(out.encode()) <= MAX_COMPONENT_BYTES and out.endswith(".flac")


def test_confine_stays_inside(tmp_path):
    p = confine(tmp_path, "Artist", "../../etc", "x.flac")
    assert p.is_relative_to(tmp_path.resolve())


def test_confine_rejects_symlink_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "link").symlink_to(outside)
    with pytest.raises(PathEscapeError):
        confine(root, "link", "x.mkv")


def test_ensure_inside(tmp_path):
    assert ensure_inside(tmp_path, tmp_path / "a" / "b")
    with pytest.raises(PathEscapeError):
        ensure_inside(tmp_path / "a", tmp_path / "b")
