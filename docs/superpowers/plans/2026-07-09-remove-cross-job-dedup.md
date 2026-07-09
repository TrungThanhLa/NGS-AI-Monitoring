# Bỏ dedup toàn cục theo url_hash — mỗi job crawl/phân tích độc lập

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Cập nhật sau code review (2026-07-09):** Bản plan này đã được sửa lại sau khi review phát hiện 5 rủi ro trong bản gốc. 2 thay đổi kiến trúc quan trọng nhất: (1) dùng **UNIQUE composite `(job_id, url_hash)`** thay vì bỏ hẳn UNIQUE — vẫn đạt mục tiêu chính (URL trùng được phép ở job khác) nhưng giữ được lưới an toàn DB chống trùng trong 1 job; (2) `downgrade()` tự dedupe trước khi tạo lại UNIQUE đơn, tránh crash khi rollback. Ngoài ra thêm Task 3 (cảnh báo chi phí AI khi job trùng phạm vi ngày) và bổ sung ghi chú rủi ro AI non-determinism (không đảm bảo giống hệt nhau — tiếng Anh: kết quả có thể khác nhau giữa các lần gọi) + theo dõi kích thước bảng `articles`.

**Goal:** Bỏ dedup toàn cục theo `url_hash` trong `_crawl_sources()` — mỗi job giờ crawl + phân tích AI lại từ đầu, không còn bị chặn bởi dữ liệu đã crawl từ job khác (kể cả job đã thành công). Thay UNIQUE đơn trên `url_hash` bằng UNIQUE composite `(job_id, url_hash)` — vẫn chống trùng trong phạm vi 1 job ở tầng DB, không chỉ dựa vào code application. Thêm cảnh báo (log warning) khi tạo job mới trùng phạm vi ngày/nguồn với job đã `completed`, để không ai bị bất ngờ về chi phí AI phải chạy lại.

**Architecture:** Migration `0009` xoá constraint `articles_url_hash_key` (unique đơn trên `url_hash`), thêm constraint `articles_job_id_url_hash_key` (unique composite `job_id + url_hash`) + 1 index thường trên `url_hash` để tra cứu nhanh. `downgrade()` tự dọn dữ liệu trùng trước khi tạo lại UNIQUE đơn, tránh crash khi rollback. `_crawl_sources()` (`backend/workers/report_job.py`) thay query DB toàn cục bằng 1 `set()` Python cục bộ trong phạm vi 1 lần gọi hàm (composite constraint ở DB là lưới an toàn dự phòng, không phải cơ chế chính). Đơn giản hoá hash `failed_locs` (không còn cần mẹo né UNIQUE đơn cũ). `POST /api/reports/create` (`backend/routers/reports.py`) thêm check overlap, log warning nếu job mới trùng phạm vi ngày + nguồn với job `completed` trước đó. Cập nhật 5 rule doc + CLAUDE.md để phản ánh đúng kiến trúc mới.

Xem đầy đủ bối cảnh + quyết định đã chốt tại spec: `docs/superpowers/specs/2026-07-09-remove-cross-job-dedup-design.md`. Xem review 5 rủi ro đã dẫn tới bản sửa này ở transcript review (không có file riêng — ghi tóm tắt trong bảng quyết định CLAUDE.md ở Task 5).

**Tech Stack:** Python, SQLAlchemy, Alembic, pytest, Postgres, FastAPI

---

## Mapping file → trách nhiệm sau khi sửa

| File | Thay đổi |
|---|---|
| `backend/alembic/versions/0009_add_composite_unique_articles_job_url_hash.py` | Migration mới — xoá UNIQUE đơn `url_hash`, thêm UNIQUE composite `(job_id, url_hash)` + index thường; `downgrade()` tự dedupe trước khi tạo lại UNIQUE đơn |
| `backend/models/articles.py` | `url_hash`: bỏ `unique=True`, thêm `index=True`; thêm `__table_args__` với `UniqueConstraint("job_id", "url_hash", ...)` |
| `backend/workers/report_job.py` | `_crawl_sources()`: bỏ query DB toàn cục, thêm `seen_urls` set cục bộ (composite constraint DB là lưới an toàn dự phòng); đơn giản hoá hash `failed_locs` |
| `backend/tests/test_report_job.py` | 3 test mới (2 test hành vi + 1 test xác nhận composite constraint chặn trùng trong 1 job ở tầng DB) |
| `backend/routers/reports.py` | `create_report()`: thêm check overlap (source + date range) với job `completed` trước đó, log warning nếu có |
| `backend/tests/test_reports_router.py` | 2 test mới (có overlap → log warning; không overlap → không log) |
| `.claude/rules/03-database-schema.md` | Sửa comment `url_hash` — composite UNIQUE, không phải unique đơn |
| `.claude/rules/04-business-flow.md` | Sửa mô tả bước 4 (dedup trong phạm vi 1 job) |
| `.claude/rules/06-crawler-strategy.md` | Sửa mục "Quy tắc" về dedup — set() cục bộ + composite UNIQUE DB |
| `.claude/rules/07-ai-pipeline.md` | Thêm ghi chú rủi ro: AI không đảm bảo output giống hệt nhau giữa các lần gọi khác nhau (non-determinism) |
| `.claude/rules/10-error-handling.md` | Sửa dòng "Sub-sitemap lỗi"/"Dữ liệu trùng lặp", xoá dòng "Job fail/cancel giữa lúc phân tích AI...", |
| `CLAUDE.md` | Thêm bullet "Đã hoàn thành", xoá bullet "Vấn đề cần làm rõ" về job mồ côi, thêm 2 bullet "Vấn đề cần làm rõ" mới (AI non-determinism + theo dõi kích thước bảng `articles`), cập nhật "Bước tiếp theo", thêm 3 dòng vào bảng quyết định |

---

## Task 1 — Migration `0009`: UNIQUE composite `(job_id, url_hash)` + downgrade tự dedupe

**Files:**
- Create: `backend/alembic/versions/0009_add_composite_unique_articles_job_url_hash.py`
- Modify: `backend/models/articles.py`

- [ ] **Step 1.1: Viết migration**

