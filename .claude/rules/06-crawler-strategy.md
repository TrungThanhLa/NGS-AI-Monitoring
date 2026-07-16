---
description: Chiến lược crawl — Sitemap XML primary, listing page fallback, dedup, scheduler liên tục
alwaysApply: false
---

# Chiến lược crawl

> Phần dưới đây (crawl theo yêu cầu 1 lần, per-article fetch, dedup trong phạm vi 1 job) là `[ĐÃ CODE]`, đang chạy thật. Mục "Scheduler & crawl liên tục" cuối file là `[CHƯA CODE]` — không phải "tính năng thêm sau", mà là phần **sửa lại cơ chế crawl hiện tại** cho đúng nghiệp vụ giám sát liên tục (xem [04 · Business Flow](04-business-flow.md)).

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

**Quy tắc — `[ĐÃ CODE]`:**
- Dedup bằng `SHA256(url)` **trong phạm vi 1 job** trước khi insert vào bảng `articles` — không dedup xuyên job: mỗi job crawl/phân tích lại từ đầu dù trùng URL với job khác (kể cả job đã thành công), để không bỏ lỡ nội dung đã thay đổi và không tạo dữ liệu "mồ côi" khi job cũ fail/cancel giữa chừng (2026-07-09). Chống trùng bằng 2 lớp: `set()` Python cục bộ trong 1 lần chạy job (nhanh, không đụng DB) + `UNIQUE` composite `(job_id, url_hash)` ở DB làm lưới an toàn dự phòng. **Sẽ đảo ngược khi migrate sang crawl liên tục** — xem mục cuối file.
- `MAX_ARTICLES_PER_JOB` mặc định áp dụng tuần tự theo `source_ids` — nguồn đầu tiên đủ bài sẽ "ăn hết" ngân sách trước khi chạm tới nguồn sau. Bật `EVEN_DISTRIBUTE_ACROSS_SOURCES=true` để chia đều ngân sách cho từng nguồn đã chọn — hữu ích khi test với số bài nhỏ nhưng muốn thấy đa dạng nguồn. Dùng thuật toán water-filling: quota của mỗi nguồn tính LẠI ngay trước khi xử lý nguồn đó (`ngân_sách_còn_lại / số_nguồn_chưa_xử_lý`, dư dồn đầu) — nguồn nào thiếu bài (VD không có bài đăng đúng ngày yêu cầu) sẽ tự động nhường phần ngân sách chưa dùng cho nguồn xử lý sau, tổng job tiến gần đúng `MAX_ARTICLES_PER_JOB` hơn thay vì bỏ phí (2026-07-10, đổi từ thiết kế "không bù" ban đầu sau khi verify thật)
- Delay 1–2 giây giữa các request đến cùng một domain — tránh bị block
- Website dùng JavaScript render (JS-heavy) → dùng Playwright thay cho httpx
- Cấu hình CSS selector riêng theo từng nguồn lưu ở cột `sources.parsing_rules` (JSONB), dạng `{title, content, date, author}`
- **2 hạn chế thật đã sửa của sitemap index (2026-07-10):** (1) `vov.vn` chỉ thêm entry sub-sitemap của 1 tháng vào `sitemap.xml` SAU KHI tháng đó kết thúc → job chạy giữa tháng không bao giờ thấy sub-sitemap tháng hiện tại. Sửa bằng `_SITEMAP_URL_TEMPLATES` (`sitemap.py`): với domain đã khai, **bỏ hẳn việc fetch/parse index**, tự sinh URL sub-sitemap trực tiếp từ `(year, month)` cho mọi tháng trong `date_from`–`date_to` (format dự đoán được, verify tay bằng curl). (2) `vtv.vn` build sub-sitemap theo khối 5 ngày → vài ngày gần nhất có thể chưa đóng khối, không nằm trong sub-sitemap nào theo `_SITEMAP_DATE_PATTERNS`. Sửa bằng `_SITEMAP_ALWAYS_INCLUDE`: domain có khai sẽ luôn fetch kèm 1 URL "catch-all" cố định (`latest-news-sitemap.xml`), không qua bộ lọc ngày — URL này đã có sẵn trong chính index nhưng bị regex loại vì không mang ngày tháng trong path. **Tối ưu (cùng ngày):** chỉ fetch URL catch-all khi `date_to >= hôm nay` (tham số `today` injectable, mặc định `date.today()`, cùng pattern với `client`/`delay_seconds`/`max_retries`) — job có phạm vi hoàn toàn trong quá khứ chắc chắn không nhận thêm được bài nào từ URL này nên bỏ qua, tránh 1 request vô ích

