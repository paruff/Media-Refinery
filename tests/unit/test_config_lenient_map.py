from app.core.config import Settings


def test_malformed_plex_sections_is_ignored_not_fatal(monkeypatch):
    monkeypatch.setenv("PLEX_SECTIONS", "music=1")  # not JSON
    monkeypatch.setenv("NOTIFY_PATH_MAP", "[1]")  # JSON, not a map
    s = Settings(_env_file=None)
    assert s.PLEX_SECTIONS == {} and s.NOTIFY_PATH_MAP == {}


def test_valid_plex_sections_still_parse(monkeypatch):
    monkeypatch.setenv("PLEX_SECTIONS", '{"music": "3"}')
    monkeypatch.setenv("NOTIFY_PATH_MAP", "")
    s = Settings(_env_file=None)
    assert s.PLEX_SECTIONS == {"music": "3"} and s.NOTIFY_PATH_MAP == {}