```python
"""composite UNIQUE (job_id, url_hash) trên articles — mỗi job crawl/phân tích độc
lập, vẫn chống trùng URL trong phạm vi 1 job ở tầng DB (không chỉ dựa vào code)

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("articles_url_hash_key", "articles", type_="unique")
    op.create_unique_constraint("articles_job_id_url_hash_key", "articles", ["job_id", "url_hash"])
    op.create_index("ix_articles_url_hash", "articles", ["url_hash"])


def downgrade():
    # Dedupe TRƯỚC khi tạo lại UNIQUE đơn trên url_hash — nếu không, lệnh
    # create_unique_constraint bên dưới sẽ crash vì lúc này DB đã có nhiều dòng
    # cùng url_hash khác job_id (đúng hành vi mong muốn sau khi upgrade chạy 1 thời
    # gian). Giữ lại đúng 1 dòng mới nhất cho mỗi url_hash (ưu tiên crawled_at lớn
    # nhất, dùng article_id làm tie-breaker khi trùng crawled_at), xoá các dòng còn
    # lại — downgrade là thao tác hiếm khi cần, chấp nhận mất dữ liệu các bản trùng
    # cũ hơn.
    op.execute(
        """
        DELETE FROM articles a
        USING articles b
        WHERE a.url_hash = b.url_hash
          AND (a.crawled_at, a.article_id) < (b.crawled_at, b.article_id)
        """
    )
    op.drop_index("ix_articles_url_hash", "articles")
    op.drop_constraint("articles_job_id_url_hash_key", "articles", type_="unique")
    op.create_unique_constraint("articles_url_hash_key", "articles", ["url_hash"])
```

- [ ] **Step 1.2: Cập nhật model**

Tìm trong `backend/models/articles.py`:
```python
import uuid

from sqlalchemy import Column, Float, ForeignKey, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class Article(Base):
    __tablename__ = "articles"

    article_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.job_id"))
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.source_id"))
    url = Column(Text, nullable=False)
    url_hash = Column(String(64), nullable=False, unique=True)
```

Thay bằng:
```python
import uuid

from sqlalchemy import Column, Float, ForeignKey, String, TIMESTAMP, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class Article(Base):
    __tablename__ = "articles"
    # Composite UNIQUE (job_id, url_hash) — không phải unique đơn trên url_hash: mỗi
    # job crawl/phân tích độc lập, cùng 1 URL có thể xuất hiện ở nhiều job khác nhau,
    # nhưng vẫn chống trùng NGAY Ở TẦNG DB nếu cùng 1 job vô tình insert trùng URL
    # (lưới an toàn dự phòng, bổ sung cho check seen_urls ở report_job.py).
    __table_args__ = (UniqueConstraint("job_id", "url_hash", name="articles_job_id_url_hash_key"),)

    article_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.job_id"))
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.source_id"))
    url = Column(Text, nullable=False)
    url_hash = Column(String(64), nullable=False, index=True)
```

- [ ] **Step 1.3: Chạy migration thật**

```bash
docker compose exec backend sh -c "cd /app/backend && alembic upgrade head"
```

- [ ] **Step 1.4: Verify DB**

```bash
docker compose exec postgres psql -U ngs -d ngs_monitor -c "\d articles"
```

Expected: mục "Indexes" hiện `"articles_job_id_url_hash_key" UNIQUE CONSTRAINT, btree (job_id, url_hash)` + `"ix_articles_url_hash" btree (url_hash)` — **không còn** dòng `"articles_url_hash_key" UNIQUE CONSTRAINT` (unique đơn cũ).

- [ ] **Step 1.5: Commit**

```bash
git add backend/alembic/versions/0009_add_composite_unique_articles_job_url_hash.py backend/models/articles.py
git commit -m "$(cat <<'EOF'
feat: đổi UNIQUE articles.url_hash sang composite (job_id, url_hash)

Chuẩn bị cho việc mỗi job crawl/phân tích AI độc lập, không còn bị chặn
bởi dữ liệu đã crawl từ job khác (kể cả job đã thành công) — xem spec
docs/superpowers/specs/2026-07-09-remove-cross-job-dedup-design.md.
Dùng composite UNIQUE thay vì bỏ hẳn constraint, để vẫn giữ lưới an
toàn DB chống trùng URL trong phạm vi 1 job. downgrade() tự dedupe
trước khi tạo lại UNIQUE đơn để tránh crash khi rollback.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — `_crawl_sources()`: bỏ check DB toàn cục, thêm check nội bộ job

**Files:**
- Modify: `backend/workers/report_job.py`
- Modify: `backend/tests/test_report_job.py`

- [ ] **Step 2.1: Thêm import + viết 3 test mới**

Tìm đầu file `backend/tests/test_report_job.py`:
```python
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.models import Article, ArticleAnalysis, Job, Source
from backend.workers.report_job import _analyze_articles, _crawl_sources
```

Thay bằng:
```python
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from backend.crawler.article import compute_url_hash
from backend.models import Article, ArticleAnalysis, Job, Source
from backend.workers.report_job import _analyze_articles, _crawl_sources
```

Thêm vào cuối file 3 test mới:
```python
def test_crawl_sources_recrawls_url_already_belonging_to_another_job(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job_a = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job_a)
    db_session.flush()

    shared_url = "https://example.test/bai-da-crawl-truoc"
    existing_article = Article(
        job_id=job_a.job_id,
        source_id=source.source_id,
        url=shared_url,
        url_hash=compute_url_hash(shared_url),
        title="Bài cũ",
        content_raw="Nội dung cũ",
        status="analyzed",
    )
    db_session.add(existing_article)
    db_session.commit()

    job_b = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job_b)
    db_session.flush()

    candidates = [{"url": shared_url, "lastmod": date(2026, 6, 1)}]

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url,
            "url_hash": compute_url_hash(url),
            "title": "Bài mới (đã crawl lại)",
            "content_raw": "Nội dung mới",
            "author": None,
            "published_at": None,
            "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job_b)

        job_b_articles = db_session.query(Article).filter_by(job_id=job_b.job_id).all()
        assert len(job_b_articles) == 1
        assert job_b_articles[0].url == shared_url
        assert job_b_articles[0].title == "Bài mới (đã crawl lại)"
    finally:
        db_session.query(Article).filter_by(job_id=job_b.job_id).delete()
        db_session.query(Article).filter_by(job_id=job_a.job_id).delete()
        db_session.delete(job_b)
        db_session.delete(job_a)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_dedups_within_same_job_when_candidates_repeat_url(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    repeated_url = "https://example.test/bai-lap-lai"
    candidates = [
        {"url": repeated_url, "lastmod": date(2026, 6, 1)},
        {"url": repeated_url, "lastmod": date(2026, 6, 1)},
    ]

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url,
            "url_hash": compute_url_hash(url),
            "title": "Title",
            "content_raw": "Content",
            "author": None,
            "published_at": None,
            "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        count = db_session.query(Article).filter_by(job_id=job.job_id).count()
        assert count == 1
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_composite_unique_constraint_blocks_duplicate_within_same_job_at_db_level(db_session):
    """Lưới an toàn dự phòng ở tầng DB — kể cả khi seen_urls (Python) có bug bỏ sót,
    UNIQUE composite (job_id, url_hash) vẫn phải chặn insert trùng trong CÙNG 1 job."""
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    url = "https://example.test/bai-trung-trong-cung-job"
    db_session.add(
        Article(job_id=job.job_id, source_id=source.source_id, url=url, url_hash=compute_url_hash(url))
    )
    db_session.commit()

    try:
        with pytest.raises(IntegrityError):
            db_session.add(
                Article(job_id=job.job_id, source_id=source.source_id, url=url, url_hash=compute_url_hash(url))
            )
            db_session.commit()
    finally:
        db_session.rollback()
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()
```

- [ ] **Step 2.2: Chạy để xác nhận đúng test nào FAIL/PASS trước khi sửa code**

```bash
docker compose exec backend pytest backend/tests/test_report_job.py -k "recrawls_url_already or dedups_within_same_job or composite_unique_constraint" -v
```

Expected: `test_crawl_sources_recrawls_url_already_belonging_to_another_job` FAIL (job B nhận được 0 bài thay vì 1, vì code hiện tại vẫn skip URL đã tồn tại). `test_crawl_sources_dedups_within_same_job_when_candidates_repeat_url` có thể PASS ngay (code hiện tại vô tình cũng chặn trùng qua DB check) — không sao, sẽ vẫn PASS sau khi sửa vì check DB được thay bằng check nội bộ tương đương. `test_composite_unique_constraint_blocks_duplicate_within_same_job_at_db_level` **phải chạy sau Task 1** (cần migration `0009` áp dụng trước, nếu không DB vẫn đang unique đơn trên `url_hash` — test này vẫn PASS tình cờ nhưng vì lý do sai; chỉ tin kết quả sau khi đã chạy Task 1).

- [ ] **Step 2.3: Sửa `_crawl_sources()` trong `backend/workers/report_job.py`**

Tìm:
```python
def _crawl_sources(db, job: Job) -> None:
    delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))
    max_articles = _parse_max_articles(os.environ.get("MAX_ARTICLES_PER_JOB"))

    def crawled_count() -> int:
        return db.query(Article).filter_by(job_id=job.job_id).count()

    for source_id in job.source_ids:
        if max_articles is not None and crawled_count() >= max_articles:
            break

        source = db.get(Source, source_id)
        try:
            candidates, failed_locs = _get_candidates(source, job.date_from, job.date_to)
        except Exception:
            logger.exception("Lỗi lấy danh sách bài viết cho nguồn %s", source.domain)
            continue

        for loc in failed_locs:
            # Hash theo job_id+url (không phải SHA256(url) như bài viết) vì url_hash UNIQUE
            # toàn cục — cùng 1 sub-sitemap/listing-page có thể lỗi lại ở job khác, nguồn khác
            db.add(
                Article(
                    job_id=job.job_id,
                    source_id=source.source_id,
                    url=loc,
                    url_hash=compute_url_hash(f"{job.job_id}:{loc}"),
                    status="error",
                )
            )
            db.commit()

        for candidate in candidates:
            if max_articles is not None and crawled_count() >= max_articles:
                break

            url_hash = compute_url_hash(candidate["url"])
            if db.query(Article).filter_by(url_hash=url_hash).first() is not None:
                continue
