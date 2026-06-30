from datetime import date

import httpx

from backend.crawler.listing import get_listing_urls


class FakeListingSource:
    listing_url = "https://tingia.gov.vn/"
    parsing_rules = {
        "listing_item": "div.info",
        "listing_link": "h2.title a",
        "listing_date": "span.date",
    }


LISTING_HTML = """
<html><body>
<div class="info">
    <h2 class="title"><a href="https://tingia.gov.vn/bai-trong-khoang.html">Bài trong khoảng</a></h2>
    <span class="date">26/01/2026 - 17:37</span>
</div>
<div class="info">
    <h2 class="title"><a href="https://tingia.gov.vn/bai-ngoai-khoang.html">Bài ngoài khoảng</a></h2>
    <span class="date">20/02/2025 - 09:00</span>
</div>
</body></html>
"""


def test_returns_only_items_with_date_inside_range():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=LISTING_HTML)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed = get_listing_urls(
        FakeListingSource(), date_from=date(2026, 1, 1), date_to=date(2026, 1, 31), client=client
    )

    assert [item["url"] for item in result] == ["https://tingia.gov.vn/bai-trong-khoang.html"]
    assert failed == []


def test_returns_failed_url_when_fetch_exhausts_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed = get_listing_urls(
        FakeListingSource(),
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
        client=client,
        max_retries=2,
    )

    assert result == []
    assert failed == ["https://tingia.gov.vn/"]


def test_skips_items_with_unparseable_date():
    html = """
    <div class="info">
        <h2 class="title"><a href="https://tingia.gov.vn/bai-khong-co-ngay.html">Không có ngày</a></h2>
        <span class="date">Không rõ</span>
    </div>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed = get_listing_urls(
        FakeListingSource(), date_from=date(2026, 1, 1), date_to=date(2026, 1, 31), client=client
    )

    assert result == []
    assert failed == []
