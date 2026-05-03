from __future__ import annotations

from pathlib import Path

from .config import Settings

STATIC_DIR = Path(__file__).parent / "static"


def static_version() -> str:
    version = 0
    for path in STATIC_DIR.iterdir():
        if not path.is_file() or path.suffix == ".html":
            continue
        try:
            version = max(version, path.stat().st_mtime_ns)
        except OSError:
            continue
    return str(version)


def render_static_html(template_name: str, settings: Settings, **replacements: str) -> str:
    html = (STATIC_DIR / template_name).read_text(encoding="utf-8")
    values = {
        "__ROOT_PATH__": settings.root_path,
        "__APP_TITLE__": settings.app_title,
        "__STATIC_VERSION__": static_version(),
        **replacements,
    }
    for token, value in values.items():
        html = html.replace(token, value)
    return html