```

Thay bằng:
```python
def _crawl_sources(db, job: Job) -> None:
    delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))
    max_articles = _parse_max_articles(os.environ.get("MAX_ARTICLES_PER_JOB"))
    # Chỉ chống trùng URL TRONG PHẠM VI 1 lần chạy job này (không đụng DB) — một số nguồn
    # (VD sitemap index) có thể vô tình trả về cùng 1 URL 2 lần. KHÔNG chặn URL đã crawl ở
    # job khác: mỗi job crawl/phân tích độc lập, kể cả trùng URL với job trước (xem spec
    # docs/superpowers/specs/2026-07-09-remove-cross-job-dedup-design.md). UNIQUE composite
    # (job_id, url_hash) ở DB (migration 0009) là lưới an toàn dự phòng cho trường hợp check
    # này có bug bỏ sót — không phải cơ chế chính, không cần xử lý IntegrityError riêng ở đây.
    seen_urls: set[str] = set()

    def crawled_count() -> int:
        return db.query(Article).filter_by(job_id=job.job_id).count()

    for source_id in job.source_ids:
        if max_articles is not None and crawled_count() >= max_articles:
            break

        source = db.get(Source, source_id)
        try:
            candidates, failed_locs = _get_candidates(source, job.date_from, job.date_to)
        except Exception:
            logger.exception("Lỗi lấy danh sách bài viết cho nguồn %s", source.domain)
            continue

        for loc in failed_locs:
            db.add(
                Article(
                    job_id=job.job_id,
                    source_id=source.source_id,
                    url=loc,
                    url_hash=compute_url_hash(loc),
                    status="error",
                )
            )
            db.commit()

        for candidate in candidates:
            if max_articles is not None and crawled_count() >= max_articles:
                break

            if candidate["url"] in seen_urls:
                continue
            seen_urls.add(candidate["url"])
            url_hash = compute_url_hash(candidate["url"])
```

(Phần thân vòng lặp `for candidate in candidates:` bên dưới dòng `url_hash = compute_url_hash(candidate["url"])` giữ nguyên hoàn toàn — không đổi gì thêm.)

- [ ] **Step 2.4: Chạy lại test — cả 3 phải PASS**

```bash
docker compose exec backend pytest backend/tests/test_report_job.py -v
```

- [ ] **Step 2.5: Chạy toàn bộ test suite — không được regression**

```bash
docker compose exec backend pytest backend/tests/ -v
```

- [ ] **Step 2.6: Commit**

```bash
git add backend/workers/report_job.py backend/tests/test_report_job.py
git commit -m "$(cat <<'EOF'
feat: _crawl_sources không còn dedup xuyên job, chỉ dedup trong 1 job

Bỏ query DB toàn cục (đã bị chặn bởi URL đã crawl ở job khác) — thay
bằng 1 set() cục bộ chỉ sống trong phạm vi 1 lần gọi _crawl_sources(),
chống trùng khi sitemap/listing vô tình trả về cùng URL 2 lần trong
cùng 1 job. Đơn giản hoá hash failed_locs (không còn cần né UNIQUE
đơn cũ, đã đổi thành composite ở migration trước). Thêm test xác
nhận UNIQUE composite (job_id, url_hash) ở DB vẫn chặn trùng trong
cùng 1 job như lưới an toàn dự phòng.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — [MỚI] Cảnh báo chi phí AI khi tạo job trùng phạm vi ngày/nguồn với job cũ

