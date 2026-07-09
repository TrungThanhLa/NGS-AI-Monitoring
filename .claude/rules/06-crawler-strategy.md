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
- Dedup bằng `SHA256(url)` **trong phạm vi 1 job** trước khi insert vào bảng `articles` — không dedup xuyên job: mỗi job crawl/phân tích lại từ đầu dù trùng URL với job khác (kể cả job đã thành công), để không bỏ lỡ nội dung đã thay đổi và không tạo dữ liệu "mồ côi" khi job cũ fail/cancel giữa chừng (2026-07-09). Chống trùng bằng 2 lớp: `set()` Python cục bộ trong 1 lần chạy job (nhanh, không đụng DB) + `UNIQUE` composite `(job_id, url_hash)` ở DB làm lưới an toàn dự phòng
- Delay 1–2 giây giữa các request đến cùng một domain — tránh bị block
- Website dùng JavaScript render (JS-heavy) → dùng Playwright thay cho httpx
- Cấu hình CSS selector riêng theo từng nguồn lưu ở cột `sources.parsing_rules` (JSONB), dạng `{title, content, date, author}`

---

## Fetch article content — 2 engine (httpx mặc định / Crawl4AI tùy chọn)

Điểm vào duy nhất gọi từ `workers/report_job.py`: `fetch_article_dispatch(url, source.parsing_rules)` (`backend/crawler/crawl4ai_client.py`) — rẽ nhánh theo key `engine` trong `parsing_rules`:

```python
def fetch_article_dispatch(url: str, parsing_rules: dict) -> dict | None:
    if parsing_rules.get("engine") == "crawl4ai":
        return fetch_article_crawl4ai(url)
    return fetch_article(url, parsing_rules)   # httpx + CSS selector — mặc định, không đổi
```

- **Mặc định (không khai `engine`)** — `fetch_article()` (`crawler/article.py`), httpx + BeautifulSoup + CSS selector tay như cũ. Đang dùng cho VTV.
- **`"engine": "crawl4ai"`** — `fetch_article_crawl4ai()` (`crawler/crawl4ai_client.py`), dùng Crawl4AI **HTTP-only mode** (không chạy JS/browser):
  - Không cần khai CSS selector nào — tự nhận diện vùng nội dung chính (`PruningContentFilter`) + tự parse toàn bộ thẻ `<meta>` (`og:title`, `article:author`, `article:published_time`...) lấy title/author/ngày đăng
  - Output content là Markdown đã được hậu xử lý cắt tại marker `"Tin liên quan"`/`"Bình luận"` (convention phổ biến báo điện tử VN, verify trên VTV + VOV) để giảm rác trước khi feed AI
  - **Hạn chế đã biết, chấp nhận tạm thời:** nguồn nhúng box "bài liên quan" ngay trong nội dung chính (không có heading riêng, gặp ở VOV) thì vẫn còn dư rác (~600-700 ký tự) sau bước trim — CSS selector thủ công cũng gặp đúng vấn đề này (rác nằm trong chính content container), không phải nhược điểm riêng của Crawl4AI. Đã cân nhắc dùng thêm `excluded_selector` của Crawl4AI để dọn tiếp nhưng quyết định chưa làm — xem CLAUDE.md "Quyết định quan trọng & lý do" (2026-06-29)
  - Phụ thuộc nặng hơn nhiều so với httpx (kéo theo `numpy`, `scipy`, `playwright`, `patchright`... dù chỉ dùng HTTP-only) — chỉ nên bật cho nguồn thực sự cần (chưa có CSS selector hoạt động tốt), không cần đổi nguồn đang chạy ổn (VTV)
  - Không tự retry khi lỗi network (khác với `fetch_article()` httpx có retry 3 lần exponential backoff) — lỗi/thiếu title hoặc content → trả `None`, vẫn được `report_job.py` xử lý như crawl lỗi bình thường (insert `Article(status="error")`)

---

## Môi trường & Cấu hình

```env
CRAWLER_DELAY_SECONDS=1.5
CRAWLER_MAX_RETRIES=3
CRAWLER_TIMEOUT_SECONDS=30
```
