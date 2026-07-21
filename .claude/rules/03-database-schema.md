---
description: PostgreSQL schema — toàn bộ bảng theo đúng nghiệp vụ (đã code + chưa code)
alwaysApply: true
---

# Database Schema

> Đây là toàn bộ schema đúng theo nghiệp vụ đã chốt ([01 · Project Overview](01-project-overview.md)) — **không phải 2 schema của 2 giai đoạn sản phẩm khác nhau**. Mỗi bảng/cột được đánh dấu trạng thái implement thực tế:
> - `[ĐÃ CODE]` — đang chạy thật trong `main`.
> - `[CHƯA CODE]` — thuộc nghiệp vụ đúng nhưng chưa hiện thực, xem thứ tự triển khai ở [docs/ROADMAP_CONTINUOUS_MONITORING.md](../../docs/ROADMAP_CONTINUOUS_MONITORING.md).
> - `[SẼ SỬA]` — bảng đang tồn tại nhưng cấu trúc hiện tại sai/thiếu so với nghiệp vụ đúng, cần migrate.

---

## Nhóm: Người dùng & Phân quyền (Auth/RBAC) — `[CHƯA CODE]`

> Business rules chi tiết (BR-USER), RBAC matrix đầy đủ theo permission: xem [15 · Auth & RBAC](15-auth-rbac.md). Dự án hiện tại **chưa có Auth ở bất kỳ đâu** — đây là nền tảng bắt buộc, mọi bảng có cột `*_by`/`owner_id`/`assigned_to` ở dưới đều tham chiếu `users`.

```sql
CREATE TABLE users (
    user_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username            VARCHAR(100) NOT NULL UNIQUE,
    email               VARCHAR(255) UNIQUE,
    full_name           VARCHAR(255),
    password_hash       TEXT NOT NULL,
    status              VARCHAR(30) DEFAULT 'ACTIVE',   -- ACTIVE | LOCKED | INACTIVE
    failed_login_count  INTEGER DEFAULT 0,
    locked_until        TIMESTAMP,
    last_login_at       TIMESTAMP,
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP,
    deleted_at          TIMESTAMP
);

CREATE TABLE roles (
    role_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code         VARCHAR(50) NOT NULL UNIQUE,   -- ADMIN | MANAGER | ANALYST | OPERATOR | VIEWER
    name         VARCHAR(255) NOT NULL,
    is_system    BOOLEAN DEFAULT true,
    is_active    BOOLEAN DEFAULT true
);

CREATE TABLE permissions (
    permission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code          VARCHAR(100) NOT NULL UNIQUE,  -- vd "campaign.create"
    resource      VARCHAR(100) NOT NULL,
    action        VARCHAR(50) NOT NULL,
    description   TEXT
);

CREATE TABLE user_roles (
    user_id UUID REFERENCES users(user_id) ON DELETE RESTRICT,
    role_id UUID REFERENCES roles(role_id) ON DELETE RESTRICT,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE role_permissions (
    role_id       UUID REFERENCES roles(role_id) ON DELETE RESTRICT,
    permission_id UUID REFERENCES permissions(permission_id) ON DELETE RESTRICT,
    PRIMARY KEY (role_id, permission_id)
);

-- Bất biến, KHÔNG soft-delete (BR-SYS-01 ngoại lệ) — ghi mọi CREATE/UPDATE/DELETE/
-- APPROVE/REJECT/LOGIN/LOGOUT/EXPORT
CREATE TABLE audit_logs (
    audit_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID REFERENCES users(user_id),
    action       VARCHAR(100) NOT NULL,
    entity_type  VARCHAR(100),
    entity_id    UUID,
    old_value    JSONB,
    new_value    JSONB,
    ip_address   VARCHAR(100),
    user_agent   TEXT,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- [ĐÃ CODE — Phase 3, migration 0018] Đưa các hằng số hiện đang hardcode trong .env lên cấu
-- hình được qua UI — 2 công tắc đã seed: SCHEDULER_ENABLED, AI_AUTO_TRIGGER (xem
-- 17-continuous-crawler-scheduler.md) — chỉ ADMIN được sửa
CREATE TABLE system_settings (
    setting_key   VARCHAR(255) PRIMARY KEY,
    setting_value TEXT,
    data_type     VARCHAR(50),   -- STRING|INTEGER|BOOLEAN|JSON
    description   TEXT,
    updated_at    TIMESTAMP,
    updated_by    UUID REFERENCES users(user_id)
);
```

