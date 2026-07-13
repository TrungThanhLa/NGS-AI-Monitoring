from backend.crawler.article import compute_url_hash
from backend.crawler.playwright_client import PlaywrightError, fetch_article_playwright

URL = "https://vtv.vn/bai-viet-test.htm"

PARSING_RULES = {"title": "h1.title", "content": "div.content", "author": "span.author", "date": "meta.published"}

HTML = """
<html><body>
<h1 class="title">Tiêu đề bài viết</h1>
<div class="content">Nội dung bài viết.</div>
<span class="author">Tác giả A</span>
<meta class="published" content="2026-06-25T16:19:00">
</body></html>
"""


def _fake_renderer(html=HTML, fail_times=0):
    calls = {"count": 0}

    def renderer(url):
        calls["count"] += 1
        if calls["count"] <= fail_times:
            raise PlaywrightError("simulated render failure")
        return html

    renderer.calls = calls
    return renderer


def test_extracts_title_content_author_date_and_url_hash():
    result = fetch_article_playwright(URL, PARSING_RULES, renderer=_fake_renderer())

    assert result["title"] == "Tiêu đề bài viết"
    assert result["content_raw"] == "Nội dung bài viết."
    assert result["author"] == "Tác giả A"
    assert result["published_at"].isoformat() == "2026-06-25T16:19:00"
    assert result["url"] == URL
    assert result["url_hash"] == compute_url_hash(URL)


def test_returns_none_when_title_selector_does_not_match():
    html = HTML.replace('class="title"', 'class="not-title"')

    result = fetch_article_playwright(URL, PARSING_RULES, renderer=_fake_renderer(html=html))

    assert result is None


def test_returns_none_when_content_selector_does_not_match():
    html = HTML.replace('class="content"', 'class="not-content"')

    result = fetch_article_playwright(URL, PARSING_RULES, renderer=_fake_renderer(html=html))

    assert result is None


def test_returns_crawl_duration_seconds():
    result = fetch_article_playwright(URL, PARSING_RULES, renderer=_fake_renderer())

    assert result["crawl_duration_seconds"] > 0


def test_retries_on_render_error_then_succeeds():
    renderer = _fake_renderer(fail_times=2)

    result = fetch_article_playwright(URL, PARSING_RULES, renderer=renderer, retry_backoff_seconds=0)

    assert result["title"] == "Tiêu đề bài viết"
    assert renderer.calls["count"] == 3


def test_returns_none_after_exhausting_retries():
    renderer = _fake_renderer(fail_times=5)

    result = fetch_article_playwright(
        URL, PARSING_RULES, renderer=renderer, max_retries=3, retry_backoff_seconds=0
    )

    assert result is None
    assert renderer.calls["count"] == 3