**Bối cảnh:** Sau khi bỏ dedup xuyên job, tạo 1 job mới trùng `source_ids` + khoảng ngày với 1 job `completed` trước đó sẽ khiến toàn bộ bài viết bị crawl + phân tích AI **lại từ đầu** (đánh đổi đã được user chấp nhận). Nhưng hiện tại không có gì cảnh báo điều này — thêm log warning ở tầng backend để ít nhất có dấu vết trong log khi việc này xảy ra, làm nền cho cảnh báo ở FE sau này (ngoài phạm vi plan này).

**Files:**
- Modify: `backend/routers/reports.py`
- Modify: `backend/tests/test_reports_router.py`

- [ ] **Step 3.1: Viết 2 test mới trước**

Tìm đầu file `backend/tests/test_reports_router.py`, thêm import `caplog` không cần thiết (là fixture built-in của pytest, không cần import). Thêm vào cuối file:

```python
def test_create_logs_warning_when_overlaps_completed_job_same_source(app_client, active_source, db_session, caplog):
    existing_job = Job(
        source_ids=[active_source.source_id],
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        status="completed",
    )
    db_session.add(existing_job)
    db_session.commit()

    try:
        with patch("backend.routers.reports.run_report_job"):
            with caplog.at_level("WARNING"):
                response = app_client.post(
                    "/api/reports/create",
                    json={
                        "source_ids": [str(active_source.source_id)],
                        "date_from": "2026-06-15",
                        "date_to": "2026-07-15",
                    },
                )

        assert response.status_code == 200
        assert "trùng phạm vi" in caplog.text

        new_job_id = response.json()["job_id"]
        db_session.query(Job).filter_by(job_id=new_job_id).delete()
    finally:
        db_session.delete(existing_job)
        db_session.commit()


def test_create_does_not_log_warning_when_no_overlap(app_client, active_source, db_session, caplog):
    existing_job = Job(
        source_ids=[active_source.source_id],
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
        status="completed",
    )
    db_session.add(existing_job)
    db_session.commit()

    try:
        with patch("backend.routers.reports.run_report_job"):
            with caplog.at_level("WARNING"):
                response = app_client.post(
                    "/api/reports/create",
                    json={
                        "source_ids": [str(active_source.source_id)],
                        "date_from": "2026-06-01",
                        "date_to": "2026-06-30",
                    },
                )

        assert response.status_code == 200
        assert "trùng phạm vi" not in caplog.text

        new_job_id = response.json()["job_id"]
        db_session.query(Job).filter_by(job_id=new_job_id).delete()
    finally:
        db_session.delete(existing_job)
        db_session.commit()
```

- [ ] **Step 3.2: Chạy để xác nhận FAIL**

```bash
docker compose exec backend pytest backend/tests/test_reports_router.py -k "logs_warning_when_overlaps or does_not_log_warning" -v
```

Expected: `test_create_logs_warning_when_overlaps_completed_job_same_source` FAIL (chưa có log warning nào được ghi).

- [ ] **Step 3.3: Sửa `backend/routers/reports.py`**

Tìm:
```python
import uuid
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import Article, ArticleAnalysis, Job, Source
from backend.workers.celery_app import celery_app
from backend.workers.report_job import run_report_job

router = APIRouter(prefix="/api/reports", tags=["reports"])
```

Thay bằng:
```python
import logging
import uuid
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import Article, ArticleAnalysis, Job, Source
from backend.workers.celery_app import celery_app
from backend.workers.report_job import run_report_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])
```

Tìm:
```python
    task_id = str(uuid.uuid4())
    job = Job(
        source_ids=payload.source_ids,
        date_from=payload.date_from,
        date_to=payload.date_to,
        celery_task_id=task_id,
    )
    db.add(job)
    db.commit()
```

Thay bằng:
```python
    # Cảnh báo (không chặn) nếu job mới trùng phạm vi ngày + nguồn với job đã completed
    # trước đó — sau khi bỏ dedup xuyên job (migration 0009), trường hợp này sẽ crawl +
    # phân tích AI lại TOÀN BỘ từ đầu, tốn thời gian đáng kể (AI CPU-only ~90s/bài).
    overlapping_completed_jobs = (
        db.query(Job)
        .filter(
            Job.status == "completed",
            Job.date_from <= payload.date_to,
            Job.date_to >= payload.date_from,
            Job.source_ids.overlap(payload.source_ids),
        )
        .count()
    )
    if overlapping_completed_jobs > 0:
        logger.warning(
            "Job mới trùng phạm vi ngày/nguồn với %d job đã completed trước đó — "
            "sẽ crawl + phân tích AI lại toàn bộ, không dùng lại kết quả cũ",
            overlapping_completed_jobs,
        )

    task_id = str(uuid.uuid4())
    job = Job(
        source_ids=payload.source_ids,
        date_from=payload.date_from,
        date_to=payload.date_to,
        celery_task_id=task_id,
    )
    db.add(job)
    db.commit()
```

- [ ] **Step 3.4: Chạy lại test — cả 2 phải PASS**

```bash
docker compose exec backend pytest backend/tests/test_reports_router.py -v
```

- [ ] **Step 3.5: Chạy toàn bộ test suite**

```bash
docker compose exec backend pytest backend/tests/ -v
```

- [ ] **Step 3.6: Commit**

```bash
git add backend/routers/reports.py backend/tests/test_reports_router.py
git commit -m "$(cat <<'EOF'
feat: cảnh báo log khi tạo job trùng phạm vi ngày/nguồn với job cũ

Sau khi bỏ dedup xuyên job, tạo job mới trùng source_ids + date range
với 1 job đã completed sẽ crawl + phân tích AI lại toàn bộ từ đầu.
Thêm log warning ở POST /api/reports/create để có dấu vết khi việc
này xảy ra — chưa làm cảnh báo ở FE (để dành sau nếu cần).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — Cập nhật 5 rule doc phản ánh đúng kiến trúc mới

**Files:**
- Modify: `.claude/rules/03-database-schema.md`
- Modify: `.claude/rules/04-business-flow.md`
- Modify: `.claude/rules/06-crawler-strategy.md`
- Modify: `.claude/rules/07-ai-pipeline.md`
- Modify: `.claude/rules/10-error-handling.md`

- [ ] **Step 4.1: `.claude/rules/03-database-schema.md`**

Tìm:
```
    url_hash              VARCHAR(64) UNIQUE NOT NULL,  -- SHA256(url) — dùng để dedup
