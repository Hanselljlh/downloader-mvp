from __future__ import annotations

from vidgrab.desktop import DesktopShellState, LinkGrabberRow


def test_desktop_shell_defaults_match_mvp():
    state = DesktopShellState()

    assert state.crawl_depth == 2
    assert state.selected_categories == {
        "video",
        "audio",
        "image",
        "archive",
        "subtitle",
        "document",
        "page",
    }
    assert state.rows == []
    assert state.uses_background_webserver is False


def test_scan_text_populates_linkgrabber_rows_with_categories():
    state = DesktopShellState()

    rows = state.scan_text(
        "Copied page https://example.com/watch and https://cdn.example.com/movie.mp4 "
        "plus https://files.example.com/bundle.zip"
    )

    assert rows == [
        LinkGrabberRow(url="https://example.com/watch", category="page", selected=True, depth=0),
        LinkGrabberRow(
            url="https://cdn.example.com/movie.mp4", category="video", selected=True, depth=0
        ),
        LinkGrabberRow(
            url="https://files.example.com/bundle.zip", category="archive", selected=True, depth=0
        ),
    ]
    assert state.rows == rows


def test_category_checkboxes_filter_visible_rows_without_losing_scan_results():
    state = DesktopShellState()
    state.scan_text(
        "https://cdn.example.com/movie.mp4 https://img.example.com/poster.jpg "
        "https://example.com/page"
    )

    state.set_category_enabled("video", False)
    state.set_category_enabled("page", False)

    assert [row.category for row in state.visible_rows()] == ["image"]
    assert [row.category for row in state.rows] == ["video", "image", "page"]


def test_crawl_depth_setting_rejects_negative_values():
    state = DesktopShellState()

    state.set_crawl_depth(4)
    assert state.crawl_depth == 4

    try:
        state.set_crawl_depth(-1)
    except ValueError as exc:
        assert "crawl depth" in str(exc)
    else:
        raise AssertionError("negative crawl depth should fail")
