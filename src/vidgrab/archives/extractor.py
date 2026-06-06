"""Archive detection, password testing, and extraction worker."""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from vidgrab.archives.passwords import load_passwords

logger = logging.getLogger(__name__)

SevenZipRunner = Callable[..., "subprocess.CompletedProcess[str]"]

# Suffix appended to the output directory name during extraction to create a
# staging area.  The staging dir is renamed to the real output dir on success
# and removed on failure, so partial extractions are never visible.
_STAGING_SUFFIX = "._extracting"

# Matches numbered 7z split volumes like .7z.001, .7z.002 …
_7Z_SPLIT_RE = re.compile(r"\.7z\.(\d+)$", re.IGNORECASE)
# Matches numbered RAR multi-part files like .part01.rar, .part1.rar …
_RAR_PART_RE = re.compile(r"\.part(\d+)\.rar$", re.IGNORECASE)


def is_archive_first_part(path: Path) -> bool:
    """Return True only for archive files that should trigger extraction.

    Multi-volume subsequent parts (.7z.002, .part2.rar, …) return False so the
    worker ignores them and only acts when the first part appears.
    """
    name = path.name

    m7 = _7Z_SPLIT_RE.search(name)
    if m7:
        return int(m7.group(1)) == 1

    mr = _RAR_PART_RE.search(name)
    if mr:
        return int(mr.group(1)) == 1

    lower = name.lower()
    return lower.endswith((".zip", ".7z", ".rar"))


def wait_for_stable_size(
    path: Path,
    *,
    poll_interval: float = 2.0,
    stable_polls: int = 2,
    timeout: float = 300.0,
    _sizer: Callable[[Path], int] | None = None,
    _sleep: Callable[[float], None] | None = None,
    _clock: Callable[[], float] | None = None,
) -> bool:
    """Poll *path* until its size stops changing for *stable_polls* consecutive reads.

    Returns True when stable, False if *timeout* expires first.  The private
    injectable parameters exist solely for deterministic unit testing.
    """
    get_size = _sizer if _sizer is not None else lambda p: p.stat().st_size
    sleep = _sleep if _sleep is not None else time.sleep
    clock = _clock if _clock is not None else time.monotonic

    deadline = clock() + timeout
    last_size = -1
    stable_count = 0

    while clock() < deadline:
        try:
            size = get_size(path)
        except OSError:
            sleep(poll_interval)
            continue

        if size == last_size:
            stable_count += 1
            if stable_count >= stable_polls:
                return True
        else:
            stable_count = 0
            last_size = size

        sleep(poll_interval)

    return False


def probe_password(
    archive: Path,
    password: str,
    *,
    binary: str = "7zz",
    runner: SevenZipRunner = subprocess.run,
) -> bool:
    """Return True if *password* successfully opens *archive* (7zz t command).

    SECURITY NOTE: 7zz does not support reading passwords from stdin in
    non-interactive/batch mode, so the password is embedded in the ``-p``
    command-line argument.  It may therefore be visible to other local
    processes via ``/proc/<pid>/cmdline`` or tools such as ``ps``.
    Passwords are never written to log output by this module.
    """
    cmd = [binary, "t", f"-p{password}", str(archive)]
    result = runner(cmd, capture_output=True, text=True, check=False)
    return result.returncode == 0


def extract_archive(
    archive: Path,
    dest: Path,
    password: str,
    *,
    binary: str = "7zz",
    runner: SevenZipRunner = subprocess.run,
) -> bool:
    """Extract *archive* into *dest* using *password*.  Returns True on success.

    SECURITY NOTE: see ``probe_password`` — the same ``-p`` limitation applies.
    """
    cmd = [binary, "x", f"-p{password}", f"-o{dest}", "-y", str(archive)]
    result = runner(cmd, capture_output=True, text=True, check=False)
    return result.returncode == 0


def _is_safe_member_path(member_path: str) -> bool:
    """Return True if *member_path* contains no absolute reference or '..' traversal."""
    normalised = member_path.replace("\\", "/")
    parts = [p for p in normalised.split("/") if p]
    if ".." in parts:
        return False
    if normalised.startswith("/"):
        return False
    # Windows drive-letter absolute path (e.g. "C:/...")
    if len(normalised) >= 2 and normalised[1] == ":":
        return False
    return True