```

Thay bằng:
```
    url_hash              VARCHAR(64) NOT NULL,         -- SHA256(url), UNIQUE composite
                                                          -- cùng job_id (KHÔNG unique riêng
                                                          -- lẻ) — mỗi job crawl/phân tích
                                                          -- độc lập, cùng URL có thể xuất
                                                          -- hiện ở nhiều job, nhưng 1 job
                                                          -- không được trùng URL với chính nó
```

- [ ] **Step 4.2: `.claude/rules/04-business-flow.md`**

Tìm:
```
         Dedup SHA256(url) → insert bảng articles
```

Thay bằng:
```
         Dedup SHA256(url) trong phạm vi 1 job (không xuyên job) → insert bảng articles
```

- [ ] **Step 4.3: `.claude/rules/06-crawler-strategy.md`**

Tìm:
```
**Quy tắc:**
- Dedup bằng `SHA256(url)` trước khi insert vào bảng `articles` (cột `url_hash` có `UNIQUE` constraint)
```

Thay bằng:
```
**Quy tắc:**
- Dedup bằng `SHA256(url)` **trong phạm vi 1 job** trước khi insert vào bảng `articles` — không dedup xuyên job: mỗi job crawl/phân tích lại từ đầu dù trùng URL với job khác (kể cả job đã thành công), để không bỏ lỡ nội dung đã thay đổi và không tạo dữ liệu "mồ côi" khi job cũ fail/cancel giữa chừng (2026-07-09). Chống trùng bằng 2 lớp: `set()` Python cục bộ trong 1 lần chạy job (nhanh, không đụng DB) + `UNIQUE` composite `(job_id, url_hash)` ở DB làm lưới an toàn dự phòng
```

- [ ] **Step 4.4: `.claude/rules/07-ai-pipeline.md`**

Tìm cuối file (trước phần "Môi trường & Cấu hình"):
```
**Quy tắc xử lý output:**
- `confidence < 0.6` → flag `needs_review=true`, vẫn lưu và đưa vào báo cáo (không xóa)
- AI trả về JSON không hợp lệ → parse với try/except, retry 1 lần, nếu vẫn lỗi thì skip bài đó
- Nội dung bài viết dài hơn `AI_MAX_CONTENT_LENGTH` → cắt tại ranh giới câu gần nhất (`.`, `!`, `?`, xuống dòng), không cắt cứng giữa câu/từ (`_truncate_at_sentence_boundary` trong `backend/ai/ollama_client.py`)
```

Thay bằng:
```
**Quy tắc xử lý output:**
- `confidence < 0.6` → flag `needs_review=true`, vẫn lưu và đưa vào báo cáo (không xóa)
- AI trả về JSON không hợp lệ → parse với try/except, retry 1 lần, nếu vẫn lỗi thì skip bài đó
- Nội dung bài viết dài hơn `AI_MAX_CONTENT_LENGTH` → cắt tại ranh giới câu gần nhất (`.`, `!`, `?`, xuống dòng), không cắt cứng giữa câu/từ (`_truncate_at_sentence_boundary` trong `backend/ai/ollama_client.py`)

**Giới hạn đã biết — kết quả AI không đảm bảo giống hệt nhau giữa các lần gọi (2026-07-09):**
Sau khi bỏ dedup xuyên job (xem [06 · Crawler Strategy](06-crawler-strategy.md)), cùng 1 bài
viết có thể được phân tích AI nhiều lần ở các job khác nhau (job trùng phạm vi ngày). Do
`qwen3:8b` qua Ollama không set `temperature`/seed cố định, output giữa các lần gọi **không
đảm bảo giống hệt nhau** (`topics`/`sentiment`/`emotion`/`confidence` có thể khác nhau cho
cùng 1 bài). Đây là đánh đổi đã biết, chưa xử lý — xem "Vấn đề cần làm rõ" ở CLAUDE.md.
```

- [ ] **Step 4.5: `.claude/rules/10-error-handling.md`**

Tìm:
```
| Sub-sitemap lỗi (1 khối ngày của sitemap VTV không tải được) | Retry 3 lần; hết retry → log cảnh báo phía server **và** insert row `Article` với `status="error"` (`url` = URL sub-sitemap lỗi, `title=null`, hash theo `job_id + url` thay vì `SHA256(url)` để tránh đụng `UNIQUE` constraint khi job khác sau này gặp lại đúng sub-sitemap lỗi) → hiện trên bảng crawl trực tiếp ở FE, bỏ qua khối đó, tiếp tục các sub-sitemap khác (2026-06-26) |
| Website không có sitemap | Tự động fallback sang listing page crawler (chưa code — Slice 2) |
| Dữ liệu trùng lặp | Check SHA256(url) trước khi insert — bỏ qua nếu đã tồn tại |
```

Thay bằng:
```
| Sub-sitemap lỗi (1 khối ngày của sitemap VTV không tải được) | Retry 3 lần; hết retry → log cảnh báo phía server **và** insert row `Article` với `status="error"` (`url` = URL sub-sitemap lỗi, `title=null`, hash `SHA256(url)` như mọi trường hợp khác — không còn cần mẹo né UNIQUE đơn, đã đổi sang composite `(job_id, url_hash)` từ 2026-07-09) → hiện trên bảng crawl trực tiếp ở FE, bỏ qua khối đó, tiếp tục các sub-sitemap khác (2026-06-26) |
| Website không có sitemap | Tự động fallback sang listing page crawler (chưa code — Slice 2) |
| Dữ liệu trùng lặp | Check SHA256(url) **trong phạm vi 1 job** (`set()` cục bộ + `UNIQUE` composite `(job_id, url_hash)` ở DB) — không dedup xuyên job (2026-07-09, xem "Quyết định quan trọng") |
```

Tìm tiếp:
```
| Job fail/cancel giữa lúc phân tích AI, sau đó tạo job mới cùng nguồn/khoảng ngày | **Chưa xử lý (Slice 3, phát hiện 2026-07-08) — để dành Slice sau.** `articles.url_hash` là UNIQUE toàn cục (không theo `job_id`) — job mới sẽ tự động bỏ qua (skip) mọi URL đã crawl từ job cũ (dù job cũ đã fail/cancel), nên các bài đó **không bao giờ được gắn vào job mới** (`Article.job_id`/`ArticleAnalysis.job_id` là khóa ngoại cố định). Report của job mới chỉ tổng hợp theo đúng `job_id` của nó → **thiếu vĩnh viễn** các bài "mồ côi" thuộc job cũ, trừ khi can thiệp tay vào DB. Đã cân nhắc 5 phương án (đổi dedup theo job / "nhận nuôi" bài mồ côi / cho phép retry đúng `job_id` cũ / dọn rác định kỳ / rollback xóa sạch khi fail) — phương án chọn cho tương lai: **cho phép retry đúng `job_id` cũ** (`POST /api/reports/{job_id}/retry` gọi lại `run_report_job(job_id)`), vì `_crawl_sources`/`_analyze_articles` đã tự resumable sẵn (dedup theo URL + chỉ xử lý `status="pending_analysis"`) — chỉ cần thêm endpoint + UI, không cần đổi logic dedup/crawl/analyze hiện có. Chưa implement — Task 4 (Slice 3) giữ nguyên hành vi hiện tại (không chia chunk), chấp nhận đánh đổi tạm thời vì batch verify hiện tại nhỏ (5-15 bài) |
```

Xoá hẳn dòng này (thay bằng dòng trống — không thêm dòng thay thế nào, vì vấn đề đã được giải quyết bằng cách bỏ dedup xuyên job, đã ghi ở "Quyết định quan trọng" trong CLAUDE.md, không cần lặp lại chi tiết ở đây).

- [ ] **Step 4.6: Commit**

```bash
git add .claude/rules/03-database-schema.md .claude/rules/04-business-flow.md \
        .claude/rules/06-crawler-strategy.md .claude/rules/07-ai-pipeline.md \
        .claude/rules/10-error-handling.md
