from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
import time

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.config import Settings
from .dependencies import optional_user
from .sessions import create_session_cookie
from .users import authenticate_user

_attempts: dict[str, deque[float]] = defaultdict(deque)


def _cookie_path(settings: Settings) -> str:
    return settings.root_path or "/"


def _login_path(settings: Settings) -> str:
    return f"{settings.root_path}/login"


def _browse_path(settings: Settings) -> str:
    return f"{settings.root_path}/browse/"


def _parse_rate_limit(value: str) -> tuple[int, int]:
    try:
        count_raw, window_raw = value.split("/", 1)
        count = int(count_raw)
    except ValueError:
        return 10, 60
    seconds = {"second": 1, "minute": 60, "hour": 3600}.get(window_raw.rstrip("s"), 60)
    return max(count, 1), seconds


def _rate_limited(request: Request, settings: Settings) -> bool:
    limit, seconds = _parse_rate_limit(settings.login_rate_limit)
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _attempts[ip]
    while bucket and bucket[0] < now - seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        return True
    bucket.append(now)
    return False


def register_auth_routes(app, settings: Settings) -> None:
    @app.get("/login", include_in_schema=False)
    def login_page(request: Request) -> Response:
        if not settings.auth_enabled:
            return RedirectResponse(url=_browse_path(settings), status_code=303)
        if optional_user(request, settings):
            return RedirectResponse(url=_browse_path(settings), status_code=303)
        html = (Path(__file__).resolve().parent.parent / "static" / "login.html").read_text(encoding="utf-8")
        return HTMLResponse(
            html.replace("__ROOT_PATH__", settings.root_path).replace("__APP_TITLE__", settings.app_title)
        )

    @app.post("/login", include_in_schema=False)
    async def login(request: Request, username: str = Form(...), password: str = Form(...)) -> Response:
        if not settings.auth_enabled:
            return RedirectResponse(url=_browse_path(settings), status_code=303)
        if _rate_limited(request, settings):
            return JSONResponse({"detail": "Too many login attempts"}, status_code=429)

        user = authenticate_user(settings.users_file, username, password)
        if user is None:
            return JSONResponse({"detail": "Invalid username or password"}, status_code=401)

        response = RedirectResponse(url=_browse_path(settings), status_code=303)
        response.set_cookie(
            settings.session_cookie_name,
            create_session_cookie(user.username, settings.session_secret, settings.session_ttl_hours),
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=settings.session_ttl_hours * 3600,
            path=_cookie_path(settings),
        )
        return response

    @app.post("/logout", include_in_schema=False)
    def logout() -> Response:
        response = RedirectResponse(url=_login_path(settings), status_code=303)
        response.delete_cookie(settings.session_cookie_name, path=_cookie_path(settings))
        return response
