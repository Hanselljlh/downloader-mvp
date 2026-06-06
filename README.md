# VidGrab Portable

Portable desktop LinkGrabber-style downloader for Windows and Linux.

## Goal

Build a lightweight app that behaves more like JDownloader's LinkGrabber than a web service:

- monitor clipboard for browser page URLs
- accept copied full-page text/HTML and extract every URL
- crawl discovered page links with configurable depth, default `2`
- let the user choose download categories before starting
- use `yt-dlp` first for video/page URLs
- detect direct media streams/files such as `.m3u8`, `.mpd`, `.mp4`, `.webm`, archives, images, documents, and subtitles
- watch configured folders for archives and extract with a hot-reloaded password list

This is **not** an installed webserver. The planned UI is a portable desktop app.

## Current status

Tested core primitives plus the first portable desktop shell:

- URL extraction from copied page text/HTML
- LinkGrabber category detection
- crawl-depth helper with default depth 2
- LinkGrabber table state for pasted/scanned rows
- category checkbox filtering without losing scan results
- local PySide6 desktop window entry point, not a background webserver
- archive password-list loader that reloads from disk every call
- minimal CLI for testing and launching these pieces

## Intended stack

- Python 3.12+
- PySide6 / Qt for desktop UI
- yt-dlp for video extraction/downloads
- httpx + BeautifulSoup for page/link discovery
- watchdog for folder monitoring
- SQLite for local job history
- 7zz / 7-Zip CLI for archive testing/extraction
- PyInstaller or Nuitka for portable builds

## MVP UX

1. App runs as a desktop window/tray app.
2. User copies browser address bar URL.
3. Clipboard monitor adds it to LinkGrabber.
4. App runs yt-dlp discovery and page link discovery.
5. App shows found items grouped by category:
   - Videos
   - Audio
   - Images
   - Archives
   - Documents
   - Subtitles
   - Pages/playlists
6. User checks what to download.
7. Download queue starts.
8. Archive watcher/extractor handles compressed downloads using the user's password list.

## Commands

Run tests:

```bash
python -m pytest tests -q
```

Scan copied text saved to a file:

```bash
python -m vidgrab.cli scan-text copied-page.txt
```

Check password-list loading without printing real passwords:

```bash
python -m vidgrab.cli passwords passwords.txt
```

Launch the desktop LinkGrabber shell after installing project dependencies:

```bash
vidgrab gui
```

## JDownloader fork/reference use

Use JDownloader as a conceptual reference for:

- LinkGrabber workflow
- package/grouping UX
- clipboard monitor behavior
- duplicate detection ideas
- archive extraction queue ideas

Do not copy code directly unless license compatibility is reviewed first.

## DRM note

VidGrab Portable should download normal web videos, direct streams, HLS/DASH streams, embedded media, and files the user is allowed to access. It will not bypass DRM-protected video.
