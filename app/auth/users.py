from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from .passwords import verify_password


@dataclass(frozen=True)
class User:
    username: str
    password_hash: str
    display_name: str
    disabled: bool = False


class UsersError(ValueError):
    pass


def load_users(users_file: Path) -> dict[str, User]:
    if not users_file.exists():
        return {}
    with users_file.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    users: dict[str, User] = {}
    for item in payload.get("users", []):
        username = str(item.get("username", "")).strip()
        password_hash = str(item.get("password_hash", ""))
        if not username or not password_hash:
            raise UsersError("Each user needs username and password_hash")
        users[username] = User(
            username=username,
            password_hash=password_hash,
            display_name=str(item.get("display_name") or username),
            disabled=bool(item.get("disabled", False)),
        )
    return users


def authenticate_user(users_file: Path, username: str, password: str) -> User | None:
    user = load_users(users_file).get(username)
    if user is None or user.disabled:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_active_user(users_file: Path, username: str) -> User | None:
    user = load_users(users_file).get(username)
    if user is None or user.disabled:
        return None
    return user
