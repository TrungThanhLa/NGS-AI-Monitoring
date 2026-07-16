# NGS Monitor — Domain Model & Database Schema đề xuất

> Mô tả các entity/bảng **mới** cần thêm để hỗ trợ mô hình continuous monitoring, dựa trên 5 bảng hiện có (`sources, jobs, articles, article_analysis, report_history` — xem `.claude/rules/03-database-schema.md`). Không lặp lại các bảng hiện có trừ khi cần sửa đổi.

---

## 1. Domain Model — Entity mới & trách nhiệm

### 1.1 Domain bổ sung
1. **Identity & Access** — User, Role, Permission (hiện chưa có Auth).
2. **Campaign Management** — Campaign, Keyword, quan hệ Campaign↔Source, Campaign↔Keyword.
3. **Alert Management** — AlertRule, Alert.
4. **Case Management** — Case, CaseContent, CaseAttachment.
5. **Audit & System Config** — AuditLog, SystemSetting.

### 1.2 Aggregate Roots mới
`User`, `Campaign`, `Alert`, `Case`

| Aggregate Root | Child Entities |
|---|---|
| User | UserRole |
| Role | RolePermission |
| Campaign | CampaignKeyword, CampaignSource |
| Alert | (không có child) |
| Case | CaseContent, CaseAttachment |

### 1.3 Trách nhiệm từng Entity

- **User** — tài khoản đăng nhập hệ thống. N:N với Role.
- **Role** — vai trò (`ADMIN/MANAGER/ANALYST/OPERATOR/VIEWER`). N:N với Permission.
- **Permission** — quyền hạn dạng `resource.action`.
- **Campaign** — đơn vị giám sát trung tâm mới, có vòng đời (`DRAFT→ACTIVE→PAUSED/COMPLETED→ARCHIVED`), sở hữu bởi 1 User, theo dõi N Source và N Keyword.
- **Keyword** — từ khóa giám sát, thuộc 1 nhóm chủ đề trong 8 nhóm chuẩn hiện có.
- **AlertRule** — định nghĩa điều kiện sinh cảnh báo (lưu dạng cấu hình JSON đơn giản, không cần rule engine phức tạp ở giai đoạn đầu).
- **Alert** — cảnh báo cụ thể sinh ra, thuộc 1 Campaign, có thể gắn 1 `article` (nullable — cảnh báo tổng hợp không gắn bài cụ thể).
- **Case** — hồ sơ vụ việc điều tra, có thể gắn 1 Alert và/hoặc nhiều `articles`.
- **CaseAttachment** — file đính kèm vụ việc.
- **AuditLog** — nhật ký hành động, bất biến, không soft-delete.

### 1.4 Quan hệ tổng quan

```
User --(owner)--> Campaign --(N:N)--> Source
Campaign --(N:N)--> Keyword
Campaign --(1:N)--> Alert --(0..1)--> Article (bảng hiện có)
Alert --(0..1)--> Case --(N:N)--> Article
Case --(1:N)--> CaseAttachment
User --(1:N)--> AuditLog
```

---

## 2. Bảng mới cần thêm (migration)

### 2.1 Nhóm Identity & RBAC

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
    is_system    BOOLEAN DEFAULT true,          -- vai trò hệ thống không được xóa
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
```

### 2.2 Nhóm Campaign

```sql
CREATE TABLE campaigns (
    campaign_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(50) UNIQUE,
    name            VARCHAR(500) NOT NULL,
    description     TEXT,
    objective       TEXT,
    owner_id        UUID REFERENCES users(user_id) ON DELETE RESTRICT,
    status          VARCHAR(50) DEFAULT 'DRAFT',  -- DRAFT|ACTIVE|PAUSED|COMPLETED|ARCHIVED
    mode            VARCHAR(20) DEFAULT 'CONTINUOUS', -- CONTINUOUS|ONE_SHOT — thay thế hoàn toàn
                                                        -- bảng `jobs` cũ (đã chốt 2026-07-16, xem
                                                        -- 06_OPEN_DECISIONS.md mục 1). ONE_SHOT:
                                                        -- crawl đúng 1 lần theo start_date/end_date,
                                                        -- không đăng ký Celery Beat, tự COMPLETED
                                                        -- khi xong. CONTINUOUS: crawl lặp lại theo
                                                        -- crawl_frequency của từng Source, vô thời hạn
                                                        -- nếu end_date = NULL
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
    topic_group   VARCHAR(255),   -- 1 trong 8 nhóm chủ đề chuẩn hiện có (xem 07-ai-pipeline.md)
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
    source_id   UUID REFERENCES sources(source_id) ON DELETE RESTRICT,   -- bảng sources đã có
    PRIMARY KEY (campaign_id, source_id)
);

