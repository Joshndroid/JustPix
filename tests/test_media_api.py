from __future__ import annotations

from importlib import reload
from pathlib import Path

from fastapi.testclient import TestClient

import app.config
import app.main
from app.version import __version__


def make_client(monkeypatch, media_root: Path) -> TestClient:
    monkeypatch.setenv("MEDIA_ROOT", str(media_root))
    monkeypatch.setenv("THUMB_CACHE_DIR", str(media_root.parent / "thumbs"))
    monkeypatch.setenv("ROOT_PATH", "")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    reload(app.config)
    reload(app.main)
    return TestClient(app.main.app)


def test_health_and_browse_json(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()
    (media_root / "image.jpg").write_bytes(b"image")

    client = make_client(monkeypatch, media_root)

    assert client.get("/health").json() == {"status": "ok", "version": __version__}
    assert app.main.app.version == __version__
    response = client.get("/browse/", headers={"accept": "application/json"})
    assert response.status_code == 200
    assert response.json()["media"][0]["name"] == "image.jpg"


def test_media_serves_content_type(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()
    (media_root / "image.jpg").write_bytes(b"image")

    client = make_client(monkeypatch, media_root)
    response = client.get("/media/image.jpg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.content == b"image"


def test_audio_video_range_request(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()
    (media_root / "song.mp3").write_bytes(b"0123456789")
    (media_root / "clip.mp4").write_bytes(b"abcdefghij")

    client = make_client(monkeypatch, media_root)
    response = client.get("/media/song.mp3", headers={"range": "bytes=2-5"})

    assert response.status_code == 206
    assert response.headers["content-range"] == "bytes 2-5/10"
    assert response.content == b"2345"

    response = client.get("/media/clip.mp4", headers={"range": "bytes=1-3"})
    assert response.status_code == 206
    assert response.headers["content-range"] == "bytes 1-3/10"
    assert response.content == b"bcd"


def test_mkv_served_as_media(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()
    (media_root / "movie.mkv").write_bytes(b"mkv")

    client = make_client(monkeypatch, media_root)
    response = client.get("/media/movie.mkv")

    assert response.status_code == 200
    assert response.content == b"mkv"
    assert response.headers["accept-ranges"] == "bytes"


def test_thumb_route_uses_cache(monkeypatch, tmp_path: Path) -> None:
    from PIL import Image

    media_root = tmp_path / "photos"
    media_root.mkdir()
    Image.new("RGB", (640, 480), "#55aa99").save(media_root / "image.jpg")

    client = make_client(monkeypatch, media_root)
    response = client.get("/thumb/image.jpg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert (tmp_path / "thumbs").exists()


def test_traversal_does_not_leak_host_path(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()

    client = make_client(monkeypatch, media_root)
    response = client.get("/media/%2e%2e/secret.jpg")

    assert response.status_code in {403, 404}
    assert str(tmp_path) not in response.text
