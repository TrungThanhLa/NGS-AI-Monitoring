import hashlib
import os
import time
from datetime import datetime

import httpx
from bs4 import BeautifulSoup


def compute_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _extract(soup: BeautifulSoup, selector: str | None) -> str | None:
    if not selector:
        return None
    el = soup.select_one(selector)
    if el is None:
        return None
    if el.name == "meta":
        return el.get("content")
    return el.get_text(strip=True)


def fetch_article(
    url: str,
    parsing_rules: dict,
    client: httpx.Client | None = None,
    max_retries: int | None = None,
    retry_backoff_seconds: float | None = None,
) -> dict | None:
    owns_client = client is None
    client = client or httpx.Client(timeout=int(os.environ.get("CRAWLER_TIMEOUT_SECONDS", "30")))
    if max_retries is None:
        max_retries = int(os.environ.get("CRAWLER_MAX_RETRIES", "3"))

    try:
        response = None
        for attempt in range(max_retries):
            try:
                response = client.get(url)
                break
            except httpx.HTTPError:
                if attempt < max_retries - 1:
                    backoff = retry_backoff_seconds if retry_backoff_seconds is not None else 2**attempt
                    time.sleep(backoff)
        if response is None:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
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
        }
    finally:
        if owns_client:
            client.close()
