from __future__ import annotations

from importlib import reload
from pathlib import Path
import json

from fastapi.testclient import TestClient

import app.config
import app.main
from app.auth.passwords import hash_password, verify_password


def make_client(monkeypatch, media_root: Path, users_file: Path) -> TestClient:
    monkeypatch.setenv("MEDIA_ROOT", str(media_root))
    monkeypatch.setenv("THUMB_CACHE_DIR", str(media_root.parent / "thumbs"))
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_SECRET", "test-secret-with-enough-length")
    monkeypatch.setenv("USERS_FILE", str(users_file))
    reload(app.config)
    reload(app.main)
    return TestClient(app.main.app)


def test_password_hash_round_trip() -> None:
    password_hash = hash_password("correct horse")

    assert "correct horse" not in password_hash
    assert verify_password("correct horse", password_hash)
    assert not verify_password("wrong", password_hash)


def test_auth_blocks_and_then_allows_gallery_routes(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()
    (media_root / "image.jpg").write_bytes(b"image")
    users_file = tmp_path / "users.json"
    users_file.write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "admin",
                        "password_hash": hash_password("secret"),
                        "display_name": "Admin",
                        "role": "admin",
                        "disabled": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    client = make_client(monkeypatch, media_root, users_file)

    assert client.get("/browse/", headers={"accept": "application/json"}).status_code == 401
    assert client.get("/media/image.jpg").status_code == 401
    assert client.get("/thumb/image.jpg").status_code == 401
    login = client.post("/login", data={"username": "admin", "password": "secret"}, follow_redirects=False)

    assert login.status_code == 303
    assert "httponly" in login.headers["set-cookie"].lower()
    assert "samesite=lax" in login.headers["set-cookie"].lower()
    assert client.get("/browse/", headers={"accept": "application/json"}).status_code == 200
    assert client.get("/media/image.jpg").status_code == 200


def test_auth_login_rejects_bad_password(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()
    users_file = tmp_path / "users.json"
    users_file.write_text(
        json.dumps({"users": [{"username": "admin", "password_hash": hash_password("secret")}]}),
        encoding="utf-8",
    )

    client = make_client(monkeypatch, media_root, users_file)
    response = client.post("/login", data={"username": "admin", "password": "bad"})

    assert response.status_code == 401
    assert "set-cookie" not in response.headers


def test_login_cookie_path_honors_root_path(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()
    users_file = tmp_path / "users.json"
    users_file.write_text(
        json.dumps({"users": [{"username": "admin", "password_hash": hash_password("secret")}]}),
        encoding="utf-8",
    )

    monkeypatch.setenv("MEDIA_ROOT", str(media_root))
    monkeypatch.setenv("THUMB_CACHE_DIR", str(tmp_path / "thumbs"))
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_SECRET", "test-secret-with-enough-length")
    monkeypatch.setenv("USERS_FILE", str(users_file))
    monkeypatch.setenv("ROOT_PATH", "/justpix")
    reload(app.config)
    reload(app.main)
    client = TestClient(app.main.app)

    response = client.post("/login", data={"username": "admin", "password": "secret"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/justpix/browse/"
    assert "path=/justpix" in response.headers["set-cookie"].lower()


def test_first_run_setup_creates_admin_and_logs_in(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()
    users_file = tmp_path / "config" / "users.json"
    client = make_client(monkeypatch, media_root, users_file)

    login_page = client.get("/login", follow_redirects=False)
    assert login_page.status_code == 303
    assert login_page.headers["location"] == "/setup"

    response = client.post(
        "/setup",
        data={"username": "owner", "display_name": "Owner", "password": "long-secret"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "set-cookie" in response.headers
    payload = json.loads(users_file.read_text(encoding="utf-8"))
    assert payload["users"][0]["username"] == "owner"
    assert payload["users"][0]["role"] == "admin"
    assert client.get("/browse/", headers={"accept": "application/json"}).status_code == 200


def test_admin_can_create_users_manually(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()
    users_file = tmp_path / "users.json"
    users_file.write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "admin",
                        "password_hash": hash_password("admin-secret"),
                        "display_name": "Admin",
                        "role": "admin",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    client = make_client(monkeypatch, media_root, users_file)
    client.post("/login", data={"username": "admin", "password": "admin-secret"})
    response = client.post(
        "/admin/users",
        data={"username": "viewer", "display_name": "Viewer", "password": "viewer-secret", "role": "user"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["user"]["role"] == "user"
    users_payload = json.loads(users_file.read_text(encoding="utf-8"))
    assert [user["username"] for user in users_payload["users"]] == ["admin", "viewer"]


def test_non_admin_cannot_create_users(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "photos"
    media_root.mkdir()
    users_file = tmp_path / "users.json"
    users_file.write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "admin",
                        "password_hash": hash_password("admin-secret"),
                        "role": "admin",
                    },
                    {
                        "username": "viewer",
                        "password_hash": hash_password("viewer-secret"),
                        "role": "user",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    client = make_client(monkeypatch, media_root, users_file)
    client.post("/login", data={"username": "viewer", "password": "viewer-secret"})
    response = client.post(
        "/admin/users",
        data={"username": "other", "password": "other-secret", "role": "user"},
    )

    assert response.status_code == 403
