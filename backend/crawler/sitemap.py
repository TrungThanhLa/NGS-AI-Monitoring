import calendar
import logging
import os
import re
import time
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# VTV: sitemaps-YYYY-MM-DD_start-DD_end.xml (khoảng ngày trong 1 tháng)
_DATE_RANGE_RE = re.compile(r"sitemaps-(\d+)-(\d+)-(\d+)-(\d+)\.xml$")
# VOV/VietnamPlus/CAND: chỉ năm-tháng, không có khoảng ngày trong tên
# (VD .../2026/5/article.xml hoặc news-2026-6.xml)
_YEAR_MONTH_RE = re.compile(r"(?:^|[/-])(\d{4})[/-](\d{1,2})(?:[/.]|$)")


def _parse_lastmod(value: str) -> date:
    return datetime.fromisoformat(value).date()


def _sub_sitemap_date_range(loc: str) -> tuple[date, date] | None:
    match = _DATE_RANGE_RE.search(loc)
    if match:
        year, month, day_start, day_end = (int(g) for g in match.groups())
        return date(year, month, day_start), date(year, month, day_end)

    match = _YEAR_MONTH_RE.search(loc)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12:
            day_end = calendar.monthrange(year, month)[1]
            return date(year, month, 1), date(year, month, day_end)

    return None


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

        sub_sitemap_locs = []
        for sitemap_tag in sitemap_tags:
            loc = sitemap_tag.find("loc").get_text(strip=True)
            date_range = _sub_sitemap_date_range(loc)
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
