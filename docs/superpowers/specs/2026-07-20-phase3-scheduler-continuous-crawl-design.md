# Phase 3 — Scheduler & Continuous Crawl — Design

> Trạng thái: đã thống nhất với user qua brainstorming 2026-07-20. Chưa code. Kế hoạch triển khai chi tiết ở file `docs/superpowers/plans/2026-07-20-phase3-scheduler-continuous-crawl-plan.md` (bước tiếp theo, viết bằng writing-plans skill).

## Vì sao làm Phase 3, và vì sao sau Phase 2

Chỉ Campaign `ACTIVE` (Phase 2) mới cần crawl tự động theo lịch. Phase 3 là hạ tầng biến "crawl 1 lần theo yêu cầu" (Job) thành "crawl liên tục theo Nguồn" mà **không sửa/xóa bất kỳ phần nào của luồng Job/Report on-demand đang chạy thật** — 2 hệ thống chạy song song, đúng tiền lệ đã chọn ở Phase 2.

Tham chiếu nghiệp vụ gốc: [17 · Continuous Crawler & Scheduler](../../.claude/rules/17-continuous-crawler-scheduler.md), [06 · Crawler Strategy](../../.claude/rules/06-crawler-strategy.md) mục "Scheduler & crawl liên tục", [03 · Database Schema](../../.claude/rules/03-database-schema.md), `docs/ROADMAP_CONTINUOUS_MONITORING.md` mục "Phase 3".

## Phạm vi

**Trong phạm vi:**
- Celery Beat quét mỗi 60s, enqueue crawl theo Source (không theo Campaign).
- Công tắc `SCHEDULER_ENABLED` + `AI_AUTO_TRIGGER` trong `system_settings` — mặc định `false` cả hai.
- `crawl_task(source_id)` 2 giai đoạn (Discover/Fetch) qua bảng `crawl_queue`, tái dùng 100% parser hiện có (sitemap/listing/httpx/Crawl4AI/Playwright).
- Dedup toàn cục theo Source cho dữ liệu crawl liên tục, qua **partial unique index**, không đụng dedup của Job cũ.
- Matching từ khóa hậu-crawl → `campaign_articles` + `campaign_article_keywords` (lưu đủ mọi từ khóa trúng, không chỉ 1).
- AI trigger tự động theo bài (không theo Campaign) khi `AI_AUTO_TRIGGER=true`, tái dùng `analyze_article()` có sẵn.
- Cột mới trên `sources`: `crawl_frequency`, `last_crawled_at`, `status` (ACTIVE|INACTIVE|ERROR), `consecutive_error_count`.
- `PUT /api/sources/{id}` (mới — trước đây tài liệu ghi đã code nhưng thực tế chưa từng có) — chỉ cho sửa `source_group`/`crawl_frequency`/`status` (ACTIVE|INACTIVE, không cho set ERROR qua API).
- `GET/PUT /api/system-settings` — chỉ ADMIN (`system.configure`).
- FE tối thiểu: modal sửa nguồn trên `/sources`, 1 Card mới trên `/system/settings` cho 2 công tắc trên.

**Ngoài phạm vi (để dành phase khác, không tự làm thêm):**
- Content Detail page hiện từ khóa trúng cho người dùng xem — **Phase 4**. Phase 3 chỉ đảm bảo dữ liệu (`campaign_article_keywords`) được ghi đủ, đúng để Phase 4 dùng lại, không tự xây màn hình.
- Xóa hẳn `jobs`/`/api/reports/create`, đổi `UNIQUE(source_id, url_hash)` áp dụng toàn bảng `articles` — **Phase 7**, khi đã có Campaign `mode=ONE_SHOT` thay thế. Đã cân nhắc làm ngay ở Phase 3 (gọn code hơn) nhưng bị từ chối vì phá vỡ tính năng Report on-demand đang chạy thật mà chưa có gì thay thế.
- `POST`/`DELETE /api/sources` — khoảng trống tài liệu có sẵn từ trước (rule 05 ghi đã code nhưng thực tế chưa), không thuộc nhu cầu Phase 3, không tự thêm.
- Alert (`KEYWORD_SPIKE`/`NEGATIVE_TREND`/`HIGH_ATTENTION`) — Phase 5, dữ liệu Phase 3 tạo ra (`campaign_articles`, `article_analysis`) là input cho Alert sau này nhưng logic sinh Alert không code ở đây.

