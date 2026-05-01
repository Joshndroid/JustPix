from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _sign(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def create_session_cookie(username: str, secret: str, ttl_hours: int) -> str:
    payload: dict[str, Any] = {
        "sub": username,
        "exp": int(time.time()) + ttl_hours * 3600,
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign(body, secret)
    return f"{body}.{signature}"


def verify_session_cookie(cookie_value: str | None, secret: str) -> str | None:
    if not cookie_value or "." not in cookie_value or not secret:
        return None
    body, signature = cookie_value.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(body, secret)):
        return None
    try:
        payload = json.loads(_b64decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    username = payload.get("sub")
    return username if isinstance(username, str) and username else None