git commit -m "$(cat <<'EOF'
docs: cập nhật rule 03/04/06/07/10 — dedup chỉ còn trong phạm vi 1 job

Phản ánh đúng kiến trúc mới: UNIQUE composite (job_id, url_hash) thay
vì unique đơn. Xoá mô tả vấn đề "job mồ côi" ở 10-error-handling.md —
không còn tồn tại sau khi bỏ dedup xuyên job. Thêm ghi chú rủi ro AI
non-determinism ở 07-ai-pipeline.md.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — Cập nhật CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 5.1: Thêm bullet vào "Đã hoàn thành"**

Tìm:
```
- **Bug thật phát hiện + đã sửa (2026-07-09):** khi user tự đọc CSV kết quả verify Slice 3, phát hiện 1 bài VTV bị `status="error"` dù URL vẫn hợp lệ khi truy cập tay — nguyên nhân: VTV trả `301 redirect` sang subdomain khác (`worldcup.vtv.vn`), httpx mặc định không tự theo redirect. Đã thêm `follow_redirects=True` cho `httpx.Client()` ở cả 3 nơi crawl (`article.py`/`listing.py`/`sitemap.py`, cùng nguyên nhân gốc), 3 test mới, verify bằng dữ liệu thật (crawl lại đúng URL đã lỗi, thành công). Đã push `main`
```

Thay bằng (thêm 1 dòng mới ngay sau, giữ nguyên dòng cũ):
```
- **Bug thật phát hiện + đã sửa (2026-07-09):** khi user tự đọc CSV kết quả verify Slice 3, phát hiện 1 bài VTV bị `status="error"` dù URL vẫn hợp lệ khi truy cập tay — nguyên nhân: VTV trả `301 redirect` sang subdomain khác (`worldcup.vtv.vn`), httpx mặc định không tự theo redirect. Đã thêm `follow_redirects=True` cho `httpx.Client()` ở cả 3 nơi crawl (`article.py`/`listing.py`/`sitemap.py`, cùng nguyên nhân gốc), 3 test mới, verify bằng dữ liệu thật (crawl lại đúng URL đã lỗi, thành công). Đã push `main`
- **Bỏ dedup toàn cục theo `url_hash` (2026-07-09) — giải quyết dứt điểm vấn đề "job mồ côi" + "report rỗng âm thầm":** qua thảo luận sâu với user (đọc kết quả verify Slice 3), phát hiện 2 vấn đề cùng gốc rễ (`articles.url_hash` UNIQUE toàn cục): (1) job fail/cancel giữa chừng để lại dữ liệu "mồ côi" không gắn được vào job mới, (2) job mới trùng khoảng ngày với job cũ (dù job cũ **thành công**) bị skip hết, báo `status="completed"` nhưng report **rỗng hoàn toàn**, không cảnh báo. Cân nhắc 5 phương án (retry đúng `job_id` / minh bạch số liệu / content-hash so sánh nội dung / chặn tạo job trùng / bỏ dedup hoàn toàn) — user chọn phương án triệt để nhất: **bỏ hẳn dedup xuyên job**, mỗi job luôn crawl + phân tích AI lại từ đầu. **Cập nhật sau code review:** thay vì bỏ hẳn UNIQUE, đổi sang **UNIQUE composite `(job_id, url_hash)`** (migration `0009`) — vẫn đạt đúng mục tiêu (URL trùng được phép ở job khác) nhưng giữ lưới an toàn DB chống trùng trong 1 job, không phụ thuộc hoàn toàn vào `set()` Python. `downgrade()` tự dedupe trước khi tạo lại UNIQUE đơn để tránh crash khi rollback. Thêm log warning ở `POST /api/reports/create` khi job mới trùng phạm vi ngày/nguồn với job `completed` trước đó, để có dấu vết chi phí AI phải chạy lại. Đánh đổi chấp nhận: tốn AI chạy lại khi job trùng phạm vi (kể cả bài không đổi nội dung), bảng `articles` phình to hơn theo thời gian, kết quả AI có thể khác nhau giữa các lần phân tích cùng 1 bài (non-determinism) — user ưu tiên đúng đắn dữ liệu hơn tiết kiệm tài nguyên. Tác dụng phụ có lợi: tự động mở khả năng bắt được nội dung bài viết đã thay đổi (đính chính/cập nhật) mà không cần cơ chế riêng
```

- [ ] **Step 5.2: Xoá bullet "Vấn đề cần làm rõ" về job mồ côi, thêm 2 bullet mới**

