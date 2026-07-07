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


class FakeMultiListingSource:
    listing_url = None
    parsing_rules = {
        "listing_pages": [
            "https://bocongan.gov.vn/chuyen-muc/a",
            "https://bocongan.gov.vn/chuyen-muc/b",
            "https://bocongan.gov.vn/chuyen-muc/c",
        ],
        "fetch_pages": [
            "https://bocongan.gov.vn/chuyen-muc/a",
            "https://bocongan.gov.vn/chuyen-muc/c",
        ],
        "listing_item": "div.info",
        "listing_link": "h2.title a",
        "listing_date": "span.date",
    }


def _category_page_html(slug: str, date_text: str) -> str:
    return f"""
    <div class="info">
        <h2 class="title"><a href="https://bocongan.gov.vn/bai-viet/{slug}.html">Bai {slug}</a></h2>
        <span class="date">{date_text}</span>
    </div>
    """


def test_multi_listing_fetches_only_urls_listed_in_fetch_pages():
    page_html = {
        "https://bocongan.gov.vn/chuyen-muc/a": _category_page_html("a", "15/06/2026 - 10:00"),
        "https://bocongan.gov.vn/chuyen-muc/b": _category_page_html("b", "16/06/2026 - 11:00"),
        "https://bocongan.gov.vn/chuyen-muc/c": _category_page_html("c", "17/06/2026 - 12:00"),
    }
    requested_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requested_urls.append(url)
        return httpx.Response(200, text=page_html[url])

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed = get_listing_urls(
        FakeMultiListingSource(),
        date_from=date(2026, 1, 1),
        date_to=date(2026, 12, 31),
        client=client,
        delay_seconds=0,
    )

    # Chỉ 2 URL trong fetch_pages được gọi, "b" (chỉ khai ở listing_pages) bị bỏ qua
    assert requested_urls == [
        "https://bocongan.gov.vn/chuyen-muc/a",
        "https://bocongan.gov.vn/chuyen-muc/c",
    ]
    urls = [item["url"] for item in result]
    assert urls == [
        "https://bocongan.gov.vn/bai-viet/a.html",
        "https://bocongan.gov.vn/bai-viet/c.html",
    ]
    assert failed == []


def test_multi_listing_fetches_all_listing_pages_when_fetch_pages_missing():
    source = FakeMultiListingSource()
    source.parsing_rules = {
        "listing_pages": [
            "https://bocongan.gov.vn/chuyen-muc/a",
            "https://bocongan.gov.vn/chuyen-muc/b",
        ],
        "listing_item": "div.info",
        "listing_link": "h2.title a",
        "listing_date": "span.date",
    }
    page_html = {
        "https://bocongan.gov.vn/chuyen-muc/a": _category_page_html("a", "15/06/2026 - 10:00"),
        "https://bocongan.gov.vn/chuyen-muc/b": _category_page_html("b", "16/06/2026 - 11:00"),
    }
    requested_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requested_urls.append(url)
        return httpx.Response(200, text=page_html[url])

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed = get_listing_urls(
        source, date_from=date(2026, 1, 1), date_to=date(2026, 12, 31), client=client, delay_seconds=0
    )

    assert requested_urls == [
        "https://bocongan.gov.vn/chuyen-muc/a",
        "https://bocongan.gov.vn/chuyen-muc/b",
    ]
    assert len(result) == 2


def test_multi_listing_sleeps_between_each_page_fetch(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr("backend.crawler.listing.time.sleep", lambda seconds: sleep_calls.append(seconds))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_category_page_html("x", "15/06/2026 - 10:00"))

    client = httpx.Client(transport=httpx.MockTransport(handler))

    get_listing_urls(
        FakeMultiListingSource(),
        date_from=date(2026, 1, 1),
        date_to=date(2026, 12, 31),
        client=client,
        delay_seconds=1.5,
    )

    # fetch_pages có 2 URL ("a", "c") → phải sleep trước mỗi lần fetch, đúng 2 lần
    assert sleep_calls == [1.5, 1.5]


def test_multi_listing_collects_failed_urls_across_pages_and_continues():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://bocongan.gov.vn/chuyen-muc/a":
            raise httpx.ConnectError("boom")
        return httpx.Response(200, text=_category_page_html("c", "17/06/2026 - 12:00"))

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed = get_listing_urls(
        FakeMultiListingSource(),
        date_from=date(2026, 1, 1),
        date_to=date(2026, 12, 31),
        client=client,
        delay_seconds=0,
        max_retries=1,
    )

    assert failed == ["https://bocongan.gov.vn/chuyen-muc/a"]
    assert [item["url"] for item in result] == ["https://bocongan.gov.vn/bai-viet/c.html"]


class FakeRelativeHrefSource:
    listing_url = "https://bocongan.gov.vn/chuyen-muc/chi-dao-dieu-hanh"
    parsing_rules = {
        "listing_item": "article.card-large",
        "listing_link": 'a[href^="/bai-viet/"]',
        "listing_date": "span.date",
    }


def test_resolves_relative_href_against_listing_page_url():
    html = """
    <article class="card-large">
        <a href="/bai-viet/bai-trong-khoang"><h2>Bai trong khoang</h2></a>
        <span class="date">15/06/2026</span>
    </article>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed = get_listing_urls(
        FakeRelativeHrefSource(), date_from=date(2026, 1, 1), date_to=date(2026, 12, 31), client=client
    )

    # href tương đối "/bai-viet/..." phải được urljoin với listing_url thành URL tuyệt đối
    assert [item["url"] for item in result] == ["https://bocongan.gov.vn/bai-viet/bai-trong-khoang"]
    assert failed == []
