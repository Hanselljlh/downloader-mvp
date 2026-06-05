from vidgrab.linkgrabber import categorize_url, extract_urls_from_clipboard_text, should_crawl


def test_extract_urls_from_plain_text_and_html():
    copied = '''
    <a href="https://example.com/watch?v=abc">video</a>
    plain https://cdn.example.com/movie.mp4 and https://files.example.com/archive.part01.rar
    duplicate https://cdn.example.com/movie.mp4
    '''

    urls = extract_urls_from_clipboard_text(copied)

    assert urls == [
        "https://example.com/watch?v=abc",
        "https://cdn.example.com/movie.mp4",
        "https://files.example.com/archive.part01.rar",
    ]


def test_categorize_url_groups_downloadable_file_types():
    assert categorize_url("https://cdn.example.com/movie.m3u8") == "video"
    assert categorize_url("https://cdn.example.com/song.flac") == "audio"
    assert categorize_url("https://cdn.example.com/photo.webp") == "image"
    assert categorize_url("https://cdn.example.com/file.7z.001") == "archive"
    assert categorize_url("https://cdn.example.com/subs.srt") == "subtitle"
    assert categorize_url("https://cdn.example.com/manual.pdf") == "document"
    assert categorize_url("https://example.com/watch?v=123") == "page"


def test_should_crawl_honors_depth_limit_default_two():
    assert should_crawl(current_depth=0, max_depth=2) is True
    assert should_crawl(current_depth=1, max_depth=2) is True
    assert should_crawl(current_depth=2, max_depth=2) is False
