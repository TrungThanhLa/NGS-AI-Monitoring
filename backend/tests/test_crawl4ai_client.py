from types import SimpleNamespace

from backend.crawler.article import compute_url_hash
from backend.crawler.crawl4ai_client import fetch_article_crawl4ai, fetch_article_dispatch

URL = "https://vtv.vn/bai-viet-test.htm"

DEFAULT_METADATA = {
    "title": "Tiêu đề bài viết",
    "article:author": "Tác giả A",
    "article:published_time": "2026-06-25T16:19:00",
}


def _fake_runner(metadata=None, fit_markdown="Nội dung bài viết.", success=True):
    metadata = DEFAULT_METADATA if metadata is None else metadata

    async def runner(url):
        return SimpleNamespace(
            success=success,
            metadata=metadata,
            markdown=SimpleNamespace(fit_markdown=fit_markdown),
        )

    return runner


def test_extracts_title_content_author_date_and_url_hash_from_fit_markdown():
    result = fetch_article_crawl4ai(URL, runner=_fake_runner())

    assert result["title"] == "Tiêu đề bài viết"
    assert result["content_raw"] == "Nội dung bài viết."
    assert result["author"] == "Tác giả A"
    assert result["published_at"].isoformat() == "2026-06-25T16:19:00"
    assert result["url"] == URL
    assert result["url_hash"] == compute_url_hash(URL)


def test_returns_none_when_crawl_unsuccessful():
    result = fetch_article_crawl4ai(URL, runner=_fake_runner(success=False))

    assert result is None


def test_returns_none_when_title_missing():
    result = fetch_article_crawl4ai(URL, runner=_fake_runner(metadata={}))

    assert result is None


def test_returns_none_when_fit_markdown_empty():
    result = fetch_article_crawl4ai(URL, runner=_fake_runner(fit_markdown=""))

    assert result is None


def test_falls_back_to_generic_author_when_article_author_missing():
    metadata = {"title": "Tiêu đề", "author": "tac-gia-chung"}

    result = fetch_article_crawl4ai(URL, runner=_fake_runner(metadata=metadata))

    assert result["author"] == "tac-gia-chung"


def test_returns_none_published_at_when_date_missing():
    metadata = {"title": "Tiêu đề"}

    result = fetch_article_crawl4ai(URL, runner=_fake_runner(metadata=metadata))

    assert result["published_at"] is None


def test_returns_crawl_duration_seconds():
    result = fetch_article_crawl4ai(URL, runner=_fake_runner())

    assert result["crawl_duration_seconds"] > 0


def test_trims_content_at_tin_lien_quan_marker():
    fit_markdown = (
        "Nội dung bài viết thật.\n"
        "##  Tin liên quan \n"
        "###  [Bài gợi ý 1](https://example.test/bai-1)\n"
        "###  [Bài gợi ý 2](https://example.test/bai-2)"
    )

    result = fetch_article_crawl4ai(URL, runner=_fake_runner(fit_markdown=fit_markdown))

    assert result["content_raw"] == "Nội dung bài viết thật."


def test_trims_content_at_binh_luan_marker():
    fit_markdown = "Nội dung bài viết thật.\n####  Bình luận\nBạn cần đăng nhập để thực hiện chức năng này!"

    result = fetch_article_crawl4ai(URL, runner=_fake_runner(fit_markdown=fit_markdown))

    assert result["content_raw"] == "Nội dung bài viết thật."


def test_keeps_content_unchanged_when_no_boundary_marker_present():
    fit_markdown = "Nội dung bài viết thật, không có marker nào."

    result = fetch_article_crawl4ai(URL, runner=_fake_runner(fit_markdown=fit_markdown))

    assert result["content_raw"] == fit_markdown


def test_dispatch_calls_crawl4ai_when_engine_configured(monkeypatch):
    captured = {}

    def fake_fetch_crawl4ai(url, runner=None):
        captured["called_with"] = url
        return {"title": "fake-crawl4ai"}

    monkeypatch.setattr("backend.crawler.crawl4ai_client.fetch_article_crawl4ai", fake_fetch_crawl4ai)

    result = fetch_article_dispatch(URL, {"engine": "crawl4ai"})

    assert captured["called_with"] == URL
    assert result == {"title": "fake-crawl4ai"}


def test_dispatch_calls_httpx_fetch_when_engine_not_configured(monkeypatch):
    captured = {}

    def fake_fetch_article(url, parsing_rules, **kwargs):
        captured["called_with"] = (url, parsing_rules)
        return {"title": "fake-httpx"}

    monkeypatch.setattr("backend.crawler.crawl4ai_client.fetch_article", fake_fetch_article)

    parsing_rules = {"title": "h1"}
    result = fetch_article_dispatch(URL, parsing_rules)

    assert captured["called_with"] == (URL, parsing_rules)
    assert result == {"title": "fake-httpx"}


def test_dispatch_calls_playwright_when_engine_configured(monkeypatch):
    captured = {}

    def fake_fetch_playwright(url, parsing_rules):
        captured["called_with"] = (url, parsing_rules)
        return {"title": "fake-playwright"}

    monkeypatch.setattr("backend.crawler.crawl4ai_client.fetch_article_playwright", fake_fetch_playwright)

    parsing_rules = {"engine": "playwright", "title": "h1"}
    result = fetch_article_dispatch(URL, parsing_rules)

    assert captured["called_with"] == (URL, parsing_rules)
    assert result == {"title": "fake-playwright"}
