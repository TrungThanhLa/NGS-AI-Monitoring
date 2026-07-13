import os
import time
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from backend.crawler.article import _extract, compute_url_hash


def _render_html(url: str) -> str:
    timeout_ms = int(os.environ.get("CRAWLER_TIMEOUT_SECONDS", "30")) * 1000
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(url, timeout=timeout_ms)
            return page.content()
        finally:
            browser.close()


def fetch_article_playwright(
    url: str,
    parsing_rules: dict,
    renderer=None,
    max_retries: int | None = None,
    retry_backoff_seconds: float | None = None,
) -> dict | None:
    renderer = renderer or _render_html
    if max_retries is None:
        max_retries = int(os.environ.get("CRAWLER_MAX_RETRIES", "3"))

    start = time.perf_counter()
    html = None
    for attempt in range(max_retries):
        try:
            html = renderer(url)
            break
        except PlaywrightError:
            if attempt < max_retries - 1:
                backoff = retry_backoff_seconds if retry_backoff_seconds is not None else 2**attempt
                time.sleep(backoff)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    title = _extract(soup, parsing_rules["title"])
    content_raw = _extract(soup, parsing_rules["content"])
    if not title or not content_raw:
        return None

    author = _extract(soup, parsing_rules.get("author", ""))
    date_raw = _extract(soup, parsing_rules.get("date", ""))
    published_at = datetime.fromisoformat(date_raw) if date_raw else None

    return {
        "url": url,
        "url_hash": compute_url_hash(url),
        "title": title,
        "content_raw": content_raw,
        "author": author,
        "published_at": published_at,
        "crawl_duration_seconds": time.perf_counter() - start,
    }
