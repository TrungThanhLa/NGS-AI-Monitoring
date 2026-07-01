from datetime import date

import httpx

from backend.crawler.sitemap import get_article_urls


class FakeSource:
    """Domain không có trong _SITEMAP_DATE_PATTERNS → pattern=None → fetch-all (safe fallback)."""
    sitemap_url = "https://vtv.vn/sitemap.xml"
    domain = "unknown.example.com"


class VTVSource:
    """VTV: regex khoảng ngày trong tháng (day_start + day_end)."""
    sitemap_url = "https://vtv.vn/sitemap.xml"
    domain = "vtv.vn"


class VOVSource:
    """VOV: regex năm-tháng, path-based (/YYYY/M/)."""
    sitemap_url = "https://vov.vn/sitemap.xml"
    domain = "vov.vn"


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

    result, failed_locs = get_article_urls(
        VTVSource(),
        date_from=date(2026, 6, 22),
        date_to=date(2026, 6, 24),
        client=client,
        delay_seconds=0,
    )

    urls = [item["url"] for item in result]
    assert urls == ["https://vtv.vn/bai-viet-trong-khoang-ngay-100260623123456789.htm"]
    # sub-sitemap 11-15 không giao với khoảng 22-24 -> không được fetch
    assert "https://vtv.vn/sitemaps/sitemaps-2026-6-11-15.xml" not in requested
    assert failed_locs == []


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

    result, failed_locs = get_article_urls(
        VTVSource(),
        date_from=date(2026, 6, 22),
        date_to=date(2026, 6, 24),
        client=client,
        delay_seconds=0,
        max_retries=3,
    )

    assert result == []
    assert attempts["count"] == 3
    # sub-sitemap lỗi hết retry phải được báo lại cho caller để hiện lỗi trên UI
    assert failed_locs == ["https://vtv.vn/sitemaps/sitemaps-2026-6-21-25.xml"]


def test_flat_urlset_returns_all_urls_without_lastmod_filtering():
    # Một số nguồn (VD bocongan.gov.vn) sitemap KHÔNG có index, liệt kê <url> trực tiếp,
    # và ghi <lastmod> giống nhau cho MỌI url (timestamp lúc sitemap được build lại, không
    # phải ngày đăng bài thật, đã verify thật) — không lọc ở đây, để report_job.py lọc lại
    # bằng ngày đăng thật sau khi fetch từng bài (xem _crawl_sources).
    flat_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://bocongan.gov.vn/bai-viet-a</loc>
        <lastmod>2025-08-20T08:02:22+00:00</lastmod>
    </url>
    <url>
        <loc>https://bocongan.gov.vn/bai-viet-b</loc>
        <lastmod>2025-08-20T08:02:22+00:00</lastmod>
    </url>
</urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=flat_sitemap)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed_locs = get_article_urls(
        FakeSource(),
        date_from=date(2026, 1, 1),
        date_to=date(2026, 5, 30),
        client=client,
        delay_seconds=0,
    )

    urls = [item["url"] for item in result]
    assert urls == ["https://bocongan.gov.vn/bai-viet-a", "https://bocongan.gov.vn/bai-viet-b"]
    assert failed_locs == []


def test_recognizes_year_month_only_sub_sitemap_pattern():
    # VOV dùng pattern path-based (/YYYY/M/): year+month, không có khoảng ngày trong tên sub-sitemap.
    # Sub-sitemap tháng 4 không giao với yêu cầu tháng 6 → không được fetch.
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap>
        <loc>https://vov.vn/sitemaps/2026/4/article.xml</loc>
    </sitemap>
    <sitemap>
        <loc>https://vov.vn/sitemaps/2026/6/article.xml</loc>
    </sitemap>
</sitemapindex>"""
    sub_sitemap_june = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://vov.vn/bai-viet-thang-6</loc>
        <lastmod>2026-06-15T10:00:00+07:00</lastmod>
    </url>
</urlset>"""

    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "2026/6" in str(request.url):
            return httpx.Response(200, text=sub_sitemap_june)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed_locs = get_article_urls(
        VOVSource(),
        date_from=date(2026, 6, 10),
        date_to=date(2026, 6, 20),
        client=client,
        delay_seconds=0,
    )

    urls = [item["url"] for item in result]
    assert urls == ["https://vov.vn/bai-viet-thang-6"]
    assert "https://vov.vn/sitemaps/2026/4/article.xml" not in requested
    assert failed_locs == []


