# Phase 3 — Scheduler & Continuous Crawl Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm hạ tầng crawl liên tục theo lịch (Celery Beat theo Nguồn, hàng đợi bền `crawl_queue` 2 giai đoạn, dedup toàn cục theo Source, matching từ khóa hậu-crawl vào `campaign_articles`, AI trigger tự động theo công tắc `AI_AUTO_TRIGGER`) — theo đúng spec đã duyệt tại `docs/superpowers/specs/2026-07-20-phase3-scheduler-continuous-crawl-design.md`.

**Architecture:** 1 migration Alembic thêm 4 bảng mới (`crawl_queue`, `system_settings`, `campaign_articles`, `campaign_article_keywords`) + 4 cột mới trên `sources` + 1 partial unique index trên `articles`. Logic nghiệp vụ viết thành các hàm thuần nhận `db: Session` làm tham số (test được trực tiếp bằng fixture `db_session`, theo đúng pattern `_crawl_sources(db, job)` đã có ở `report_job.py`), bọc ngoài bởi 2 Celery task mỏng (`crawl_task`, `check_due_sources`) chỉ tự mở `SessionLocal()` — 2 task mỏng này KHÔNG unit test trực tiếp, chỉ verify qua smoke test Docker thật ở Task cuối (đúng pattern `run_report_job` hiện có không có unit test riêng). Toàn bộ parser crawl hiện có (sitemap/listing/httpx/Crawl4AI/Playwright) tái dùng nguyên xi, không sửa.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + PostgreSQL + Celery (worker + Beat) + Redis, pytest + `TestClient`, Vite + React + AntD (FE tối thiểu).

## Model Selection Policy (bắt buộc — áp dụng trước khi thực thi MỖI Task)

Trước khi bắt đầu bất kỳ Task nào, người/agent thực thi **phải tự đánh giá độ khó thật của Task đó** (không dùng máy móc 1 model cho toàn bộ plan) rồi chọn model theo đúng 1 trong 3 mức sau:

1. **Cơ học/đơn giản** (copy code đã viết sẵn đầy đủ trong Task, đổi tên biến/đường dẫn theo pattern có sẵn, không cần tự quyết định logic mới, rủi ro sai thấp) → dùng **Haiku**.
2. **Cần suy luận nghiệp vụ/thiết kế** (viết logic mới, xử lý edge case, quyết định thứ tự thực thi, việc sai sẽ khó phát hiện qua test đơn giản) → dùng **Sonnet**.
3. **Nghi ngờ cần model mạnh hơn Sonnet (Opus)** — VD Task đòi hỏi suy luận nhiều bước phức tạp bất thường so với phần còn lại của plan, hoặc rủi ro cao nếu làm sai (ảnh hưởng dữ liệu thật, đảo ngược khó) → **DỪNG LẠI, xin quyết định của user trước khi dùng Opus.** Không tự ý nâng cấp model lên Opus.

Mỗi Task dưới đây có dòng **Model gợi ý** dựa trên đánh giá độ khó thực tế của Task đó tại thời điểm viết plan — đây là gợi ý ban đầu để tham khảo, **không thay thế** việc tự đánh giá lại ngay trước khi thực thi (VD nếu code base đã đổi từ lúc viết plan, độ khó thực tế có thể khác). Tuyệt đối không mặc định toàn bộ 14 Task đều chạy Sonnet.

## Global Constraints

- **Không đụng `jobs`, `routers/reports.py`, `workers/report_job.py`, `report_history`, `article_analysis.job_id`, `articles.job_id`** — dữ liệu continuous crawl luôn insert với `job_id=NULL`, hoàn toàn tách biệt khỏi luồng Job on-demand đang chạy thật. Quyết định đã chốt với user (2026-07-20): không xóa/sửa `jobs` ở Phase 3 (dời qua Phase 7).
- **Dedup continuous crawl dùng PARTIAL unique index** `articles_source_id_url_hash_continuous_key` trên `(source_id, url_hash) WHERE job_id IS NULL` — KHÔNG đổi `UNIQUE(job_id, url_hash)` hiện có (migration 0009), không đụng hành vi dedup của Job cũ.
- **`SCHEDULER_ENABLED` và `AI_AUTO_TRIGGER` mặc định `'false'`** khi seed — Beat/AI không tự chạy cho tới khi ADMIN chủ động bật qua `/system/settings`.
- **Không tạo permission mới** — dùng `source.update` (PUT `/api/sources/{id}`) và `system.configure` (`/api/system-settings`) đã seed sẵn ở migration `0011`.
- **`PUT /api/sources/{id}` chỉ nhận `status` là `ACTIVE` hoặc `INACTIVE`** — không cho set `ERROR` qua API, `ERROR` chỉ do hệ thống tự set trong `fetch_pending_urls()` (BR-SRC-03).
- **`campaign_articles.matched_keyword_id` = `keyword_id` NHỎ NHẤT trong số từ khóa trúng** (sort theo `keyword_id` vì `campaign_keywords` không có cột thứ tự khai báo) — `campaign_article_keywords` lưu ĐẦY ĐỦ mọi từ khóa trúng, không chỉ 1.
- **AI phân tích theo bài (`article_id`), không theo Campaign** — `article_analysis` không có cột `campaign_id` (schema có sẵn từ rule 03), tái dùng hàm `analyze_article()` per-article đã có, không viết AI logic mới.
- **Mọi endpoint ghi dữ liệu phải gọi `log_action()`** (`backend/audit/logger.py`) — cùng pattern `routers/campaigns.py`/`routers/users.py`.
- Tiếng Việt cho mọi comment giải thích logic quan trọng, tiếng Việt cho mọi message lỗi (`HTTPException.detail`) — đúng convention toàn bộ codebase hiện có.
- Migration tiếp theo là `0018` (`down_revision = "0017"`), đặt tại `backend/alembic/versions/0018_add_scheduler_tables.py`.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `backend/alembic/versions/0018_add_scheduler_tables.py` | Migration: 4 bảng mới + 4 cột `sources` + partial unique index `articles` |
| `backend/models/crawl_queue.py` | Model `CrawlQueue` |
| `backend/models/system_settings.py` | Model `SystemSetting` |
| `backend/models/campaign_articles.py` | Model `CampaignArticle` |
| `backend/models/campaign_article_keywords.py` | Model `CampaignArticleKeyword` |
| `backend/models/sources.py` | Sửa: thêm 4 cột `crawl_frequency/last_crawled_at/status/consecutive_error_count` |
| `backend/models/__init__.py` | Sửa: export 4 model mới |
| `backend/system_settings.py` | Helper `get_setting()`/`get_bool_setting()` — dùng chung bởi router và worker |
| `backend/routers/system_settings.py` | `GET`/`PUT /api/system-settings` |
| `backend/routers/sources.py` | Sửa: thêm `PUT /api/sources/{id}`, mở rộng field trả về của `GET` |
| `backend/main.py` | Sửa: `include_router` router `system_settings` mới |
| `backend/workers/continuous_crawl.py` | `discover_source_urls()`, `fetch_pending_urls()`, `match_campaigns_for_article()`, `maybe_analyze_article()`, Celery task `crawl_task` |
| `backend/workers/scheduler.py` | `list_due_sources()`, Celery Beat task `check_due_sources` |
| `backend/workers/celery_app.py` | Sửa: đăng ký `beat_schedule`, import 2 module worker mới |
| `docker-compose.yml` | Sửa: thêm service `celery-beat` |
| `frontend/src/pages/Sources/SourceEditModal.tsx` | Modal sửa `source_group`/`crawl_frequency`/`status` |
| `frontend/src/pages/Sources/index.tsx` | Sửa: bật nút "Sửa", mở `SourceEditModal` |
| `frontend/src/pages/System/Settings/index.tsx` | Sửa: thêm Card "Giám sát liên tục" nối API thật |
| `backend/tests/test_system_settings.py` | Test `backend/system_settings.py` |
| `backend/tests/test_system_settings_router.py` | Test router `system_settings.py` |
| `backend/tests/test_sources_router.py` | Sửa: thêm test `PUT /api/sources/{id}` |
| `backend/tests/test_continuous_crawl.py` | Test `discover_source_urls`/`fetch_pending_urls`/`match_campaigns_for_article`/`maybe_analyze_article` |
| `backend/tests/test_scheduler.py` | Test `list_due_sources` |

---

## Task 1: Migration — 4 bảng mới + cột lịch crawl trên `sources` + partial unique index `articles`

**Model gợi ý:** Haiku — cơ học — copy nguyên schema đúng pattern migration 0017 đã có, không cần quyết định thiết kế mới. (Tự đánh giá lại trước khi thực thi — xem "Model Selection Policy" ở đầu file.)

**Files:**
- Create: `backend/alembic/versions/0018_add_scheduler_tables.py`

**Interfaces:**
- Produces: bảng `crawl_queue(queue_id, source_id, url, url_hash, status, retry_count, discovered_at, fetched_at)`, `system_settings(setting_key, setting_value, data_type, description, updated_at, updated_by)` (seed sẵn 2 dòng `SCHEDULER_ENABLED='false'`, `AI_AUTO_TRIGGER='false'`), `campaign_articles(campaign_id, article_id, matched_keyword_id, matched_at)`, `campaign_article_keywords(campaign_id, article_id, keyword_id)`; cột `sources.crawl_frequency/last_crawled_at/status/consecutive_error_count`; index `articles_source_id_url_hash_continuous_key`.

- [ ] **Step 1: Viết migration**

