from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from html import escape
import re

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .auth.dependencies import optional_user, require_user
from .auth.routes import register_auth_routes
from .config import settings
from .scanner import PathSafetyError, classify_media, content_type_for, list_folder, safe_resolve
from .thumbnailer import get_thumbnail, pregenerate_thumbnails

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "media-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    ),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.thumb_cache_dir.mkdir(parents=True, exist_ok=True)
    if settings.pregen_thumbs:
        pregenerate_thumbnails(
            settings.media_root,
            settings.thumb_cache_dir,
            size=settings.thumb_size,
            quality=settings.thumb_quality,
        )
    yield


app = FastAPI(title=settings.app_title, root_path=settings.root_path, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
register_auth_routes(app, settings)

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")


@app.middleware("http")
async def add_security_and_cache_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)

    path = request.url.path
    if path.startswith(f"{settings.root_path}/static/") or path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "public, max-age=86400")
    elif path.startswith(f"{settings.root_path}/thumb/") or path.startswith("/thumb/"):
        response.headers.setdefault("Cache-Control", "private, max-age=86400")
    elif path.startswith(f"{settings.root_path}/media/") or path.startswith("/media/"):
        response.headers.setdefault("Cache-Control", "private, max-age=3600")
    return response


@app.exception_handler(HTTPException)
async def justpix_http_exception_handler(request: Request, exc: HTTPException) -> Response:
    if _wants_html(request):
        detail = escape(str(exc.detail))
        title = f"{exc.status_code} - {detail}"
        body = (
            "<!doctype html><html lang=\"en\"><head>"
            "<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{title}</title><link rel=\"stylesheet\" href=\"{settings.root_path}/static/style.css\">"
            "</head><body><main class=\"error-page\">"
            f"<h1>{exc.status_code}</h1><p>{detail}</p>"
            f"<a href=\"{settings.root_path}/browse/\">Back to gallery</a>"
            "</main></body></html>"
        )
        return HTMLResponse(body, status_code=exc.status_code, headers=exc.headers)
    return await http_exception_handler(request, exc)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url=f"{settings.root_path}/browse/")


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept


def _static_index(request: Request) -> Response:
    if settings.auth_enabled and optional_user(request, settings) is None:
        return RedirectResponse(url=f"{settings.root_path}/login", status_code=303)
    index = Path(__file__).parent / "static" / "index.html"
    html = (
        index.read_text(encoding="utf-8")
        .replace("__ROOT_PATH__", settings.root_path)
        .replace("__APP_TITLE__", settings.app_title)
        .replace("__AUTH_ENABLED__", "true" if settings.auth_enabled else "false")
    )
    return HTMLResponse(html)


def _safe_file(path: str) -> Path:
    try:
        resolved = safe_resolve(settings.media_root, path)
    except PathSafetyError as exc:
        raise HTTPException(status_code=403, detail="Forbidden") from exc
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    return resolved


@app.get("/browse/{path:path}")
def browse(
    request: Request,
    path: str = "",
    sort: str = Query("name_asc"),
    page: int = Query(1, ge=1),
    per_page: int | None = Query(None, ge=0),
) -> Response:
    if _wants_html(request):
        return _static_index(request)

    user = require_user(request, settings)

    try:
        listing = list_folder(
            settings.media_root,
            path,
            sort=sort,
            page=page,
            per_page=settings.items_per_page if per_page is None else per_page,
        )
    except PathSafetyError as exc:
        raise HTTPException(status_code=403, detail="Forbidden") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    except NotADirectoryError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc

    payload = asdict(listing)
    payload["app"] = {
        "title": settings.app_title,
        "root_path": settings.root_path,
        "auth_enabled": settings.auth_enabled,
        "user": asdict(user) if user else None,
    }
    if payload["app"]["user"]:
        payload["app"]["user"].pop("password_hash", None)
    return JSONResponse(payload)


@app.get("/media/{path:path}")
def media(request: Request, path: str) -> Response:
    require_user(request, settings)
    resolved = _safe_file(path)
    if not resolved.is_file() or classify_media(resolved) == "other":
        raise HTTPException(status_code=404, detail="Not found")

    content_type = content_type_for(resolved)
    range_header = request.headers.get("range")
    if range_header and classify_media(resolved) in {"video", "audio"}:
        return _range_response(resolved, range_header, content_type)

    return FileResponse(
        resolved,
        media_type=content_type,
        filename=resolved.name,
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, max-age=3600",
        },
    )


@app.get("/thumb/{path:path}")
def thumb(request: Request, path: str) -> Response:
    require_user(request, settings)
    resolved = _safe_file(path)
    if not resolved.is_file() or classify_media(resolved) == "other":
        raise HTTPException(status_code=404, detail="Not found")
    thumbnail = get_thumbnail(
        resolved,
        settings.thumb_cache_dir,
        size=settings.thumb_size,
        quality=settings.thumb_quality,
    )
    return FileResponse(
        thumbnail,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=86400"},
    )




def _range_response(path: Path, range_header: str, content_type: str) -> Response:
    match = RANGE_RE.match(range_header.strip())
    file_size = path.stat().st_size
    if not match:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    start_raw, end_raw = match.groups()
    if start_raw == "" and end_raw == "":
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    if start_raw == "":
        suffix_length = int(end_raw)
        start = max(file_size - suffix_length, 0)
        end = file_size - 1
    else:
        start = int(start_raw)
        end = int(end_raw) if end_raw else file_size - 1

    if start >= file_size or end < start:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
    end = min(end, file_size - 1)
    chunk_size = end - start + 1

    def iter_file() -> bytes:
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = chunk_size
            while remaining > 0:
                chunk = handle.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        iter_file(),
        status_code=206,
        media_type=content_type,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Cache-Control": "private, max-age=3600",
        },
    )
