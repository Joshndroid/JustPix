# JustPix

JustPix is a small read-only photo, video, and audio gallery for a local media folder. It is designed for Unraid and other Docker hosts where your media is mounted into the container as read-only storage.

The app never uploads, edits, tags, deletes, or writes metadata to your media library. The filesystem is the source of truth.

## Features

- Folder and subfolder browsing
- Read-only media serving from `/photos`
- Images, videos, and audio files in one gallery
- Responsive browser UI with breadcrumbs, sorting, pagination, lazy thumbnails, and a lightbox
- Native browser playback for video and audio
- Cached image thumbnails and video poster frames in `/thumbcache`
- Optional local login gate backed by `/config/users.json`
- Reverse proxy support with `ROOT_PATH`
- Basic security and cache headers

## Quick Start

```bash
docker compose up --build
```

Then open:

```text
http://localhost:3000
```

The sample `docker-compose.yml` expects you to edit the host paths before deploying:

```yaml
volumes:
  - /mnt/user/Photos:/photos:ro
  - /mnt/user/appdata/justpix/thumbcache:/thumbcache
  - /mnt/user/appdata/justpix/config:/config
```

Keep the `/photos` mount read-only with `:ro`.

## GitHub Container Registry

The GitHub Actions workflow builds the Docker image on pull requests and publishes it to GitHub Container Registry on pushes to `main` and version tags like `v1.0.0`.

Published image tags include:

```text
ghcr.io/<owner>/<repo>:latest
ghcr.io/<owner>/<repo>:main
ghcr.io/<owner>/<repo>:v1.0.0
ghcr.io/<owner>/<repo>:sha-<commit>
```

For this repository, replace your compose `build: .` line with an image once the package exists:

```yaml
image: ghcr.io/<owner>/<repo>:latest
```

## Unraid Setup

1. Put this project somewhere Unraid can build it, or build/publish the image from another machine.
2. Create appdata folders:

```text
/mnt/user/appdata/justpix/config
/mnt/user/appdata/justpix/thumbcache
```

3. Map your photo share read-only:

```text
/mnt/user/Photos -> /photos:ro
```

4. Use Unraid defaults unless your share requires another user:

```text
PUID=99
PGID=100
```

5. Start the container and open port `3000`.

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `PUID` | `1000` | Runtime user ID |
| `PGID` | `1000` | Runtime group ID |
| `MEDIA_ROOT` | `/photos` | Read-only mounted media folder |
| `THUMB_CACHE_DIR` | `/thumbcache` | Writable thumbnail cache |
| `APP_TITLE` | `JustPix` | Browser title and header |
| `ROOT_PATH` | empty | Reverse proxy sub-path such as `/justpix` |
| `TRUSTED_PROXIES` | `*` | Uvicorn forwarded-header trusted IPs |
| `PORT` | `3000` | Internal listen port |
| `ITEMS_PER_PAGE` | `80` | Media items per page, `0` disables pagination |
| `THUMB_SIZE` | `320` | Maximum thumbnail dimension |
| `THUMB_QUALITY` | `75` | JPEG thumbnail quality |
| `PREGEN_THUMBS` | `false` | Generate thumbnails at startup |
| `AUTH_ENABLED` | `false` | Enable login/session protection |
| `USERS_FILE` | `/config/users.json` | User account file |
| `SESSION_SECRET` | empty | Required when auth is enabled |
| `SESSION_COOKIE_NAME` | `justpix_session` | Session cookie name |
| `SESSION_TTL_HOURS` | `168` | Session lifetime |
| `COOKIE_SECURE` | `false` | Set `true` when serving only over HTTPS |
| `LOGIN_RATE_LIMIT` | `10/minute` | Per-IP login throttle |

## Optional Auth

Auth is disabled by default. To enable it:

1. Generate a user entry:

```bash
docker compose run --rm justpix python -m app.tools.create_user admin --json
```

2. Put the output in:

```text
/mnt/user/appdata/justpix/config/users.json
```

3. Set:

```text
AUTH_ENABLED=true
SESSION_SECRET=replace-this-with-a-long-random-value
USERS_FILE=/config/users.json
```

Passwords are hashed with PBKDF2-SHA256 and per-user salts. Sessions are signed, expiring, `HttpOnly`, and `SameSite=Lax`. Set `COOKIE_SECURE=true` when JustPix is only accessed over HTTPS.

This auth system is a simple LAN gate. For internet exposure, use a VPN, SSO, or reverse-proxy authentication in front of JustPix.

## Reverse Proxy

For a normal host/subdomain proxy, point your proxy at:

```text
http://unraid-ip:3000
```

For a sub-path such as `/justpix`, set:

```text
ROOT_PATH=/justpix
```

Nginx Proxy Manager custom location example:

```nginx
location /justpix/ {
    proxy_pass http://unraid-ip:3000/;
    proxy_set_header X-Forwarded-Prefix /justpix;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
}
```

Caddy example:

```caddy
handle_path /justpix/* {
    reverse_proxy unraid-ip:3000
}
```

For exposed reverse proxies, avoid `TRUSTED_PROXIES=*` and set it to the proxy IP or CIDR.

## Compatibility

JustPix does not transcode. Browser playback depends on the browser and codec.

| Format | Expected behavior |
|---|---|
| JPEG/JPG | Gallery thumbnail and lightbox image |
| PNG | Gallery thumbnail and lightbox image |
| GIF | Served directly; animation support depends on browser display |
| WebP | Gallery thumbnail and lightbox image in modern browsers |
| HEIC/HEIF | Thumbnail support via `pillow-heif` and `libheif`; test with real iPhone files |
| AVIF | Best effort via Pillow/browser support |
| SVG | Served with CSP headers; avoid untrusted SVG libraries |
| MP4 | Native playback and seeking when browser supports the codec |
| MOV | Served as video; playback depends on browser codec support |
| MKV | Listed and served; many browsers may not play it natively |
| MP3 | Native audio playback and seeking |
| M4A/OGG/WAV/FLAC | Served as audio; playback depends on browser codec support |

## Known Limits

- No uploads, edits, deletes, tags, albums, or media database
- No video transcoding
- Very large folders should keep pagination enabled
- HEIC, AVIF, and video poster behavior should be verified with your real media collection
- Docker runtime checks require a host with Docker installed

## Development Checks

```bash
python -m pytest -q
```

The test suite covers safe path resolution, media listing, range requests, auth/session behavior, thumbnail cache behavior, cache/security headers, and root path HTML generation.
