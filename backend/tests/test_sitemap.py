from datetime import date
from unittest.mock import patch

import httpx

from backend.crawler.sitemap import get_article_urls


class FakeSource:
    """Domain không có trong _SITEMAP_DATE_PATTERNS → pattern=None → fetch-all (safe fallback)."""
    sitemap_url = "https://vtv.vn/sitemap.xml"
    domain = "unknown.example.com"
    parsing_rules = {}


class VTVSource:
    """VTV: regex khoảng ngày trong tháng (day_start + day_end)."""
    sitemap_url = "https://vtv.vn/sitemap.xml"
    domain = "vtv.vn"
    parsing_rules = {}


class VOVSource:
    """VOV: regex năm-tháng, path-based (/YYYY/M/)."""
    sitemap_url = "https://vov.vn/sitemap.xml"
    domain = "vov.vn"
    parsing_rules = {}


class VietnamPlusSource:
    """VietnamPlus: regex năm-tháng, filename-based (news-YYYY-M.xml)."""
    sitemap_url = "https://www.vietnamplus.vn/sitemap.xml"
    domain = "vietnamplus.vn"
    parsing_rules = {}


class CANDSource:
    """CAND: regex năm-tháng, filename-based (news-YYYY-M.xml) — giống VietnamPlus."""
    sitemap_url = "https://cand.vn/sitemap.xml"
    domain = "cand.vn"
    parsing_rules = {}


class VietnamVNSource:
    """vietnam.vn: sub-sitemap chia đúng 1 ngày/file (sitemap-post/YYYY-MM-DD.xml) — convention mới, khác VTV (khoảng ngày) và VOV/VN+/CAND (cả tháng)."""
    sitemap_url = "https://www.vietnam.vn/sitemap.xml"
    domain = "vietnam.vn"
    parsing_rules = {}


class TinGiaSource:
    """sitemap_url=None cố ý — nếu code lỡ đọc source.sitemap_url sẽ crash ngay, phát hiện sớm bug routing."""
    sitemap_url = None
    domain = "tingia.gov.vn"
    parsing_rules = {
        "sitemap_pages": [
            "https://tingia.gov.vn/sitemap/tin-vua-check.xml",
            "https://tingia.gov.vn/sitemap/multimedia.xml",
        ]
    }


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


def test_vietnamplus_domain_pre_filters_by_news_filename_pattern():
    # domain="vietnamplus.vn" → regex news-YYYY-M.xml (year+month) → chỉ fetch sub-sitemap
    # của tháng giao với yêu cầu; sub-sitemap tháng 4 không được fetch khi yêu cầu tháng 6.
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://www.vietnamplus.vn/sitemaps/news-2026-4.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnamplus.vn/sitemaps/news-2026-6.xml</loc></sitemap>
</sitemapindex>"""
    sub_sitemap_june = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://www.vietnamplus.vn/bai-viet-thang-6</loc>
        <lastmod>2026-06-15T10:00:00+07:00</lastmod>
    </url>
</urlset>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "news-2026-6" in str(request.url):
            return httpx.Response(200, text=sub_sitemap_june)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        VietnamPlusSource(), date_from=date(2026, 6, 10), date_to=date(2026, 6, 20),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://www.vietnamplus.vn/bai-viet-thang-6"]
    assert "https://www.vietnamplus.vn/sitemaps/news-2026-4.xml" not in requested
    assert failed_locs == []


def test_vietnamplus_skips_non_news_sub_sitemaps_when_domain_has_pattern():
    # Reproduce bug thật (2026-07-01): sitemapindex VietnamPlus chứa categories.xml, topics.xml,
    # google-news.xml cùng lastmod hôm nay — các URL này không khớp pattern news-YYYY-M.xml
    # của domain, phải bị bỏ qua hoàn toàn, KHÔNG được fetch và KHÔNG được trả về URL trang
    # danh mục như URL bài viết.
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://www.vietnamplus.vn/sitemaps/categories.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnamplus.vn/sitemaps/topics.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnamplus.vn/sitemaps/news-2026-7.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnamplus.vn/sitemaps/google-news.xml</loc></sitemap>
</sitemapindex>"""
    news_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://www.vietnamplus.vn/bai-viet-thang-7</loc>
        <lastmod>2026-07-01T10:00:00+07:00</lastmod>
    </url>
</urlset>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "news-2026-7" in str(request.url):
            return httpx.Response(200, text=news_sitemap)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        VietnamPlusSource(), date_from=date(2026, 7, 1), date_to=date(2026, 7, 1),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://www.vietnamplus.vn/bai-viet-thang-7"]
    assert "https://www.vietnamplus.vn/sitemaps/categories.xml" not in requested
    assert "https://www.vietnamplus.vn/sitemaps/topics.xml" not in requested
    assert "https://www.vietnamplus.vn/sitemaps/google-news.xml" not in requested
    assert failed_locs == []