---

## Nhóm: Nguồn dữ liệu — `sources` `[ĐÃ CODE, SẼ SỬA]`

```sql
CREATE TABLE sources (
    source_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(255) NOT NULL,        -- Tên hiển thị (VD: Báo QĐND)
    domain        VARCHAR(255) NOT NULL UNIQUE, -- VD: qdnd.vn
    group_name    VARCHAR(255) NOT NULL,        -- Nhóm kênh (VD: Bộ Quốc phòng)
    sitemap_url   TEXT,                         -- URL sitemap.xml nếu có
    listing_url   TEXT,                         -- URL trang danh sách bài (fallback)
    parsing_rules JSONB DEFAULT '{}',           -- CSS selector: {title, content, date, author}
                                                  -- + key tùy chọn "engine": "crawl4ai"/"playwright"
                                                  -- (xem 06-crawler-strategy.md)
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMP DEFAULT NOW(),

    -- [ĐÃ CODE] — cột bổ sung cho crawl liên tục theo lịch (xem 17-continuous-crawler-scheduler.md)
    source_group        VARCHAR(255),           -- nhóm nguồn dùng chung (Chính phủ/Bộ ngành/Báo chí...) — Phase 2 (migration 0017)
    crawl_frequency      INTEGER DEFAULT 1800,   -- giây, mặc định 30 phút cho báo điện tử — Phase 3 (migration 0018)
    last_crawled_at       TIMESTAMP,             -- Phase 3
    status                VARCHAR(30) DEFAULT 'ACTIVE',  -- ACTIVE|INACTIVE|ERROR, thay thế is_active
                                                           -- cho mục đích crawl tự động (BR-SRC-03) — Phase 3
    consecutive_error_count INTEGER DEFAULT 0    -- đếm số chu kỳ Fetch liên tiếp không fetch được bài
                                                   -- nào (chỉ tính khi crawl_queue có URL để thử — nguồn
                                                   -- đăng bài thưa không bị tính lỗi oan); >10 → tự chuyển
                                                   -- status=ERROR (BR-SRC-03). Cột này KHÔNG có trong thiết
                                                   -- kế BR-SRC-03 gốc, bổ sung khi code Phase 3 vì cần 1 nơi
                                                   -- lưu trạng thái đếm — Phase 3 (migration 0018)
);
```

**Business rules đầy đủ (BR-SRC):** xem [16 · Campaign Management](16-campaign-management.md).

---

## Nhóm: Chiến dịch giám sát (Campaign) — `[CHƯA CODE]`, thay thế hoàn toàn bảng `jobs`

> **Quan trọng:** đây không phải "tính năng thêm sau MVP" — mô hình "Job đơn lẻ chạy 1 lần" (bên dưới) là cách hiểu nghiệp vụ **ban đầu chưa đúng/chưa đủ** so với nhu cầu thật (giám sát liên tục, xem [01 · Project Overview](01-project-overview.md)). `campaigns` là mô hình đúng, `jobs` sẽ bị xóa hẳn khi migrate — không giữ 2 hệ thống song song. Business rules đầy đủ (BR-CAMP): xem [16 · Campaign Management](16-campaign-management.md).