---

## Fetch article content — 3 engine (httpx mặc định / Crawl4AI / Playwright tùy chọn) — `[ĐÃ CODE]`

Điểm vào duy nhất gọi từ `workers/report_job.py`: `fetch_article_dispatch(url, source.parsing_rules)` (`backend/crawler/crawl4ai_client.py`) — rẽ nhánh theo key `engine` trong `parsing_rules`:

```python
def fetch_article_dispatch(url: str, parsing_rules: dict) -> dict | None:
    engine = parsing_rules.get("engine")
    if engine == "crawl4ai":
        return fetch_article_crawl4ai(url)
    if engine == "playwright":
        return fetch_article_playwright(url, parsing_rules)
    return fetch_article(url, parsing_rules)   # httpx + CSS selector — mặc định, không đổi
```

- **Mặc định (không khai `engine`)** — `fetch_article()` (`crawler/article.py`), httpx + BeautifulSoup + CSS selector tay như cũ. Đang dùng cho VTV.
- **`"engine": "crawl4ai"`** — `fetch_article_crawl4ai()` (`crawler/crawl4ai_client.py`), dùng Crawl4AI **HTTP-only mode** (không chạy JS/browser):
  - Không cần khai CSS selector nào — tự nhận diện vùng nội dung chính (`PruningContentFilter`) + tự parse toàn bộ thẻ `<meta>` (`og:title`, `article:author`, `article:published_time`...) lấy title/author/ngày đăng
  - Output content là Markdown đã được hậu xử lý cắt tại marker `"Tin liên quan"`/`"Bình luận"` (convention phổ biến báo điện tử VN, verify trên VTV + VOV) để giảm rác trước khi feed AI
  - **Hạn chế đã biết, chấp nhận tạm thời:** nguồn nhúng box "bài liên quan" ngay trong nội dung chính (không có heading riêng, gặp ở VOV) thì vẫn còn dư rác (~600-700 ký tự) sau bước trim — CSS selector thủ công cũng gặp đúng vấn đề này (rác nằm trong chính content container), không phải nhược điểm riêng của Crawl4AI. Đã cân nhắc dùng thêm `excluded_selector` của Crawl4AI để dọn tiếp nhưng quyết định chưa làm
  - Phụ thuộc nặng hơn nhiều so với httpx (kéo theo `numpy`, `scipy`, `playwright`, `patchright`... dù chỉ dùng HTTP-only) — chỉ nên bật cho nguồn thực sự cần (chưa có CSS selector hoạt động tốt), không cần đổi nguồn đang chạy ổn (VTV)
  - Không tự retry khi lỗi network (khác với `fetch_article()` httpx có retry 3 lần exponential backoff) — lỗi/thiếu title hoặc content → trả `None`, vẫn được `report_job.py` xử lý như crawl lỗi bình thường (insert `Article(status="error")`)
- **`"engine": "playwright"`** — `fetch_article_playwright()` (`crawler/playwright_client.py`), dùng Playwright (headless Chromium) để render trang có JavaScript rồi lấy HTML đã render, sau đó parse bằng **đúng CSS selector khai trong `parsing_rules`** (`title`/`content`/`author`/`date`) — khác với Crawl4AI (tự nhận diện nội dung), Playwright chỉ thay bước fetch, không thay bước parse. Admin phải khai CSS selector khi cấu hình nguồn dùng engine này, giống engine mặc định httpx. Có retry 3 lần exponential backoff giống httpx (không phải ngoại lệ như Crawl4AI).

---

## Môi trường & Cấu hình

```env
CRAWLER_DELAY_SECONDS=1.5
CRAWLER_MAX_RETRIES=3
CRAWLER_TIMEOUT_SECONDS=30
```

---

## Scheduler & crawl liên tục — `[CHƯA CODE]`

> Mở rộng [17 · Continuous Crawler & Scheduler](17-continuous-crawler-scheduler.md) (matching từ khóa hậu-crawl, content review, `AI_AUTO_TRIGGER`) — **giữ nguyên 100%** toàn bộ logic parser (sitemap/listing/Crawl4AI/Playwright) ở trên, chỉ đổi **nơi/cách trigger** từ "1 lần theo yêu cầu" sang "định kỳ theo lịch".

