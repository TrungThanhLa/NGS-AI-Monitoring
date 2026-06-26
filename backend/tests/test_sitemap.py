from datetime import date

import httpx

from backend.crawler.sitemap import get_article_urls


class FakeSource:
    sitemap_url = "https://vtv.vn/sitemap.xml"


SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap>
        <loc>https://vtv.vn/sitemaps/sitemaps-2026-6-11-15.xml</loc>
        <lastmod>2026-06-15T00:00:00+07:00</lastmod>
    </sitemap>
    <sitemap>
        <loc>https://vtv.vn/sitemaps/sitemaps-2026-6-21-25.xml</loc>
        <lastmod>2026-06-25T00:00:00+07:00</lastmod>
    </sitemap>
</sitemapindex>"""

SUB_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://vtv.vn/bai-viet-trong-khoang-ngay-100260623123456789.htm</loc>
        <lastmod>2026-06-23T10:00:00+07:00</lastmod>
    </url>
    <url>
        <loc>https://vtv.vn/bai-viet-ngoai-khoang-ngay-100260621123456789.htm</loc>
        <lastmod>2026-06-21T10:00:00+07:00</lastmod>
    </url>
</urlset>"""


def make_handler():
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=SITEMAP_INDEX)
        if request.url.path == "/sitemaps/sitemaps-2026-6-21-25.xml":
            return httpx.Response(200, text=SUB_SITEMAP)
        raise AssertionError(f"unexpected request: {request.url}")

    return handler, requested


def test_returns_only_urls_with_lastmod_inside_date_range_and_skips_irrelevant_sub_sitemaps():
    handler, requested = make_handler()
    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = get_article_urls(
        FakeSource(),
        date_from=date(2026, 6, 22),
        date_to=date(2026, 6, 24),
        client=client,
        delay_seconds=0,
    )

    urls = [item["url"] for item in result]
    assert urls == ["https://vtv.vn/bai-viet-trong-khoang-ngay-100260623123456789.htm"]
    # sub-sitemap 11-15 không giao với khoảng 22-24 -> không được fetch
    assert "https://vtv.vn/sitemaps/sitemaps-2026-6-11-15.xml" not in requested


def test_skips_sub_sitemap_that_keeps_failing_after_retries_without_raising():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=SITEMAP_INDEX)
        if request.url.path == "/sitemaps/sitemaps-2026-6-21-25.xml":
            attempts["count"] += 1
            raise httpx.ConnectError("boom")
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = get_article_urls(
        FakeSource(),
        date_from=date(2026, 6, 22),
        date_to=date(2026, 6, 24),
        client=client,
        delay_seconds=0,
        max_retries=3,
    )

    assert result == []
    assert attempts["count"] == 3