## Kiến trúc & luồng dữ liệu

```
Celery Beat (mỗi 60s)
  → đọc system_settings['SCHEDULER_ENABLED'] — false thì dừng, không làm gì
  → SELECT DISTINCT source_id FROM sources
      JOIN campaign_sources JOIN campaigns WHERE campaigns.status='ACTIVE'
      WHERE sources.status='ACTIVE'
  → với mỗi source: now - last_crawled_at >= crawl_frequency ? enqueue crawl_task(source_id) : bỏ qua

crawl_task(source_id)  [Celery task]
  Stage 1 — Discover:
    get_article_urls()/get_listing_urls() (KHÔNG đổi, tái dùng nguyên xi)
    → INSERT crawl_queue (source_id, url, url_hash, status='pending') ON CONFLICT DO NOTHING

  Stage 2 — Fetch:
    SELECT * FROM crawl_queue WHERE source_id=X AND status='pending'
    (gồm cả URL lỡ chu kỳ trước — đây là cơ chế tự phục hồi khi bị đứt giữa chừng)
    với mỗi URL:
      fetch_article_dispatch(url, parsing_rules)  (KHÔNG đổi, tái dùng nguyên xi)
      thành công → INSERT articles(source_id=X, job_id=NULL, ...) + crawl_queue.status='fetched'
      thất bại   → retry_count += 1; > CRAWLER_MAX_RETRIES → status='error', ngược lại giữ 'pending'

    sau khi xử lý hết URL của chu kỳ này:
      sources.last_crawled_at = now()
      nếu ≥1 bài fetch thành công → consecutive_error_count = 0
      nếu 0 bài fetch được (toàn bộ URL lỗi/rỗng) → consecutive_error_count += 1
      nếu consecutive_error_count > 10 → sources.status = 'ERROR'  (BR-SRC-03)

  Post-crawl matching (mỗi bài fetch thành công):
    với mỗi Campaign ACTIVE có campaign_sources chứa source_id X:
      duyệt TOÀN BỘ keyword của Campaign, SẮP XẾP theo keyword_id tăng dần (campaign_keywords
      không có cột thứ tự khai báo — dùng keyword_id làm khóa sắp xếp xác định/deterministic,
      không phụ thuộc thứ tự trả về ngẫu nhiên của Postgres), không break sớm:
        keyword.keyword.lower() in (title + content_raw).lower() ?
          → ghi vào tập matched_keywords (giữ nguyên thứ tự đã sắp xếp)
      nếu matched_keywords rỗng → bỏ qua, bài không thuộc Campaign này
      nếu không rỗng →
        INSERT campaign_articles(campaign_id, article_id,
                                  matched_keyword_id=matched_keywords[0])  -- keyword_id nhỏ nhất trúng
        INSERT campaign_article_keywords(campaign_id, article_id, keyword_id)
          cho MỌI keyword_id trong matched_keywords (không chỉ cái đầu)

  AI trigger (mỗi bài fetch thành công, độc lập với việc có match Campaign nào không):
    nếu system_settings['AI_AUTO_TRIGGER'] == 'true':
      result = await analyze_article(title, content_raw)  -- hàm per-article có sẵn, KHÔNG viết mới
      INSERT article_analysis(article_id=..., job_id=NULL, **result)
    ngược lại: giữ nguyên articles.status='pending_analysis'
```

### Vì sao AI phân tích theo bài, không theo Campaign

Kết quả AI (`sentiment`/`emotion`/`confidence`/`summary`) là thuộc tính của nội dung bài viết, không đổi theo "Campaign nào đang xem". `article_analysis` không có cột `campaign_id` (đúng schema rule 03 sẵn có). Phân tích theo Campaign sẽ: (1) tốn gấp nhiều lần tài nguyên AI cho cùng 1 bài — vốn đã là điểm nghẽn thật (Ollama CPU-only từng timeout, rule 10); (2) `qwen3:8b` không cố định seed/temperature (rule 07) nên 2 lần gọi có thể ra 2 kết quả khác nhau cho cùng 1 bài — nếu phân tích theo Campaign, 2 Campaign cùng theo dõi 1 bài có thể thấy 2 kết quả AI mâu thuẫn. Giải pháp: phân tích đúng 1 lần/bài, mọi Campaign match được bài đó đều tham chiếu chung 1 kết quả qua `campaign_articles → articles → article_analysis`.

