import logging
import os
import re
import time
from datetime import date
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Format thật đã verify trên tingia.gov.vn: "26/01/2026 - 17:37"
_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def _fetch_with_retry(client: httpx.Client, url: str, max_retries: int) -> httpx.Response | None:
    for attempt in range(max_retries):
        try:
            return client.get(url)
        except httpx.HTTPError:
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
    logger.warning("Hết %d lượt thử, bỏ qua trang danh sách: %s", max_retries, url)
    return None


def _parse_listing_date(text: str) -> date | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    day, month, year = (int(g) for g in match.groups())
    return date(year, month, day)


def _fetch_one_listing_page(
    client: httpx.Client,
    url: str,
    rules: dict,
    date_from: date,
    date_to: date,
    max_retries: int,
) -> tuple[list[dict], list[str]]:
    resp = _fetch_with_retry(client, url, max_retries)
    if resp is None:
        return [], [url]

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select(rules["listing_item"])
    if not items:
        # Fetch trang OK nhưng selector không khớp item nào — có thể HTML đã đổi cấu trúc,
        # không phải do thực sự không có bài nào trong khoảng ngày. Log để phát hiện sớm,
        # vẫn trả về rỗng (không đổi contract trả về của hàm).
        logger.warning(
            "Fetch trang danh sách OK nhưng selector '%s' không khớp item nào: %s",
            rules["listing_item"],
            url,
        )
    results = []
    for item in items:
        link_el = item.select_one(rules["listing_link"])
        date_el = item.select_one(rules["listing_date"])
        if link_el is None or date_el is None:
            continue
        # urljoin xử lý cả 2 trường hợp: href tuyệt đối (tingia.gov.vn, giữ nguyên) và
        # tương đối (bocongan.gov.vn, ghép với URL trang danh sách đang fetch)
        href = link_el.get("href")
        item_url = urljoin(url, href) if href else None
        published = _parse_listing_date(date_el.get_text(strip=True))
        if item_url and published and date_from <= published <= date_to:
            results.append({"url": item_url, "lastmod": published})
    return results, []


def get_listing_urls(
    source,
    date_from: date,
    date_to: date,
    client: httpx.Client | None = None,
    max_retries: int | None = None,
    delay_seconds: float | None = None,
) -> tuple[list[dict], list[str]]:
    owns_client = client is None
    client = client or httpx.Client(
        timeout=int(os.environ.get("CRAWLER_TIMEOUT_SECONDS", "30")), follow_redirects=True
    )
    if max_retries is None:
        max_retries = int(os.environ.get("CRAWLER_MAX_RETRIES", "3"))

    try:
        rules = source.parsing_rules
        listing_pages = rules.get("listing_pages")

        if not listing_pages:
            # Nguồn dùng 1 trang danh sách duy nhất (VD tingia.gov.vn) — hành vi cũ, không đổi.
            return _fetch_one_listing_page(client, source.listing_url, rules, date_from, date_to, max_retries)

        # Nhiều trang chuyên mục (VD bocongan.gov.vn) — fetch_pages là tập con thực sự crawl,
        # thiếu fetch_pages → mặc định crawl toàn bộ listing_pages đã khai báo.
        if delay_seconds is None:
            delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))
        pages_to_fetch = rules.get("fetch_pages") or listing_pages

        results: list[dict] = []
        failed: list[str] = []
        for page_url in pages_to_fetch:
            time.sleep(delay_seconds)
            page_results, page_failed = _fetch_one_listing_page(
                client, page_url, rules, date_from, date_to, max_retries
            )
            results.extend(page_results)
            failed.extend(page_failed)
        return results, failed
    finally:
        if owns_client:
            client.close()
