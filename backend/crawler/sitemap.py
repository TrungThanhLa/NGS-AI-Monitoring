import calendar
import logging
import os
import re
import time
from datetime import date, datetime
from typing import Callable

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
    # VD: https://www.vietnamplus.vn/sitemaps/news-2026-7.xml (verified 2026-07-01)
    "vietnamplus.vn": re.compile(
        r"news-(?P<year>\d{4})-(?P<month>\d{1,2})\.xml$"
    ),
    # VD: https://cand.vn/sitemaps/news-2026-7.xml (verified 2026-07-01)
    "cand.vn": re.compile(
        r"news-(?P<year>\d{4})-(?P<month>\d{1,2})\.xml$"
    ),
    # VD: https://www.vietnam.vn/sitemap/sitemap-post/2026-07-08.xml (verified 2026-07-08) —
    # chia đúng 1 ngày/file, khác VTV (khoảng ngày)/VOV,VN+,CAND (cả tháng).
    "vietnam.vn": re.compile(
        r"sitemap-post/(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})\.xml$"
    ),
}

# Domain nào build sub-sitemap theo tháng nhưng CHỈ thêm entry vào index sitemap.xml SAU KHI
# tháng đã kết thúc (verify thật 2026-07-10: vov.vn/sitemap.xml giữa tháng 7 vẫn chỉ liệt kê
# tới tháng 6) → không thể dùng index để tìm sub-sitemap của tháng đang chạy (bao gồm cả
# tháng hiện tại). URL sub-sitemap của các domain này có format cố định, dự đoán được từ
# (year, month) — bỏ hẳn việc fetch/parse index, tự sinh URL trực tiếp cho MỌI tháng nằm
# trong date_from..date_to (không riêng tháng hiện tại, để nhất quán và không phụ thuộc
# index có cập nhật đúng hay không).
_SITEMAP_URL_TEMPLATES: dict[str, Callable[[int, int], str]] = {
    # VD: https://vov.vn/sitemaps/2026/7/article.xml (verify tay bằng curl 2026-07-10 —
    # trả HTTP 200 với bài viết thật dù chưa xuất hiện trong index)
    "vov.vn": lambda year, month: f"https://vov.vn/sitemaps/{year}/{month}/article.xml",
}

# Domain nào build sub-sitemap định kỳ (VD vtv.vn — 5 ngày/lần) nên vài ngày gần nhất luôn
# "rơi" ra ngoài mọi sub-sitemap đã đủ điều kiện đóng khối, nhưng có sẵn 1 sub-sitemap
# "catch-all" chứa đúng phần bài mới nhất này (verify tay 2026-07-10: latest-news-sitemap.xml
# có mặt trong chính index, trả HTTP 200 với bài đăng trong ngày) — luôn fetch kèm, không qua
# _SITEMAP_DATE_PATTERNS (URL không mang ngày tháng trong path nên bị regex loại nếu không
# xử lý riêng).
_SITEMAP_ALWAYS_INCLUDE: dict[str, list[str]] = {
    "vtv.vn": ["https://vtv.vn/latest-news-sitemap.xml"],
}


def _months_in_range(date_from: date, date_to: date) -> list[tuple[int, int]]:
    months = []
    year, month = date_from.year, date_from.month
    while (year, month) <= (date_to.year, date_to.month):
        months.append((year, month))
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return months


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

    if groups.get("day") is not None:
        exact_day = date(year, month, int(groups["day"]))
        return exact_day, exact_day

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
    logger.warning("Hết %d lượt thử, bỏ qua URL: %s", max_retries, url)
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


def _fetch_declared_sitemap_pages(
    sitemap_pages: list[str],
    date_from: date,
    date_to: date,
    client: httpx.Client,
    delay_seconds: float,
    max_retries: int,
) -> tuple[list[dict], list[str]]:
    # Sub-sitemap chia theo CHỦ ĐỀ (VD tingia.gov.vn) — 1 bài có thể nằm ở nhiều sub-sitemap,
    # dedup theo URL để không trả về trùng (tránh caller — continuous_crawl.py, trước đây là
    # report_job.py đã bị xóa ở Phase 7 — fetch cùng 1 bài 2 lần).
    seen: set[str] = set()
    results: list[dict] = []
    failed: list[str] = []
    for loc in sitemap_pages:
        time.sleep(delay_seconds)
        resp = _fetch_with_retry(client, loc, max_retries)
        if resp is None:
            failed.append(loc)
            continue
        soup = BeautifulSoup(resp.text, "xml")
        for item in _extract_urls_in_range(soup, date_from, date_to):
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            results.append(item)
    return results, failed


