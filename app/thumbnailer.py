from __future__ import annotations

from pathlib import Path
import hashlib
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:
    pass

from .scanner import classify_media


def cache_key(path: Path) -> str:
    stat = path.stat()
    payload = f"{path.resolve(strict=True)}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def thumbnail_path(cache_dir: Path, source_path: Path) -> Path:
    return cache_dir / f"{cache_key(source_path)}.jpg"


def fallback_thumbnail(cache_dir: Path, label: str = "MEDIA", *, size: int = 320) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"fallback-{label.lower()}.jpg"
    if target.exists():
        return target
    image = Image.new("RGB", (size, size), "#262626")
    draw = ImageDraw.Draw(image)
    text = label.upper()[:12]
    box = draw.textbbox((0, 0), text)
    draw.text(((size - (box[2] - box[0])) / 2, (size - (box[3] - box[1])) / 2), text, fill="#eeeeee")
    image.save(target, "JPEG", quality=75)
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
        return fallback_thumbnail(cache_dir, "AUDIO", size=size)
    if media_type not in {"image", "video"}:
        return fallback_thumbnail(cache_dir, "FILE", size=size)

    target = thumbnail_path(cache_dir, source_path)
    if target.exists():
        return target

    try:
        if media_type == "image":
            return _image_thumbnail(source_path, target, size=size, quality=quality)
        return _video_thumbnail(source_path, target, size=size, quality=quality)
    except Exception:
        return fallback_thumbnail(cache_dir, media_type, size=size)


def pregenerate_thumbnails(media_root: Path, cache_dir: Path, *, size: int, quality: int) -> None:
    for path in media_root.rglob("*"):
        if path.name.startswith(".") or not path.is_file():
            continue
        get_thumbnail(path, cache_dir, size=size, quality=quality)