```sql
CREATE TABLE campaigns (
    campaign_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(50) UNIQUE,
    name            VARCHAR(500) NOT NULL,
    description     TEXT,
    objective       TEXT,
    owner_id        UUID REFERENCES users(user_id) ON DELETE RESTRICT,
    status          VARCHAR(50) DEFAULT 'DRAFT',      -- DRAFT|ACTIVE|PAUSED|COMPLETED|ARCHIVED
    mode            VARCHAR(20) DEFAULT 'CONTINUOUS', -- CONTINUOUS|ONE_SHOT — ONE_SHOT thay thế
                                                        -- hoàn toàn "Job" cũ (chọn nguồn + khoảng ngày,
                                                        -- crawl đúng 1 lần rồi tự COMPLETED, không đăng
                                                        -- ký Celery Beat)
    start_date      TIMESTAMP NOT NULL,
    end_date        TIMESTAMP,
    alert_threshold INTEGER DEFAULT 100,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP,
    deleted_at      TIMESTAMP
);

CREATE TABLE keywords (
    keyword_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword       VARCHAR(500) NOT NULL,
    topic_group   VARCHAR(255),   -- 1 trong 8 nhóm chủ đề chuẩn (xem 07-ai-pipeline.md)
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE campaign_keywords (
    campaign_id UUID REFERENCES campaigns(campaign_id) ON DELETE RESTRICT,
    keyword_id  UUID REFERENCES keywords(keyword_id) ON DELETE RESTRICT,
    PRIMARY KEY (campaign_id, keyword_id)
);

CREATE TABLE campaign_sources (
    campaign_id UUID REFERENCES campaigns(campaign_id) ON DELETE RESTRICT,
    source_id   UUID REFERENCES sources(source_id) ON DELETE RESTRICT,
    PRIMARY KEY (campaign_id, source_id)
);

-- Kết quả so khớp từ khóa GIỮA 1 Campaign và 1 Article, tính RIÊNG cho từng Campaign ngay
-- sau khi crawl xong (không lọc ngay lúc crawl — articles vẫn lưu chung theo source_id cho
-- mọi Campaign dùng chung Nguồn đó, xem 17-continuous-crawler-scheduler.md). Content list/
-- Report/Alert của 1 Campaign chỉ tính trên các dòng ở đây. [ĐÃ CODE — Phase 3, migration 0018]
CREATE TABLE campaign_articles (
    campaign_id         UUID REFERENCES campaigns(campaign_id) ON DELETE RESTRICT,
    article_id          UUID REFERENCES articles(article_id) ON DELETE RESTRICT,
    matched_keyword_id  UUID REFERENCES keywords(keyword_id),  -- keyword_id NHỎ NHẤT trong số từ khóa
                                                                 -- trúng (campaign_keywords không có cột
                                                                 -- thứ tự khai báo — sort theo keyword_id
                                                                 -- để có tiêu chí xác định/deterministic),
                                                                 -- chỉ dùng hiển thị rút gọn ở bảng danh
                                                                 -- sách — muốn xem ĐẦY ĐỦ mọi từ khóa trúng
                                                                 -- thì dùng bảng campaign_article_keywords
    matched_at          TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (campaign_id, article_id)
);

-- Bảng phụ [ĐÃ CODE — Phase 3, migration 0018, KHÔNG có trong thiết kế rule gốc] — lưu ĐẦY ĐỦ
-- mọi từ khóa trúng cho 1 cặp (Campaign, Article), không chỉ 1 (khác với matched_keyword_id ở
-- trên chỉ lưu 1 giá trị tham khảo). Dùng cho Content Detail (Phase 4) hiện đủ tag từ khóa.
CREATE TABLE campaign_article_keywords (
    campaign_id UUID NOT NULL,
    article_id  UUID NOT NULL,
    keyword_id  UUID NOT NULL REFERENCES keywords(keyword_id),
    PRIMARY KEY (campaign_id, article_id, keyword_id),
    FOREIGN KEY (campaign_id, article_id) REFERENCES campaign_articles(campaign_id, article_id)
);
```

### Bảng `jobs` — `[ĐÃ CODE — sẽ bị XÓA khi migrate sang campaigns]`

```sql
CREATE TABLE jobs (
    job_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_ids      UUID[] NOT NULL,
    date_from       DATE NOT NULL,
    date_to         DATE NOT NULL,
    status          VARCHAR(50) DEFAULT 'pending', -- pending|running|completed|failed|cancelled
    output_docx     TEXT,                          -- Đường dẫn file .docx
    output_json     TEXT,                          -- Đường dẫn file .json
    error_log       TEXT,
    celery_task_id  VARCHAR(255),                  -- Task ID Celery thật (tự sinh trước khi
                                                     -- gọi apply_async, KHÔNG suy ra từ job_id)
                                                     -- — dùng để revoke khi hủy job (thêm ở
                                                     -- migration 0003, Slice 1 mở rộng)
    created_at      TIMESTAMP DEFAULT NOW(),
    completed_at    TIMESTAMP
);
```

**Đường di chuyển dữ liệu:** `jobs.source_ids UUID[]` (mảng, không FK) phải migrate sang `campaign_sources` (N:N có FK) nếu muốn giữ lịch sử report cũ liên kết được — xem rủi ro ở roadmap Phase 2.

---

## Nhóm: Bài viết thu thập được — `articles` `[ĐÃ CODE, SẼ SỬA]`