Tìm:
```
### Vấn đề cần làm rõ (chưa chốt)
- **Chưa có cơ chế resume job — dữ liệu "mồ côi" khi job fail/cancel giữa lúc phân tích AI (phát hiện Slice 3, 2026-07-08):** `articles.url_hash` unique toàn cục (không theo `job_id`) khiến job mới tạo cùng nguồn/khoảng ngày tự động skip mọi URL đã crawl từ job cũ (dù job cũ fail/cancel) — các bài đó vĩnh viễn không gắn được vào job mới, report job mới thiếu bài mà không ai biết trừ khi so sánh tay. Đã cân nhắc 5 phương án (đổi dedup theo job / "nhận nuôi" bài mồ côi / cho phép retry đúng `job_id` cũ / dọn rác định kỳ / rollback xóa sạch khi fail) — phương án chọn cho tương lai: **retry đúng `job_id` cũ** (`POST /api/reports/{job_id}/retry`), vì `_crawl_sources`/`_analyze_articles` đã tự resumable sẵn (dedup URL + chỉ xử lý `status="pending_analysis"`), chi phí thấp hơn hẳn 4 phương án còn lại. Chưa implement — để dành 1 slice riêng (gợi ý Slice 5 "Error handling đầy đủ"), không làm trong Slice 3. Xem thêm [10 · Error Handling](.claude/rules/10-error-handling.md)
- **Số nguồn ước tính ở Slice 2**
```

Thay bằng:
```
### Vấn đề cần làm rõ (chưa chốt)
- **Kết quả AI không đảm bảo giống hệt nhau giữa các lần phân tích cùng 1 bài (phát hiện khi review plan bỏ dedup xuyên job, 2026-07-09):** `qwen3:8b` qua Ollama không set `temperature`/seed cố định — nếu 2 job trùng phạm vi ngày cùng phân tích 1 bài, `topics`/`sentiment`/`emotion`/`confidence` có thể khác nhau giữa 2 lần. Chưa xử lý (chưa set temperature/seed, chưa có cảnh báo trong report) — theo dõi thêm khi có dữ liệu thật từ nhiều job trùng phạm vi, cân nhắc set `temperature=0` nếu Ollama/`qwen3:8b` hỗ trợ. Xem [07 · AI Pipeline](.claude/rules/07-ai-pipeline.md)
- **Theo dõi kích thước bảng `articles` sau khi bỏ dedup xuyên job (2026-07-09):** mỗi job trùng phạm vi ngày với job trước sẽ thêm 1 bộ dòng mới (không tái sử dụng dòng cũ) — bảng phình to không giới hạn theo thời gian nếu user tạo report định kỳ trùng lịch. Chưa có ngưỡng cảnh báo hay kế hoạch dọn dẹp cụ thể — định kỳ kiểm tra `SELECT count(*) FROM articles`, nếu vượt mốc ước tính (VD >100,000 dòng) thì lên kế hoạch 1 slice archival/cleanup (ngoài phạm vi hiện tại)
- **Số nguồn ước tính ở Slice 2**
```

- [ ] **Step 5.3: Cập nhật "Bước tiếp theo"**

Tìm:
```
4. Cân nhắc mở slice riêng cho cơ chế resume job (retry đúng `job_id` cũ) — xem "Vấn đề cần làm rõ"
```

Xoá hẳn dòng này (mục 4) — vấn đề đã giải quyết, không còn là việc cần làm tiếp theo.

- [ ] **Step 5.4: Thêm dòng vào bảng "Quyết định quan trọng"**

Tìm:
```
| `httpx.Client()` ở cả 3 nơi crawl (`article.py`/`listing.py`/`sitemap.py`) thêm `follow_redirects=True` | Bug thật phát hiện khi user tự đọc kết quả verify Slice 3 (2026-07-09): 1 bài VTV bị đánh dấu `status="error"` dù URL vẫn hợp lệ khi truy cập tay — nguyên nhân là VTV trả `301` sang subdomain khác (`worldcup.vtv.vn`, có vẻ do site đang làm microsite riêng cho World Cup 2026), nhưng httpx mặc định KHÔNG tự theo redirect (khác hành vi trình duyệt), response nhận được là trang redirect rỗng nên không tìm thấy title/content — không có exception nào được raise (301 không phải lỗi HTTP) nên retry cũng không kích hoạt. Sửa cả 3 nơi cùng lúc vì cùng 1 nguyên nhân gốc (cùng thiếu tham số này), tránh để lại lỗ hổng tương tự ở listing-page/sitemap. Verify bằng dữ liệu thật: gọi lại đúng URL đã lỗi trước đó, crawl thành công |
```

Thêm ngay sau (3 dòng mới):
```
| Bỏ dedup xuyên job, dùng UNIQUE composite `(job_id, url_hash)` thay vì bỏ hẳn constraint | Quyết định của user sau khi đọc kỹ hệ quả 2 vấn đề (job mồ côi + report rỗng âm thầm khi job mới trùng khoảng ngày job cũ). Code review sau đó phát hiện: bỏ hẳn UNIQUE sẽ mất lưới an toàn DB chống trùng URL TRONG CÙNG 1 job (chỉ còn dựa vào `set()` Python, không có gì chặn nếu code tương lai có bug) — đổi sang composite `(job_id, url_hash)` đạt đúng mục tiêu (job khác được trùng URL) mà vẫn giữ an toàn DB trong phạm vi 1 job. Đánh đổi: tốn AI chạy lại khi job trùng phạm vi, chấp nhận vì ưu tiên đúng đắn dữ liệu cho production |
| `downgrade()` của migration `0009` tự dedupe (xoá dòng cũ hơn theo `crawled_at`) trước khi tạo lại UNIQUE đơn trên `url_hash` | Code review phát hiện: nếu downgrade thẳng mà không dedupe trước, `create_unique_constraint` sẽ crash ngay khi DB đã có dữ liệu trùng `url_hash` giữa các job (đúng hành vi mong muốn sau khi upgrade chạy 1 thời gian) — rollback path sẽ hỏng ngầm đúng lúc cần chạy êm xuôi nhất (giữa sự cố production) |
| Thêm log warning ở `POST /api/reports/create` khi job mới trùng phạm vi ngày/nguồn với job `completed` trước đó, KHÔNG chặn tạo job | Code review phát hiện: đánh đổi "tốn AI chạy lại" chỉ được xác nhận bằng lời, không có gì ở tầng kỹ thuật cảnh báo khi việc này xảy ra ngoài ý muốn (VD user vô tình tạo lại report trùng lịch tháng/quý). Chọn mức tối thiểu (log warning, không chặn/không xây UI cảnh báo) để không lấn phạm vi khỏi plan gốc — mở rộng UI cảnh báo để dành sau nếu cần |
```

- [ ] **Step 5.5: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: CLAUDE.md — ghi nhận quyết định bỏ dedup toàn cục theo url_hash

Xoá mục "Vấn đề cần làm rõ" về job mồ côi (đã giải quyết), xoá bước
tiếp theo về cơ chế resume job (không còn cần), thêm bullet "Đã hoàn
thành" + 3 dòng quyết định quan trọng (composite UNIQUE, downgrade
dedupe, cảnh báo overlap) + 2 vấn đề cần theo dõi mới (AI
non-determinism, kích thước bảng articles).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — Verify thật với dữ liệu thật