def get_article_urls(
    source,
    date_from: date,
    date_to: date,
    client: httpx.Client | None = None,
    delay_seconds: float | None = None,
    max_retries: int | None = None,
    today: date | None = None,
) -> tuple[list[dict], list[str]]:
    owns_client = client is None
    client = client or httpx.Client(
        timeout=int(os.environ.get("CRAWLER_TIMEOUT_SECONDS", "30")), follow_redirects=True
    )
    if delay_seconds is None:
        delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))
    if max_retries is None:
        max_retries = int(os.environ.get("CRAWLER_MAX_RETRIES", "3"))
    if today is None:
        today = date.today()

    sitemap_pages = source.parsing_rules.get("sitemap_pages")
    if sitemap_pages:
        # Danh sách sub-sitemap curated thủ công (VD tingia.gov.vn — top-level sitemap.xml là
        # urlset phẳng trộn lẫn trang tĩnh + sub-sitemap chia theo tag, <lastmod> đóng băng ở
        # top-level, không dùng được cơ chế index/_SITEMAP_DATE_PATTERNS hiện có). Không đụng
        # source.sitemap_url — nguồn dùng nhánh này luôn có sitemap_url=NULL.
        try:
            return _fetch_declared_sitemap_pages(
                sitemap_pages, date_from, date_to, client, delay_seconds, max_retries
            )
        finally:
            if owns_client:
                client.close()

    url_template = _SITEMAP_URL_TEMPLATES.get(source.domain)
    if url_template:
        # Bỏ hẳn index (source.sitemap_url không được đụng tới) — tự sinh URL sub-sitemap cho
        # từng tháng nằm trong khoảng ngày yêu cầu, dùng lại đúng helper fetch+dedup+lọc ngày
        # đã có cho sitemap_pages (bản chất giống nhau: 1 danh sách URL sub-sitemap đã biết
        # trước, không cần khám phá qua index).
        generated_locs = [url_template(year, month) for year, month in _months_in_range(date_from, date_to)]
        try:
            return _fetch_declared_sitemap_pages(
                generated_locs, date_from, date_to, client, delay_seconds, max_retries
            )
        finally:
            if owns_client:
                client.close()

    try:
        index_resp = _fetch_with_retry(client, source.sitemap_url, max_retries)
        if index_resp is None or index_resp.status_code >= 400:
            # Site chặn tạm thời (403/WAF) hoặc lỗi mạng hết retry — KHÔNG được âm thầm coi
            # như "sitemap phẳng không có bài" (bug thật đã gặp với vietnam.vn 2026-07-08: job
            # báo completed với 0 bài, không ai biết là do bị chặn). Trả về như 1 URL lỗi để
            # caller biết mà xử lý (report_job.py — đã bị xóa ở Phase 7 — từng insert
            # Article(status="error") cho URL này để hiện rõ trên bảng crawl trực tiếp; caller
            # hiện tại continuous_crawl.py chưa làm lại việc này, chỉ nhận về danh sách lỗi).
            if index_resp is not None:
                logger.warning(
                    "Fetch sitemap index thất bại (HTTP %d): %s",
                    index_resp.status_code, source.sitemap_url,
                )
            return [], [source.sitemap_url]
        index_soup = BeautifulSoup(index_resp.text, "xml")

        sitemap_tags = index_soup.find_all("sitemap")
        if not sitemap_tags:
            # Sitemap phẳng (urlset liệt kê <url> trực tiếp, không qua sub-sitemap) — VD
            # bocongan.gov.vn. KHÔNG lọc theo <lastmod> ở đây vì một số nguồn ghi <lastmod>
            # giống nhau cho mọi URL (timestamp build lại sitemap, không phải ngày đăng thật,
            # đã verify thật) — lọc theo ngày đăng thật được làm SAU khi fetch xong từng bài
            # (report_job.py làm việc này ở luồng Job on-demand cũ, đã bị xóa ở Phase 7; ở
            # luồng campaign hiện tại, lọc theo published_at nằm ở
            # campaign_tasks.resolve_campaign_article_ids, chạy lúc build report — không lọc
            # ngay lúc crawl vì continuous crawl không còn khái niệm date_from/date_to cứng).
            return _extract_all_urls(index_soup), []

        pattern = _SITEMAP_DATE_PATTERNS.get(source.domain)
        sub_sitemap_locs = []
        for sitemap_tag in sitemap_tags:
            loc = sitemap_tag.find("loc").get_text(strip=True)
            if pattern is None:
                # Domain chưa khai pattern → không pre-filter, fetch tất cả sub-sitemap,
                # lọc theo <lastmod> của từng <url> bên trong.
                sub_sitemap_locs.append(loc)
            else:
                date_range = _sub_sitemap_date_range(loc, pattern)
                if date_range is None:
                    # URL không khớp pattern của domain → không phải sitemap bài viết, bỏ qua.
                    continue
                if _ranges_overlap(date_range[0], date_range[1], date_from, date_to):
                    sub_sitemap_locs.append(loc)

        if pattern is not None and not sub_sitemap_locs:
            logger.warning(
                "Không có sub-sitemap nào khớp pattern của %s trong khoảng %s–%s"
                " — kiểm tra lại _SITEMAP_DATE_PATTERNS hoặc cấu trúc sitemap đã đổi",
                source.domain, date_from, date_to,
            )

        if date_to >= today:
            # Sub-sitemap catch-all chỉ chứa bài MỚI NHẤT (gần hôm nay) — job có date_to nằm
            # hoàn toàn trong quá khứ chắc chắn không nhận thêm được bài nào từ URL này, fetch
            # vẫn tốn 1 request vô ích. Chỉ fetch khi phạm vi ngày còn chạm tới hôm nay trở đi.
            for always_loc in _SITEMAP_ALWAYS_INCLUDE.get(source.domain, []):
                if always_loc not in sub_sitemap_locs:
                    sub_sitemap_locs.append(always_loc)

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
