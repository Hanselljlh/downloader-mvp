from __future__ import annotations

import html
import re
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, unquote, urlparse, urlunparse

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


@dataclass(frozen=True)
class LinkCandidate:
    """A LinkGrabber row discovered from clipboard/page/crawler input."""

    url: str
    category: str
    selected: bool = True
    source_url: str | None = None
    depth: int = 0

    @classmethod
    def from_url(cls, url: str, *, source_url: str | None = None, depth: int = 0) -> LinkCandidate:
        normalized = normalize_url(url)
        return cls(
            url=normalized,
            category=categorize_url(normalized),
            selected=True,
            source_url=source_url,
            depth=depth,
        )


@dataclass(frozen=True)
class CrawlItem:
    url: str
    depth: int


class CrawlQueue:
    """Small FIFO queue that deduplicates normalized URLs and enforces max crawl depth."""

    def __init__(self, max_depth: int = 2) -> None:
        self.max_depth = max_depth
        self._queued: deque[CrawlItem] = deque()
        self._seen: set[str] = set()

    def add(self, url: str, *, depth: int = 0) -> bool:
        if not should_crawl(depth, self.max_depth):
            return False
        normalized = normalize_url(url)
        if normalized in self._seen:
            return False
        self._seen.add(normalized)
        self._queued.append(CrawlItem(normalized, depth))
        return True

    def pop_next(self) -> CrawlItem | None:
        if not self._queued:
            return None
        return self._queued.popleft()


def extract_urls_from_clipboard_text(text: str) -> list[str]:
    """Extract unique absolute URLs from copied page text or copied HTML."""
    candidates: list[str] = []
    decoded = html.unescape(text)

    candidates.extend(match.group(0) for match in URL_RE.finditer(decoded))
    candidates.extend(match.group(1) for match in HREF_SRC_RE.finditer(decoded))

    return _dedupe(
        normalize_url(url) for url in candidates if url.lower().startswith(("http://", "https://"))
    )


def normalize_url(url: str) -> str:
    """Normalize a URL for dedupe while preserving meaningful path case."""
    cleaned = _clean_url(url)
    parsed = urlparse(cleaned)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    port = parsed.port
    netloc = hostname
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        netloc = f"{hostname}:{port}"
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), doseq=True)
    return urlunparse((scheme, netloc, parsed.path or "/", "", query, ""))


def categorize_url(url: str) -> str:
    """Return the LinkGrabber category for a URL."""
    path = unquote(urlparse(url).path).lower()
    for category, extensions in CATEGORY_EXTENSIONS.items():
        if path.endswith(extensions):
            return category
    return "page"


def apply_category_filter(
    candidates: Iterable[LinkCandidate], selected_categories: set[str]
) -> list[LinkCandidate]:
    """Return candidates whose categories are enabled in the LinkGrabber filter."""
    if "all" in selected_categories:
        return list(candidates)
    return [candidate for candidate in candidates if candidate.category in selected_categories]


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
