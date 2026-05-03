from __future__ import annotations

from importlib import reload
from pathlib import Path

from fastapi.testclient import TestClient

import app.config
import app.main


def make_client(monkeypatch, media_root: Path, *, root_path: str = "") -> TestClient:
    monkeypatch.setenv("MEDIA_ROOT", str(media_root))
    monkeypatch.setenv("THUMB_CACHE_DIR", str(media_root.parent / "thumbs"))
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("ROOT_PATH", root_path)
    reload(app.config)
    reload(app.main)
    return TestClient(app.main.app)


def test_security_headers_and_static_cache(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()
    client = make_client(monkeypatch, media_root)

    response = client.get("/static/gallery.js")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["x-frame-options"] == "DENY"
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert "'unsafe-inline'" not in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "public, max-age=86400"


def test_html_shell_uses_root_path_without_inline_script(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()
    client = make_client(monkeypatch, media_root, root_path="/justpix")

    response = client.get("/browse/", headers={"accept": "text/html"})

    assert response.status_code == 200
    assert 'href="/justpix/static/style.css?v=' in response.text
    assert 'src="/justpix/static/gallery.js?v=' in response.text
    assert "__STATIC_VERSION__" not in response.text
    assert 'data-root-path="/justpix"' in response.text
    assert "<script>" not in response.text


def test_media_and_thumb_cache_headers(monkeypatch, tmp_path: Path) -> None:
    from PIL import Image

    media_root = tmp_path / "photos"
    media_root.mkdir()
    Image.new("RGB", (200, 200), "#66aa99").save(media_root / "image.jpg")
    client = make_client(monkeypatch, media_root)

    media_response = client.get("/media/image.jpg")
    thumb_response = client.get("/thumb/image.jpg")

    assert media_response.headers["cache-control"] == "private, max-age=3600"
    assert thumb_response.headers["cache-control"] == "private, max-age=86400"


def test_html_error_page_does_not_leak_paths(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()
    client = make_client(monkeypatch, media_root)

    response = client.get("/media/missing.jpg", headers={"accept": "text/html"})

    assert response.status_code == 404
    assert "Back to gallery" in response.text
    assert str(tmp_path) not in response.text