CREATE TABLE campaign_articles (
    -- Đã chốt 2026-07-16 (xem 06_OPEN_DECISIONS.md mục 2): kết quả so khớp từ khóa GIỮA 1
    -- Campaign và 1 Article, tính RIÊNG cho từng Campaign ngay sau khi crawl xong (không lọc
    -- ngay lúc crawl, vì articles vẫn lưu chung theo source_id cho mọi Campaign dùng chung
    -- Nguồn đó — xem 06_OPEN_DECISIONS.md mục 1). Đây là bảng xác định "bài nào thuộc phạm vi
    -- Campaign nào" — Content list/Report/Alert của 1 Campaign chỉ tính trên các dòng ở đây.
    campaign_id         UUID REFERENCES campaigns(campaign_id) ON DELETE RESTRICT,
    article_id          UUID REFERENCES articles(article_id) ON DELETE RESTRICT,
    matched_keyword_id  UUID REFERENCES keywords(keyword_id),
    matched_at          TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (campaign_id, article_id)
);
```

**Sửa bảng `sources` hiện có:** thêm cột `source_group VARCHAR(255)` (nhóm nguồn — VD "Chính phủ", "Bộ ngành", "Báo chí"), `crawl_frequency INTEGER DEFAULT 1800` (giây, dùng khi bật continuous crawl — đề xuất mặc định 30 phút cho báo điện tử, thấp hơn nhiều so với social media), `last_crawled_at TIMESTAMP`.

```sql
-- Đã chốt 2026-07-16 (xem 06_OPEN_DECISIONS.md mục 4): hàng đợi bền giữa bước "khám phá URL"
-- và "tải nội dung" — đảm bảo URL không bị mất vĩnh viễn nếu 1 lượt crawl bị đứt giữa chừng
-- (sitemap/listing của nguồn có thể đã "trôi" qua bài mới hơn ở chu kỳ crawl kế tiếp).
CREATE TABLE crawl_queue (
    queue_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id    UUID REFERENCES sources(source_id) ON DELETE RESTRICT,
    url          TEXT NOT NULL,
    url_hash     VARCHAR(64) NOT NULL,
    status       VARCHAR(20) DEFAULT 'pending',  -- pending|fetched|error
    retry_count  INTEGER DEFAULT 0,
    discovered_at TIMESTAMP DEFAULT NOW(),
    fetched_at    TIMESTAMP,
    UNIQUE (source_id, url_hash)
);
```

### 2.3 Nhóm Alert

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
    alert_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id    UUID REFERENCES campaigns(campaign_id) ON DELETE RESTRICT,
    article_id     UUID REFERENCES articles(article_id) ON DELETE RESTRICT,  -- nullable
    alert_rule_id  UUID REFERENCES alert_rules(alert_rule_id),
    alert_type     VARCHAR(50) NOT NULL,   -- snapshot tại thời điểm tạo
    severity       VARCHAR(50) NOT NULL,   -- snapshot tại thời điểm tạo
    title          VARCHAR(500) NOT NULL,
    description    TEXT,
    status         VARCHAR(50) DEFAULT 'NEW',  -- NEW|ACKNOWLEDGED|PROCESSING|RESOLVED|CLOSED
    acknowledged_by UUID REFERENCES users(user_id),
    acknowledged_at TIMESTAMP,
    resolved_by     UUID REFERENCES users(user_id),
    resolved_at     TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### 2.4 Nhóm Case

```sql
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

### 2.5 Nhóm Audit & System

```sql
CREATE TABLE audit_logs (
    audit_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID REFERENCES users(user_id),
    action       VARCHAR(100) NOT NULL,  -- CREATE|UPDATE|DELETE|APPROVE|REJECT|LOGIN|LOGOUT|EXPORT
    entity_type  VARCHAR(100),
    entity_id    UUID,
    old_value    JSONB,
    new_value    JSONB,
    ip_address   VARCHAR(100),
    user_agent   TEXT,
    created_at   TIMESTAMP DEFAULT NOW()
    -- KHÔNG có deleted_at/is_active — bảng bất biến, không soft-delete
);

CREATE TABLE system_settings (
    setting_key   VARCHAR(255) PRIMARY KEY,
    setting_value TEXT,
    data_type     VARCHAR(50),   -- STRING|INTEGER|BOOLEAN|JSON
    description   TEXT,
    updated_at    TIMESTAMP,
    updated_by    UUID REFERENCES users(user_id)
);
```

