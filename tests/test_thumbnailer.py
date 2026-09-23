from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.thumbnailer import get_thumbnail, prune_legacy_thumbnail_cache, thumbnail_path


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


def test_cache_key_changes_when_thumbnail_settings_change(tmp_path: Path) -> None:
    source = tmp_path / "photos" / "image.jpg"
    cache = tmp_path / "thumbcache"
    source.parent.mkdir()
    source.write_bytes(b"image")

    default = thumbnail_path(cache, source, size=320, quality=75)
    resized = thumbnail_path(cache, source, size=640, quality=75)
    higher_quality = thumbnail_path(cache, source, size=320, quality=90)

    assert len({default, resized, higher_quality}) == 3


def test_audio_uses_fallback_thumbnail(tmp_path: Path) -> None:
    source = tmp_path / "photos" / "song.mp3"
    cache = tmp_path / "thumbcache"
    source.parent.mkdir()
    source.write_bytes(b"not-real-audio")

    thumbnail = get_thumbnail(source, cache)

    assert thumbnail.parent == cache
    assert thumbnail.name == "fallback-audio-320-75.jpg"
    assert thumbnail.exists()


def test_fallback_thumbnail_changes_when_settings_change(tmp_path: Path) -> None:
    source = tmp_path / "photos" / "song.mp3"
    cache = tmp_path / "thumbcache"
    source.parent.mkdir()
    source.write_bytes(b"not-real-audio")

    first = get_thumbnail(source, cache, size=120, quality=70)
    second = get_thumbnail(source, cache, size=240, quality=80)

    assert first != second
    assert not first.exists()
    assert second.name == "fallback-audio-240-80.jpg"
    assert second.exists()


def test_legacy_cache_files_are_pruned_without_touching_other_files(tmp_path: Path) -> None:
    cache = tmp_path / "thumbcache"
    cache.mkdir()
    legacy_thumbnail = cache / f"{'a' * 40}.jpg"
    legacy_fallback = cache / "fallback-audio.jpg"
    unrelated = cache / "keep-me.txt"
    legacy_thumbnail.write_bytes(b"old")
    legacy_fallback.write_bytes(b"old")
    unrelated.write_bytes(b"keep")

    prune_legacy_thumbnail_cache(cache)

    assert not legacy_thumbnail.exists()
    assert not legacy_fallback.exists()
    assert unrelated.exists()