def test_fetches_sub_sitemap_with_unrecognized_name_pattern_instead_of_skipping():
    # tingia.gov.vn (và các nguồn tương tự) chia sitemap theo CHỦ ĐỀ, không theo ngày —
    # không nhận diện được pattern ngày trong tên thì phải fetch để lọc theo <lastmod> thật
    # bên trong, KHÔNG được bỏ qua (an toàn hơn).
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap>
        <loc>https://tingia.gov.vn/sitemap/tai-chinh-ngan-hang.xml</loc>
    </sitemap>
</sitemapindex>"""
    topic_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://tingia.gov.vn/bai-trong-khoang</loc>
        <lastmod>2026-01-26T00:00:00+07:00</lastmod>
    </url>
</urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "tai-chinh-ngan-hang" in str(request.url):
            return httpx.Response(200, text=topic_sitemap)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed_locs = get_article_urls(
        FakeSource(),
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
        client=client,
        delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://tingia.gov.vn/bai-trong-khoang"]
    assert failed_locs == []


def test_vtv_domain_pre_filters_by_date_range():
    # domain="vtv.vn" → regex day_start/day_end → chỉ fetch sub-sitemap giao với yêu cầu
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://vtv.vn/sitemaps/sitemaps-2026-6-01-10.xml</loc></sitemap>
    <sitemap><loc>https://vtv.vn/sitemaps/sitemaps-2026-6-21-25.xml</loc></sitemap>
</sitemapindex>"""
    sub_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://vtv.vn/bai-viet-ngay-22.htm</loc>
        <lastmod>2026-06-22T10:00:00+07:00</lastmod>
    </url>
</urlset>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "6-21-25" in str(request.url):
            return httpx.Response(200, text=sub_sitemap)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        VTVSource(), date_from=date(2026, 6, 20), date_to=date(2026, 6, 24),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://vtv.vn/bai-viet-ngay-22.htm"]
    assert "https://vtv.vn/sitemaps/sitemaps-2026-6-01-10.xml" not in requested
    assert failed_locs == []


def test_vov_domain_pre_filters_by_year_month():
    # domain="vov.vn" → regex year/month path-based → chỉ fetch sub-sitemap của tháng giao yêu cầu
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://vov.vn/sitemaps/2026/4/article.xml</loc></sitemap>
    <sitemap><loc>https://vov.vn/sitemaps/2026/6/article.xml</loc></sitemap>
</sitemapindex>"""
    sub_sitemap_june = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://vov.vn/bai-viet-thang-6-moi</loc>
        <lastmod>2026-06-15T10:00:00+07:00</lastmod>
    </url>
</urlset>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "2026/6" in str(request.url):
            return httpx.Response(200, text=sub_sitemap_june)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        VOVSource(), date_from=date(2026, 6, 10), date_to=date(2026, 6, 20),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://vov.vn/bai-viet-thang-6-moi"]
    assert "https://vov.vn/sitemaps/2026/4/article.xml" not in requested
    assert failed_locs == []


def test_unknown_domain_fetches_all_sub_sitemaps_as_safe_fallback():
    # domain không có trong _SITEMAP_DATE_PATTERNS → pattern=None → không pre-filter
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://vtv.vn/sitemaps/sitemaps-2026-6-01-10.xml</loc></sitemap>
    <sitemap><loc>https://vtv.vn/sitemaps/sitemaps-2026-6-21-25.xml</loc></sitemap>
</sitemapindex>"""
    empty_sub = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        return httpx.Response(200, text=empty_sub)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        FakeSource(),  # domain="unknown.example.com" → không có trong dict → fetch tất cả
        date_from=date(2026, 6, 20), date_to=date(2026, 6, 24),
        client=client, delay_seconds=0,
    )

    assert "https://vtv.vn/sitemaps/sitemaps-2026-6-01-10.xml" in requested
    assert "https://vtv.vn/sitemaps/sitemaps-2026-6-21-25.xml" in requested
    assert result == []
    assert failed_locs == []
