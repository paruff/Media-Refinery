from app.services.subtitle_service import SubtitleService


def test_detect_subtitle_streams_text(monkeypatch, tmp_path):
    svc = SubtitleService()
    fake_ffprobe_output = '{"streams": [{"index": 0, "codec_name": "mov_text", "tags": {"language": "eng"}}]}'

    def fake_run(cmd, capture_output, check, text):
        class Result:
            stdout = fake_ffprobe_output

        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)
    streams = svc.detect_subtitle_streams(tmp_path / "movie.mp4")
    assert streams[0]["codec"] == "mov_text"
    assert streams[0]["lang"] == "eng"


def test_extract_text_subtitle(monkeypatch, tmp_path):
    svc = SubtitleService()

    def fake_run(cmd, check):
        return None

    monkeypatch.setattr("subprocess.run", fake_run)
    assert svc.extract_text_subtitle(
        tmp_path / "movie.mp4", 0, tmp_path / "movie.en.srt"
    )


def test_extract_image_subtitle(monkeypatch, tmp_path):
    svc = SubtitleService()

    def fake_run(cmd, check):
        return None

    monkeypatch.setattr("subprocess.run", fake_run)
    assert svc.extract_image_subtitle(
        tmp_path / "movie.mkv", 1, tmp_path / "movie.eng.mks"
    )


def test_ocr_image_subtitle_logs_warning(monkeypatch, tmp_path, caplog):
    svc = SubtitleService()
    with caplog.at_level("WARNING"):
        result = svc.ocr_image_subtitle(
            tmp_path / "movie.eng.mks", tmp_path / "movie.eng.srt"
        )
        assert not result
        assert "Needs manual intervention" in caplog.text


def test_find_existing_srt(tmp_path):
    svc = SubtitleService()
    srt = tmp_path / "movie.en.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")
    found = svc.find_existing_srt(tmp_path / "movie.mkv", "en")
    assert found == srt


def test_mux_srt_into_mkv(monkeypatch, tmp_path):
    svc = SubtitleService()

    def fake_run(cmd, check):
        return None

    monkeypatch.setattr("subprocess.run", fake_run)
    assert svc.mux_srt_into_mkv(
        tmp_path / "movie.mkv", tmp_path / "movie.en.srt", tmp_path / "out.mkv"
    )


def test_convert_subtitles_text(monkeypatch, tmp_path):
    svc = SubtitleService()
    # Patch detect_subtitle_streams to return a text stream
    monkeypatch.setattr(
        svc,
        "detect_subtitle_streams",
        lambda f: [{"index": 0, "codec": "mov_text", "lang": "eng"}],
    )
    monkeypatch.setattr(svc, "extract_text_subtitle", lambda f, i, o: True)
    monkeypatch.setattr(svc, "mux_srt_into_mkv", lambda i, s, o: True)
    assert svc.convert_subtitles(tmp_path / "movie.mp4", tmp_path / "out.mkv")


def test_convert_subtitles_image_with_sidecar(monkeypatch, tmp_path):
    svc = SubtitleService()
    # Patch detect_subtitle_streams to return an image stream
    monkeypatch.setattr(
        svc,
        "detect_subtitle_streams",
        lambda f: [{"index": 1, "codec": "pgs", "lang": "eng"}],
    )
    monkeypatch.setattr(svc, "extract_image_subtitle", lambda f, i, o: True)
    monkeypatch.setattr(svc, "ocr_image_subtitle", lambda m, s: False)
    monkeypatch.setattr(
        svc, "find_existing_srt", lambda f, lang: tmp_path / "movie.eng.srt"
    )
    monkeypatch.setattr(svc, "mux_srt_into_mkv", lambda i, s, o: True)
    assert svc.convert_subtitles(tmp_path / "movie.mkv", tmp_path / "out.mkv")
