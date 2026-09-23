#!/usr/bin/env sh
set -eu

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
PORT="${PORT:-3000}"
ROOT_PATH="${ROOT_PATH:-}"
TRUSTED_PROXIES="${TRUSTED_PROXIES:-*}"
THUMB_CACHE_DIR="${THUMB_CACHE_DIR:-/data/thumbcache}"
CONFIG_DIR="${CONFIG_DIR:-/data/config}"
AUTH_ENABLED="${AUTH_ENABLED:-true}"
SESSION_SECRET="${SESSION_SECRET:-}"
SESSION_SECRET_FILE="${SESSION_SECRET_FILE:-$CONFIG_DIR/session_secret}"

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

case "$(printf '%s' "$AUTH_ENABLED" | tr '[:upper:]' '[:lower:]')" in
  0|false|no|off)
    ;;
  *)
    case "$SESSION_SECRET" in
      change-this-to-a-long-random-string|replace-this-with-a-long-random-value)
        echo "Refusing to start with an insecure placeholder SESSION_SECRET" >&2
        exit 1
        ;;
    esac

    if [ -z "$SESSION_SECRET" ]; then
      if [ -s "$SESSION_SECRET_FILE" ]; then
        IFS= read -r SESSION_SECRET < "$SESSION_SECRET_FILE"
      else
        umask 077
        SESSION_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
        printf '%s\n' "$SESSION_SECRET" > "$SESSION_SECRET_FILE"
      fi
      export SESSION_SECRET
    fi
    ;;
esac

chown -R "$PUID:$PGID" "$THUMB_CACHE_DIR" "$CONFIG_DIR"

exec gosu justpix uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --root-path "$ROOT_PATH" \
  --proxy-headers \
  --forwarded-allow-ips "$TRUSTED_PROXIES"