```sql
CREATE TABLE articles (
    article_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id                UUID REFERENCES jobs(job_id),        -- [SẼ XÓA] — bảng jobs không còn
                                                                  -- tồn tại sau migrate, articles
                                                                  -- không còn gắn cứng với 1 lần
                                                                  -- chạy cụ thể nào
    source_id             UUID REFERENCES sources(source_id),
    url                   TEXT NOT NULL,
    url_hash              VARCHAR(64) NOT NULL,         -- SHA256(url)
    title                 TEXT,                         -- NULL nếu status=error (crawl lỗi,
                                                          -- không lấy được title)
    content_raw           TEXT,                         -- Nội dung đã strip HTML
    author                TEXT,
    published_at          TIMESTAMP,
    crawled_at            TIMESTAMP DEFAULT NOW(),
    status                VARCHAR(50) DEFAULT 'pending_analysis', -- pending_analysis|analyzed|error
    crawl_duration_seconds FLOAT,                        -- Thời gian fetch+parse thật (giây)

    -- [CHƯA CODE] — trạng thái đánh giá NGHIỆP VỤ, tách biệt khỏi status kỹ thuật ở trên
    -- (xem BR-CONTENT ở 17-continuous-crawler-scheduler.md)
    review_status   VARCHAR(50) DEFAULT 'NEW', -- NEW|REVIEWED|NEED_VERIFY|VERIFIED|NOT_RELEVANT|CASE_CREATED
    reviewed_by     UUID REFERENCES users(user_id),
    reviewed_at     TIMESTAMP,
    reviewer_note   TEXT
);
```

**Ràng buộc UNIQUE trên `(?, url_hash)` — 2 constraint song song, KHÔNG phải 1 đổi thành 1 như thiết kế ban đầu:**
- `[ĐÃ CODE]`: composite `UNIQUE (job_id, url_hash)` (migration 0009) — dedup **trong phạm vi 1 job**, không dedup xuyên job (quyết định 2026-07-09). Dòng nào có `job_id` (do luồng Job on-demand insert) vẫn theo constraint này, không đổi gì.
- `[ĐÃ CODE — Phase 3, migration 0018]`: PARTIAL unique index `articles_source_id_url_hash_continuous_key` trên `(source_id, url_hash) WHERE job_id IS NULL` — dedup **toàn cục theo Source**, chỉ áp dụng cho dòng do continuous crawl insert (`job_id=NULL`). **Đây là sửa đổi so với thiết kế ban đầu** (rule này trước đó ghi "sau migrate: DROP COLUMN job_id, đổi thẳng thành UNIQUE(source_id, url_hash) toàn bảng") — user từ chối đổi thẳng vì sẽ buộc phải xóa hẳn `jobs` ngay (mọi FK phụ thuộc), tắt tính năng "Tạo báo cáo" on-demand cho tới khi Phase 7 xây lại. Partial index là bước đệm tương thích xuôi: khi Phase 7 xóa hẳn `jobs`, chỉ cần drop cột `job_id` + constraint cũ + đổi partial index thành index thường.

---

## Nhóm: Kết quả AI phân tích — `article_analysis` `[ĐÃ CODE, SẼ SỬA]`

```sql
CREATE TABLE article_analysis (
    analysis_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id     UUID REFERENCES articles(article_id),
    job_id         UUID REFERENCES jobs(job_id),        -- [SẼ XÓA cùng bảng jobs]
    topics         TEXT[] NOT NULL,             -- 1–N trong 8 nhóm chủ đề
    keywords       TEXT[] DEFAULT '{}',
    sentiment      VARCHAR(20),                 -- positive|neutral|negative
    emotion        VARCHAR(20),                 -- Trust|Fear|Anger|Surprise|Sadness|Happy (bảng 3.15)
    confidence     FLOAT,                       -- 0.0–1.0
    needs_review   BOOLEAN DEFAULT false,       -- true nếu confidence < 0.6
    summary        TEXT,
    prompt_version INT NOT NULL,                 -- version prompt đã sinh ra bản phân tích này
                                                   -- (backend/ai/prompts/vN.py)
    analyzed_at    TIMESTAMP DEFAULT NOW(),
    analysis_duration_seconds FLOAT               -- Thời gian gọi Ollama thật (giây)
);
```

---

## Nhóm: Crawl liên tục — `crawl_queue` `[ĐÃ CODE — Phase 3, migration 0018]`