def test_cand_domain_pre_filters_by_news_filename_pattern():
    # domain="cand.vn" → cùng pattern news-YYYY-M.xml như VietnamPlus — mỗi domain có entry
    # riêng trong dict dù pattern string giống nhau, để sau này sửa độc lập.
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://cand.vn/sitemaps/news-2026-4.xml</loc></sitemap>
    <sitemap><loc>https://cand.vn/sitemaps/news-2026-6.xml</loc></sitemap>
</sitemapindex>"""
    sub_sitemap_june = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://cand.vn/bai-viet-thang-6</loc>
        <lastmod>2026-06-15T10:00:00+07:00</lastmod>
    </url>
</urlset>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "news-2026-6" in str(request.url):
            return httpx.Response(200, text=sub_sitemap_june)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        CANDSource(), date_from=date(2026, 6, 10), date_to=date(2026, 6, 20),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://cand.vn/bai-viet-thang-6"]
    assert "https://cand.vn/sitemaps/news-2026-4.xml" not in requested
    assert failed_locs == []


def test_sitemap_pages_fetches_only_declared_urls_without_touching_index():
    # tingia.gov.vn: parsing_rules.sitemap_pages khai sẵn URL sub-sitemap cụ thể (curated thủ
    # công, không phải index tự động) — sitemap_url=None cố ý để phát hiện sớm nếu code lỡ
    # đọc nhầm sang nhánh index.
    sub_a = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://tingia.gov.vn/bai-a</loc><lastmod>2026-06-15T00:00:00+07:00</lastmod></url>
</urlset>"""
    sub_b = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://tingia.gov.vn/bai-b</loc><lastmod>2026-06-16T00:00:00+07:00</lastmod></url>
</urlset>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if "tin-vua-check" in str(request.url):
            return httpx.Response(200, text=sub_a)
        if "multimedia" in str(request.url):
            return httpx.Response(200, text=sub_b)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        TinGiaSource(), date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
        client=client, delay_seconds=0,
    )

    assert sorted(item["url"] for item in result) == ["https://tingia.gov.vn/bai-a", "https://tingia.gov.vn/bai-b"]
    assert not any(url.endswith("/sitemap.xml") for url in requested)
    assert failed_locs == []


def test_sitemap_pages_dedups_url_appearing_in_multiple_declared_sub_sitemaps():
    # Sub-sitemap của tingia.gov.vn chia theo CHỦ ĐỀ/tag — 1 bài có thể được gắn nhiều tag,
    # xuất hiện ở nhiều sub-sitemap. Không dedup sẽ khiến report_job.py fetch trùng 1 bài.
    same_article = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://tingia.gov.vn/bai-trung</loc><lastmod>2026-06-15T00:00:00+07:00</lastmod></url>
</urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=same_article)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        TinGiaSource(), date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://tingia.gov.vn/bai-trung"]
    assert failed_locs == []


def test_sitemap_pages_still_filters_by_lastmod_date_range():
    mixed = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://tingia.gov.vn/bai-trong-khoang</loc><lastmod>2026-06-15T00:00:00+07:00</lastmod></url>
    <url><loc>https://tingia.gov.vn/bai-ngoai-khoang</loc><lastmod>2025-01-01T00:00:00+07:00</lastmod></url>
</urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=mixed)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        TinGiaSource(), date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://tingia.gov.vn/bai-trong-khoang"]


def test_sitemap_pages_records_failed_loc_for_one_failing_sub_sitemap_others_still_processed():
    ok_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://tingia.gov.vn/bai-ok</loc><lastmod>2026-06-15T00:00:00+07:00</lastmod></url>
</urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if "tin-vua-check" in str(request.url):
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, text=ok_sitemap)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        TinGiaSource(), date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
        client=client, delay_seconds=0, max_retries=1,
    )

    assert [item["url"] for item in result] == ["https://tingia.gov.vn/bai-ok"]
    assert failed_locs == ["https://tingia.gov.vn/sitemap/tin-vua-check.xml"]


