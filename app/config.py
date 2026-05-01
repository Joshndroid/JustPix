from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        value = default
    else:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"{name} must be an integer") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return value


@dataclass(frozen=True)
class Settings:
    media_root: Path
    thumb_cache_dir: Path
    app_title: str
    root_path: str
    trusted_proxies: str
    port: int
    items_per_page: int
    thumb_size: int
    thumb_quality: int
    pregen_thumbs: bool
    auth_enabled: bool
    users_file: Path
    session_secret: str
    session_cookie_name: str
    session_ttl_hours: int
    cookie_secure: bool
    login_rate_limit: str


def load_settings() -> Settings:
    root_path = os.getenv("ROOT_PATH", "").strip()
    if root_path and not root_path.startswith("/"):
        root_path = f"/{root_path}"
    if root_path != "/":
        root_path = root_path.rstrip("/")
    else:
        root_path = ""

    auth_enabled = _bool_env("AUTH_ENABLED", False)
    session_secret = os.getenv("SESSION_SECRET", "")
    if auth_enabled and not session_secret:
        raise ValueError("SESSION_SECRET is required when AUTH_ENABLED=true")

    return Settings(
        media_root=Path(os.getenv("MEDIA_ROOT", "/photos")),
        thumb_cache_dir=Path(os.getenv("THUMB_CACHE_DIR", "/thumbcache")),
        app_title=os.getenv("APP_TITLE", "JustPix"),
        root_path=root_path,
        trusted_proxies=os.getenv("TRUSTED_PROXIES", "*"),
        port=_int_env("PORT", 3000, minimum=1, maximum=65535),
        items_per_page=_int_env("ITEMS_PER_PAGE", 80, minimum=0),
        thumb_size=_int_env("THUMB_SIZE", 320, minimum=1),
        thumb_quality=_int_env("THUMB_QUALITY", 75, minimum=1, maximum=95),
        pregen_thumbs=_bool_env("PREGEN_THUMBS", False),
        auth_enabled=auth_enabled,
        users_file=Path(os.getenv("USERS_FILE", "/config/users.json")),
        session_secret=session_secret,
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "justpix_session"),
        session_ttl_hours=_int_env("SESSION_TTL_HOURS", 168, minimum=1),
        cookie_secure=_bool_env("COOKIE_SECURE", False),
        login_rate_limit=os.getenv("LOGIN_RATE_LIMIT", "10/minute"),
    )


settings = load_settings()
