from __future__ import annotations

import html
import re
from collections.abc import Iterable
from urllib.parse import unquote, urlparse

URL_RE = re.compile(r"https?://[^\s<'\"`)>]+", re.IGNORECASE)
HREF_SRC_RE = re.compile(r"(?:href|src)=[\"']([^\"']+)[\"']", re.IGNORECASE)

CATEGORY_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "video": (
        ".mp4",
        ".mkv",
        ".webm",
        ".mov",
        ".avi",
        ".wmv",
        ".flv",
        ".m3u8",
        ".mpd",
    ),
    "audio": (".mp3", ".m4a", ".flac", ".wav", ".aac", ".ogg", ".opus"),
    "image": (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"),
    "archive": (
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".part01.rar",
        ".part1.rar",
        ".r00",
        ".7z.001",
        ".zip.001",
    ),
    "subtitle": (".srt", ".vtt", ".ass", ".ssa", ".sub"),
    "document": (".pdf", ".epub", ".doc", ".docx", ".txt", ".rtf"),
}


def extract_urls_from_clipboard_text(text: str) -> list[str]:
    """Extract unique absolute URLs from copied page text or copied HTML."""
    candidates: list[str] = []
    decoded = html.unescape(text)

    candidates.extend(match.group(0) for match in URL_RE.finditer(decoded))
    candidates.extend(match.group(1) for match in HREF_SRC_RE.finditer(decoded))

    return _dedupe(_clean_url(url) for url in candidates if url.lower().startswith(("http://", "https://")))


def categorize_url(url: str) -> str:
    """Return the LinkGrabber category for a URL."""
    path = unquote(urlparse(url).path).lower()
    for category, extensions in CATEGORY_EXTENSIONS.items():
        if path.endswith(extensions):
            return category
    return "page"


def should_crawl(current_depth: int, max_depth: int = 2) -> bool:
    """Return True when crawler should follow links from the current page."""
    return current_depth < max_depth


def _clean_url(url: str) -> str:
    return url.strip().rstrip(".,;])}")


def _dedupe(urls: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result