def validate_archive_members(
    archive: Path,
    password: str,
    *,
    binary: str = "7zz",
    runner: SevenZipRunner,
) -> tuple[bool, str | None]:
    """Return ``(True, None)`` if all member paths are safe, ``(False, reason)`` otherwise.

    Uses ``7zz l -slt`` to enumerate archive members and rejects any entry
    whose path is absolute or contains ``..`` (directory traversal).  Only
    entries after the first ``----------`` separator are inspected so that the
    archive-info header block is not treated as member data.
    """
    cmd = [binary, "l", "-slt", f"-p{password}", str(archive)]
    result = runner(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return False, "could not list archive members"

    past_header = False
    for line in result.stdout.splitlines():
        if line.startswith("----------"):
            past_header = True
            continue
        if past_header and line.startswith("Path = "):
            member_path = line[7:]
            if not _is_safe_member_path(member_path):
                return False, f"unsafe member path: {member_path}"

    return True, None


def archive_output_stem(path: Path) -> str:
    """Return the base archive name without split-volume suffixes.

    Examples::

        bundle.7z.001  → "bundle"
        bundle.part01.rar → "bundle"
        bundle.zip     → "bundle"
    """
    name = path.name
    if _7Z_SPLIT_RE.search(name):
        # e.g. bundle.7z.001 → stem = "bundle.7z" → stem again = "bundle"
        return Path(path.stem).stem
    m = _RAR_PART_RE.search(name)
    if m:
        # e.g. bundle.part01.rar → name[:start_of_.part] = "bundle"
        return name[: m.start()]
    return path.stem


@dataclass
class ArchiveResult:
    success: bool
    extracted_to: Path | None = field(default=None)
    error: str | None = field(default=None)


class ArchiveWorker:
    """Process an archive: wait for a stable file, find the right password, and extract.

    The *runner* parameter is injectable so that unit tests never require a real
    7zz binary.  All subprocess calls use list arguments and shell=False (the
    default) to prevent shell-injection issues.
    """

    def __init__(
        self,
        password_file: str | Path,
        *,
        binary: str = "7zz",
        runner: SevenZipRunner = subprocess.run,
        stable_timeout: float = 300.0,
        stable_poll_interval: float = 2.0,
        _sizer: Callable[[Path], int] | None = None,
    ) -> None:
        self.password_file = Path(password_file)
        self.binary = binary
        self.runner = runner
        self.stable_timeout = stable_timeout
        self.stable_poll_interval = stable_poll_interval
        self._sizer = _sizer

    def process(self, archive: Path, output_dir: Path) -> ArchiveResult:
        """Run the full extraction pipeline for one archive file."""
        if not is_archive_first_part(archive):
            return ArchiveResult(success=False, error="not an archive first part")

        logger.debug("Waiting for stable size: %s", archive.name)
        stable = wait_for_stable_size(
            archive,
            poll_interval=self.stable_poll_interval,
            timeout=self.stable_timeout,
            _sizer=self._sizer,
        )
        if not stable:
            return ArchiveResult(
                success=False,
                error=f"archive size did not stabilize within {self.stable_timeout}s",
            )

        # Hot-reload passwords before every job so newly added passwords are picked up.
        passwords = load_passwords(self.password_file)
        total = len(passwords)
        logger.debug("Loaded %d passwords from %s", total, self.password_file.name)

        for index, password in enumerate(passwords):
            logger.debug("Testing password %d/%d", index + 1, total)
            if probe_password(archive, password, binary=self.binary, runner=self.runner):
                logger.debug("Password accepted at position %d/%d", index + 1, total)
                safe, reason = validate_archive_members(
                    archive, password, binary=self.binary, runner=self.runner
                )
                if not safe:
                    return ArchiveResult(success=False, error=f"unsafe archive: {reason}")
                return self._extract_atomic(archive, output_dir, password)

        return ArchiveResult(success=False, error="no working password found")

    def _extract_atomic(self, archive: Path, output_dir: Path, password: str) -> ArchiveResult:
        """Extract to a staging directory and atomically rename it to *output_dir*.

        Keeps partial extractions invisible: the real output directory only
        appears once 7zz exits with code 0 and the rename succeeds.
        """
        staging = output_dir.parent / (output_dir.name + _STAGING_SUFFIX)
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True, exist_ok=False)
        try:
            if extract_archive(archive, staging, password, binary=self.binary, runner=self.runner):
                if output_dir.exists():
                    return ArchiveResult(
                        success=False,
                        error=f"output directory already exists: {output_dir}",
                    )
                staging.rename(output_dir)
                return ArchiveResult(success=True, extracted_to=output_dir)
            return ArchiveResult(success=False, error="extraction command failed")
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
