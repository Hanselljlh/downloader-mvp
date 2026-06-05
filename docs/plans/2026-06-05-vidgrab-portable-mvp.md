# VidGrab Portable MVP Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a portable desktop LinkGrabber-style app that discovers downloadable videos/files from copied browser URLs or copied page content, then downloads selected items and auto-extracts archives with user-supplied password lists.

**Architecture:** Start with a tested Python core library and CLI, then add a PySide6 desktop UI. Keep all services in-process; no installed webserver. External tools `yt-dlp` and `7zz` are called as subprocesses and may be bundled later for portable releases.

**Tech Stack:** Python 3.12, PySide6, yt-dlp, httpx, BeautifulSoup, watchdog, SQLite, 7zz, pytest, PyInstaller/Nuitka.

---

## Milestone 1: Core LinkGrabber library

- Extract URLs from copied text/HTML.
- Categorize file types.
- Maintain crawl queue with max depth, default 2.
- Deduplicate by normalized URL.
- Add tests for each behavior.

## Milestone 2: Page discovery

- Fetch normal HTML pages with httpx.
- Parse links, media tags, source tags, and common embedded URLs.
- Run `yt-dlp --dump-json` / `--flat-playlist` for page URLs.
- Merge direct parser findings and yt-dlp findings.
- Preserve DRM limitation messaging.

## Milestone 3: Download queue

- Add SQLite tables for discovered items, download jobs, and settings.
- Add yt-dlp download worker.
- Add direct-file download worker for non-video files.
- Add pause/resume/cancel state transitions.

## Milestone 4: Archive extraction

- Watch user-configured folders.
- Wait for stable file size before processing.
- Detect first part of multipart archives.
- Reload password list before each archive attempt.
- Test password with 7zz before extraction.
- Extract into temp folder, then move to final destination.
- Record success/failure without logging plaintext passwords.

## Milestone 5: Desktop UI

- PySide6 main window.
- Clipboard monitor toggle.
- LinkGrabber table grouped by category.
- File-type filter checkboxes.
- Crawl-depth setting, default 2.
- Download queue page.
- Archive extraction status page.
- Settings page for download folders, watched folders, and password list.

## Milestone 6: Portable packaging

- Bundle for Windows and Linux.
- Include or locate `yt-dlp` and `7zz`.
- Store config/data under a portable app data directory if running from USB/folder.
- Add GitHub Actions builds.

## First implementable tasks

1. Expand link extraction tests for copied rich HTML from browsers.
2. Add URL normalization and duplicate rules.
3. Add crawler queue model and tests.
4. Add yt-dlp probe wrapper with tests using subprocess abstraction.
5. Add SQLite schema and migration bootstrap.
6. Add PySide6 shell with LinkGrabber table fed by current core functions.