### Celery Beat — duyệt theo Nguồn, không theo Campaign

Celery Beat (mới) — duyệt theo **Nguồn** (không duyệt theo từng Campaign, tránh 1 Nguồn bị enqueue crawl trùng nhiều lần trong cùng 1 lượt kiểm tra khi có ≥2 Campaign `ACTIVE` cùng tham chiếu tới nó). Dữ liệu crawl được chỉ gắn theo `source_id`, **không gắn `campaign_id`** ngay từ lúc crawl:

```
Celery Beat (chạy mỗi 1 phút, kiểm tra):
  for each Source đang được ≥1 Campaign ACTIVE tham chiếu (SELECT DISTINCT qua campaign_sources):
    if now - source.last_crawled_at >= source.crawl_frequency:
      enqueue crawl_task(source_id)   # KHÔNG kèm campaign_id
```

**Lý do không gắn `campaign_id` lúc crawl:** nếu nhiều Campaign cùng theo dõi 1 Nguồn, dữ liệu chỉ nên lưu 1 bản gắn theo Nguồn — "Campaign nào cần biết bài này" xác định qua matching từ khóa (`campaign_articles`) ngay sau khi crawl, không cần biết ngay từ lúc crawl thô (xem [16 · Campaign Management](16-campaign-management.md)).

Tần suất kiểm tra của Beat: 1 phút là đủ, không cần dày hơn vì `crawl_frequency` đề xuất tối thiểu 30 phút cho báo điện tử (khác social media 5-15 phút).

### Crawl 2 giai đoạn — chống mất dữ liệu khi bị đứt giữa chừng

`crawl_task(source_id)` tách 2 giai đoạn qua bảng `crawl_queue` ([03 · Database Schema](03-database-schema.md)):

**Giai đoạn 1 — khám phá URL (rẻ, nhanh, ít khi lỗi):** đọc sitemap/listing của Nguồn → lấy danh sách URL ứng viên → `INSERT ... ON CONFLICT DO NOTHING` vào `crawl_queue` theo `(source_id, url_hash)` (`status='pending'`) — không tải nội dung ở bước này, chỉ ghi nhận "đã biết URL này tồn tại".

**Giai đoạn 2 — tải nội dung (tốn thời gian, dễ đứt giữa chừng):** lấy TẤT CẢ URL đang `status='pending'` của Nguồn này (gồm cả URL bị lỡ từ các chu kỳ trước, không chỉ URL mới phát hiện lần này) → fetch từng URL, cập nhật `status='fetched'/'error'` NGAY theo từng bài (không đợi xong cả batch) → fetch thành công → lưu vào `articles` (gắn `source_id`, không đổi cơ chế fetch hiện có ở trên). Nếu quy trình bị đứt giữa chừng (crash/timeout/mất mạng), URL còn `'pending'` **tự động được thử lại ở chu kỳ kế tiếp** — không phụ thuộc việc sitemap/listing của nguồn còn hiển thị URL đó hay không. URL fail quá `CRAWLER_MAX_RETRIES` lần liên tiếp → `status='error'` hẳn, ngừng thử lại.

### Dedup — toàn cục theo Nguồn (đảo ngược quyết định "không dedup xuyên job")

`SHA256(url)` dedup **toàn cục theo `source_id`** (`UNIQUE(source_id, url_hash)`, xem [03 · Database Schema](03-database-schema.md)) — đảo ngược quyết định "không dedup xuyên job" ở trên (2026-07-09), bắt buộc phải đổi vì crawl liên tục sẽ liệt kê lại URL cũ mỗi chu kỳ. **Đánh đổi chấp nhận:** hệ thống sẽ không phát hiện được nếu 1 bài báo bị chỉnh sửa nội dung sau khi đăng (URL trùng → bỏ qua ngay, không tải lại so sánh) — chấp nhận vì báo điện tử VN ít khi sửa nội dung sau khi đăng.

**`CRAWLER_MAX_RETRIES=3, CRAWLER_TIMEOUT_SECONDS=30, CRAWLER_DELAY_SECONDS=1.5` — không đổi.** Không có endpoint public riêng cho crawler/scheduler — vận hành hoàn toàn qua Celery Beat + `system_settings`.
