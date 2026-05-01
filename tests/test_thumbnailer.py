from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.thumbnailer import get_thumbnail, thumbnail_path


def test_image_thumbnail_written_to_cache(tmp_path: Path) -> None:
    source = tmp_path / "photos" / "image.jpg"
    cache = tmp_path / "thumbcache"
    source.parent.mkdir()
    Image.new("RGB", (800, 600), "#53b8a4").save(source)

    thumbnail = get_thumbnail(source, cache, size=120, quality=70)

    assert thumbnail.parent == cache
    assert thumbnail.exists()
    assert thumbnail != source
    with Image.open(thumbnail) as image:
        assert max(image.size) == 120


def test_cache_key_changes_when_source_changes(tmp_path: Path) -> None:
    source = tmp_path / "photos" / "image.jpg"
    cache = tmp_path / "thumbcache"
    source.parent.mkdir()
    source.write_bytes(b"one")
    first = thumbnail_path(cache, source)
    source.write_bytes(b"two")
    second = thumbnail_path(cache, source)

    assert first != second


def test_audio_uses_fallback_thumbnail(tmp_path: Path) -> None:
    source = tmp_path / "photos" / "song.mp3"
    cache = tmp_path / "thumbcache"
    source.parent.mkdir()
    source.write_bytes(b"not-real-audio")

    thumbnail = get_thumbnail(source, cache)

    assert thumbnail.parent == cache
    assert thumbnail.name == "fallback-audio.jpg"
    assert thumbnail.exists()