### 2.6 Sửa bảng `articles` hiện có

Thêm cột đánh giá nghiệp vụ (tách biệt với trạng thái kỹ thuật `status` hiện có):

```sql
ALTER TABLE articles ADD COLUMN review_status VARCHAR(50) DEFAULT 'NEW';
-- NEW | REVIEWED | NEED_VERIFY | VERIFIED | NOT_RELEVANT | CASE_CREATED
ALTER TABLE articles ADD COLUMN reviewed_by UUID REFERENCES users(user_id);
ALTER TABLE articles ADD COLUMN reviewed_at TIMESTAMP;
ALTER TABLE articles ADD COLUMN reviewer_note TEXT;
```

**Đổi cơ chế dedup (đã chốt 2026-07-16 — hệ quả của việc gộp Job vào Campaign + dedup toàn cục theo Source, xem `06_OPEN_DECISIONS.md` mục 1 và 4):**

```sql
ALTER TABLE articles DROP COLUMN job_id;              -- bảng `jobs` không còn tồn tại
ALTER TABLE articles DROP CONSTRAINT <tên_constraint>; -- bỏ UNIQUE (job_id, url_hash) cũ
ALTER TABLE articles ADD CONSTRAINT articles_source_url_unique UNIQUE (source_id, url_hash);
```

Hệ quả: 1 bài viết không còn gắn cứng với 1 lần chạy cụ thể nào (Job cũ hay Campaign). Khi build Report (dù `mode=ONE_SHOT` hay `CONTINUOUS`), hệ thống xác định "bài nào thuộc báo cáo này" bằng cách lọc `source_id` (qua `campaign_sources`) kết hợp khoảng ngày (`published_at` nằm trong `start_date`–`end_date` chọn lúc tạo báo cáo) — không dùng FK trực tiếp từ `articles` tới `campaigns` nữa.

---

## 3. Enum Values — tổng hợp

| Field | Enum |
|---|---|
| `users.status` | `ACTIVE, LOCKED, INACTIVE` |
| `roles.code` (seed) | `ADMIN, MANAGER, ANALYST, OPERATOR, VIEWER` |
| `campaigns.status` | `DRAFT, ACTIVE, PAUSED, COMPLETED, ARCHIVED` |
| `sources.status` (mở rộng thêm giá trị mới) | `ACTIVE, INACTIVE, ERROR` |
| `articles.review_status` (mới) | `NEW, REVIEWED, NEED_VERIFY, VERIFIED, NOT_RELEVANT, CASE_CREATED` |
| `alert_rules.alert_type` / `alerts.alert_type` | `HIGH_ATTENTION, NEGATIVE_TREND, KEYWORD_SPIKE` (mở rộng dần) |
| `alerts.severity` / `cases.priority` | `LOW, MEDIUM, HIGH, CRITICAL` |
| `alerts.status` | `NEW, ACKNOWLEDGED, PROCESSING, RESOLVED, CLOSED` |
| `cases.status` | `NEW, VERIFYING, PROCESSING, RESOLVED, CLOSED` (5 giá trị — không dùng `MONITORING`) |
| `audit_logs.action` | `CREATE, UPDATE, DELETE, APPROVE, REJECT, LOGIN, LOGOUT, EXPORT` |
| `system_settings.data_type` | `STRING, INTEGER, BOOLEAN, JSON` |

---

## 4. Nguyên tắc thiết kế áp dụng cho toàn bộ bảng mới

- **Soft-delete đầy đủ** ngay từ đầu cho mọi bảng nghiệp vụ (trừ `audit_logs`) — không để thiếu `deleted_at`/`deleted_by` rồi phải bổ sung sau.
- **ON DELETE RESTRICT** cho mọi FK — không dùng CASCADE (tránh xóa dây chuyền ngoài ý muốn), cân nhắc SET NULL cho các FK "người phụ trách" (VD `cases.assigned_to`) khi user bị vô hiệu hóa.
- **1 nguồn sự thật cho mỗi trường dữ liệu** — không để 2 bảng cùng lưu 1 giá trị (VD sentiment) mà không có cơ chế đồng bộ rõ ràng. `article_analysis` (bảng hiện có) tiếp tục là nguồn sự thật duy nhất cho kết quả AI; `articles.review_status` là nguồn sự thật duy nhất cho đánh giá của con người — không trộn 2 khái niệm này vào cùng 1 cột.
- Mọi bảng lookup (VD nhóm nguồn) nếu thêm sau này nên có FK thật trỏ tới, không dùng VARCHAR tự do không ràng buộc.
