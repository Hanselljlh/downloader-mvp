import json
import subprocess

from vidgrab.discovery.ytdlp import YtDlpDiscovery, YtDlpError


class FakeRunner:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr
        self.commands = []

    def __call__(self, command, **kwargs):
        self.commands.append((command, kwargs))
        return subprocess.CompletedProcess(command, self.returncode, self.stdout, self.stderr)


def test_discover_builds_safe_flat_playlist_command_and_returns_candidates():
    payload = {
        "webpage_url": "https://example.com/watch?v=abc",
        "title": "Example Video",
        "entries": [
            {"url": "https://cdn.example.com/video.mp4", "title": "video"},
            {"webpage_url": "https://example.com/next", "title": "next page"},
        ],
    }
    runner = FakeRunner(json.dumps(payload))

    discovery = YtDlpDiscovery(runner=runner)
    candidates = discovery.discover("https://example.com/watch?v=abc")

    command, kwargs = runner.commands[0]
    assert command[:4] == ["yt-dlp", "--dump-single-json", "--flat-playlist", "--no-warnings"]
    assert command[-1] == "https://example.com/watch?v=abc"
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert [candidate.url for candidate in candidates] == [
        "https://cdn.example.com/video.mp4",
        "https://example.com/next",
    ]
    assert [candidate.category for candidate in candidates] == ["video", "page"]


def test_discover_handles_single_video_json_without_entries():
    runner = FakeRunner(json.dumps({"url": "https://cdn.example.com/stream.m3u8", "title": "stream"}))

    candidates = YtDlpDiscovery(runner=runner).discover("https://example.com/watch")

    assert len(candidates) == 1
    assert candidates[0].url == "https://cdn.example.com/stream.m3u8"
    assert candidates[0].category == "video"


def test_discover_raises_clear_error_without_leaking_command_noise():
    runner = FakeRunner("", returncode=1, stderr="ERROR: Unsupported URL")

    try:
        YtDlpDiscovery(runner=runner).discover("https://example.com/drm")
    except YtDlpError as exc:
        assert "yt-dlp discovery failed" in str(exc)
        assert "Unsupported URL" in str(exc)
    else:
        raise AssertionError("expected YtDlpError")