### Vì sao dedup dùng partial index thay vì đổi thẳng `UNIQUE(source_id, url_hash)` toàn bảng

`jobs`/`report_job.py`/`/api/reports/*` đang là tính năng "Tạo báo cáo" duy nhất chạy thật (ngoài `/sources`). Đổi thẳng constraint toàn bảng đòi hỏi xóa hẳn `jobs` (và mọi FK phụ thuộc: `article_analysis.job_id`, `report_history.job_id`) — tắt tính năng report on-demand cho tới khi Campaign `mode=ONE_SHOT` thay thế (Phase 7, còn phải qua Phase 4/5/6). User đã xác nhận **không chấp nhận đánh đổi này** — chọn:

```sql
CREATE UNIQUE INDEX articles_source_id_url_hash_continuous_key
    ON articles (source_id, url_hash) WHERE job_id IS NULL;
```

Dòng có `job_id` (Job cũ) không đổi hành vi gì. Dòng `job_id IS NULL` (continuous crawl mới) tự dedup theo Source. Khi Phase 7 xóa hẳn `jobs`, chỉ cần 1 migration nhỏ: drop cột `job_id` + constraint cũ + đổi partial index thành index thường — không phải viết lại logic dedup continuous crawl đã có.

### Vì sao tách cột `status` khỏi `is_active` trên `sources`

`is_active` (có sẵn) chỉ phục vụ luồng Job — `GET /api/sources` lọc theo nó để hiện sidebar chọn nguồn tạo báo cáo; `POST /api/reports/create` từ chối nguồn `is_active=false`. `status` (mới) phục vụ riêng Scheduler — chỉ nguồn `status='ACTIVE'` mới được Beat chọn (BR-SRC-04), và có trạng thái `ERROR` **tự động** (không do Admin gõ tay) khi lỗi liên tiếp >10 lần (BR-SRC-03). Hai khái niệm lệch nhau trong thực tế (VD: Admin ẩn nguồn khỏi sidebar Job nhưng vẫn để Scheduler crawl nền: `is_active=false`, `status='ACTIVE'`) nên không dùng chung 1 cột.

## Schema — migration `0018_add_scheduler_tables.py`

```sql
CREATE TABLE crawl_queue (
    queue_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id     UUID REFERENCES sources(source_id) ON DELETE RESTRICT,
    url           TEXT NOT NULL,
    url_hash      VARCHAR(64) NOT NULL,
    status        VARCHAR(20) DEFAULT 'pending',  -- pending|fetched|error
    retry_count   INTEGER DEFAULT 0,
    discovered_at TIMESTAMP DEFAULT NOW(),
    fetched_at    TIMESTAMP,
    UNIQUE (source_id, url_hash)
);

CREATE TABLE system_settings (
    setting_key   VARCHAR(255) PRIMARY KEY,
    setting_value TEXT,
    data_type     VARCHAR(50),
    description   TEXT,
    updated_at    TIMESTAMP,
    updated_by    UUID REFERENCES users(user_id)
);
-- seed: ('SCHEDULER_ENABLED', 'false', 'BOOLEAN', ...), ('AI_AUTO_TRIGGER', 'false', 'BOOLEAN', ...)

CREATE TABLE campaign_articles (
    campaign_id         UUID REFERENCES campaigns(campaign_id) ON DELETE RESTRICT,
    article_id          UUID REFERENCES articles(article_id) ON DELETE RESTRICT,
    matched_keyword_id  UUID REFERENCES keywords(keyword_id),
    matched_at          TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (campaign_id, article_id)
);

CREATE TABLE campaign_article_keywords (
    campaign_id UUID NOT NULL,
    article_id  UUID NOT NULL,
    keyword_id  UUID NOT NULL REFERENCES keywords(keyword_id),
    PRIMARY KEY (campaign_id, article_id, keyword_id),
    FOREIGN KEY (campaign_id, article_id) REFERENCES campaign_articles(campaign_id, article_id)
);

ALTER TABLE sources
    ADD COLUMN crawl_frequency         INTEGER DEFAULT 1800,
    ADD COLUMN last_crawled_at         TIMESTAMP,
    ADD COLUMN status                  VARCHAR(30) DEFAULT 'ACTIVE',
    ADD COLUMN consecutive_error_count INTEGER DEFAULT 0;

CREATE UNIQUE INDEX articles_source_id_url_hash_continuous_key
    ON articles (source_id, url_hash) WHERE job_id IS NULL;
```