> Hàng đợi bền, tách "khám phá URL" (rẻ, nhanh) khỏi "tải nội dung" (tốn thời gian, dễ đứt giữa chừng) — chống mất dữ liệu khi crawl bị gián đoạn. Chi tiết cơ chế: xem [17 · Continuous Crawler & Scheduler](17-continuous-crawler-scheduler.md).

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
```

---

## Nhóm: Báo cáo — `report_history` `[ĐÃ CODE, SẼ SỬA]`

```sql
CREATE TABLE report_history (
    report_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id       UUID REFERENCES jobs(job_id),   -- [SẼ ĐỔI] → campaign_id, bắt buộc NOT NULL
                                                    -- sau khi bảng jobs bị xóa hẳn
    file_path    TEXT NOT NULL,
    created_at   TIMESTAMP DEFAULT NOW()
);
```

Chi tiết định dạng xuất (PDF/Excel/CSV): xem [08 · DOCX Report](08-docx-report.md).

---

## Nhóm: Cảnh báo & Vụ việc — `[CHƯA CODE]`

> Business rules đầy đủ (BR-ALERT, BR-CASE): xem [18 · Alert & Case Management](18-alert-case-management.md).

```sql
CREATE TABLE alert_rules (
    alert_rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(255) NOT NULL,
    alert_type    VARCHAR(50) NOT NULL,   -- HIGH_ATTENTION | NEGATIVE_TREND | KEYWORD_SPIKE
    severity      VARCHAR(50) DEFAULT 'MEDIUM',
    condition_json JSONB NOT NULL,        -- vd {"confidence_gte": 0.8, "sentiment": "negative"}
    is_active     BOOLEAN DEFAULT true
);

CREATE TABLE alerts (
    alert_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     UUID REFERENCES campaigns(campaign_id) ON DELETE RESTRICT,
    article_id      UUID REFERENCES articles(article_id) ON DELETE RESTRICT,  -- nullable
    alert_rule_id   UUID REFERENCES alert_rules(alert_rule_id),
    alert_type      VARCHAR(50) NOT NULL,   -- snapshot tại thời điểm tạo
    severity        VARCHAR(50) NOT NULL,   -- snapshot tại thời điểm tạo
    title           VARCHAR(500) NOT NULL,
    description     TEXT,
    status          VARCHAR(50) DEFAULT 'NEW',  -- NEW|ACKNOWLEDGED|PROCESSING|RESOLVED|CLOSED
    acknowledged_by UUID REFERENCES users(user_id),
    acknowledged_at TIMESTAMP,
    resolved_by     UUID REFERENCES users(user_id),
    resolved_at     TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE cases (
    case_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_no       VARCHAR(100) UNIQUE,   -- format gợi ý: VV-{YYYY}-{NNNN}
    title         VARCHAR(500) NOT NULL,
    description   TEXT,
    priority      VARCHAR(50) DEFAULT 'MEDIUM',  -- LOW|MEDIUM|HIGH|CRITICAL
    status        VARCHAR(50) DEFAULT 'NEW',     -- NEW|VERIFYING|PROCESSING|RESOLVED|CLOSED
    alert_id      UUID REFERENCES alerts(alert_id),   -- nullable
    assigned_to   UUID REFERENCES users(user_id),
    assigned_org  VARCHAR(255),
    result        TEXT,
    created_by    UUID REFERENCES users(user_id) NOT NULL,
    closed_by     UUID REFERENCES users(user_id),
    closed_at     TIMESTAMP,
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP,
    deleted_at    TIMESTAMP
);

CREATE TABLE case_articles (
    case_id    UUID REFERENCES cases(case_id) ON DELETE RESTRICT,
    article_id UUID REFERENCES articles(article_id) ON DELETE RESTRICT,
    added_at   TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (case_id, article_id)
);

CREATE TABLE case_attachments (
    attachment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id       UUID REFERENCES cases(case_id) ON DELETE RESTRICT NOT NULL,
    file_name     VARCHAR(500) NOT NULL,
    file_path     TEXT NOT NULL,
    file_size     BIGINT,
    uploaded_by   UUID REFERENCES users(user_id),
    uploaded_at   TIMESTAMP DEFAULT NOW(),
    is_active     BOOLEAN DEFAULT true,
    deleted_at    TIMESTAMP
);
```

---

## Môi trường & Cấu hình

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/ngs_monitor
```