def test_vietnamvn_domain_pre_filters_by_exact_day():
    # domain="vietnam.vn" → regex day đơn lẻ → chỉ fetch sub-sitemap của đúng ngày giao yêu cầu
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-post/2026-07-05.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-post/2026-07-08.xml</loc></sitemap>
</sitemapindex>"""
    sub_sitemap_08 = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://www.vietnam.vn/bai-viet-ngay-08</loc>
        <lastmod>2026-07-08T04:04:10.339Z</lastmod>
    </url>
</urlset>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "2026-07-08" in str(request.url):
            return httpx.Response(200, text=sub_sitemap_08)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        VietnamVNSource(), date_from=date(2026, 7, 8), date_to=date(2026, 7, 8),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://www.vietnam.vn/bai-viet-ngay-08"]
    assert "https://www.vietnam.vn/sitemap/sitemap-post/2026-07-05.xml" not in requested
    assert failed_locs == []


def test_vietnamvn_skips_non_post_sub_sitemaps_when_domain_has_pattern():
    # sitemap-page/author/organization/category/tag/tag-N/news-sitemap không khớp
    # pattern "sitemap-post/YYYY-MM-DD.xml" → bị bỏ qua hoàn toàn, KHÔNG fetch (verify thật
    # 2026-07-08: đây là trang tĩnh/tác giả/tổ chức/danh mục/tag, không phải bài viết).
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://www.vietnam.vn/news-sitemap.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-page.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-author.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-organization.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-category.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-tag.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-tag/220001.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-post/2026-07-08.xml</loc></sitemap>
</sitemapindex>"""
    sub_sitemap_08 = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://www.vietnam.vn/bai-that</loc><lastmod>2026-07-08T04:04:10.339Z</lastmod></url>
</urlset>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "sitemap-post/2026-07-08" in str(request.url):
            return httpx.Response(200, text=sub_sitemap_08)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        VietnamVNSource(), date_from=date(2026, 7, 1), date_to=date(2026, 7, 8),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://www.vietnam.vn/bai-that"]
    assert len(requested) == 2  # /sitemap.xml (index) + đúng 1 sub-sitemap post khớp pattern


def test_vietnamvn_fetches_multiple_days_when_range_spans_several_files():
    # Có thêm 1 sub-sitemap NGOÀI khoảng ngày (2026-07-01) — nếu pattern "day" chưa hoạt động,
    # domain rơi vào pattern=None (fetch-all) và sẽ fetch luôn sub-sitemap này (test FAIL đúng
    # cách vì request không mong đợi), phân biệt rõ với hành vi fetch-all tình cờ đúng kết quả.
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-post/2026-07-01.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-post/2026-07-07.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-post/2026-07-08.xml</loc></sitemap>
</sitemapindex>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "2026-07-07" in str(request.url):
            return httpx.Response(
                200,
                text='<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                '<url><loc>https://www.vietnam.vn/bai-07</loc><lastmod>2026-07-07T10:00:00Z</lastmod></url>'
                "</urlset>",
            )
        if "2026-07-08" in str(request.url):
            return httpx.Response(
                200,
                text='<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                '<url><loc>https://www.vietnam.vn/bai-08</loc><lastmod>2026-07-08T10:00:00Z</lastmod></url>'
                "</urlset>",
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        VietnamVNSource(), date_from=date(2026, 7, 7), date_to=date(2026, 7, 8),
        client=client, delay_seconds=0,
    )

    assert sorted(item["url"] for item in result) == ["https://www.vietnam.vn/bai-07", "https://www.vietnam.vn/bai-08"]
    assert "https://www.vietnam.vn/sitemap/sitemap-post/2026-07-01.xml" not in requested


def test_returns_index_url_as_failed_loc_when_sitemap_index_returns_error_status():
    # Bug thật phát hiện 2026-07-08: vietnam.vn bị chặn tạm thời (403), trước đây code không
    # check status trước khi parse → trang lỗi bị hiểu nhầm thành "sitemap phẳng không bài
    # nào" → job báo completed với 0 bài, không có error_log nào, không ai biết là do bị chặn.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="<html><body>Forbidden</body></html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        VTVSource(), date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
        client=client, delay_seconds=0,
    )

    assert result == []
    assert failed_locs == ["https://vtv.vn/sitemap.xml"]


def test_creates_default_client_with_follow_redirects_enabled():
    # Cùng bug với article.py/listing.py (2026-07-09): httpx mặc định không tự theo redirect —
    # nếu sitemap.xml bị 301 sang URL khác, response rỗng sẽ bị hiểu nhầm thành "sitemap phẳng
    # không có bài".
    with patch("backend.crawler.sitemap.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.get.return_value = httpx.Response(200, text="<urlset></urlset>")

        get_article_urls(VTVSource(), date_from=date(2026, 6, 1), date_to=date(2026, 6, 30), delay_seconds=0)

    _, kwargs = mock_client_cls.call_args
    assert kwargs.get("follow_redirects") is True


def test_returns_index_url_as_failed_loc_when_sitemap_index_request_raises():
    # Lỗi network (connection error/timeout) khi fetch sitemap index — trước đây exception
    # bay thẳng lên report_job.py (bị nuốt bởi except Exception chung, không insert error row
    # nào cho URL index) — nay retry rồi trả về failed_loc như sub-sitemap lỗi, nhất quán hơn.
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        VTVSource(), date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
        client=client, delay_seconds=0, max_retries=1,
    )

    assert result == []
    assert failed_locs == ["https://vtv.vn/sitemap.xml"]