```python
"""thêm bảng crawl_queue/system_settings/campaign_articles/campaign_article_keywords
+ cột lịch crawl trên sources + partial unique index articles cho Phase 3
Scheduler & Continuous Crawl

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sources", sa.Column("crawl_frequency", sa.Integer, server_default="1800"))
    op.add_column("sources", sa.Column("last_crawled_at", sa.TIMESTAMP))
    op.add_column("sources", sa.Column("status", sa.String(30), server_default="ACTIVE"))
    op.add_column("sources", sa.Column("consecutive_error_count", sa.Integer, server_default="0"))

    op.create_table(
        "crawl_queue",
        sa.Column("queue_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("sources.source_id", ondelete="RESTRICT")),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("discovered_at", sa.TIMESTAMP, server_default=sa.text("now()")),
        sa.Column("fetched_at", sa.TIMESTAMP),
        sa.UniqueConstraint("source_id", "url_hash", name="crawl_queue_source_id_url_hash_key"),
    )

    op.create_table(
        "system_settings",
        sa.Column("setting_key", sa.String(255), primary_key=True),
        sa.Column("setting_value", sa.Text),
        sa.Column("data_type", sa.String(50)),
        sa.Column("description", sa.Text),
        sa.Column("updated_at", sa.TIMESTAMP),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.user_id")),
    )
    op.execute(
        """
        INSERT INTO system_settings (setting_key, setting_value, data_type, description) VALUES
        ('SCHEDULER_ENABLED', 'false', 'BOOLEAN', 'Bật/tắt Celery Beat tự động crawl liên tục theo Campaign ACTIVE'),
        ('AI_AUTO_TRIGGER', 'false', 'BOOLEAN', 'Tự động chạy AI phân tích ngay sau khi crawl xong 1 bài')
        """
    )

    op.create_table(
        "campaign_articles",
        sa.Column(
            "campaign_id", UUID(as_uuid=True),
            sa.ForeignKey("campaigns.campaign_id", ondelete="RESTRICT"), primary_key=True,
        ),
        sa.Column(
            "article_id", UUID(as_uuid=True),
            sa.ForeignKey("articles.article_id", ondelete="RESTRICT"), primary_key=True,
        ),
        sa.Column("matched_keyword_id", UUID(as_uuid=True), sa.ForeignKey("keywords.keyword_id")),
        sa.Column("matched_at", sa.TIMESTAMP, server_default=sa.text("now()")),
    )

    op.create_table(
        "campaign_article_keywords",
        sa.Column("campaign_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("article_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "keyword_id", UUID(as_uuid=True),
            sa.ForeignKey("keywords.keyword_id"), primary_key=True,
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "article_id"],
            ["campaign_articles.campaign_id", "campaign_articles.article_id"],
            name="campaign_article_keywords_campaign_article_fkey",
        ),
    )

    op.create_index(
        "articles_source_id_url_hash_continuous_key",
        "articles",
        ["source_id", "url_hash"],
        unique=True,
        postgresql_where=sa.text("job_id IS NULL"),
    )


def downgrade():
    op.drop_index("articles_source_id_url_hash_continuous_key", table_name="articles")
    op.drop_table("campaign_article_keywords")
    op.drop_table("campaign_articles")
    op.drop_table("system_settings")
    op.drop_table("crawl_queue")
    op.drop_column("sources", "consecutive_error_count")
    op.drop_column("sources", "status")
    op.drop_column("sources", "last_crawled_at")
    op.drop_column("sources", "crawl_frequency")
```

- [ ] **Step 2: Chạy migration trên DB dev thật**

Run: `cd backend && alembic upgrade head`
Expected: log hiện `Running upgrade 0017 -> 0018`, không lỗi.

- [ ] **Step 3: Verify round-trip (downgrade rồi upgrade lại)**

Run: `cd backend && alembic downgrade -1 && alembic upgrade head`
Expected: cả 2 lệnh chạy không lỗi — xác nhận `downgrade()` viết đúng, không sót bảng/cột/index nào chưa drop.

- [ ] **Step 4: Verify bằng psql**

Run: `docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT setting_key, setting_value FROM system_settings;"`
Expected: 2 dòng `SCHEDULER_ENABLED | false` và `AI_AUTO_TRIGGER | false`.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0018_add_scheduler_tables.py
git commit -m "feat: thêm migration schema Phase 3 (crawl_queue/system_settings/campaign_articles/campaign_article_keywords + cột lịch crawl sources + partial unique index articles)"
```

---

## Task 2: SQLAlchemy Models

**Model gợi ý:** Haiku — cơ học — copy model đúng pattern các model hiện có (Campaign/Keyword...). (Tự đánh giá lại trước khi thực thi — xem "Model Selection Policy" ở đầu file.)

**Files:**
- Create: `backend/models/crawl_queue.py`
- Create: `backend/models/system_settings.py`
- Create: `backend/models/campaign_articles.py`
- Create: `backend/models/campaign_article_keywords.py`
- Modify: `backend/models/sources.py`
- Modify: `backend/models/__init__.py`
- Test: `backend/tests/test_scheduler_models.py`

**Interfaces:**
- Produces: `CrawlQueue`, `SystemSetting`, `CampaignArticle`, `CampaignArticleKeyword` (import từ `backend.models`); `Source.crawl_frequency`, `Source.last_crawled_at`, `Source.status`, `Source.consecutive_error_count`.

- [ ] **Step 1: Viết test cho các model mới (sẽ fail vì model chưa tồn tại)**

```python
# backend/tests/test_scheduler_models.py
import uuid

from backend.models import (
    Campaign,
    CampaignArticle,
    CampaignArticleKeyword,
    CrawlQueue,
    Keyword,
    Source,
    SystemSetting,
)


