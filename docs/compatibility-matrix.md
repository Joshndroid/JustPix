# JustPix Compatibility Matrix

This matrix records expected behavior for the first deployable version. Browser playback is intentionally native: JustPix serves files as-is and does not transcode.

| Type | Extension | Thumbnail | Browser view/playback | Notes |
|---|---|---|---|---|
| Image | `.jpg`, `.jpeg` | Yes | Yes | Baseline supported format |
| Image | `.png` | Yes | Yes | Transparency rendered by browser |
| Image | `.gif` | First frame thumbnail | Yes | Browser handles animation |
| Image | `.webp` | Yes | Yes | Modern browser support |
| Image | `.heic`, `.heif` | Yes, when libheif works | Best effort | Verify with real iPhone files |
| Image | `.avif` | Best effort | Best effort | Depends on Pillow/browser support |
| Image | `.svg` | Best effort/fallback | Yes | Served with CSP; avoid untrusted SVGs |
| Video | `.mp4` | ffmpeg poster | Usually yes | Codec still matters |
| Video | `.mov` | ffmpeg poster | Best effort | Common Apple codecs vary |
| Video | `.mkv` | ffmpeg poster | Often no | Still listed and served |
| Video | `.webm` | ffmpeg poster | Usually yes | Good modern browser support |
| Audio | `.mp3` | Audio fallback tile | Usually yes | Broad browser support |
| Audio | `.m4a`, `.ogg`, `.wav`, `.flac` | Audio fallback tile | Best effort | Browser codec support varies |

## Smoke Test Notes

- Verify JPEG/PNG thumbnails and lightbox rendering.
- Verify MP4 and MP3 range requests by seeking in the native controls.
- Verify MKV appears in the grid even if the browser cannot play it.
- Verify HEIC with a real iPhone file inside the final Docker image.
- Verify `/justpix` deployments with `ROOT_PATH=/justpix`, especially login/logout when auth is enabled.
