from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from typing import Any

from vidgrab.linkgrabber import LinkCandidate

Runner = Callable[..., subprocess.CompletedProcess[str]]


class YtDlpError(RuntimeError):
    """Raised when yt-dlp cannot discover downloadable entries for a URL."""


class YtDlpDiscovery:
    """Thin wrapper around yt-dlp metadata discovery.

    The wrapper uses JSON metadata only; it does not download. Keeping subprocess execution behind
    an injectable runner makes tests deterministic and prevents shell quoting issues.
    """

    def __init__(self, binary: str = "yt-dlp", runner: Runner = subprocess.run) -> None:
        self.binary = binary
        self.runner = runner

    def discover(self, url: str) -> list[LinkCandidate]:
        command = [self.binary, "--dump-single-json", "--flat-playlist", "--no-warnings", url]
        completed = self.runner(command, capture_output=True, text=True, timeout=60, check=False)
        if completed.returncode != 0:
            message = completed.stderr.strip() or "unknown yt-dlp error"
            raise YtDlpError(f"yt-dlp discovery failed: {message}")

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise YtDlpError("yt-dlp discovery failed: invalid JSON output") from exc

        return self._payload_to_candidates(payload, source_url=url)

    def _payload_to_candidates(self, payload: dict[str, Any], *, source_url: str) -> list[LinkCandidate]:
        entries = payload.get("entries")
        if isinstance(entries, list):
            candidates = [self._entry_to_candidate(entry, source_url=source_url) for entry in entries]
            return [candidate for candidate in candidates if candidate is not None]

        candidate = self._entry_to_candidate(payload, source_url=source_url)
        return [] if candidate is None else [candidate]

    def _entry_to_candidate(
        self, entry: dict[str, Any], *, source_url: str
    ) -> LinkCandidate | None:
        discovered_url = entry.get("url") or entry.get("webpage_url")
        if not isinstance(discovered_url, str) or not discovered_url.startswith(("http://", "https://")):
            return None
        return LinkCandidate.from_url(discovered_url, source_url=source_url)
