"""TDD tests for the archive extraction worker (issue #4)."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

from vidgrab.archives.extractor import (
    ArchiveResult,
    ArchiveWorker,
    _STAGING_SUFFIX,
    extract_archive,
    is_archive_first_part,
    probe_password,
    wait_for_stable_size,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeRunner:
    """Minimal subprocess.run replacement that records calls and returns a preset code."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.commands: list[tuple[list[str], dict]] = []

    def __call__(self, cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.commands.append((list(cmd), dict(kwargs)))
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, self.stderr)


class SmartPasswordRunner:
    """Runner that returns success only for a specific correct password."""

    def __init__(self, correct_password: str) -> None:
        self.correct_password = correct_password
        self.commands: list[tuple[list[str], dict]] = []

    def __call__(self, cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.commands.append((list(cmd), dict(kwargs)))
        # cmd[2] is "-p<password>"
        password = cmd[2][2:]  # strip leading "-p"
        subcommand = cmd[1]
        if subcommand == "t":
            rc = 0 if password == self.correct_password else 1
        else:
            rc = 0
        return subprocess.CompletedProcess(cmd, rc, "", "")


# ---------------------------------------------------------------------------
# is_archive_first_part
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "filename,expected",
    [
        # plain single-volume archives → first part
        ("bundle.zip", True),
        ("bundle.7z", True),
        ("bundle.rar", True),
        # 7z split volumes → only .001 is first
        ("bundle.7z.001", True),
        ("bundle.7z.002", False),
        ("bundle.7z.010", False),
        # RAR numbered parts → only part 1 is first
        ("bundle.part1.rar", True),
        ("bundle.part01.rar", True),
        ("bundle.part001.rar", True),
        ("bundle.part2.rar", False),
        ("bundle.part02.rar", False),
        ("bundle.part10.rar", False),
        # upper-case extension should still match
        ("BUNDLE.ZIP", True),
        ("BUNDLE.7Z.001", True),
        # unrelated files
        ("video.mp4", False),
        ("document.pdf", False),
        ("bundle.zip.bak", False),
    ],
)
def test_is_archive_first_part(filename: str, expected: bool) -> None:
    assert is_archive_first_part(Path(filename)) is expected


# ---------------------------------------------------------------------------
# wait_for_stable_size
# ---------------------------------------------------------------------------

def test_wait_for_stable_size_returns_true_when_size_stabilizes() -> None:
    sizes = iter([1024, 2048, 2048])
    clock_val = [0.0]

    def sizer(_: Path) -> int:
        return next(sizes)

    def sleep(n: float) -> None:
        clock_val[0] += n

    def clock() -> float:
        return clock_val[0]

    result = wait_for_stable_size(
        Path("dummy.zip"),
        poll_interval=1.0,
        stable_polls=1,
        timeout=100.0,
        _sizer=sizer,
        _sleep=sleep,
        _clock=clock,
    )
    assert result is True


def test_wait_for_stable_size_returns_false_when_timeout_expires() -> None:
    counter = [0]
    clock_val = [0.0]

    def always_growing(_: Path) -> int:
        counter[0] += 1
        return counter[0] * 100  # size grows every call

    def sleep(n: float) -> None:
        clock_val[0] += 10.0  # advance clock quickly past deadline

    def clock() -> float:
        return clock_val[0]

    result = wait_for_stable_size(
        Path("dummy.zip"),
        poll_interval=1.0,
        stable_polls=2,
        timeout=5.0,
        _sizer=always_growing,
        _sleep=sleep,
        _clock=clock,
    )
    assert result is False


def test_wait_for_stable_size_handles_missing_file_gracefully() -> None:
    call_count = [0]
    clock_val = [0.0]

    def raise_first_then_stable(_: Path) -> int:
        call_count[0] += 1
        if call_count[0] == 1:
            raise OSError("not yet written")
        return 512

    def sleep(n: float) -> None:
        clock_val[0] += n

    def clock() -> float:
        return clock_val[0]

    result = wait_for_stable_size(
        Path("dummy.zip"),
        poll_interval=1.0,
        stable_polls=1,
        timeout=30.0,
        _sizer=raise_first_then_stable,
        _sleep=sleep,
        _clock=clock,
    )
    assert result is True


# ---------------------------------------------------------------------------
# probe_password
# ---------------------------------------------------------------------------

def test_probe_password_builds_list_command_and_returns_true_on_success(tmp_path: Path) -> None:
    archive = tmp_path / "archive.zip"
    archive.write_bytes(b"fake")

    runner = FakeRunner(returncode=0)
    result = probe_password(archive, "secret", binary="7zz", runner=runner)

    assert result is True
    cmd, kwargs = runner.commands[0]
    assert cmd == ["7zz", "t", "-psecret", str(archive)]
    assert kwargs.get("shell", False) is False  # no shell injection


