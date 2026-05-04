from __future__ import annotations

from pathlib import Path

import pytest

from app.scanner import PathSafetyError, classify_media, list_folder, safe_resolve


def touch(path: Path, data: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_safe_resolve_rejects_parent_traversal(tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()

    with pytest.raises(PathSafetyError):
        safe_resolve(media_root, "../outside.jpg")


def test_safe_resolve_rejects_encoded_traversal(tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()

    with pytest.raises(PathSafetyError):
        safe_resolve(media_root, "%2e%2e/outside.jpg")


def test_safe_resolve_rejects_symlink_escape(tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    outside = tmp_path / "outside"
    media_root.mkdir()
    outside.mkdir()
    touch(outside / "secret.jpg")
    (media_root / "escape").symlink_to(outside)

    with pytest.raises(PathSafetyError):
        safe_resolve(media_root, "escape/secret.jpg")


def test_classifies_common_media_types() -> None:
    assert classify_media(Path("photo.JPG")) == "image"
    assert classify_media(Path("clip.mp4")) == "video"
    assert classify_media(Path("movie.mkv")) == "video"
    assert classify_media(Path("song.mp3")) == "audio"
    assert classify_media(Path("notes.txt")) == "other"


def test_list_folder_excludes_hidden_and_reports_stats(tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    outside = tmp_path / "outside"
    touch(media_root / "image.jpg")
    touch(media_root / "movie.mkv")
    touch(media_root / "song.mp3")
    touch(media_root / ".hidden.jpg")
    touch(outside / "secret.jpg")
    (media_root / "Album").mkdir()
    (media_root / ".secret").mkdir()
    (media_root / "escape").symlink_to(outside)

    listing = list_folder(media_root)

    assert [folder.name for folder in listing.folders] == ["Album"]
    assert [item.name for item in listing.media] == ["image.jpg", "movie.mkv", "song.mp3"]
    assert listing.stats == {"folders": 1, "images": 1, "videos": 1, "audio": 1}


def test_list_folder_includes_folder_preview_paths(tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    touch(media_root / "Album" / "a.jpg")
    touch(media_root / "Album" / "b.mp4")
    touch(media_root / "Album" / ".hidden.jpg")
    touch(media_root / "Album" / "notes.txt")
    touch(media_root / "Album" / "Subfolder" / "nested.jpg")

    listing = list_folder(media_root)

    assert listing.folders[0].preview_paths == ["Album/a.jpg", "Album/b.mp4"]


def test_list_folder_paginates_media(tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    for name in ["a.jpg", "b.jpg", "c.jpg"]:
        touch(media_root / name)

    listing = list_folder(media_root, page=2, per_page=2)

    assert [item.name for item in listing.media] == ["c.jpg"]
    assert listing.has_previous is True
    assert listing.has_next is False
