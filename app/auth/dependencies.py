from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.config import Settings
from .sessions import verify_session_cookie
from .users import User, get_active_user


def optional_user(request: Request, settings: Settings) -> User | None:
    if not settings.auth_enabled:
        return None
    username = verify_session_cookie(
        request.cookies.get(settings.session_cookie_name),
        settings.session_secret,
    )
    if username is None:
        return None
    return get_active_user(settings.users_file, username)


def require_user(request: Request, settings: Settings) -> User | None:
    if not settings.auth_enabled:
        return None
    user = optional_user(request, settings)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    return user


def require_admin(request: Request, settings: Settings) -> User:
    user = require_user(request, settings)
    if user is None or user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user
