#!/usr/bin/env sh
set -eu

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
PORT="${PORT:-3000}"
ROOT_PATH="${ROOT_PATH:-}"
TRUSTED_PROXIES="${TRUSTED_PROXIES:-*}"
THUMB_CACHE_DIR="${THUMB_CACHE_DIR:-/data/thumbcache}"
CONFIG_DIR="${CONFIG_DIR:-/data/config}"

GROUP_NAME="$(getent group "$PGID" 2>/dev/null | cut -d: -f1 || true)"
if [ -z "$GROUP_NAME" ]; then
  GROUP_NAME="justpix"
  groupadd -g "$PGID" "$GROUP_NAME"
fi

if ! id justpix >/dev/null 2>&1; then
  useradd -u "$PUID" -g "$PGID" -M -s /usr/sbin/nologin justpix
else
  usermod -o -u "$PUID" -g "$PGID" justpix
fi

mkdir -p "$THUMB_CACHE_DIR" "$CONFIG_DIR"
chown -R "$PUID:$PGID" "$THUMB_CACHE_DIR" "$CONFIG_DIR"

exec gosu justpix uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --root-path "$ROOT_PATH" \
  --proxy-headers \
  --forwarded-allow-ips "$TRUSTED_PROXIES"
