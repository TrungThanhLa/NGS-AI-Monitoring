---
description: PostgreSQL schema — 5 bảng chính với full DDL
alwaysApply: true
---

# Database Schema

### Bảng `sources` — Cấu hình nguồn dữ liệu
```sql
CREATE TABLE sources (
    source_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(255) NOT NULL,        -- Tên hiển thị (VD: Báo QĐND)
    domain        VARCHAR(255) NOT NULL UNIQUE, -- VD: qdnd.vn
    group_name    VARCHAR(255) NOT NULL,        -- Nhóm kênh (VD: Bộ Quốc phòng)
    sitemap_url   TEXT,                         -- URL sitemap.xml nếu có
    listing_url   TEXT,                         -- URL trang danh sách bài (fallback)
    parsing_rules JSONB DEFAULT '{}',           -- CSS selector: {title, content, date, author}
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMP DEFAULT NOW()
);
```

### Bảng `jobs` — Trạng thái job
```sql
CREATE TABLE jobs (
    job_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_ids   UUID[] NOT NULL,
    date_from    DATE NOT NULL,
    date_to      DATE NOT NULL,
    status       VARCHAR(50) DEFAULT 'pending', -- pending|running|completed|failed
    output_docx  TEXT,                          -- Đường dẫn file .docx
    output_json  TEXT,                          -- Đường dẫn file .json
    error_log    TEXT,
    created_at   TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

### Bảng `articles` — Bài viết thu thập được
```sql
CREATE TABLE articles (
    article_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id        UUID REFERENCES jobs(job_id),
    source_id     UUID REFERENCES sources(source_id),
    url           TEXT NOT NULL,
    url_hash      VARCHAR(64) UNIQUE NOT NULL,  -- SHA256(url) — dùng để dedup
    title         TEXT,
    content_raw   TEXT,                         -- Nội dung đã strip HTML
    author        TEXT,
    published_at  TIMESTAMP,
    crawled_at    TIMESTAMP DEFAULT NOW(),
    status        VARCHAR(50) DEFAULT 'pending_analysis' -- pending_analysis|analyzed|error
);
```

### Bảng `article_analysis` — Kết quả AI phân tích
```sql
CREATE TABLE article_analysis (
    analysis_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id     UUID REFERENCES articles(article_id),
    job_id         UUID REFERENCES jobs(job_id),
    topics         TEXT[] NOT NULL,             -- 1–N trong 8 nhóm chủ đề
    keywords       TEXT[] DEFAULT '{}',
    sentiment      VARCHAR(20),                 -- positive|neutral|negative
    emotion        VARCHAR(20),                 -- Trust|Fear|Anger|Surprise|Sadness|Happy (bảng 3.15)
    confidence     FLOAT,                       -- 0.0–1.0
    needs_review   BOOLEAN DEFAULT false,       -- true nếu confidence < 0.6
    summary        TEXT,
    prompt_version INT NOT NULL,                 -- version prompt đã sinh ra bản phân tích này (backend/ai/prompts/vN.py)
    analyzed_at    TIMESTAMP DEFAULT NOW()
);
```

### Bảng `report_history` — Lịch sử báo cáo
```sql
CREATE TABLE report_history (
    report_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id       UUID REFERENCES jobs(job_id),
    file_path    TEXT NOT NULL,
    created_at   TIMESTAMP DEFAULT NOW()
);
```

---

## Môi trường & Cấu hình

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/ngs_monitor
```