def test_crawl_queue_model_roundtrip(db_session):
    source = Source(name="X", domain=f"x-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.flush()

    row = CrawlQueue(source_id=source.source_id, url="https://x.example/a", url_hash="hash1")
    db_session.add(row)
    db_session.commit()

    fetched = db_session.query(CrawlQueue).filter_by(url_hash="hash1").one()
    assert fetched.status == "pending"
    assert fetched.retry_count == 0


def test_system_setting_model_roundtrip(db_session):
    row = db_session.query(SystemSetting).filter_by(setting_key="SCHEDULER_ENABLED").first()
    assert row is not None
    assert row.setting_value == "false"


def test_source_has_scheduler_columns_with_defaults(db_session):
    source = Source(name="Y", domain=f"y-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.commit()

    assert source.crawl_frequency == 1800
    assert source.status == "ACTIVE"
    assert source.consecutive_error_count == 0
    assert source.last_crawled_at is None


def test_campaign_article_and_keyword_bridge_roundtrip(db_session):
    source = Source(name="Z", domain=f"z-{uuid.uuid4()}.example", group_name="G", is_active=True)
    campaign = Campaign(name="C1", start_date="2026-08-01")
    keyword = Keyword(keyword="lừa đảo")
    db_session.add_all([source, campaign, keyword])
    db_session.flush()

    from backend.models import Article

    article = Article(source_id=source.source_id, url="https://z.example/a", url_hash="hash2")
    db_session.add(article)
    db_session.flush()

    db_session.add(
        CampaignArticle(campaign_id=campaign.campaign_id, article_id=article.article_id, matched_keyword_id=keyword.keyword_id)
    )
    db_session.add(
        CampaignArticleKeyword(campaign_id=campaign.campaign_id, article_id=article.article_id, keyword_id=keyword.keyword_id)
    )
    db_session.commit()

    ca = db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id).one()
    assert ca.article_id == article.article_id
    cak = db_session.query(CampaignArticleKeyword).filter_by(campaign_id=campaign.campaign_id).one()
    assert cak.keyword_id == keyword.keyword_id
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_scheduler_models.py -v`
Expected: FAIL với `ImportError: cannot import name 'CrawlQueue'` (hoặc tương tự cho `SystemSetting`/`CampaignArticle`/`CampaignArticleKeyword`).

- [ ] **Step 3: Viết model `CrawlQueue`**

```python
# backend/models/crawl_queue.py
import uuid

from sqlalchemy import Column, ForeignKey, Integer, String, TIMESTAMP, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class CrawlQueue(Base):
    __tablename__ = "crawl_queue"
    __table_args__ = (UniqueConstraint("source_id", "url_hash", name="crawl_queue_source_id_url_hash_key"),)

    queue_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.source_id"))
    url = Column(Text, nullable=False)
    url_hash = Column(String(64), nullable=False)
    status = Column(String(20), server_default="pending")
    retry_count = Column(Integer, server_default="0")
    discovered_at = Column(TIMESTAMP, server_default=func.now())
    fetched_at = Column(TIMESTAMP)
```

- [ ] **Step 4: Viết model `SystemSetting`**

```python
# backend/models/system_settings.py
from sqlalchemy import Column, ForeignKey, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID

from backend.db import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    setting_key = Column(String(255), primary_key=True)
    setting_value = Column(Text)
    data_type = Column(String(50))
    description = Column(Text)
    updated_at = Column(TIMESTAMP)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
```

- [ ] **Step 5: Viết model `CampaignArticle` và `CampaignArticleKeyword`**

```python
# backend/models/campaign_articles.py
from sqlalchemy import Column, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class CampaignArticle(Base):
    __tablename__ = "campaign_articles"

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.campaign_id"), primary_key=True)
    article_id = Column(UUID(as_uuid=True), ForeignKey("articles.article_id"), primary_key=True)
    matched_keyword_id = Column(UUID(as_uuid=True), ForeignKey("keywords.keyword_id"))
    matched_at = Column(TIMESTAMP, server_default=func.now())
```

```python
# backend/models/campaign_article_keywords.py
from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID

from backend.db import Base


class CampaignArticleKeyword(Base):
    __tablename__ = "campaign_article_keywords"
    __table_args__ = (
        ForeignKeyConstraint(
            ["campaign_id", "article_id"],
            ["campaign_articles.campaign_id", "campaign_articles.article_id"],
            name="campaign_article_keywords_campaign_article_fkey",
        ),
    )

    campaign_id = Column(UUID(as_uuid=True), primary_key=True)
    article_id = Column(UUID(as_uuid=True), primary_key=True)
    keyword_id = Column(UUID(as_uuid=True), ForeignKey("keywords.keyword_id"), primary_key=True)
```

- [ ] **Step 6: Thêm 4 cột mới vào model `Source`**

Modify `backend/models/sources.py` — thêm ngay sau dòng `is_active = Column(Boolean, server_default="true")`:

```python
    crawl_frequency = Column(Integer, server_default="1800")
    last_crawled_at = Column(TIMESTAMP)
    status = Column(String(30), server_default="ACTIVE")
    consecutive_error_count = Column(Integer, server_default="0")
```

Và sửa dòng import đầu file từ:
```python
from sqlalchemy import Boolean, Column, String, TIMESTAMP
```
thành:
```python
from sqlalchemy import Boolean, Column, Integer, String, TIMESTAMP
```

- [ ] **Step 7: Đăng ký export trong `backend/models/__init__.py`**

Thêm import và `__all__`:

```python
from backend.models.campaign_article_keywords import CampaignArticleKeyword
from backend.models.campaign_articles import CampaignArticle
from backend.models.crawl_queue import CrawlQueue
from backend.models.system_settings import SystemSetting
```

Thêm vào `__all__`: `"CrawlQueue"`, `"SystemSetting"`, `"CampaignArticle"`, `"CampaignArticleKeyword"`.

- [ ] **Step 8: Chạy lại test, xác nhận pass**

Run: `cd backend && pytest tests/test_scheduler_models.py -v`
Expected: PASS toàn bộ 4 test.

- [ ] **Step 9: Commit**

```bash
git add backend/models/ backend/tests/test_scheduler_models.py
git commit -m "feat: thêm SQLAlchemy models CrawlQueue/SystemSetting/CampaignArticle/CampaignArticleKeyword + cột lịch crawl trên Source"
```

---

## Task 3: Helper `backend/system_settings.py`

**Model gợi ý:** Haiku — cơ học — 2 hàm nhỏ, logic tuyến tính, không có nhánh phức tạp. (Tự đánh giá lại trước khi thực thi — xem "Model Selection Policy" ở đầu file.)

**Files:**
- Create: `backend/system_settings.py`
- Test: `backend/tests/test_system_settings.py`

**Interfaces:**
- Consumes: `SystemSetting` (Task 2).
- Produces: `get_setting(db: Session, key: str) -> str | None`, `get_bool_setting(db: Session, key: str, default: bool = False) -> bool` — dùng ở Task 4 (router) và Task 9/11 (worker).

- [ ] **Step 1: Viết test**

```python
# backend/tests/test_system_settings.py
from backend.system_settings import get_bool_setting, get_setting


def test_get_setting_returns_seeded_value(db_session):
    assert get_setting(db_session, "SCHEDULER_ENABLED") == "false"


def test_get_setting_returns_none_for_unknown_key(db_session):
    assert get_setting(db_session, "KHONG_TON_TAI") is None


def test_get_bool_setting_parses_true_false(db_session):
    from backend.models import SystemSetting

    db_session.query(SystemSetting).filter_by(setting_key="AI_AUTO_TRIGGER").update({"setting_value": "true"})
    db_session.commit()

    assert get_bool_setting(db_session, "AI_AUTO_TRIGGER") is True
    assert get_bool_setting(db_session, "SCHEDULER_ENABLED") is False


def test_get_bool_setting_returns_default_for_unknown_key(db_session):
    assert get_bool_setting(db_session, "KHONG_TON_TAI", default=True) is True
    assert get_bool_setting(db_session, "KHONG_TON_TAI", default=False) is False
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_system_settings.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'backend.system_settings'`.

- [ ] **Step 3: Viết implementation**

```python
# backend/system_settings.py
from sqlalchemy.orm import Session

from backend.models import SystemSetting


def get_setting(db: Session, key: str) -> str | None:
    row = db.get(SystemSetting, key)
    return row.setting_value if row else None


def get_bool_setting(db: Session, key: str, default: bool = False) -> bool:
    value = get_setting(db, key)
    if value is None:
        return default
    return value.lower() == "true"
```

- [ ] **Step 4: Chạy lại test, xác nhận pass**

Run: `cd backend && pytest tests/test_system_settings.py -v`
Expected: PASS toàn bộ 4 test.

- [ ] **Step 5: Commit**

```bash
git add backend/system_settings.py backend/tests/test_system_settings.py
git commit -m "feat: thêm helper get_setting/get_bool_setting cho system_settings"
```

---

## Task 4: Router `system_settings.py` — `GET`/`PUT /api/system-settings`

**Model gợi ý:** Haiku — code đã viết đầy đủ trong Task, đúng pattern router hiện có (campaigns.py) — chủ yếu chép & khớp tên. (Tự đánh giá lại trước khi thực thi — xem "Model Selection Policy" ở đầu file.)

**Files:**
- Create: `backend/routers/system_settings.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_system_settings_router.py`

**Interfaces:**
- Consumes: `SystemSetting` (Task 2), `require_permission` (`backend.auth.dependencies`), `log_action` (`backend.audit.logger`).
- Produces: `GET /api/system-settings`, `PUT /api/system-settings/{key}`.

- [ ] **Step 1: Viết test**

```python
# backend/tests/test_system_settings_router.py
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models import Role, User, UserRole
from backend.routers import system_settings


@pytest.fixture
def admin_user(db_session):
    role = db_session.query(Role).filter_by(code="ADMIN").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    user = User(username=f"admin-{uuid.uuid4()}", password_hash="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db_session.commit()
    return user


@pytest.fixture
def viewer_user(db_session):
    role = db_session.query(Role).filter_by(code="VIEWER").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    user = User(username=f"viewer-{uuid.uuid4()}", password_hash="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db_session.commit()
    return user


@pytest.fixture
def app_client(db_session, admin_user):
    app = FastAPI()
    app.include_router(system_settings.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(app)


def test_list_settings_returns_seeded_rows(app_client):
    response = app_client.get("/api/system-settings")

    assert response.status_code == 200
    keys = {s["setting_key"] for s in response.json()["settings"]}
    assert {"SCHEDULER_ENABLED", "AI_AUTO_TRIGGER"} <= keys


def test_list_settings_rejects_user_without_permission(db_session, viewer_user):
    app = FastAPI()
    app.include_router(system_settings.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: viewer_user
    client = TestClient(app)

    response = client.get("/api/system-settings")

    assert response.status_code == 403


def test_update_setting_changes_value(app_client):
    response = app_client.put("/api/system-settings/AI_AUTO_TRIGGER", json={"setting_value": "true"})

    assert response.status_code == 200
    assert response.json()["setting_value"] == "true"


def test_update_unknown_setting_returns_404(app_client):
    response = app_client.put("/api/system-settings/KHONG_TON_TAI", json={"setting_value": "true"})

    assert response.status_code == 404
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_system_settings_router.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'backend.routers.system_settings'`.

- [ ] **Step 3: Viết router**

```python
# backend/routers/system_settings.py
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.audit.logger import log_action
from backend.auth.dependencies import require_permission
from backend.db import get_db
from backend.models import SystemSetting, User

router = APIRouter(prefix="/api/system-settings", tags=["system-settings"])


@router.get("")
def list_settings(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("system", "configure")),
):
    rows = db.query(SystemSetting).order_by(SystemSetting.setting_key).all()
    return {
        "settings": [
            {
                "setting_key": r.setting_key,
                "setting_value": r.setting_value,
                "data_type": r.data_type,
                "description": r.description,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]
    }


class SettingUpdateRequest(BaseModel):
    setting_value: str


@router.put("/{key}")
def update_setting(
    key: str,
    payload: SettingUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("system", "configure")),
):
    setting = db.get(SystemSetting, key)
    if setting is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cấu hình")

    old_value = {"setting_value": setting.setting_value}
    setting.setting_value = payload.setting_value
    setting.updated_at = datetime.now(timezone.utc)
    setting.updated_by = current_user.user_id

    log_action(
        db,
        user_id=current_user.user_id,
        action="UPDATE",
        entity_type="system_setting",
        entity_id=None,
        old_value=old_value,
        new_value={"setting_value": setting.setting_value},
        request=request,
    )
    db.commit()

    return {
        "setting_key": setting.setting_key,
        "setting_value": setting.setting_value,
        "data_type": setting.data_type,
        "description": setting.description,
        "updated_at": setting.updated_at,
    }
```

- [ ] **Step 4: Đăng ký router trong `backend/main.py`**

Sửa dòng import:
```python
from backend.routers import audit_logs, auth, campaigns, keywords, reports, roles, sources, system_settings, users
```

Thêm sau `app.include_router(campaigns.router)`:
```python
app.include_router(system_settings.router)
```

- [ ] **Step 5: Chạy lại test, xác nhận pass**

Run: `cd backend && pytest tests/test_system_settings_router.py -v`
Expected: PASS toàn bộ 4 test.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/system_settings.py backend/main.py backend/tests/test_system_settings_router.py
git commit -m "feat: thêm API GET/PUT /api/system-settings"
```

---

## Task 5: Router `sources.py` — thêm `PUT /api/sources/{id}` + mở rộng `GET`

**Model gợi ý:** Haiku — tương tự Task 4 — code đã viết đầy đủ, đúng pattern router sources.py hiện có. (Tự đánh giá lại trước khi thực thi — xem "Model Selection Policy" ở đầu file.)

**Files:**
- Modify: `backend/routers/sources.py`
- Modify: `backend/tests/test_sources_router.py`

**Interfaces:**
- Produces: `PUT /api/sources/{id}` (body: `source_group?`, `crawl_frequency?`, `status?` — chỉ nhận `ACTIVE`/`INACTIVE`); `GET /api/sources` trả thêm `source_group`, `crawl_frequency`, `status`.

- [ ] **Step 1: Thêm test cho `PUT` và field mở rộng của `GET`**

Thêm vào cuối `backend/tests/test_sources_router.py`:

```python
def test_list_sources_includes_scheduler_fields(app_client, db_session):
    source = Source(
        name="Scheduled", domain=f"sched-{uuid.uuid4()}.example", group_name="G1",
        is_active=True, source_group="Báo chí", crawl_frequency=900, status="ACTIVE",
    )
    db_session.add(source)
    db_session.commit()

    try:
        response = app_client.get("/api/sources")
        body = next(s for s in response.json()["sources"] if s["name"] == "Scheduled")
        assert body["source_group"] == "Báo chí"
        assert body["crawl_frequency"] == 900
        assert body["status"] == "ACTIVE"
    finally:
        db_session.delete(source)
        db_session.commit()


def test_update_source_changes_allowed_fields(app_client, db_session):
    source = Source(name="Editable", domain=f"edit-{uuid.uuid4()}.example", group_name="G1", is_active=True)
    db_session.add(source)
    db_session.commit()

    try:
        response = app_client.put(
            f"/api/sources/{source.source_id}",
            json={"source_group": "Bộ ngành", "crawl_frequency": 3600, "status": "INACTIVE"},
        )

        assert response.status_code == 200
        assert response.json()["source_group"] == "Bộ ngành"
        assert response.json()["crawl_frequency"] == 3600
        assert response.json()["status"] == "INACTIVE"
    finally:
        db_session.delete(source)
        db_session.commit()


def test_update_source_rejects_error_status(app_client, db_session):
    source = Source(name="NoError", domain=f"noerror-{uuid.uuid4()}.example", group_name="G1", is_active=True)
    db_session.add(source)
    db_session.commit()

    try:
        response = app_client.put(f"/api/sources/{source.source_id}", json={"status": "ERROR"})

        assert response.status_code == 400
    finally:
        db_session.delete(source)
        db_session.commit()


def test_update_source_returns_404_for_unknown_id(app_client):
    response = app_client.put(f"/api/sources/{uuid.uuid4()}", json={"crawl_frequency": 1000})

    assert response.status_code == 404
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_sources_router.py -v -k "scheduler_fields or update_source"`
Expected: FAIL — `test_list_sources_includes_scheduler_fields` fail vì thiếu field trong response; `test_update_source_*` fail với 405 (chưa có route `PUT`).

- [ ] **Step 3: Viết implementation**

Thay toàn bộ nội dung `backend/routers/sources.py` bằng:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.audit.logger import log_action
from backend.auth.dependencies import require_permission
from backend.db import get_db
from backend.models import Source, User

router = APIRouter(prefix="/api/sources", tags=["sources"])

_VALID_SOURCE_STATUSES = {"ACTIVE", "INACTIVE"}


@router.get("")
def list_sources(db: Session = Depends(get_db), _user=Depends(require_permission("source", "view"))):
    # Chỉ trả nguồn active — FE dùng để render sidebar chọn nguồn (Slice 2)
    rows = db.query(Source).filter_by(is_active=True).order_by(Source.group_name, Source.name).all()
    return {
        "sources": [
            {
                "source_id": str(s.source_id),
                "name": s.name,
                "domain": s.domain,
                "group_name": s.group_name,
                "source_group": s.source_group,
                "crawl_frequency": s.crawl_frequency,
                "status": s.status,
            }
            for s in rows
        ]
    }


class SourceUpdateRequest(BaseModel):
    source_group: str | None = None
    crawl_frequency: int | None = None
    status: str | None = None


@router.put("/{source_id}")
def update_source(
    source_id: str,
    payload: SourceUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("source", "update")),
):
    try:
        source = db.get(Source, uuid.UUID(source_id))
    except ValueError:
        source = None
    if source is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nguồn")

    # Chỉ ADMIN/OPERATOR (permission source.update) được sửa, và chỉ được set
    # ACTIVE/INACTIVE thủ công — ERROR là trạng thái hệ thống tự set (BR-SRC-03),
    # không cho gán qua API để tránh nhầm lẫn với cơ chế tự động phát hiện lỗi.
    if payload.status is not None and payload.status not in _VALID_SOURCE_STATUSES:
        raise HTTPException(status_code=400, detail=f"status phải là 1 trong {_VALID_SOURCE_STATUSES}")

    old_value = {
        "source_group": source.source_group,
        "crawl_frequency": source.crawl_frequency,
        "status": source.status,
    }

    if payload.source_group is not None:
        source.source_group = payload.source_group
    if payload.crawl_frequency is not None:
        source.crawl_frequency = payload.crawl_frequency
    if payload.status is not None:
        source.status = payload.status

    log_action(
        db,
        user_id=current_user.user_id,
        action="UPDATE",
        entity_type="source",
        entity_id=source.source_id,
        old_value=old_value,
        new_value={
            "source_group": source.source_group,
            "crawl_frequency": source.crawl_frequency,
            "status": source.status,
        },
        request=request,
    )
    db.commit()

    return {
        "source_id": str(source.source_id),
        "name": source.name,
        "domain": source.domain,
        "group_name": source.group_name,
        "source_group": source.source_group,
        "crawl_frequency": source.crawl_frequency,
        "status": source.status,
    }
```

- [ ] **Step 4: Chạy lại test, xác nhận pass**

Run: `cd backend && pytest tests/test_sources_router.py -v`
Expected: PASS toàn bộ (test cũ + test mới).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/sources.py backend/tests/test_sources_router.py
git commit -m "feat: thêm API PUT /api/sources/{id}, mở rộng GET /api/sources trả field lịch crawl"
```

---

## Task 6: `discover_source_urls()` — Giai đoạn 1 (Discover)

**Model gợi ý:** Sonnet — cần hiểu đúng ngữ nghĩa ON CONFLICT DO NOTHING + lý do tái dùng _get_candidates với date range giả — sai ở đây làm sai cả dedup. (Tự đánh giá lại trước khi thực thi — xem "Model Selection Policy" ở đầu file.)

**Files:**
- Create: `backend/workers/continuous_crawl.py`
- Test: `backend/tests/test_continuous_crawl.py`

**Interfaces:**
- Consumes: `_get_candidates(source, date_from, date_to)` (tái dùng nguyên xi từ `backend.workers.report_job`), `compute_url_hash()` (`backend.crawler.article`), `CrawlQueue` (Task 2).
- Produces: `discover_source_urls(db: Session, source: Source, today: date | None = None) -> int` — trả về số URL MỚI vừa ghi vào `crawl_queue`.

- [ ] **Step 1: Viết test**

```python
# backend/tests/test_continuous_crawl.py
import uuid
from datetime import date

from backend.crawler.article import compute_url_hash
from backend.models import CrawlQueue, Source
from backend.workers.continuous_crawl import discover_source_urls


def test_discover_source_urls_inserts_new_pending_rows(db_session, monkeypatch):
    source = Source(name="X", domain=f"x-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.commit()

    fake_candidates = [{"url": "https://x.example/a", "lastmod": date(2026, 1, 1)}]
    monkeypatch.setattr(
        "backend.workers.continuous_crawl._get_candidates",
        lambda src, date_from, date_to: (fake_candidates, []),
    )

    inserted = discover_source_urls(db_session, source)

    assert inserted == 1
    rows = db_session.query(CrawlQueue).filter_by(source_id=source.source_id).all()
    assert len(rows) == 1
    assert rows[0].status == "pending"


def test_discover_source_urls_skips_already_known_url(db_session, monkeypatch):
    source = Source(name="X2", domain=f"x2-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.commit()
    existing_hash = compute_url_hash("https://x.example/a")
    db_session.add(
        CrawlQueue(source_id=source.source_id, url="https://x.example/a", url_hash=existing_hash, status="fetched")
    )
    db_session.commit()

    fake_candidates = [{"url": "https://x.example/a", "lastmod": date(2026, 1, 1)}]
    monkeypatch.setattr(
        "backend.workers.continuous_crawl._get_candidates",
        lambda src, date_from, date_to: (fake_candidates, []),
    )

    inserted = discover_source_urls(db_session, source)

    assert inserted == 0
    rows = db_session.query(CrawlQueue).filter_by(source_id=source.source_id).all()
    assert len(rows) == 1
    assert rows[0].status == "fetched"  # không bị ghi đè


def test_discover_source_urls_returns_zero_when_no_candidates(db_session, monkeypatch):
    source = Source(name="X3", domain=f"x3-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.commit()

    monkeypatch.setattr(
        "backend.workers.continuous_crawl._get_candidates",
        lambda src, date_from, date_to: ([], []),
    )

    assert discover_source_urls(db_session, source) == 0
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_continuous_crawl.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'backend.workers.continuous_crawl'`.

- [ ] **Step 3: Viết implementation**

```python
# backend/workers/continuous_crawl.py
from datetime import date

from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.crawler.article import compute_url_hash
from backend.models import CrawlQueue, Source
from backend.workers.report_job import _get_candidates

# Discover không giới hạn theo date_from/date_to như Job on-demand — lấy TOÀN BỘ URL
# hiện đang được sitemap/listing liệt kê, chống trùng đã có crawl_queue lo (ON CONFLICT
# DO NOTHING), không cần biết trước "khoảng ngày cần crawl" như mô hình Job cũ.
_DISCOVER_DATE_FROM = date(2000, 1, 1)


def discover_source_urls(db, source: Source, today: date | None = None) -> int:
    """Giai đoạn 1 (Discover): tìm URL ứng viên của nguồn (tái dùng nguyên xi
    _get_candidates của report_job.py — không đổi logic ưu tiên sitemap/listing),
    ghi vào crawl_queue. Trả về số URL MỚI vừa ghi (không tính URL đã có từ chu kỳ
    trước — ON CONFLICT DO NOTHING không ghi đè trạng thái cũ)."""
    today = today or date.today()
    candidates, _failed_locs = _get_candidates(source, _DISCOVER_DATE_FROM, today)

    if not candidates:
        return 0

    rows = [
        {
            "source_id": source.source_id,
            "url": c["url"],
            "url_hash": compute_url_hash(c["url"]),
            "status": "pending",
        }
        for c in candidates
    ]
    stmt = pg_insert(CrawlQueue).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["source_id", "url_hash"])
    result = db.execute(stmt)
    db.commit()
    return result.rowcount
```

- [ ] **Step 4: Chạy lại test, xác nhận pass**

Run: `cd backend && pytest tests/test_continuous_crawl.py -v`
Expected: PASS toàn bộ 3 test.

- [ ] **Step 5: Commit**

```bash
git add backend/workers/continuous_crawl.py backend/tests/test_continuous_crawl.py
git commit -m "feat: thêm discover_source_urls (giai đoạn 1 Discover crawl liên tục)"
```

---

## Task 7: `fetch_pending_urls()` — Giai đoạn 2 (Fetch) + BR-SRC-03

**Model gợi ý:** Sonnet — có nuance nghiệp vụ dễ làm sai nếu không hiểu rationale (consecutive_error_count chỉ tăng/reset khi pending_rows không rỗng — xem comment trong code). (Tự đánh giá lại trước khi thực thi — xem "Model Selection Policy" ở đầu file.)

**Files:**
- Modify: `backend/workers/continuous_crawl.py`
- Modify: `backend/tests/test_continuous_crawl.py`

**Interfaces:**
- Consumes: `fetch_article_dispatch()` (`backend.crawler.crawl4ai_client`), `CrawlQueue`, `Article` (Task 2/hiện có).
- Produces: `fetch_pending_urls(db: Session, source: Source) -> list[Article]` — trả về danh sách bài fetch THÀNH CÔNG trong lượt này (dùng ở Task 10 để chain sang matching/AI).

- [ ] **Step 1: Thêm test**

Thêm vào cuối `backend/tests/test_continuous_crawl.py`:

```python
from backend.models import Article
from backend.workers.continuous_crawl import fetch_pending_urls


def _make_source(db_session, name_prefix: str, **kwargs) -> Source:
    source = Source(
        name=name_prefix, domain=f"{name_prefix.lower()}-{uuid.uuid4()}.example", group_name="G",
        is_active=True, **kwargs,
    )
    db_session.add(source)
    db_session.commit()
    return source


def test_fetch_pending_urls_creates_article_and_resets_error_count(db_session, monkeypatch):
    source = _make_source(db_session, "Fetch1", consecutive_error_count=3)
    db_session.add(CrawlQueue(source_id=source.source_id, url="https://f1.example/a", url_hash="h1", status="pending"))
    db_session.commit()

    monkeypatch.setattr(
        "backend.workers.continuous_crawl.fetch_article_dispatch",
        lambda url, rules: {
            "url": url, "url_hash": "h1", "title": "Tiêu đề", "content_raw": "Nội dung",
            "author": None, "published_at": None, "crawl_duration_seconds": 0.1,
        },
    )
    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")

    fetched = fetch_pending_urls(db_session, source)

    assert len(fetched) == 1
    assert fetched[0].job_id is None
    assert fetched[0].source_id == source.source_id
    row = db_session.query(CrawlQueue).filter_by(source_id=source.source_id).one()
    assert row.status == "fetched"
    db_session.refresh(source)
    assert source.consecutive_error_count == 0
    assert source.last_crawled_at is not None


def test_fetch_pending_urls_increments_retry_then_marks_error(db_session, monkeypatch):
    source = _make_source(db_session, "Fetch2")
    db_session.add(CrawlQueue(source_id=source.source_id, url="https://f2.example/a", url_hash="h2", status="pending", retry_count=3))
    db_session.commit()

    monkeypatch.setattr("backend.workers.continuous_crawl.fetch_article_dispatch", lambda url, rules: None)
    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")
    monkeypatch.setenv("CRAWLER_MAX_RETRIES", "3")

    fetched = fetch_pending_urls(db_session, source)

    assert fetched == []
    row = db_session.query(CrawlQueue).filter_by(source_id=source.source_id).one()
    assert row.retry_count == 4
    assert row.status == "error"  # đã vượt CRAWLER_MAX_RETRIES=3


def test_fetch_pending_urls_leaves_error_count_untouched_when_nothing_pending(db_session):
    source = _make_source(db_session, "Fetch3", consecutive_error_count=5)

    fetched = fetch_pending_urls(db_session, source)

    assert fetched == []
    db_session.refresh(source)
    assert source.consecutive_error_count == 5  # không tăng, không reset — chu kỳ này đơn giản không có gì để fetch


def test_fetch_pending_urls_sets_status_error_after_11_consecutive_failed_cycles(db_session, monkeypatch):
    source = _make_source(db_session, "Fetch4", consecutive_error_count=10)
    db_session.add(CrawlQueue(source_id=source.source_id, url="https://f4.example/a", url_hash="h4", status="pending"))
    db_session.commit()

    monkeypatch.setattr("backend.workers.continuous_crawl.fetch_article_dispatch", lambda url, rules: None)
    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")
    monkeypatch.setenv("CRAWLER_MAX_RETRIES", "3")

    fetch_pending_urls(db_session, source)

    db_session.refresh(source)
    assert source.consecutive_error_count == 11
    assert source.status == "ERROR"
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_continuous_crawl.py -v -k fetch_pending_urls`
Expected: FAIL với `ImportError: cannot import name 'fetch_pending_urls'`.

- [ ] **Step 3: Viết implementation**

Thêm vào `backend/workers/continuous_crawl.py`:

```python
import os
import time
from datetime import datetime, timezone

from backend.crawler.crawl4ai_client import fetch_article_dispatch
from backend.models import Article

_CONSECUTIVE_ERROR_LIMIT = 10  # BR-SRC-03 — ngưỡng khởi điểm, chưa dựa trên dữ liệu vận hành thật


def fetch_pending_urls(db, source: Source) -> list[Article]:
    """Giai đoạn 2 (Fetch): tải nội dung mọi URL đang 'pending' của nguồn (gồm cả URL
    lỡ chu kỳ trước — đây là cơ chế tự phục hồi khi worker bị đứt giữa chừng). Trả về
    danh sách Article vừa fetch THÀNH CÔNG trong lượt này."""
    delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))
    max_retries = int(os.environ.get("CRAWLER_MAX_RETRIES", "3"))

    pending_rows = db.query(CrawlQueue).filter_by(source_id=source.source_id, status="pending").all()

    fetched_articles: list[Article] = []
    for row in pending_rows:
        try:
            parsed = fetch_article_dispatch(row.url, source.parsing_rules)
        except Exception:
            parsed = None
        time.sleep(delay_seconds)

        if parsed is None:
            row.retry_count += 1
            if row.retry_count > max_retries:
                row.status = "error"
            db.commit()
            continue

        article = Article(
            job_id=None,
            source_id=source.source_id,
            url=parsed["url"],
            url_hash=parsed["url_hash"],
            title=parsed["title"],
            content_raw=parsed["content_raw"],
            author=parsed["author"],
            published_at=parsed.get("published_at"),
            crawl_duration_seconds=parsed.get("crawl_duration_seconds"),
        )
        db.add(article)
        row.status = "fetched"
        row.fetched_at = datetime.now(timezone.utc)
        db.commit()
        fetched_articles.append(article)

    source.last_crawled_at = datetime.now(timezone.utc)
    # Chỉ tính là "chu kỳ lỗi" khi THỰC SỰ có URL để thử mà không fetch được bài nào —
    # nguồn không có bài mới trong 1 chu kỳ (pending_rows rỗng, VD nguồn đăng bài thưa)
    # KHÔNG được tính là lỗi, nếu không nguồn khỏe mạnh nhưng ít đăng bài sẽ bị tự
    # chuyển ERROR oan sau vài chu kỳ yên ắng.
    if pending_rows:
        if fetched_articles:
            source.consecutive_error_count = 0
        else:
            source.consecutive_error_count += 1
            if source.consecutive_error_count > _CONSECUTIVE_ERROR_LIMIT:
                source.status = "ERROR"
    db.commit()

    return fetched_articles
```

Thêm `CrawlQueue` vào dòng import model đã có ở đầu file (gộp với `Source`): `from backend.models import Article, CrawlQueue, Source`.

- [ ] **Step 4: Chạy lại test, xác nhận pass**

Run: `cd backend && pytest tests/test_continuous_crawl.py -v -k fetch_pending_urls`
Expected: PASS toàn bộ 4 test.

- [ ] **Step 5: Commit**

```bash
git add backend/workers/continuous_crawl.py backend/tests/test_continuous_crawl.py
git commit -m "feat: thêm fetch_pending_urls (giai đoạn 2 Fetch) + tự chuyển source ERROR theo BR-SRC-03"
```

---

## Task 8: `match_campaigns_for_article()` — matching từ khóa hậu-crawl

**Model gợi ý:** Sonnet — logic nghiệp vụ matching + quy ước sort deterministic theo keyword_id — cần hiểu đúng lý do trước khi sửa. (Tự đánh giá lại trước khi thực thi — xem "Model Selection Policy" ở đầu file.)

**Files:**
- Modify: `backend/workers/continuous_crawl.py`
- Modify: `backend/tests/test_continuous_crawl.py`

**Interfaces:**
- Consumes: `Campaign`, `CampaignSource`, `CampaignKeyword`, `Keyword`, `CampaignArticle`, `CampaignArticleKeyword`.
- Produces: `match_campaigns_for_article(db: Session, article: Article) -> None`.

- [ ] **Step 1: Thêm test**

Thêm vào cuối `backend/tests/test_continuous_crawl.py`:

```python
from backend.models import (
    Campaign,
    CampaignArticle,
    CampaignArticleKeyword,
    CampaignKeyword,
    CampaignSource,
    Keyword,
)
from backend.workers.continuous_crawl import match_campaigns_for_article


def test_match_campaigns_for_article_creates_bridge_rows_for_all_matched_keywords(db_session):
    source = _make_source(db_session, "Match1")
    campaign = Campaign(name="Chống lừa đảo", start_date="2026-08-01", status="ACTIVE")
    kw_match_1 = Keyword(keyword="lừa đảo")
    kw_match_2 = Keyword(keyword="Zalo")
    kw_no_match = Keyword(keyword="Facebook")
    db_session.add_all([campaign, kw_match_1, kw_match_2, kw_no_match])
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=kw_match_1.keyword_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=kw_match_2.keyword_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=kw_no_match.keyword_id))
    article = Article(source_id=source.source_id, url="https://m1.example/a", url_hash="hm1",
                       title="Cảnh báo lừa đảo qua Zalo", content_raw="Nội dung chi tiết")
    db_session.add(article)
    db_session.commit()

    match_campaigns_for_article(db_session, article)

    ca = db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id, article_id=article.article_id).one()
    expected_first = min([kw_match_1.keyword_id, kw_match_2.keyword_id])
    assert ca.matched_keyword_id == expected_first

    matched_keyword_ids = {
        row.keyword_id
        for row in db_session.query(CampaignArticleKeyword).filter_by(
            campaign_id=campaign.campaign_id, article_id=article.article_id
        ).all()
    }
    assert matched_keyword_ids == {kw_match_1.keyword_id, kw_match_2.keyword_id}


def test_match_campaigns_for_article_skips_when_no_keyword_matches(db_session):
    source = _make_source(db_session, "Match2")
    campaign = Campaign(name="Không liên quan", start_date="2026-08-01", status="ACTIVE")
    kw = Keyword(keyword="an ninh mạng")
    db_session.add_all([campaign, kw])
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=kw.keyword_id))
    article = Article(source_id=source.source_id, url="https://m2.example/a", url_hash="hm2",
                       title="Tin tức thể thao", content_raw="Không liên quan gì")
    db_session.add(article)
    db_session.commit()

    match_campaigns_for_article(db_session, article)

    assert db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id).count() == 0


def test_match_campaigns_for_article_ignores_non_active_campaign(db_session):
    source = _make_source(db_session, "Match3")
    campaign = Campaign(name="Còn nháp", start_date="2026-08-01", status="DRAFT")
    kw = Keyword(keyword="lừa đảo")
    db_session.add_all([campaign, kw])
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=kw.keyword_id))
    article = Article(source_id=source.source_id, url="https://m3.example/a", url_hash="hm3",
                       title="Cảnh báo lừa đảo", content_raw="Nội dung")
    db_session.add(article)
    db_session.commit()

    match_campaigns_for_article(db_session, article)

    assert db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id).count() == 0
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_continuous_crawl.py -v -k match_campaigns`
Expected: FAIL với `ImportError: cannot import name 'match_campaigns_for_article'`.

- [ ] **Step 3: Viết implementation**

Thêm vào `backend/workers/continuous_crawl.py`:

```python
from backend.models import (
    Campaign,
    CampaignArticle,
    CampaignArticleKeyword,
    CampaignKeyword,
    CampaignSource,
    Keyword,
)


def match_campaigns_for_article(db, article: Article) -> None:
    """Hậu-crawl (rule 17): với mỗi Campaign ACTIVE đang theo dõi source_id của bài này,
    so khớp TOÀN BỘ từ khóa của Campaign đó (không dừng sớm khi trúng 1 từ) — mọi từ
    khóa trúng đều được ghi vào campaign_article_keywords để FE hiện đủ (Phase 4).
    campaign_articles.matched_keyword_id chỉ lưu keyword_id NHỎ NHẤT trong số trúng —
    dùng làm giá trị tham khảo/hiển thị rút gọn, vì campaign_keywords không có cột thứ
    tự khai báo nên không có khái niệm "từ khóa đầu tiên" thật sự, phải chọn 1 tiêu chí
    sắp xếp xác định (deterministic)."""
    haystack = f"{article.title or ''} {article.content_raw or ''}".lower()

    campaign_ids = (
        db.query(CampaignSource.campaign_id)
        .join(Campaign, Campaign.campaign_id == CampaignSource.campaign_id)
        .filter(CampaignSource.source_id == article.source_id, Campaign.status == "ACTIVE")
        .all()
    )

    for (campaign_id,) in campaign_ids:
        keywords = (
            db.query(Keyword)
            .join(CampaignKeyword, CampaignKeyword.keyword_id == Keyword.keyword_id)
            .filter(CampaignKeyword.campaign_id == campaign_id)
            .order_by(Keyword.keyword_id)
            .all()
        )
        matched = [k for k in keywords if k.keyword.lower() in haystack]
        if not matched:
            continue

        db.add(
            CampaignArticle(
                campaign_id=campaign_id, article_id=article.article_id, matched_keyword_id=matched[0].keyword_id
            )
        )
        for k in matched:
            db.add(CampaignArticleKeyword(campaign_id=campaign_id, article_id=article.article_id, keyword_id=k.keyword_id))
        db.commit()
```

- [ ] **Step 4: Chạy lại test, xác nhận pass**

Run: `cd backend && pytest tests/test_continuous_crawl.py -v -k match_campaigns`
Expected: PASS toàn bộ 3 test.

- [ ] **Step 5: Commit**

```bash
git add backend/workers/continuous_crawl.py backend/tests/test_continuous_crawl.py
git commit -m "feat: thêm match_campaigns_for_article — matching từ khóa hậu-crawl vào campaign_articles/campaign_article_keywords"
```

---

## Task 9: `maybe_analyze_article()` — AI trigger theo công tắc `AI_AUTO_TRIGGER`

**Model gợi ý:** Sonnet — wiring async trong hàm đồng bộ (asyncio.run) + phân biệt lỗi ValueError/httpx.HTTPError — dễ sai nếu không cẩn thận. (Tự đánh giá lại trước khi thực thi — xem "Model Selection Policy" ở đầu file.)

**Files:**
- Modify: `backend/workers/continuous_crawl.py`
- Modify: `backend/tests/test_continuous_crawl.py`

**Interfaces:**
- Consumes: `analyze_article()` (`backend.ai.ollama_client`), `get_bool_setting()` (Task 3), `ArticleAnalysis`.
- Produces: `maybe_analyze_article(db: Session, article: Article) -> None`.

- [ ] **Step 1: Thêm test**

Thêm vào cuối `backend/tests/test_continuous_crawl.py`:

```python
from backend.models import ArticleAnalysis, SystemSetting
from backend.workers.continuous_crawl import maybe_analyze_article


def _set_ai_auto_trigger(db_session, value: str):
    db_session.query(SystemSetting).filter_by(setting_key="AI_AUTO_TRIGGER").update({"setting_value": value})
    db_session.commit()


def test_maybe_analyze_article_does_nothing_when_trigger_disabled(db_session):
    source = _make_source(db_session, "AI1")
    article = Article(source_id=source.source_id, url="https://ai1.example/a", url_hash="hai1", status="pending_analysis")
    db_session.add(article)
    _set_ai_auto_trigger(db_session, "false")

    maybe_analyze_article(db_session, article)

    assert article.status == "pending_analysis"
    assert db_session.query(ArticleAnalysis).filter_by(article_id=article.article_id).count() == 0


def test_maybe_analyze_article_saves_analysis_when_trigger_enabled(db_session, monkeypatch):
    source = _make_source(db_session, "AI2")
    article = Article(source_id=source.source_id, url="https://ai2.example/a", url_hash="hai2",
                       title="Tiêu đề", content_raw="Nội dung", status="pending_analysis")
    db_session.add(article)
    _set_ai_auto_trigger(db_session, "true")

    async def fake_analyze_article(title, content, client=None):
        return {
            "topics": ["Tin giả và thông tin sai lệch"], "keywords": ["a"], "sentiment": "negative",
            "emotion": "Fear", "confidence": 0.9, "needs_review": False, "summary": "tóm tắt",
            "prompt_version": 1, "ai_model": "qwen3:8b", "analysis_duration_seconds": 0.5,
        }

    monkeypatch.setattr("backend.workers.continuous_crawl.analyze_article", fake_analyze_article)

    maybe_analyze_article(db_session, article)

    assert article.status == "analyzed"
    analysis = db_session.query(ArticleAnalysis).filter_by(article_id=article.article_id).one()
    assert analysis.job_id is None
    assert analysis.sentiment == "negative"


def test_maybe_analyze_article_marks_error_on_ai_failure(db_session, monkeypatch):
    source = _make_source(db_session, "AI3")
    article = Article(source_id=source.source_id, url="https://ai3.example/a", url_hash="hai3",
                       title="X", content_raw="Y", status="pending_analysis")
    db_session.add(article)
    _set_ai_auto_trigger(db_session, "true")

    async def failing_analyze_article(title, content, client=None):
        raise ValueError("JSON không hợp lệ")

    monkeypatch.setattr("backend.workers.continuous_crawl.analyze_article", failing_analyze_article)

    maybe_analyze_article(db_session, article)

    assert article.status == "error"
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_continuous_crawl.py -v -k maybe_analyze`
Expected: FAIL với `ImportError: cannot import name 'maybe_analyze_article'`.

- [ ] **Step 3: Viết implementation**

Thêm vào `backend/workers/continuous_crawl.py`:

```python
import asyncio

import httpx

from backend.ai.ollama_client import analyze_article
from backend.models import ArticleAnalysis
from backend.system_settings import get_bool_setting


def maybe_analyze_article(db, article: Article) -> None:
    """Nếu AI_AUTO_TRIGGER=true, phân tích AI ngay cho bài NÀY (per-article, KHÔNG theo
    Campaign — kết quả AI là thuộc tính của nội dung, không đổi theo Campaign nào đang
    xem, xem lý do đầy đủ ở design spec Phase 3 mục "Vì sao AI phân tích theo bài").
    Nếu false, giữ nguyên articles.status='pending_analysis', không làm gì thêm."""
    if not get_bool_setting(db, "AI_AUTO_TRIGGER"):
        return

    try:
        result = asyncio.run(analyze_article(article.title or "", article.content_raw or ""))
    except (ValueError, httpx.HTTPError):
        article.status = "error"
        db.commit()
        return

    db.add(
        ArticleAnalysis(
            article_id=article.article_id,
            job_id=None,
            topics=result["topics"],
            keywords=result.get("keywords", []),
            sentiment=result["sentiment"],
            emotion=result["emotion"],
            confidence=result["confidence"],
            needs_review=result["needs_review"],
            summary=result.get("summary"),
            prompt_version=result["prompt_version"],
            ai_model=result["ai_model"],
            analysis_duration_seconds=result.get("analysis_duration_seconds"),
        )
    )
    article.status = "analyzed"
    db.commit()
```

- [ ] **Step 4: Chạy lại test, xác nhận pass**

Run: `cd backend && pytest tests/test_continuous_crawl.py -v -k maybe_analyze`
Expected: PASS toàn bộ 3 test.

- [ ] **Step 5: Commit**

```bash
git add backend/workers/continuous_crawl.py backend/tests/test_continuous_crawl.py
git commit -m "feat: thêm maybe_analyze_article — AI trigger theo công tắc AI_AUTO_TRIGGER"
```

---

## Task 10: Celery task `crawl_task` — wiring toàn bộ pipeline

**Model gợi ý:** Sonnet — rủi ro import vòng lặp giữa continuous_crawl.py và celery_app.py — cần hiểu đúng thứ tự import mới không lỗi. (Tự đánh giá lại trước khi thực thi — xem "Model Selection Policy" ở đầu file.)

**Files:**
- Modify: `backend/workers/continuous_crawl.py`
- Modify: `backend/workers/celery_app.py`

**Interfaces:**
- Consumes: `discover_source_urls`, `fetch_pending_urls`, `match_campaigns_for_article`, `maybe_analyze_article` (Task 6-9), `SessionLocal` (`backend.db`).
- Produces: Celery task `crawl_task` (tên đăng ký `continuous_crawl.crawl_task`), gọi qua `crawl_task.delay(source_id)`.

- [ ] **Step 1: Viết implementation (không unit test trực tiếp — task Celery mở `SessionLocal()` riêng, giống `run_report_job` trong `report_job.py` không có unit test riêng, chỉ verify qua smoke test Docker ở Task 14)**

Thêm vào `backend/workers/continuous_crawl.py`:

```python
import uuid

from backend.db import SessionLocal
from backend.workers.celery_app import celery_app


@celery_app.task(name="continuous_crawl.crawl_task")
def crawl_task(source_id: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(source_id))
        if source is None:
            return
        discover_source_urls(db, source)
        fetched_articles = fetch_pending_urls(db, source)
        for article in fetched_articles:
            match_campaigns_for_article(db, article)
            maybe_analyze_article(db, article)
    finally:
        db.close()
```

- [ ] **Step 2: Đăng ký module trong `celery_app.py`**

Sửa `backend/workers/celery_app.py`, thêm sau dòng import `report_job` hiện có:

```python
from backend.workers import continuous_crawl  # noqa: E402,F401  đăng ký task crawl_task
```

- [ ] **Step 3: Xác nhận import không lỗi (kiểm tra vòng lặp import: `continuous_crawl.py` import `celery_app`, `celery_app.py` import `continuous_crawl` — cần đặt import ở CUỐI `celery_app.py`, sau khi `celery_app` đã được khởi tạo, đúng pattern `report_job` đang dùng)**

Run: `cd backend && python -c "from backend.workers.celery_app import celery_app; print(celery_app.tasks.get('continuous_crawl.crawl_task'))"`
Expected: in ra `<@task: continuous_crawl.crawl_task of ngs_monitor>` — không lỗi `ImportError`/`RecursionError`.

- [ ] **Step 4: Chạy lại toàn bộ test cũ để chắc chắn không phá vỡ gì**

Run: `cd backend && pytest tests/test_continuous_crawl.py tests/test_report_job.py -v`
Expected: PASS toàn bộ.

- [ ] **Step 5: Commit**

```bash
git add backend/workers/continuous_crawl.py backend/workers/celery_app.py
git commit -m "feat: thêm Celery task crawl_task nối Discover→Fetch→Matching→AI trigger"
```

---

## Task 11: `list_due_sources()` + Celery Beat `check_due_sources`

**Model gợi ý:** Sonnet — logic so sánh thời gian (timezone-aware) + sửa docker-compose.yml — sai timezone dễ làm Beat không bao giờ enqueue hoặc enqueue liên tục. (Tự đánh giá lại trước khi thực thi — xem "Model Selection Policy" ở đầu file.)

**Files:**
- Create: `backend/workers/scheduler.py`
- Modify: `backend/workers/celery_app.py`
- Modify: `docker-compose.yml`
- Test: `backend/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `Campaign`, `CampaignSource`, `Source` models; `get_bool_setting` (Task 3); `crawl_task` (Task 10).
- Produces: `list_due_sources(db: Session, now: datetime | None = None) -> list[Source]`; Celery Beat task `check_due_sources` (tên `scheduler.check_due_sources`), chạy mỗi 60s qua `celery_app.conf.beat_schedule`.

- [ ] **Step 1: Viết test cho `list_due_sources`**

```python
# backend/tests/test_scheduler.py
import uuid
from datetime import datetime, timedelta, timezone

from backend.models import Campaign, CampaignSource, Source
from backend.workers.scheduler import list_due_sources


def _make_campaign(db_session, status="ACTIVE"):
    campaign = Campaign(name=f"C-{uuid.uuid4()}", start_date="2026-08-01", status=status)
    db_session.add(campaign)
    db_session.flush()
    return campaign


def _make_source(db_session, **kwargs):
    source = Source(name=f"S-{uuid.uuid4()}", domain=f"s-{uuid.uuid4()}.example", group_name="G", is_active=True, **kwargs)
    db_session.add(source)
    db_session.flush()
    return source


def test_list_due_sources_includes_never_crawled_source(db_session):
    campaign = _make_campaign(db_session)
    source = _make_source(db_session, status="ACTIVE", last_crawled_at=None, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session)

    assert source.source_id in {s.source_id for s in due}


def test_list_due_sources_excludes_recently_crawled_source(db_session):
    campaign = _make_campaign(db_session)
    now = datetime.now(timezone.utc)
    source = _make_source(db_session, status="ACTIVE", last_crawled_at=now, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session, now=now + timedelta(seconds=60))

    assert source.source_id not in {s.source_id for s in due}


def test_list_due_sources_excludes_inactive_source_status(db_session):
    campaign = _make_campaign(db_session)
    source = _make_source(db_session, status="ERROR", last_crawled_at=None, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session)

    assert source.source_id not in {s.source_id for s in due}


def test_list_due_sources_excludes_source_of_non_active_campaign(db_session):
    campaign = _make_campaign(db_session, status="DRAFT")
    source = _make_source(db_session, status="ACTIVE", last_crawled_at=None, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session)

    assert source.source_id not in {s.source_id for s in due}


def test_list_due_sources_deduplicates_source_watched_by_two_active_campaigns(db_session):
    campaign_a = _make_campaign(db_session)
    campaign_b = _make_campaign(db_session)
    source = _make_source(db_session, status="ACTIVE", last_crawled_at=None, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=campaign_a.campaign_id, source_id=source.source_id))
    db_session.add(CampaignSource(campaign_id=campaign_b.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session)

    assert [s.source_id for s in due].count(source.source_id) == 1
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_scheduler.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'backend.workers.scheduler'`.

- [ ] **Step 3: Viết implementation**

```python
# backend/workers/scheduler.py
from datetime import datetime, timezone

from backend.models import Campaign, CampaignSource, Source


def list_due_sources(db, now: datetime | None = None) -> list[Source]:
    """Nguồn nào đang được ≥1 Campaign ACTIVE theo dõi, status=ACTIVE, và đã tới giờ
    crawl lại (chưa từng crawl lần nào, hoặc now - last_crawled_at >= crawl_frequency).
    DISTINCT theo source_id — 1 nguồn được nhiều Campaign ACTIVE theo dõi vẫn chỉ trả
    về đúng 1 lần, tránh Beat enqueue trùng nhiều lần trong 1 lượt quét (rule 17)."""
    now = now or datetime.now(timezone.utc)

    watched_source_ids = (
        db.query(CampaignSource.source_id)
        .join(Campaign, Campaign.campaign_id == CampaignSource.campaign_id)
        .filter(Campaign.status == "ACTIVE")
        .distinct()
        .all()
    )
    candidate_sources = (
        db.query(Source)
        .filter(Source.source_id.in_([sid for (sid,) in watched_source_ids]), Source.status == "ACTIVE")
        .all()
    )

    due = []
    for source in candidate_sources:
        if source.last_crawled_at is None:
            due.append(source)
            continue
        last_crawled = source.last_crawled_at
        if last_crawled.tzinfo is None:
            last_crawled = last_crawled.replace(tzinfo=timezone.utc)
        elapsed = (now - last_crawled).total_seconds()
        if elapsed >= source.crawl_frequency:
            due.append(source)
    return due
```

```python
# thêm vào cuối backend/workers/scheduler.py
from backend.db import SessionLocal
from backend.system_settings import get_bool_setting
from backend.workers.celery_app import celery_app
from backend.workers.continuous_crawl import crawl_task


@celery_app.task(name="scheduler.check_due_sources")
def check_due_sources() -> None:
    db = SessionLocal()
    try:
        if not get_bool_setting(db, "SCHEDULER_ENABLED"):
            return
        for source in list_due_sources(db):
            crawl_task.delay(str(source.source_id))
    finally:
        db.close()
```

- [ ] **Step 4: Chạy lại test, xác nhận pass**

Run: `cd backend && pytest tests/test_scheduler.py -v`
Expected: PASS toàn bộ 5 test.

- [ ] **Step 5: Đăng ký `beat_schedule` trong `celery_app.py`**

Sửa `backend/workers/celery_app.py` — thêm trước dòng import `report_job` cuối file:

```python
celery_app.conf.beat_schedule = {
    "check-due-sources-every-60s": {
        "task": "scheduler.check_due_sources",
        "schedule": 60.0,
    },
}

from backend.workers import scheduler  # noqa: E402,F401  đăng ký task check_due_sources
```

- [ ] **Step 6: Thêm service `celery-beat` vào `docker-compose.yml`**

Thêm sau block `celery-worker:` trong `docker-compose.yml`:

```yaml
  celery-beat:
    build:
      context: .
      dockerfile: backend/Dockerfile
    command: celery -A backend.workers.celery_app beat --loglevel=info
    env_file: .env
    volumes:
      - ./backend:/app/backend
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
```

- [ ] **Step 7: Chạy lại toàn bộ test suite để chắc chắn không phá vỡ gì**

Run: `cd backend && pytest -v`
Expected: PASS toàn bộ (test cũ + test mới của Phase 3).

- [ ] **Step 8: Commit**

```bash
git add backend/workers/scheduler.py backend/workers/celery_app.py backend/tests/test_scheduler.py docker-compose.yml
git commit -m "feat: thêm Celery Beat check_due_sources quét mỗi 60s theo Source, service celery-beat"
```

---

## Task 12: FE — Modal sửa Nguồn (`crawl_frequency`/`status`/`source_group`)

**Model gợi ý:** Haiku — code FE đã viết đầy đủ trong Task, chỉ cần chép đúng & nối vào file hiện có. (Tự đánh giá lại trước khi thực thi — xem "Model Selection Policy" ở đầu file.)

**Files:**
- Create: `frontend/src/pages/Sources/SourceEditModal.tsx`
- Modify: `frontend/src/pages/Sources/index.tsx`

**Interfaces:**
- Consumes: `PUT /api/sources/{id}` (Task 5), `authFetch` (`@/lib/api`).

- [ ] **Step 1: Viết `SourceEditModal.tsx`**

```tsx
import { useEffect } from 'react'
import { App, Modal, Form, Input, InputNumber, Select } from 'antd'
import { authFetch } from '@/lib/api'

type Source = {
  source_id: string
  name: string
  source_group: string | null
  crawl_frequency: number | null
  status: string | null
}

export default function SourceEditModal({
  source, open, onClose, onSaved,
}: {
  source: Source | null
  open: boolean
  onClose: () => void
  onSaved: () => void
}) {
  const { message } = App.useApp()
  const [form] = Form.useForm()

  useEffect(() => {
    if (source) {
      form.setFieldsValue({
        source_group: source.source_group,
        crawl_frequency_minutes: source.crawl_frequency ? Math.round(source.crawl_frequency / 60) : 30,
        status: source.status ?? 'ACTIVE',
      })
    }
  }, [source, form])

  const onFinish = async (values: { source_group?: string; crawl_frequency_minutes: number; status: string }) => {
    if (!source) return
    const res = await authFetch(`/api/sources/${source.source_id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_group: values.source_group,
        crawl_frequency: values.crawl_frequency_minutes * 60,
        status: values.status,
      }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: 'Không thể cập nhật nguồn' }))
      message.error(body.detail ?? 'Không thể cập nhật nguồn')
      return
    }
    message.success('Cập nhật nguồn thành công')
    onSaved()
    onClose()
  }

  return (
    <Modal title={`Sửa nguồn: ${source?.name ?? ''}`} open={open} onCancel={onClose} onOk={() => form.submit()} destroyOnClose>
      <Form form={form} layout="vertical" onFinish={onFinish}>
        <Form.Item name="source_group" label="Nhóm nguồn (Chính phủ/Bộ ngành/Báo chí...)">
          <Input />
        </Form.Item>
        <Form.Item
          name="crawl_frequency_minutes"
          label="Chu kỳ crawl lại (phút)"
          rules={[{ required: true, message: 'Vui lòng nhập chu kỳ crawl' }]}
        >
          <InputNumber min={5} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="status" label="Trạng thái" rules={[{ required: true }]}>
          <Select
            options={[
              { value: 'ACTIVE', label: 'Đang hoạt động' },
              { value: 'INACTIVE', label: 'Tạm dừng' },
            ]}
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}
```

- [ ] **Step 2: Nối modal vào `frontend/src/pages/Sources/index.tsx`**

Sửa `type Source` thêm field mới:
```tsx
type Source = {
  source_id: string;
  name: string;
  domain: string;
  group_name: string;
  source_group: string | null;
  crawl_frequency: number | null;
  status: string | null;
};
```

Thêm import và state:
```tsx
import SourceEditModal from "./SourceEditModal";
```
```tsx
  const [editingSource, setEditingSource] = useState<Source | null>(null);
  const reload = () => {
    setLoading(true);
    authFetch("/api/sources")
      .then((res) => (res.ok ? res.json() : { sources: [] }))
      .then((data) => setSources(data.sources ?? []))
      .catch(() => setError("Không tải được danh sách nguồn dữ liệu"))
      .finally(() => setLoading(false));
  };
```

Thay `useEffect` hiện có (gọi `reload()` thay vì lặp lại logic):
```tsx
  useEffect(() => { reload(); }, []);
```

Sửa cột "Thao tác" — bật nút "Sửa" (bỏ `disabled`, gắn `onClick`):
```tsx
    {
      title: "Thao tác",
      key: "actions",
      width: 140,
      render: (_: unknown, r: Source) => (
        <Space>
          <Tooltip title="Chưa triển khai — CRUD nguồn qua UI thuộc phạm vi Slice 6, chưa code">
            <Button type="text" icon={<ApiOutlined />} disabled />
          </Tooltip>
          <Tooltip title="Sửa nhóm nguồn / chu kỳ crawl / trạng thái">
            <Button type="text" icon={<EditOutlined />} onClick={() => setEditingSource(r)} />
          </Tooltip>
        </Space>
      ),
    },
```

Thêm modal vào cuối JSX, ngay trước `</div>` đóng component:
```tsx
      <SourceEditModal
        source={editingSource}
        open={editingSource !== null}
        onClose={() => setEditingSource(null)}
        onSaved={reload}
      />
```

- [ ] **Step 3: Chạy dev server và verify thủ công**

Run: `cd frontend && npm run dev`
Expected: mở `/sources`, bấm icon "Sửa" ở 1 dòng → modal hiện đúng giá trị hiện tại → sửa "Chu kỳ crawl lại" → bấm OK → bảng reload, không lỗi console.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Sources/
git commit -m "feat: thêm modal sửa nguồn (source_group/crawl_frequency/status) trên trang /sources"
```

---

## Task 13: FE — Card "Giám sát liên tục" trên `/system/settings`

**Model gợi ý:** Haiku — tương tự Task 12 — code đã viết đầy đủ, chép & nối. (Tự đánh giá lại trước khi thực thi — xem "Model Selection Policy" ở đầu file.)

**Files:**
- Modify: `frontend/src/pages/System/Settings/index.tsx`

**Interfaces:**
- Consumes: `GET`/`PUT /api/system-settings` (Task 4), `authFetch`.

- [ ] **Step 1: Sửa `frontend/src/pages/System/Settings/index.tsx`**

Thêm import và state đầu component (giữ nguyên 2 Card cũ, không đụng):

```tsx
import { useEffect, useState } from 'react'
import { authFetch } from '@/lib/api'
```

Thêm state + effect load + hàm toggle trong `SystemSettings()`:

```tsx
  const [schedulerEnabled, setSchedulerEnabled] = useState(false)
  const [aiAutoTrigger, setAiAutoTrigger] = useState(false)
  const [loadingSettings, setLoadingSettings] = useState(true)

  useEffect(() => {
    authFetch('/api/system-settings')
      .then((res) => (res.ok ? res.json() : { settings: [] }))
      .then((body) => {
        const settings: { setting_key: string; setting_value: string }[] = body.settings ?? []
        setSchedulerEnabled(settings.find((s) => s.setting_key === 'SCHEDULER_ENABLED')?.setting_value === 'true')
        setAiAutoTrigger(settings.find((s) => s.setting_key === 'AI_AUTO_TRIGGER')?.setting_value === 'true')
      })
      .catch(() => message.error('Không tải được cấu hình hệ thống'))
      .finally(() => setLoadingSettings(false))
  }, [])

  const updateSetting = async (key: string, value: boolean, onLocalRevert: () => void) => {
    const res = await authFetch(`/api/system-settings/${key}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ setting_value: String(value) }),
    })
    if (!res.ok) {
      message.error('Không thể cập nhật cấu hình')
      onLocalRevert()
      return
    }
    message.success('Cập nhật cấu hình thành công')
  }
```

Thêm Card mới ngay sau Card "Cài đặt crawler" (trong cùng `<Row>`, thêm 1 `<Col>` mới):

```tsx
        <Col xs={24} lg={12}>
          <Card title="Giám sát liên tục" style={{ borderRadius: 12 }}>
            <Form layout="vertical">
              <Form.Item label="Bật Celery Beat tự động crawl liên tục theo Campaign đang hoạt động">
                <Switch
                  checked={schedulerEnabled}
                  loading={loadingSettings}
                  onChange={(checked) => {
                    setSchedulerEnabled(checked)
                    updateSetting('SCHEDULER_ENABLED', checked, () => setSchedulerEnabled(!checked))
                  }}
                />
              </Form.Item>
              <Form.Item label="Tự động chạy AI phân tích ngay sau khi crawl xong 1 bài">
                <Switch
                  checked={aiAutoTrigger}
                  loading={loadingSettings}
                  onChange={(checked) => {
                    setAiAutoTrigger(checked)
                    updateSetting('AI_AUTO_TRIGGER', checked, () => setAiAutoTrigger(!checked))
                  }}
                />
              </Form.Item>
            </Form>
          </Card>
        </Col>
```

Thêm `const { message } = App.useApp()` nếu file chưa có (kiểm tra đầu component — file hiện tại chưa import `App`/`message`, cần thêm `App` vào import antd và gọi `const { message } = App.useApp()` đầu hàm `SystemSettings()`).

- [ ] **Step 2: Chạy dev server và verify thủ công**

Run: `cd frontend && npm run dev`
Expected: mở `/system/settings`, thấy Card "Giám sát liên tục" hiện đúng trạng thái 2 switch (mặc định tắt cả 2, khớp seed migration 0018) → bật 1 switch → reload trang → switch vẫn giữ trạng thái đã lưu (xác nhận gọi API thật, không phải state cục bộ).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/System/Settings/index.tsx
git commit -m "feat: thêm Card Giám sát liên tục (SCHEDULER_ENABLED/AI_AUTO_TRIGGER) trên /system/settings"
```

---

## Task 14: Verify toàn diện (bước Commit của EPCC)

**Model gợi ý:** Sonnet — cần phán đoán khi đọc log/kết quả verify thực tế (Docker, psql), không chỉ làm theo kịch bản cố định. (Tự đánh giá lại trước khi thực thi — xem "Model Selection Policy" ở đầu file.)

**Files:** không tạo file mới — chỉ chạy verify.

- [ ] **Step 1: Chạy toàn bộ test suite backend**

Run: `cd backend && pytest -v`
Expected: PASS toàn bộ, không có test nào bị skip ngoài các test đã có điều kiện skip sẵn (VD thiếu migration 0011 seed roles trên DB test — không liên quan Phase 3).

- [ ] **Step 2: Lint + type check (nếu dự án có cấu hình sẵn)**

Run: `cd backend && python -m py_compile $(git diff --name-only main -- 'backend/**/*.py')`
Expected: không lỗi cú pháp trên toàn bộ file Python đã sửa/thêm.

- [ ] **Step 3: Rebuild và khởi động toàn bộ stack qua Docker**

Run: `docker compose up -d --build`
Expected: mọi service `healthy` — đặc biệt `celery-worker` và `celery-beat` mới thêm, kiểm tra log `celery-beat` không lỗi:

Run: `docker compose logs celery-beat --tail 30`
Expected: thấy dòng `Scheduler: Sending due task check-due-sources-every-60s`.

- [ ] **Step 4: Smoke test thật — bật Scheduler cho 1 nguồn thật với chu kỳ ngắn**

Qua `/system/settings`: bật `SCHEDULER_ENABLED=true`. Qua `/sources`: chọn 1 nguồn thật đã verify job on-demand chạy tốt trước đây (VD VTV), sửa `crawl_frequency` xuống 60 (giây, nhập `1` phút ở modal). Tạo (qua API, chưa có FE) 1 Campaign `ACTIVE` có `campaign_sources` trỏ tới nguồn này và ≥1 từ khóa khớp được với ít nhất 1 bài thật của nguồn.

Run: `docker compose logs celery-beat celery-worker --tail 50 -f` (theo dõi trong ≥2 phút)
Expected: thấy `crawl_task` được enqueue và chạy, không exception.

- [ ] **Step 5: Verify dữ liệu bằng psql**

Run: `docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT status, count(*) FROM crawl_queue GROUP BY status;"`
Expected: có dòng `fetched` với `count > 0`.

Run: `docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT count(*) FROM articles WHERE job_id IS NULL;"`
Expected: `count > 0`.

Run: `docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT count(*) FROM campaign_articles;"`
Expected: `count > 0` nếu từ khóa Campaign test đã khớp được ≥1 bài thật.

- [ ] **Step 6: Xác nhận không ảnh hưởng luồng Job on-demand cũ**

Qua `/reports/create`, tạo 1 job on-demand nhỏ với đúng nguồn vừa test ở Step 4 (nguồn đã có dữ liệu `job_id=NULL` từ continuous crawl).
Expected: job chạy xong bình thường, `GET /api/reports/{job_id}/articles` trả về đúng bài crawl được trong job này — không bị ảnh hưởng bởi dữ liệu continuous crawl (partial unique index không chặn insert `(job_id, url_hash)` mới dù `(source_id, url_hash)` đã tồn tại ở dòng `job_id=NULL`).

- [ ] **Step 7: Tắt Scheduler lại sau khi verify xong (tránh crawl liên tục chạy ngoài ý muốn trong môi trường dev)**

Qua `/system/settings`: tắt `SCHEDULER_ENABLED=false`.

- [ ] **Step 8: Cập nhật CLAUDE.md**

Thêm mục "Phase 3 — Scheduler & Continuous Crawl" vào bảng "Trạng thái dự án & Quyết định quan trọng" trong `CLAUDE.md`, theo đúng format các mục Phase 1/Phase 2 đã có — liệt kê đã code gì, quyết định partial index (không xóa `jobs`), và cập nhật "Bước tiếp theo" trỏ sang Phase 4.

- [ ] **Step 9: Commit cuối**

```bash
git add CLAUDE.md
git commit -m "docs: cập nhật CLAUDE.md sau khi hoàn thành Phase 3 (Scheduler & Continuous Crawl)"
```
