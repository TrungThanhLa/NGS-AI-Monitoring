---
description: Chiến lược crawl — Sitemap XML primary, listing page fallback, dedup
alwaysApply: false
---

# Chiến lược crawl

Ưu tiên Sitemap XML vì có sẵn URL + ngày đăng, ít cần config theo từng site. Chỉ fallback sang listing page khi nguồn không có sitemap.

```python
# Priority 1: Sitemap XML
async def crawl_via_sitemap(source, date_from, date_to):
    sitemap = await fetch_sitemap(source.sitemap_url)
    urls = filter_by_date(sitemap.urls, date_from, date_to)
    return urls

# Priority 2: Listing page (fallback)
async def crawl_via_listing(source, date_from, date_to):
    page = 1
    while True:
        articles = await fetch_listing_page(source.listing_url, page)
        if all_before_range(articles, date_from):
            break
        yield filter_by_date(articles, date_from, date_to)
        page += 1

# Dedup
def get_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()
```

**Quy tắc:**
- Dedup bằng `SHA256(url)` trước khi insert vào bảng `articles` (cột `url_hash` có `UNIQUE` constraint)
- Delay 1–2 giây giữa các request đến cùng một domain — tránh bị block
- Website dùng JavaScript render (JS-heavy) → dùng Playwright thay cho httpx
- Cấu hình CSS selector riêng theo từng nguồn lưu ở cột `sources.parsing_rules` (JSONB), dạng `{title, content, date, author}`

---

## Môi trường & Cấu hình

```env
CRAWLER_DELAY_SECONDS=1.5
CRAWLER_MAX_RETRIES=3
CRAWLER_TIMEOUT_SECONDS=30
```
