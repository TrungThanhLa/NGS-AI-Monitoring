import logging
import os
import re
import time
from datetime import date

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


def get_listing_urls(
    source,
    date_from: date,
    date_to: date,
    client: httpx.Client | None = None,
    max_retries: int | None = None,
) -> tuple[list[dict], list[str]]:
    owns_client = client is None
    client = client or httpx.Client(timeout=int(os.environ.get("CRAWLER_TIMEOUT_SECONDS", "30")))
    if max_retries is None:
        max_retries = int(os.environ.get("CRAWLER_MAX_RETRIES", "3"))

    try:
        resp = _fetch_with_retry(client, source.listing_url, max_retries)
        if resp is None:
            return [], [source.listing_url]

        soup = BeautifulSoup(resp.text, "html.parser")
        rules = source.parsing_rules
        items = soup.select(rules["listing_item"])
        if not items:
            # Fetch trang OK nhưng selector không khớp item nào — có thể HTML đã đổi cấu trúc,
            # không phải do thực sự không có bài nào trong khoảng ngày. Log để phát hiện sớm,
            # vẫn trả về rỗng (không đổi contract trả về của hàm).
            logger.warning(
                "Fetch trang danh sách OK nhưng selector '%s' không khớp item nào: %s",
                rules["listing_item"],
                source.listing_url,
            )
        results = []
        for item in items:
            link_el = item.select_one(rules["listing_link"])
            date_el = item.select_one(rules["listing_date"])
            if link_el is None or date_el is None:
                continue
            # Giả định href là URL tuyệt đối — đã verify đúng trên tingia.gov.vn qua curl;
            # nguồn listing-page khác sau này nếu trả href tương đối thì cần xử lý qua urljoin.
            url = link_el.get("href")
            published = _parse_listing_date(date_el.get_text(strip=True))
            if url and published and date_from <= published <= date_to:
                results.append({"url": url, "lastmod": published})
        return results, []
    finally:
        if owns_client:
            client.close()
