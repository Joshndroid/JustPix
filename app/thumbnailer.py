from __future__ import annotations

from pathlib import Path
import hashlib
import re
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:
    pass

from .scanner import classify_media


LEGACY_CACHE_RE = re.compile(r"^[0-9a-f]{40}\.jpg$")


def _source_key(path: Path) -> str:
    return hashlib.sha1(str(path.resolve(strict=True)).encode("utf-8")).hexdigest()


def cache_key(path: Path, *, size: int = 320, quality: int = 75) -> str:
    stat = path.stat()
    payload = f"{stat.st_mtime_ns}:{stat.st_size}:{size}:{quality}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def thumbnail_path(cache_dir: Path, source_path: Path, *, size: int = 320, quality: int = 75) -> Path:
    return cache_dir / f"v2-{_source_key(source_path)}-{cache_key(source_path, size=size, quality=quality)}.jpg"


def _remove_other_variants(cache_dir: Path, pattern: str, keep: Path) -> None:
    for candidate in cache_dir.glob(pattern):
        if candidate == keep or not candidate.is_file():
            continue
        try:
            candidate.unlink()
        except OSError:
            continue


def prune_legacy_thumbnail_cache(cache_dir: Path) -> None:
    """Remove cache files created before thumbnail settings were part of the key."""
    if not cache_dir.exists():
        return
    legacy_fallbacks = {"fallback-audio.jpg", "fallback-file.jpg", "fallback-image.jpg", "fallback-video.jpg"}
    for candidate in cache_dir.iterdir():
        if not candidate.is_file():
            continue
        if LEGACY_CACHE_RE.fullmatch(candidate.name) or candidate.name in legacy_fallbacks:
            try:
                candidate.unlink()
            except OSError:
                continue


def fallback_thumbnail(
    cache_dir: Path,
    label: str = "MEDIA",
    *,
    size: int = 320,
    quality: int = 75,
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"fallback-{label.lower()}-{size}-{quality}.jpg"
    if target.exists():
        _remove_other_variants(cache_dir, f"fallback-{label.lower()}-*.jpg", target)
        return target
    image = Image.new("RGB", (size, size), "#262626")
    draw = ImageDraw.Draw(image)
    text = label.upper()[:12]
    box = draw.textbbox((0, 0), text)
    draw.text(((size - (box[2] - box[0])) / 2, (size - (box[3] - box[1])) / 2), text, fill="#eeeeee")
    image.save(target, "JPEG", quality=quality)
    _remove_other_variants(cache_dir, f"fallback-{label.lower()}-*.jpg", target)
    return target


def _save_resized(image: Image.Image, target: Path, *, size: int, quality: int) -> Path:
    image = ImageOps.exif_transpose(image)
    image.thumbnail((size, size))
    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "JPEG", quality=quality, optimize=True)
    return target


def _image_thumbnail(source_path: Path, target: Path, *, size: int, quality: int) -> Path:
    with Image.open(source_path) as image:
        return _save_resized(image, target, size=size, quality=quality)


def _video_thumbnail(source_path: Path, target: Path, *, size: int, quality: int) -> Path:
    with tempfile.TemporaryDirectory() as tmpdir:
        frame = Path(tmpdir) / "frame.jpg"
        duration = _video_duration(source_path)
        seek = max(duration * 0.10, 1.0) if duration else 1.0
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{seek:.3f}",
                "-i",
                str(source_path),
                "-frames:v",
                "1",
                "-y",
                str(frame),
            ],
            check=True,
            timeout=30,
        )
        return _image_thumbnail(frame, target, size=size, quality=quality)


def _video_duration(source_path: Path) -> float | None:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(source_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return float(result.stdout.strip())
    except (subprocess.SubprocessError, ValueError):
        return None


def get_thumbnail(source_path: Path, cache_dir: Path, *, size: int = 320, quality: int = 75) -> Path:
    media_type = classify_media(source_path)
    if media_type == "audio":
        return fallback_thumbnail(cache_dir, "AUDIO", size=size, quality=quality)
    if media_type not in {"image", "video"}:
        return fallback_thumbnail(cache_dir, "FILE", size=size, quality=quality)

    target = thumbnail_path(cache_dir, source_path, size=size, quality=quality)
    if target.exists():
        _remove_other_variants(cache_dir, f"v2-{_source_key(source_path)}-*.jpg", target)
        return target

    try:
        if media_type == "image":
            thumbnail = _image_thumbnail(source_path, target, size=size, quality=quality)
        else:
            thumbnail = _video_thumbnail(source_path, target, size=size, quality=quality)
        _remove_other_variants(cache_dir, f"v2-{_source_key(source_path)}-*.jpg", target)
        return thumbnail
    except Exception:
        return fallback_thumbnail(cache_dir, media_type, size=size, quality=quality)


def pregenerate_thumbnails(media_root: Path, cache_dir: Path, *, size: int, quality: int) -> None:
    for path in media_root.rglob("*"):
        if path.name.startswith(".") or not path.is_file():
            continue
        get_thumbnail(path, cache_dir, size=size, quality=quality)
