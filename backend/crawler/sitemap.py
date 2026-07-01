import calendar
import logging
import os
import re
import time
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Mỗi domain có regex riêng với named groups — không dùng chung regex dễ false-positive.
# Named groups quy ước:
#   year + month + day_start + day_end → sub-sitemap chia theo khoảng ngày trong tháng
#   year + month (không có day_*) → sub-sitemap chia theo tháng, tự tính ngày cuối
# Domain không có entry → pattern=None → không pre-filter, fetch tất cả (safe fallback).
#
# Khi thêm nguồn mới: verify URL thật từ sitemap bằng curl trước khi điền regex,
# không đoán pattern từ tên miền.
_SITEMAP_DATE_PATTERNS: dict[str, re.Pattern] = {
    # VD: https://vtv.vn/sitemaps/sitemaps-2026-6-21-25.xml
    "vtv.vn": re.compile(
        r"sitemaps-(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day_start>\d{1,2})-(?P<day_end>\d{1,2})\.xml$"
    ),
    # VD: https://vov.vn/sitemaps/2026/6/article.xml
    "vov.vn": re.compile(
        r"/(?P<year>\d{4})/(?P<month>\d{1,2})/"
    ),
    # VD: https://www.vietnamplus.vn/sitemaps/news-2026-7.xml (verified 2026-07-01)
    "vietnamplus.vn": re.compile(
        r"news-(?P<year>\d{4})-(?P<month>\d{1,2})\.xml$"
    ),
    # VD: https://cand.vn/sitemaps/news-2026-7.xml (verified 2026-07-01)
    "cand.vn": re.compile(
        r"news-(?P<year>\d{4})-(?P<month>\d{1,2})\.xml$"
    ),
}


def _parse_lastmod(value: str) -> date:
    return datetime.fromisoformat(value).date()


def _sub_sitemap_date_range(loc: str, pattern: re.Pattern | None) -> tuple[date, date] | None:
    if pattern is None:
        return None

    match = pattern.search(loc)
    if not match:
        logger.warning("sub-sitemap URL không khớp pattern đã khai: %s", loc)
        return None

    groups = match.groupdict()
    year, month = int(groups["year"]), int(groups["month"])

    if not (1 <= month <= 12):
        logger.warning("month không hợp lệ (%d) trong URL: %s", month, loc)
        return None

    if groups.get("day_start") is not None:
        return date(year, month, int(groups["day_start"])), date(year, month, int(groups["day_end"]))

    day_end = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, day_end)


def _ranges_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and b_start <= a_end


def _fetch_with_retry(client: httpx.Client, url: str, max_retries: int) -> httpx.Response | None:
    for attempt in range(max_retries):
        try:
            return client.get(url)
        except httpx.HTTPError:
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
    logger.warning("Hết %d lượt thử, bỏ qua sub-sitemap: %s", max_retries, url)
    return None


def _extract_all_urls(soup: BeautifulSoup) -> list[dict]:
    results = []
    for url_tag in soup.find_all("url"):
        article_url = url_tag.find("loc").get_text(strip=True)
        lastmod_tag = url_tag.find("lastmod")
        lastmod = _parse_lastmod(lastmod_tag.get_text(strip=True)) if lastmod_tag else None
        results.append({"url": article_url, "lastmod": lastmod})
    return results


def _extract_urls_in_range(soup: BeautifulSoup, date_from: date, date_to: date) -> list[dict]:
    return [item for item in _extract_all_urls(soup) if item["lastmod"] and date_from <= item["lastmod"] <= date_to]


def get_article_urls(
    source,
    date_from: date,
    date_to: date,
    client: httpx.Client | None = None,
    delay_seconds: float | None = None,
    max_retries: int | None = None,
) -> tuple[list[dict], list[str]]:
    owns_client = client is None
    client = client or httpx.Client(timeout=int(os.environ.get("CRAWLER_TIMEOUT_SECONDS", "30")))
    if delay_seconds is None:
        delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))
    if max_retries is None:
        max_retries = int(os.environ.get("CRAWLER_MAX_RETRIES", "3"))

    try:
        index_resp = client.get(source.sitemap_url)
        index_soup = BeautifulSoup(index_resp.text, "xml")

        sitemap_tags = index_soup.find_all("sitemap")
        if not sitemap_tags:
            # Sitemap phẳng (urlset liệt kê <url> trực tiếp, không qua sub-sitemap) — VD
            # bocongan.gov.vn. KHÔNG lọc theo <lastmod> ở đây vì một số nguồn ghi <lastmod>
            # giống nhau cho mọi URL (timestamp build lại sitemap, không phải ngày đăng thật,
            # đã verify thật) — lọc theo ngày đăng thật được làm ở report_job.py sau khi fetch
            # xong từng bài.
            return _extract_all_urls(index_soup), []

        pattern = _SITEMAP_DATE_PATTERNS.get(source.domain)
        sub_sitemap_locs = []
        for sitemap_tag in sitemap_tags:
            loc = sitemap_tag.find("loc").get_text(strip=True)
            date_range = _sub_sitemap_date_range(loc, pattern)
            # Không nhận diện được pattern ngày trong tên (VD chia theo chủ đề như
            # tingia.gov.vn) -> không pre-filter, luôn fetch để lọc theo <lastmod> thật bên
            # trong (an toàn hơn bỏ qua nhầm).
            if date_range is None or _ranges_overlap(date_range[0], date_range[1], date_from, date_to):
                sub_sitemap_locs.append(loc)

        results = []
        failed_locs = []
        for loc in sub_sitemap_locs:
            time.sleep(delay_seconds)
            sub_resp = _fetch_with_retry(client, loc, max_retries)
            if sub_resp is None:
                failed_locs.append(loc)
                continue
            sub_soup = BeautifulSoup(sub_resp.text, "xml")
            results.extend(_extract_urls_in_range(sub_soup, date_from, date_to))
        return results, failed_locs
    finally:
        if owns_client:
            client.close()
