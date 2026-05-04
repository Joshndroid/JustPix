from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeVar
from urllib.parse import unquote
import mimetypes

MediaKind = Literal["image", "video", "audio", "other"]

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif",
    ".heic", ".heif", ".avif", ".jxl", ".svg", ".ico",
}
VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".ts", ".wmv",
    ".flv", ".3gp", ".ogv",
}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".ogg", ".oga", ".wav", ".flac"}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


class PathSafetyError(ValueError):
    """Raised when a requested path is not safe to resolve under MEDIA_ROOT."""


@dataclass(frozen=True)
class FolderEntry:
    name: str
    path: str
    mtime: float
    item_count: int
    preview_paths: list[str]


@dataclass(frozen=True)
class MediaEntry:
    name: str
    path: str
    media_type: MediaKind
    content_type: str
    size: int
    mtime: float


@dataclass(frozen=True)
class FolderListing:
    path: str
    parent: str | None
    folders: list[FolderEntry]
    media: list[MediaEntry]
    stats: dict[str, int]
    page: int
    per_page: int
    total_media: int
    total_folders: int
    has_next: bool
    has_previous: bool


def _decode_path(value: str) -> str:
    previous = value
    for _ in range(3):
        decoded = unquote(previous)
        if decoded == previous:
            return decoded
        previous = decoded
    return previous


def _is_hidden_relative(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts if part not in {"", "."})


def safe_resolve(media_root: Path, requested_path: str = "") -> Path:
    decoded = _decode_path((requested_path or "").replace("\\", "/")).lstrip("/")
    if "\x00" in decoded:
        raise PathSafetyError("Invalid path")

    relative = Path(decoded)
    if relative.is_absolute() or any(part in {"..", ""} for part in relative.parts):
        if decoded not in {"", "."}:
            raise PathSafetyError("Path escapes media root")

    root = media_root.resolve(strict=True)
    target = (root / relative).resolve(strict=True)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise PathSafetyError("Path escapes media root") from exc
    return target


def relative_media_path(media_root: Path, path: Path) -> str:
    root = media_root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    return resolved.relative_to(root).as_posix()


def classify_media(path: Path) -> MediaKind:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    return "other"


def content_type_for(path: Path) -> str:
    kind = classify_media(path)
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    return {
        "image": "application/octet-stream",
        "video": "application/octet-stream",
        "audio": "application/octet-stream",
    }.get(kind, "application/octet-stream")


def _folder_item_count(path: Path) -> int:
    try:
        return sum(1 for child in path.iterdir() if not child.name.startswith("."))
    except OSError:
        return 0


def _folder_preview_paths(media_root: Path, folder: Path, *, limit: int = 4) -> list[str]:
    previews: list[str] = []
    try:
        children = sorted(folder.iterdir(), key=lambda child: child.name.lower())
    except OSError:
        return previews

    for child in children:
        if len(previews) >= limit:
            break
        if child.name.startswith("."):
            continue
        try:
            child.resolve(strict=True).relative_to(media_root)
        except (OSError, ValueError):
            continue
        if not child.is_file() or classify_media(child) == "other":
            continue
        relative = relative_media_path(media_root, child)
        if _is_hidden_relative(Path(relative)):
            continue
        previews.append(relative)
    return previews


def _parent_for(relative_path: str) -> str | None:
    if not relative_path:
        return None
    parent = Path(relative_path).parent.as_posix()
    return "" if parent == "." else parent


def _sort_key(item: FolderEntry | MediaEntry, sort: str) -> tuple:
    if sort in {"date_desc", "newest"}:
        return (-item.mtime, item.name.lower())
    if sort in {"date_asc", "oldest"}:
        return (item.mtime, item.name.lower())
    if sort in {"name_desc", "za"}:
        return tuple(-ord(char) for char in item.name.lower())
    return (item.name.lower(),)


T = TypeVar("T")


def paginate(items: list[T], page: int, per_page: int) -> tuple[list[T], bool, bool]:
    page = max(page, 1)
    if per_page <= 0:
        return items, False, False
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], end < len(items), start > 0


def list_folder(
    media_root: Path,
    requested_path: str = "",
    *,
    sort: str = "name_asc",
    page: int = 1,
    per_page: int = 80,
) -> FolderListing:
    folder = safe_resolve(media_root, requested_path)
    if not folder.is_dir():
        raise NotADirectoryError("Requested path is not a folder")

    resolved_root = media_root.resolve(strict=True)
    relative_folder = relative_media_path(media_root, folder) if folder != resolved_root else ""
    folders: list[FolderEntry] = []
    media: list[MediaEntry] = []

    for child in folder.iterdir():
        if child.name.startswith("."):
            continue
        try:
            stat = child.stat()
            child.resolve(strict=True).relative_to(resolved_root)
        except OSError:
            continue
        except ValueError:
            continue

        child_relative = Path(relative_folder, child.name).as_posix() if relative_folder else child.name
        if _is_hidden_relative(Path(child_relative)):
            continue
        if child.is_dir():
            folders.append(
                FolderEntry(
                    name=child.name,
                    path=child_relative,
                    mtime=stat.st_mtime,
                    item_count=_folder_item_count(child),
                    preview_paths=_folder_preview_paths(resolved_root, child),
                )
            )
        elif child.is_file():
            media_type = classify_media(child)
            if media_type == "other":
                continue
            media.append(
                MediaEntry(
                    name=child.name,
                    path=child_relative,
                    media_type=media_type,
                    content_type=content_type_for(child),
                    size=stat.st_size,
                    mtime=stat.st_mtime,
                )
            )

    folders.sort(key=lambda item: _sort_key(item, sort))
    media.sort(key=lambda item: _sort_key(item, sort))
    paged_media, has_next, has_previous = paginate(media, page, per_page)

    return FolderListing(
        path=relative_folder,
        parent=_parent_for(relative_folder),
        folders=folders,
        media=paged_media,
        stats={
            "folders": len(folders),
            "images": sum(1 for item in media if item.media_type == "image"),
            "videos": sum(1 for item in media if item.media_type == "video"),
            "audio": sum(1 for item in media if item.media_type == "audio"),
        },
        page=max(page, 1),
        per_page=per_page,
        total_media=len(media),
        total_folders=len(folders),
        has_next=has_next,
        has_previous=has_previous,
    )
