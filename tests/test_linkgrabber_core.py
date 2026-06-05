from vidgrab.linkgrabber import (
    CrawlQueue,
    LinkCandidate,
    apply_category_filter,
    normalize_url,
)


def test_normalize_url_removes_fragments_default_ports_and_trailing_punctuation():
    assert normalize_url(" https://Example.com:443/Video.MP4?b=2&a=1#player). ") == (
        "https://example.com/Video.MP4?a=1&b=2"
    )
    assert normalize_url("http://example.com:80/path/") == "http://example.com/path/"


def test_link_candidate_uses_normalized_url_and_category():
    candidate = LinkCandidate.from_url("HTTPS://CDN.Example.com/movie.m3u8#frag")

    assert candidate.url == "https://cdn.example.com/movie.m3u8"
    assert candidate.category == "video"
    assert candidate.selected is True


def test_apply_category_filter_selects_only_requested_categories():
    candidates = [
        LinkCandidate.from_url("https://cdn.example.com/movie.mp4"),
        LinkCandidate.from_url("https://cdn.example.com/archive.zip"),
        LinkCandidate.from_url("https://example.com/page"),
    ]

    filtered = apply_category_filter(candidates, {"video", "archive"})

    assert [candidate.url for candidate in filtered] == [
        "https://cdn.example.com/movie.mp4",
        "https://cdn.example.com/archive.zip",
    ]


def test_crawl_queue_deduplicates_urls_and_stops_at_default_depth_two():
    queue = CrawlQueue(max_depth=2)
    queue.add("https://example.com/start")
    queue.add("https://example.com/start#duplicate")

    first = queue.pop_next()
    assert first is not None
    assert first.url == "https://example.com/start"
    assert first.depth == 0

    queue.add("https://example.com/child", depth=first.depth + 1)
    queue.add("https://example.com/grandchild", depth=2)

    second = queue.pop_next()
    assert second is not None
    assert second.url == "https://example.com/child"
    assert second.depth == 1
    assert queue.pop_next() is None