- [ ] **Step 6.1: Restart `celery-worker`** (bài học cũ — volume mount không tự nạp code mới)

```bash
docker compose restart celery-worker backend
```

- [ ] **Step 6.2: Chọn 1 job thật đã chạy thành công trước đó để tái sử dụng khoảng ngày**

Dùng lại chính xác `source_ids`/`date_from`/`date_to` của job Giai đoạn A Slice 3 đã verify thành công (`source_ids=[VTV, VOV]`, `date_from=2026-06-01`, `date_to=2026-07-08`, job cũ `2324df79...`, đã có 5 bài `status="analyzed"` trong DB).

- [ ] **Step 6.3: Tạo job mới (job C) với đúng tham số đó, kiểm tra log warning xuất hiện**

```bash
docker compose logs backend --tail 0 --follow &
curl -s -X POST http://localhost:8000/api/reports/create \
  -H "Content-Type: application/json" \
  -d '{
    "source_ids": ["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"],
    "date_from": "2026-06-01",
    "date_to": "2026-07-08"
  }'
```

Expected: log backend xuất hiện dòng `"Job mới trùng phạm vi ngày/nguồn với ... job đã completed trước đó"`.

- [ ] **Step 6.4: Poll tới `completed`, kiểm tra bằng SQL trực tiếp:**

```bash
docker compose exec postgres psql -U ngs -d ngs_monitor -c "SELECT count(*) FROM articles WHERE job_id = '<job_C_id>';"
```

Expected: **> 0** — job C crawl lại được các bài trùng URL với job `2324df79...` cũ (khác hẳn hành vi trước đây là 0 bài). Đối chiếu URL trùng:

```bash
docker compose exec postgres psql -U ngs -d ngs_monitor -c "
SELECT a1.url FROM articles a1
JOIN articles a2 ON a1.url = a2.url AND a1.job_id != a2.job_id
WHERE a1.job_id = '<job_C_id>';"
```

Expected: thấy được ít nhất 1 URL trùng với job `2324df79...` — xác nhận job C đã crawl lại đúng bài cũ thay vì bỏ qua.

- [ ] **Step 6.5: Kiểm tra report job C không rỗng**

```bash
docker compose exec postgres psql -U ngs -d ngs_monitor -c "SELECT status FROM jobs WHERE job_id = '<job_C_id>';"
docker compose exec backend python3 -c "
import json
d = json.load(open('storage/<job_C_id>.json'))
print('số bài trong report:', len(d['articles']))
"
```

Expected: `status=completed`, số bài trong report **> 0** (không rỗng như hành vi cũ sẽ gây ra).

- [ ] **Step 6.6: Xác nhận composite constraint hoạt động thật trên DB dev (không chỉ unit test)**

```bash
docker compose exec postgres psql -U ngs -d ngs_monitor -c "
INSERT INTO articles (article_id, job_id, source_id, url, url_hash)
SELECT gen_random_uuid(), job_id, source_id, url, url_hash FROM articles WHERE job_id = '<job_C_id>' LIMIT 1;"
```

Expected: lệnh INSERT thứ 2 với đúng `(job_id, url_hash)` đã tồn tại phải bị DB từ chối với lỗi `duplicate key value violates unique constraint "articles_job_id_url_hash_key"`.

---

## Task 7 — Regression cuối cùng

- [ ] **Step 7.1: Chạy toàn bộ test suite**

```bash
docker compose exec backend pytest backend/tests/ -v
```

Expected: tất cả PASS.

- [ ] **Step 7.2: Nếu có regression** — sửa ngay trước khi coi plan này hoàn thành.

---

## Self-review checklist

### Spec coverage
- [x] Bỏ UNIQUE đơn, thay bằng UNIQUE composite `(job_id, url_hash)` ở DB → Task 1
- [x] `downgrade()` tự dedupe trước khi tạo lại UNIQUE đơn → Task 1 Step 1.1
- [x] Bỏ check DB toàn cục, giữ dedup nội bộ 1 job qua `set()`, có test xác nhận composite constraint là lưới an toàn dự phòng → Task 2
- [x] Đơn giản hoá hash `failed_locs` → Task 2 Step 2.3
- [x] Cảnh báo chi phí AI khi job trùng phạm vi ngày/nguồn → Task 3 (mới)
- [x] Cập nhật 5 rule doc (03/04/06/07/10) → Task 4
- [x] Cập nhật CLAUDE.md (Đã hoàn thành, xoá Vấn đề cần làm rõ cũ, thêm 2 vấn đề mới, xoá Bước tiếp theo, thêm 3 dòng bảng quyết định) → Task 5
- [x] Verify dữ liệu thật (crawl lại đúng bài đã crawl trước đó, log warning xuất hiện, composite constraint chặn trùng thật trên DB dev) → Task 6
- [x] Xác nhận không test cũ nào cần xoá (đã rà soát trong spec, không có task xoá test vì không có gì để xoá) → ghi rõ trong Task 2, không tạo task thừa

### Placeholder scan
Không còn "TBD"/"TODO" — mọi step có code/lệnh cụ thể.

### Type consistency
`seen_urls: set[str]` khai báo ở Task 2 Step 2.3 dùng nhất quán trong cùng đoạn code. `Job.source_ids.overlap(...)` ở Task 3 dùng đúng comparator của `ARRAY(UUID)` trong SQLAlchemy Postgres dialect (đã xác nhận `backend/models/jobs.py` khai `source_ids = Column(ARRAY(UUID(as_uuid=True)), ...)`).

### Rủi ro đã biết (còn lại sau khi áp dụng 5 giải pháp)
- Chi phí AI tăng khi job trùng phạm vi ngày — đã là đánh đổi được user chấp nhận rõ ràng, nay có thêm log warning để ít nhất có dấu vết, không phải rủi ro ẩn hoàn toàn.
- Bảng `articles` phình to theo thời gian — chấp nhận được ở giai đoạn hiện tại, đã thêm mục theo dõi cụ thể ở CLAUDE.md "Vấn đề cần làm rõ" (Task 5).
- Kết quả AI không deterministic (không đảm bảo giống hệt) giữa các lần phân tích lại cùng 1 bài — đã ghi nhận ở rule 07 + CLAUDE.md, CHƯA xử lý kỹ thuật (chưa set temperature/seed) — để dành theo dõi, không thuộc phạm vi plan này.
- Cảnh báo overlap (Task 3) chỉ dừng ở log backend, chưa có UI cảnh báo cho user — chấp nhận là bước tối thiểu, mở rộng sau nếu cần.