def test_probe_password_returns_false_when_7zz_signals_wrong_password(tmp_path: Path) -> None:
    archive = tmp_path / "archive.zip"
    archive.write_bytes(b"fake")

    runner = FakeRunner(returncode=1)
    assert probe_password(archive, "wrong", binary="7zz", runner=runner) is False


def test_probe_password_blank_string_is_tried_as_no_password(tmp_path: Path) -> None:
    archive = tmp_path / "archive.zip"
    archive.write_bytes(b"fake")

    runner = FakeRunner(returncode=0)
    probe_password(archive, "", binary="7zz", runner=runner)

    cmd, _ = runner.commands[0]
    assert cmd[2] == "-p"  # -p with empty password


# ---------------------------------------------------------------------------
# extract_archive
# ---------------------------------------------------------------------------

def test_extract_archive_builds_correct_list_command(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.7z"
    archive.write_bytes(b"fake")
    dest = tmp_path / "out"

    runner = FakeRunner(returncode=0)
    success = extract_archive(archive, dest, "pass123", binary="7zz", runner=runner)

    assert success is True
    cmd, kwargs = runner.commands[0]
    assert cmd[0] == "7zz"
    assert cmd[1] == "x"
    assert "-ppass123" in cmd
    assert f"-o{dest}" in cmd
    assert str(archive) in cmd
    assert kwargs.get("shell", False) is False


def test_extract_archive_returns_false_on_nonzero_exit(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.7z"
    archive.write_bytes(b"fake")

    runner = FakeRunner(returncode=2)
    assert extract_archive(archive, tmp_path / "out", "pw", binary="7zz", runner=runner) is False


# ---------------------------------------------------------------------------
# ArchiveWorker
# ---------------------------------------------------------------------------

def test_archive_worker_rejects_non_first_part(tmp_path: Path) -> None:
    pw_file = tmp_path / "passwords.txt"
    pw_file.write_text("pass\n", encoding="utf-8")
    secondary = tmp_path / "bundle.7z.002"
    secondary.write_bytes(b"fake")

    worker = ArchiveWorker(pw_file, binary="7zz", runner=FakeRunner())
    result = worker.process(secondary, tmp_path / "out")

    assert result.success is False
    assert result.error is not None and "first part" in result.error


def test_archive_worker_returns_error_when_size_never_stabilizes(tmp_path: Path) -> None:
    pw_file = tmp_path / "passwords.txt"
    pw_file.write_text("pass\n", encoding="utf-8")
    archive = tmp_path / "bundle.zip"
    archive.write_bytes(b"fake")

    counter = [0]

    def always_growing(_: Path) -> int:
        counter[0] += 1
        return counter[0] * 100

    worker = ArchiveWorker(
        pw_file,
        binary="7zz",
        runner=FakeRunner(),
        stable_timeout=0.01,
        stable_poll_interval=0.001,
        _sizer=always_growing,
    )
    result = worker.process(archive, tmp_path / "out")

    assert result.success is False
    assert result.error is not None and "stabilize" in result.error


def test_archive_worker_hot_reloads_password_list(tmp_path: Path) -> None:
    pw_file = tmp_path / "passwords.txt"
    pw_file.write_text("first\n", encoding="utf-8")
    archive = tmp_path / "bundle.zip"
    archive.write_bytes(b"fake")
    out = tmp_path / "out"

    runner = SmartPasswordRunner(correct_password="second")

    # Rewrite passwords file before worker reads it — worker should pick up "second"
    pw_file.write_text("first\nsecond\n", encoding="utf-8")

    worker = ArchiveWorker(pw_file, binary="7zz", runner=runner)
    result = worker.process(archive, out)

    assert result.success is True


def test_archive_worker_returns_error_when_no_password_matches(tmp_path: Path) -> None:
    pw_file = tmp_path / "passwords.txt"
    pw_file.write_text("wrong1\nwrong2\n", encoding="utf-8")
    archive = tmp_path / "bundle.zip"
    archive.write_bytes(b"fake")

    runner = FakeRunner(returncode=1)  # test always fails
    worker = ArchiveWorker(pw_file, binary="7zz", runner=runner)
    result = worker.process(archive, tmp_path / "out")

    assert result.success is False
    assert result.error is not None and "password" in result.error


def test_archive_worker_does_not_log_plaintext_passwords(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    pw_file = tmp_path / "passwords.txt"
    pw_file.write_text("supersecretpassword\n", encoding="utf-8")
    archive = tmp_path / "bundle.zip"
    archive.write_bytes(b"fake")

    runner = FakeRunner(returncode=0)
    worker = ArchiveWorker(pw_file, binary="7zz", runner=runner)

    with caplog.at_level(logging.DEBUG, logger="vidgrab.archives.extractor"):
        worker.process(archive, tmp_path / "out")

    for record in caplog.records:
        assert "supersecretpassword" not in record.getMessage()


def test_archive_worker_processes_sample_protected_archive(tmp_path: Path) -> None:
    """End-to-end happy-path with an injectable fake runner."""
    pw_file = tmp_path / "passwords.txt"
    pw_file.write_text("wrong\ncorrect\nalso_wrong\n", encoding="utf-8")
    archive = tmp_path / "protected.zip"
    archive.write_bytes(b"fake zip bytes")
    out = tmp_path / "extracted"

    runner = SmartPasswordRunner(correct_password="correct")
    worker = ArchiveWorker(pw_file, binary="7zz", runner=runner)
    result = worker.process(archive, out)

    assert result.success is True
    assert result.extracted_to == out
    assert result.error is None

    # Verify only "correct" triggered an extract command, and it used list args
    extract_cmds = [cmd for cmd, _ in runner.commands if cmd[1] == "x"]
    assert len(extract_cmds) == 1
    assert "-pcorrect" in extract_cmds[0]


def test_archive_worker_result_fields_on_failure(tmp_path: Path) -> None:
    pw_file = tmp_path / "passwords.txt"
    pw_file.write_text("bad\n", encoding="utf-8")
    archive = tmp_path / "protected.zip"
    archive.write_bytes(b"fake")

    worker = ArchiveWorker(pw_file, binary="7zz", runner=FakeRunner(returncode=1))
    result = worker.process(archive, tmp_path / "out")

    assert isinstance(result, ArchiveResult)
    assert result.success is False
    assert result.extracted_to is None


# ---------------------------------------------------------------------------
# Atomic staging / temp-dir extraction
# ---------------------------------------------------------------------------

def test_archive_worker_success_renames_staging_to_output(tmp_path: Path) -> None:
    """On success the staging dir must not exist; output_dir must exist."""
    pw_file = tmp_path / "passwords.txt"
    pw_file.write_text("correct\n", encoding="utf-8")
    archive = tmp_path / "bundle.zip"
    archive.write_bytes(b"fake")
    out = tmp_path / "out"

    runner = SmartPasswordRunner(correct_password="correct")
    worker = ArchiveWorker(pw_file, binary="7zz", runner=runner)
    result = worker.process(archive, out)

    staging = out.parent / (out.name + _STAGING_SUFFIX)
    assert result.success is True
    assert out.is_dir(), "output dir must exist after successful extraction"
    assert not staging.exists(), "staging dir must be gone after rename"


def test_archive_worker_failed_extraction_leaves_no_output_dir(tmp_path: Path) -> None:
    """When extraction command fails the output dir and staging dir must not exist."""
    pw_file = tmp_path / "passwords.txt"
    pw_file.write_text("correct\n", encoding="utf-8")
    archive = tmp_path / "bundle.zip"
    archive.write_bytes(b"fake")
    out = tmp_path / "out"

    class ProbeOkExtractFail:
        """Runner that passes the test command but fails extraction."""

        def __call__(self, cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            rc = 0 if cmd[1] == "t" else 2
            return subprocess.CompletedProcess(cmd, rc, "", "")

    worker = ArchiveWorker(pw_file, binary="7zz", runner=ProbeOkExtractFail())
    result = worker.process(archive, out)

    staging = out.parent / (out.name + _STAGING_SUFFIX)
    assert result.success is False
    assert result.error == "extraction command failed"
    assert not out.exists(), "output dir must not be created on extraction failure"
    assert not staging.exists(), "staging dir must be cleaned up on extraction failure"


def test_archive_worker_extraction_uses_staging_path_not_output_dir(tmp_path: Path) -> None:
    """7zz -o argument must point to the staging dir, not the final output dir."""
    pw_file = tmp_path / "passwords.txt"
    pw_file.write_text("pw\n", encoding="utf-8")
    archive = tmp_path / "bundle.zip"
    archive.write_bytes(b"fake")
    out = tmp_path / "final"

    calls: list[list[str]] = []

    class RecordingRunner:
        def __call__(self, cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, "", "")

    worker = ArchiveWorker(pw_file, binary="7zz", runner=RecordingRunner())
    worker.process(archive, out)

    extract_cmds = [c for c in calls if c[1] == "x"]
    assert len(extract_cmds) == 1
    o_arg = next(a for a in extract_cmds[0] if a.startswith("-o"))
    dest_used = Path(o_arg[2:])
    staging = out.parent / (out.name + _STAGING_SUFFIX)
    assert dest_used == staging, f"7zz should extract to staging dir {staging}, got {dest_used}"
    assert not dest_used.name == out.name, "7zz must not extract directly into final output dir"
