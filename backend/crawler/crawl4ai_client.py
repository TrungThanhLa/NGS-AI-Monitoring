import asyncio
import re
import time
from datetime import datetime

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, DefaultMarkdownGenerator, HTTPCrawlerConfig
from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter

from backend.crawler.article import compute_url_hash, fetch_article
from backend.crawler.playwright_client import fetch_article_playwright

# "Tin liên quan"/"Bình luận" là convention phổ biến của báo điện tử Việt Nam đánh dấu
# ranh giới giữa nội dung bài viết thật và phần rác (bài gợi ý, box bình luận) — đã verify
# thật trên VTV và VOV (2 site khác nhau, cùng convention)
_BOUNDARY_MARKER_RE = re.compile(r"#+\s*(Tin liên quan|Bình luận)", re.IGNORECASE)


def _trim_trailing_noise(content: str) -> str:
    match = _BOUNDARY_MARKER_RE.search(content)
    return content[: match.start()].strip() if match else content


async def _run_crawl4ai(url: str):
    strategy = AsyncHTTPCrawlerStrategy(browser_config=HTTPCrawlerConfig())
    md_generator = DefaultMarkdownGenerator(content_filter=PruningContentFilter())
    async with AsyncWebCrawler(crawler_strategy=strategy) as crawler:
        return await crawler.arun(url=url, config=CrawlerRunConfig(markdown_generator=md_generator))


def fetch_article_crawl4ai(url: str, runner=None) -> dict | None:
    runner = runner or _run_crawl4ai
    start = time.perf_counter()
    result = asyncio.run(runner(url))

    if not result.success:
        return None

    metadata = result.metadata or {}
    title = metadata.get("title")
    content_raw = result.markdown.fit_markdown if result.markdown else None
    if content_raw:
        content_raw = _trim_trailing_noise(content_raw)
    if not title or not content_raw:
        return None

    author = metadata.get("article:author") or metadata.get("author")
    date_raw = metadata.get("article:published_time")
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


def fetch_article_dispatch(url: str, parsing_rules: dict) -> dict | None:
    engine = parsing_rules.get("engine")
    if engine == "crawl4ai":
        return fetch_article_crawl4ai(url)
    if engine == "playwright":
        return fetch_article_playwright(url, parsing_rules)
    return fetch_article(url, parsing_rules)
