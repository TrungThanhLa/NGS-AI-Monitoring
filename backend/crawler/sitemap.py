import logging
import os
import re
import time
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SUB_SITEMAP_NAME_RE = re.compile(r"sitemaps-(\d+)-(\d+)-(\d+)-(\d+)\.xml$")


def _parse_lastmod(value: str) -> date:
    return datetime.fromisoformat(value).date()


def _sub_sitemap_date_range(loc: str) -> tuple[date, date] | None:
    match = SUB_SITEMAP_NAME_RE.search(loc)
    if not match:
        return None
    year, month, day_start, day_end = (int(g) for g in match.groups())
    return date(year, month, day_start), date(year, month, day_end)


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

        sub_sitemap_locs = []
        for sitemap_tag in index_soup.find_all("sitemap"):
            loc = sitemap_tag.find("loc").get_text(strip=True)
            date_range = _sub_sitemap_date_range(loc)
            if date_range and _ranges_overlap(date_range[0], date_range[1], date_from, date_to):
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
            for url_tag in sub_soup.find_all("url"):
                article_url = url_tag.find("loc").get_text(strip=True)
                lastmod_tag = url_tag.find("lastmod")
                lastmod = _parse_lastmod(lastmod_tag.get_text(strip=True)) if lastmod_tag else None
                if lastmod and date_from <= lastmod <= date_to:
                    results.append({"url": article_url, "lastmod": lastmod})
        return results, failed_locs
    finally:
        if owns_client:
            client.close()
