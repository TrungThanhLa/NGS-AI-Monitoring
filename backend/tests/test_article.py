import hashlib
from pathlib import Path

import httpx

from backend.crawler.article import fetch_article

FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "vtv_article.html").read_text(encoding="utf-8")
ARTICLE_URL = "https://vtv.vn/dong-thap-bai-rac-qua-tai-nha-may-xu-ly-rac-sau-3-nam-van-cham-tien-do-100260624162946883.htm"

VTV_PARSING_RULES = {
    "title": "meta[property='og:title']",
    "content": "div.detail-content",
    "date": "meta[property='article:published_time']",
    "author": "meta[property='article:author']",
}


def _client_returning(html: str, status_code: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text=html)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_extracts_title_content_author_date_and_url_hash_from_real_vtv_html():
    client = _client_returning(FIXTURE_HTML)

    result = fetch_article(ARTICLE_URL, VTV_PARSING_RULES, client=client)

    assert result["title"] == "Đồng Tháp: Bãi rác quá tải, nhà máy xử lý rác sau 3 năm vẫn chậm tiến độ"
    assert "detail-content" not in result["content_raw"]
    assert len(result["content_raw"]) > 100
    assert result["author"] == "Giáp Công - Phạm Bằng"
    assert result["published_at"].isoformat() == "2026-06-25T16:19:00"
    assert result["url"] == ARTICLE_URL
    assert result["url_hash"] == hashlib.sha256(ARTICLE_URL.encode()).hexdigest()


def test_returns_none_when_content_selector_matches_nothing():
    client = _client_returning("<html><head></head><body><p>no content div here</p></body></html>")

    result = fetch_article(ARTICLE_URL, VTV_PARSING_RULES, client=client)

    assert result is None


def test_skips_after_retries_exhausted_on_network_error():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        raise httpx.ConnectError("boom")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = fetch_article(ARTICLE_URL, VTV_PARSING_RULES, client=client, max_retries=3, retry_backoff_seconds=0)

    assert result is None
    assert attempts["count"] == 3


def test_returns_crawl_duration_seconds_excluding_outer_sleep():
    client = _client_returning(FIXTURE_HTML)

    result = fetch_article(ARTICLE_URL, VTV_PARSING_RULES, client=client)

    assert result["crawl_duration_seconds"] > 0
    assert result["crawl_duration_seconds"] < 1.0
