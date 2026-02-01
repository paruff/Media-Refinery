import pytest
from src.audio.converter import AudioConverter


@pytest.mark.asyncio
async def test_music_album_conversion(tmp_path):
    # Simulate a music album directory with multiple tracks
    album_dir = tmp_path / "Asia - Asia (1982)"
    album_dir.mkdir()
    tracks = []
    for i in range(1, 4):
        f = album_dir / f"0{i} - Heat of the Moment.mp3"
        f.touch()
        tracks.append(f)
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    converter = AudioConverter()
    results = []
    for track in tracks:
        result = await converter.convert(track, output_dir)
        results.append(result)
    for result in results:
        assert result.success is True
        assert result.output_path.exists()
        assert result.output_path.suffix == ".flac"


@pytest.mark.asyncio
async def test_music_structure_and_naming(tmp_path):
    # Simulate Music Assistant structure: Artist/Album/Track
    artist = "Asia"
    album = "Asia (1982)"
    album_dir = tmp_path / artist / album
    album_dir.mkdir(parents=True)
    track = album_dir / "01 - Heat of the Moment.flac"
    track.touch()
    # Check structure
    assert album_dir.exists()
    assert track.exists()
    assert track.name.startswith("01 - ")
    assert track.suffix == ".flac"


@pytest.mark.asyncio
async def test_multi_disc_album(tmp_path):
    # Simulate multi-disc album
    artist = "Asia"
    album = "Asia (1982)"
    disc1 = tmp_path / artist / album / "CD1"
    disc2 = tmp_path / artist / album / "CD2"
    disc1.mkdir(parents=True)
    disc2.mkdir(parents=True)
    t1 = disc1 / "01 - Track1.flac"
    t2 = disc2 / "01 - Track2.flac"
    t1.touch()
    t2.touch()
    assert t1.exists() and t2.exists()
    assert t1.parent.name == "CD1"
    assert t2.parent.name == "CD2"
