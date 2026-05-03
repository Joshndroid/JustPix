from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import re

from .passwords import hash_password, verify_password

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")
VALID_ROLES = {"admin", "user"}


@dataclass(frozen=True)
class User:
    username: str
    password_hash: str
    display_name: str
    role: str = "user"
    disabled: bool = False


class UsersError(ValueError):
    pass


def _validate_username(username: str) -> str:
    username = username.strip()
    if not USERNAME_RE.match(username):
        raise UsersError("Username must be 3-64 characters and use letters, numbers, dot, dash, or underscore")
    return username


def _validate_role(role: str) -> str:
    role = role.strip().lower() or "user"
    if role not in VALID_ROLES:
        raise UsersError("Invalid role")
    return role


def load_users(users_file: Path) -> dict[str, User]:
    if not users_file.exists():
        return {}
    with users_file.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    users: dict[str, User] = {}
    for index, item in enumerate(payload.get("users", [])):
        username = _validate_username(str(item.get("username", "")))
        password_hash = str(item.get("password_hash", ""))
        if not username or not password_hash:
            raise UsersError("Each user needs username and password_hash")
        role = _validate_role(str(item.get("role") or ("admin" if index == 0 else "user")))
        users[username] = User(
            username=username,
            password_hash=password_hash,
            display_name=str(item.get("display_name") or username),
            role=role,
            disabled=bool(item.get("disabled", False)),
        )
    return users


def save_users(users_file: Path, users: dict[str, User]) -> None:
    users_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "users": [
            {
                "username": user.username,
                "password_hash": user.password_hash,
                "display_name": user.display_name,
                "role": user.role,
                "disabled": user.disabled,
            }
            for user in users.values()
        ]
    }
    tmp_path = users_file.with_suffix(f"{users_file.suffix}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    os.replace(tmp_path, users_file)


def has_users(users_file: Path) -> bool:
    return bool(load_users(users_file))


def create_user(
    users_file: Path,
    *,
    username: str,
    password: str,
    display_name: str | None = None,
    role: str = "user",
    disabled: bool = False,
) -> User:
    username = _validate_username(username)
    role = _validate_role(role)
    if len(password) < 8:
        raise UsersError("Password must be at least 8 characters")
    users = load_users(users_file)
    if username in users:
        raise UsersError("Username already exists")
    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=(display_name or username).strip() or username,
        role=role,
        disabled=disabled,
    )
    users[username] = user
    save_users(users_file, users)
    return user


def create_initial_admin(
    users_file: Path,
    *,
    username: str,
    password: str,
    display_name: str | None = None,
) -> User:
    if has_users(users_file):
        raise UsersError("Initial setup is already complete")
    return create_user(
        users_file,
        username=username,
        password=password,
        display_name=display_name,
        role="admin",
    )


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