Migration phải reversible (downgrade drop theo thứ tự ngược lại), theo đúng pattern các migration trước (VD 0017).

## API

```
PUT /api/sources/{id}
  body: { source_group?, crawl_frequency?, status? }   # status chỉ nhận ACTIVE|INACTIVE
  permission: source.update (đã có trong RBAC matrix)
  400 nếu status gửi lên là ERROR hoặc giá trị khác ACTIVE/INACTIVE

GET /api/system-settings
  → { settings: [{ setting_key, setting_value, data_type, description, updated_at }] }
  permission: system.configure

PUT /api/system-settings/{key}
  body: { setting_value }
  permission: system.configure
  404 nếu key không tồn tại
```

## FE

- `/sources`: thêm nút "Sửa" → modal `crawl_frequency` (input phút, quy đổi giây khi gửi API), `status` (Select: Đang hoạt động/Tạm dừng — không hiện option Lỗi).
- `/system/settings`: thêm Card "Giám sát liên tục" (2 Switch nối `GET`/`PUT /api/system-settings`) — 2 Card cũ giữ mock, không đụng.

## Error handling (bổ sung, không thay bảng rule 10 hiện có)

| Tình huống | Xử lý |
|---|---|
| Beat quét lúc `SCHEDULER_ENABLED=false` | Thoát ngay, không enqueue |
| URL fetch lỗi trong Stage 2 | `retry_count += 1`; > `CRAWLER_MAX_RETRIES` → `status='error'` trong `crawl_queue`, giữ nguyên `pending` nếu chưa hết retry (chu kỳ sau tự thử lại) |
| Cả chu kỳ không fetch được bài nào | `consecutive_error_count += 1`; > 10 → `sources.status='ERROR'`, Beat bỏ qua nguồn này từ chu kỳ sau |
| `AI_AUTO_TRIGGER=true` nhưng Ollama timeout | Bắt `httpx.HTTPError` như `report_job.py` đã làm — bài giữ `status='pending_analysis'`, không chặn các bài khác |
| Worker crash giữa Stage 2 | URL còn `pending` trong `crawl_queue`, chu kỳ sau tự thử lại — không cần cơ chế phục hồi riêng |

## Testing

- Unit test câu query Beat (source nào due for crawl) với `now` injectable (giống pattern `today` injectable đã dùng ở `sitemap.py`).
- Unit test `crawl_task` Stage 1/2 riêng biệt: Discover không tạo trùng (`ON CONFLICT DO NOTHING`), Fetch tự nhặt lại URL `pending` cũ.
- Unit test partial index: insert 2 dòng cùng `(source_id, url_hash)` với `job_id` khác nhau (không lỗi) vs 2 dòng cùng `(source_id, url_hash)` đều `job_id=NULL` (lỗi UNIQUE).
- Unit test matching: bài trúng nhiều từ khóa → `campaign_articles.matched_keyword_id` là từ khóa đầu tiên, `campaign_article_keywords` có đủ mọi từ khóa trúng.
- Unit test BR-SRC-03: giả lập 11 chu kỳ lỗi liên tiếp → `status` tự chuyển `ERROR`; 1 chu kỳ thành công → `consecutive_error_count` reset 0.
- Regression test: xác nhận `jobs`/`report_job.py`/`/api/reports/*` không bị ảnh hưởng (test cũ vẫn pass nguyên).
- Smoke test thật: bật `SCHEDULER_ENABLED=true` cho 1 nguồn thật với `crawl_frequency` ngắn (VD 60s) trong môi trường dev, verify `crawl_queue`/`articles`/`campaign_articles` được ghi đúng.
