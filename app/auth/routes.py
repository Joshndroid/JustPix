from __future__ import annotations

from collections import defaultdict, deque
import time

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.config import Settings
from app.static_templates import render_static_html
from .dependencies import optional_user, require_admin
from .sessions import create_session_cookie
from .users import UsersError, authenticate_user, create_initial_admin, create_user, has_users, load_users

_attempts: dict[str, deque[float]] = defaultdict(deque)


def _cookie_path(settings: Settings) -> str:
    return settings.root_path or "/"


def _login_path(settings: Settings) -> str:
    return f"{settings.root_path}/login"


def _browse_path(settings: Settings) -> str:
    return f"{settings.root_path}/browse/"


def _setup_path(settings: Settings) -> str:
    return f"{settings.root_path}/setup"


def _set_session_cookie(response: Response, settings: Settings, username: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        create_session_cookie(username, settings.session_secret, settings.session_ttl_hours),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
        path=_cookie_path(settings),
    )


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
        if not has_users(settings.users_file):
            return RedirectResponse(url=_setup_path(settings), status_code=303)
        if optional_user(request, settings):
            return RedirectResponse(url=_browse_path(settings), status_code=303)
        return HTMLResponse(render_static_html("login.html", settings))

    @app.post("/login", include_in_schema=False)
    async def login(request: Request, username: str = Form(...), password: str = Form(...)) -> Response:
        if not settings.auth_enabled:
            return RedirectResponse(url=_browse_path(settings), status_code=303)
        if not has_users(settings.users_file):
            return RedirectResponse(url=_setup_path(settings), status_code=303)
        if _rate_limited(request, settings):
            return JSONResponse({"detail": "Too many login attempts"}, status_code=429)

        user = authenticate_user(settings.users_file, username, password)
        if user is None:
            return JSONResponse({"detail": "Invalid username or password"}, status_code=401)

        response = RedirectResponse(url=_browse_path(settings), status_code=303)
        _set_session_cookie(response, settings, user.username)
        return response

    @app.post("/logout", include_in_schema=False)
    def logout() -> Response:
        response = RedirectResponse(url=_login_path(settings), status_code=303)
        response.delete_cookie(settings.session_cookie_name, path=_cookie_path(settings))
        return response

    @app.get("/setup", include_in_schema=False)
    def setup_page() -> Response:
        if not settings.auth_enabled:
            return RedirectResponse(url=_browse_path(settings), status_code=303)
        if has_users(settings.users_file):
            return RedirectResponse(url=_login_path(settings), status_code=303)
        return HTMLResponse(render_static_html("setup.html", settings))

    @app.post("/setup", include_in_schema=False)
    async def setup(
        username: str = Form(...),
        password: str = Form(...),
        display_name: str = Form(""),
    ) -> Response:
        if not settings.auth_enabled:
            return RedirectResponse(url=_browse_path(settings), status_code=303)
        try:
            user = create_initial_admin(
                settings.users_file,
                username=username,
                password=password,
                display_name=display_name or None,
            )
        except UsersError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)

        response = RedirectResponse(url=_browse_path(settings), status_code=303)
        _set_session_cookie(response, settings, user.username)
        return response

    @app.get("/admin", include_in_schema=False)
    def admin_page(request: Request) -> Response:
        require_admin(request, settings)
        return HTMLResponse(render_static_html("admin.html", settings))

    @app.get("/admin/users", include_in_schema=False)
    def admin_users(request: Request) -> Response:
        require_admin(request, settings)
        users = [
            {
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role,
                "disabled": user.disabled,
            }
            for user in load_users(settings.users_file).values()
        ]
        return JSONResponse({"users": users})

    @app.post("/admin/users", include_in_schema=False)
    async def admin_create_user(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        display_name: str = Form(""),
        role: str = Form("user"),
    ) -> Response:
        require_admin(request, settings)
        try:
            user = create_user(
                settings.users_file,
                username=username,
                password=password,
                display_name=display_name or None,
                role=role,
            )
        except UsersError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        return JSONResponse(
            {
                "user": {
                    "username": user.username,
                    "display_name": user.display_name,
                    "role": user.role,
                    "disabled": user.disabled,
                }
            },
            status_code=201,
        )
