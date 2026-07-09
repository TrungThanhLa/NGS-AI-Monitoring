# Bỏ dedup toàn cục theo url_hash — mỗi job crawl/phân tích độc lập

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bỏ `UNIQUE` constraint trên `articles.url_hash` và bỏ check dedup toàn cục trong `_crawl_sources()` — mỗi job giờ crawl + phân tích AI lại từ đầu, không còn bị chặn bởi dữ liệu đã crawl từ job khác (kể cả job đã thành công). Vẫn giữ 1 lớp chống trùng trong phạm vi 1 job (không đụng DB) cho các nguồn chưa có dedup riêng.

**Architecture:** Migration `0009` xoá constraint `articles_url_hash_key`, thêm index thường thay thế. `_crawl_sources()` (`backend/workers/report_job.py`) thay query DB toàn cục bằng 1 `set()` Python cục bộ trong phạm vi 1 lần gọi hàm. Đơn giản hoá hash `failed_locs` (không còn cần mẹo né UNIQUE constraint). Cập nhật 4 rule doc + CLAUDE.md để phản ánh đúng kiến trúc mới, xoá phần mô tả vấn đề "job mồ côi" đã không còn tồn tại.

Xem đầy đủ bối cảnh + quyết định đã chốt tại spec: `docs/superpowers/specs/2026-07-09-remove-cross-job-dedup-design.md`.

**Tech Stack:** Python, SQLAlchemy, Alembic, pytest, Postgres

---

## Mapping file → trách nhiệm sau khi sửa

| File | Thay đổi |
|---|---|
| `backend/alembic/versions/0009_drop_articles_url_hash_unique.py` | Migration mới — xoá UNIQUE constraint, thêm index thường |
| `backend/models/articles.py` | `url_hash`: bỏ `unique=True`, thêm `index=True` |
| `backend/workers/report_job.py` | `_crawl_sources()`: bỏ query DB toàn cục, thêm `seen_urls` set cục bộ; đơn giản hoá hash `failed_locs` |
| `backend/tests/test_report_job.py` | 2 test mới |
| `.claude/rules/03-database-schema.md` | Sửa comment `url_hash` |
| `.claude/rules/04-business-flow.md` | Sửa mô tả bước 4 (dedup) |
| `.claude/rules/06-crawler-strategy.md` | Sửa mục "Quy tắc" về dedup |
| `.claude/rules/10-error-handling.md` | Sửa dòng "Sub-sitemap lỗi"/"Dữ liệu trùng lặp", xoá dòng "Job fail/cancel giữa lúc phân tích AI..." |
| `CLAUDE.md` | Thêm bullet "Đã hoàn thành", xoá bullet "Vấn đề cần làm rõ" về job mồ côi, cập nhật "Bước tiếp theo", thêm dòng vào bảng quyết định |

---

## Task 1 — Migration `0009`: bỏ UNIQUE constraint trên `url_hash`

**Files:**
- Create: `backend/alembic/versions/0009_drop_articles_url_hash_unique.py`
- Modify: `backend/models/articles.py`

- [ ] **Step 1.1: Viết migration**

```python
"""bỏ UNIQUE constraint articles.url_hash — mỗi job crawl/phân tích độc lập, không dedup xuyên job

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
    op.create_index("ix_articles_url_hash", "articles", ["url_hash"])


def downgrade():
    op.drop_index("ix_articles_url_hash", "articles")
    op.create_unique_constraint("articles_url_hash_key", "articles", ["url_hash"])
```

- [ ] **Step 1.2: Cập nhật model**

Tìm trong `backend/models/articles.py`:
```python
    url_hash = Column(String(64), nullable=False, unique=True)
```

Thay bằng:
```python
    # Không còn UNIQUE — mỗi job crawl/phân tích độc lập, cùng 1 URL có thể xuất hiện ở
    # nhiều job khác nhau (kể cả trùng nội dung). Vẫn giữ index để tra cứu nhanh.
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

Expected: mục "Indexes" hiện `"ix_articles_url_hash" btree (url_hash)` — **không còn** dòng `"articles_url_hash_key" UNIQUE CONSTRAINT`.

- [ ] **Step 1.5: Commit**

```bash
git add backend/alembic/versions/0009_drop_articles_url_hash_unique.py backend/models/articles.py
git commit -m "$(cat <<'EOF'
feat: bỏ UNIQUE constraint articles.url_hash

Chuẩn bị cho việc mỗi job crawl/phân tích AI độc lập, không còn bị chặn
bởi dữ liệu đã crawl từ job khác (kể cả job đã thành công) — xem spec
docs/superpowers/specs/2026-07-09-remove-cross-job-dedup-design.md.
Vẫn giữ cột url_hash + thêm index thường để tra cứu.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — `_crawl_sources()`: bỏ check DB toàn cục, thêm check nội bộ job

**Files:**
- Modify: `backend/workers/report_job.py`
- Modify: `backend/tests/test_report_job.py`

- [ ] **Step 2.1: Thêm import + viết 2 test mới**

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

from backend.crawler.article import compute_url_hash
from backend.models import Article, ArticleAnalysis, Job, Source
from backend.workers.report_job import _analyze_articles, _crawl_sources
```

Thêm vào cuối file 2 test mới:
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
```

- [ ] **Step 2.2: Chạy để xác nhận FAIL**

```bash
docker compose exec backend pytest backend/tests/test_report_job.py -k "recrawls_url_already or dedups_within_same_job" -v
```

Expected: `test_crawl_sources_recrawls_url_already_belonging_to_another_job` FAIL (job B nhận được 0 bài thay vì 1, vì code hiện tại vẫn skip URL đã tồn tại). `test_crawl_sources_dedups_within_same_job_when_candidates_repeat_url` có thể PASS ngay (code hiện tại vô tình cũng chặn trùng qua DB check) — không sao, sẽ vẫn PASS sau khi sửa vì check DB được thay bằng check nội bộ tương đương.

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
    # docs/superpowers/specs/2026-07-09-remove-cross-job-dedup-design.md).
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

- [ ] **Step 2.4: Chạy lại test — cả 2 phải PASS**

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
constraint, đã bỏ ở migration trước).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — Cập nhật 4 rule doc phản ánh đúng kiến trúc mới

**Files:**
- Modify: `.claude/rules/03-database-schema.md`
- Modify: `.claude/rules/04-business-flow.md`
- Modify: `.claude/rules/06-crawler-strategy.md`
- Modify: `.claude/rules/10-error-handling.md`

- [ ] **Step 3.1: `.claude/rules/03-database-schema.md`**

Tìm:
```
    url_hash              VARCHAR(64) UNIQUE NOT NULL,  -- SHA256(url) — dùng để dedup
```

Thay bằng:
```
    url_hash              VARCHAR(64) NOT NULL,         -- SHA256(url), có index (KHÔNG unique
                                                          -- — mỗi job crawl/phân tích độc lập,
                                                          -- cùng URL có thể xuất hiện ở nhiều job)
```

- [ ] **Step 3.2: `.claude/rules/04-business-flow.md`**

Tìm:
```
         Dedup SHA256(url) → insert bảng articles
```

Thay bằng:
```
         Dedup SHA256(url) trong phạm vi 1 job (không xuyên job) → insert bảng articles
```

- [ ] **Step 3.3: `.claude/rules/06-crawler-strategy.md`**

Tìm:
```
**Quy tắc:**
- Dedup bằng `SHA256(url)` trước khi insert vào bảng `articles` (cột `url_hash` có `UNIQUE` constraint)
```

Thay bằng:
```
**Quy tắc:**
- Dedup bằng `SHA256(url)` **trong phạm vi 1 job** trước khi insert vào bảng `articles` — không dedup xuyên job: mỗi job crawl/phân tích lại từ đầu dù trùng URL với job khác (kể cả job đã thành công), để không bỏ lỡ nội dung đã thay đổi và không tạo dữ liệu "mồ côi" khi job cũ fail/cancel giữa chừng (2026-07-09)
```

- [ ] **Step 3.4: `.claude/rules/10-error-handling.md`**

Tìm:
```
| Sub-sitemap lỗi (1 khối ngày của sitemap VTV không tải được) | Retry 3 lần; hết retry → log cảnh báo phía server **và** insert row `Article` với `status="error"` (`url` = URL sub-sitemap lỗi, `title=null`, hash theo `job_id + url` thay vì `SHA256(url)` để tránh đụng `UNIQUE` constraint khi job khác sau này gặp lại đúng sub-sitemap lỗi) → hiện trên bảng crawl trực tiếp ở FE, bỏ qua khối đó, tiếp tục các sub-sitemap khác (2026-06-26) |
| Website không có sitemap | Tự động fallback sang listing page crawler (chưa code — Slice 2) |
| Dữ liệu trùng lặp | Check SHA256(url) trước khi insert — bỏ qua nếu đã tồn tại |
```

Thay bằng:
```
| Sub-sitemap lỗi (1 khối ngày của sitemap VTV không tải được) | Retry 3 lần; hết retry → log cảnh báo phía server **và** insert row `Article` với `status="error"` (`url` = URL sub-sitemap lỗi, `title=null`, hash `SHA256(url)` như mọi trường hợp khác) → hiện trên bảng crawl trực tiếp ở FE, bỏ qua khối đó, tiếp tục các sub-sitemap khác (2026-06-26) |
| Website không có sitemap | Tự động fallback sang listing page crawler (chưa code — Slice 2) |
| Dữ liệu trùng lặp | Check SHA256(url) **trong phạm vi 1 job** — không dedup xuyên job (2026-07-09, xem "Quyết định quan trọng") |
```

Tìm tiếp:
```
| Job fail/cancel giữa lúc phân tích AI, sau đó tạo job mới cùng nguồn/khoảng ngày | **Chưa xử lý (Slice 3, phát hiện 2026-07-08) — để dành Slice sau.** `articles.url_hash` là UNIQUE toàn cục (không theo `job_id`) — job mới sẽ tự động bỏ qua (skip) mọi URL đã crawl từ job cũ (dù job cũ đã fail/cancel), nên các bài đó **không bao giờ được gắn vào job mới** (`Article.job_id`/`ArticleAnalysis.job_id` là khóa ngoại cố định). Report của job mới chỉ tổng hợp theo đúng `job_id` của nó → **thiếu vĩnh viễn** các bài "mồ côi" thuộc job cũ, trừ khi can thiệp tay vào DB. Đã cân nhắc 5 phương án (đổi dedup theo job / "nhận nuôi" bài mồ côi / cho phép retry đúng `job_id` cũ / dọn rác định kỳ / rollback xóa sạch khi fail) — phương án chọn cho tương lai: **cho phép retry đúng `job_id` cũ** (`POST /api/reports/{job_id}/retry` gọi lại `run_report_job(job_id)`), vì `_crawl_sources`/`_analyze_articles` đã tự resumable sẵn (dedup theo URL + chỉ xử lý `status="pending_analysis"`) — chỉ cần thêm endpoint + UI, không cần đổi logic dedup/crawl/analyze hiện có. Chưa implement — Task 4 (Slice 3) giữ nguyên hành vi hiện tại (không chia chunk), chấp nhận đánh đổi tạm thời vì batch verify hiện tại nhỏ (5-15 bài) |
```

Xoá hẳn dòng này (thay bằng dòng trống — không thêm dòng thay thế nào, vì vấn đề đã được giải quyết bằng cách bỏ dedup toàn cục, đã ghi ở "Quyết định quan trọng" trong CLAUDE.md, không cần lặp lại chi tiết ở đây).

- [ ] **Step 3.5: Commit**

```bash
git add .claude/rules/03-database-schema.md .claude/rules/04-business-flow.md \
        .claude/rules/06-crawler-strategy.md .claude/rules/10-error-handling.md
git commit -m "$(cat <<'EOF'
docs: cập nhật rule 03/04/06/10 — dedup chỉ còn trong phạm vi 1 job

Phản ánh đúng kiến trúc mới sau khi bỏ UNIQUE constraint articles.url_hash.
Xoá mô tả vấn đề "job mồ côi" ở 10-error-handling.md — không còn tồn tại
sau khi bỏ dedup xuyên job.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — Cập nhật CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 4.1: Thêm bullet vào "Đã hoàn thành"**

Tìm:
```
- **Bug thật phát hiện + đã sửa (2026-07-09):** khi user tự đọc CSV kết quả verify Slice 3, phát hiện 1 bài VTV bị `status="error"` dù URL vẫn hợp lệ khi truy cập tay — nguyên nhân: VTV trả `301 redirect` sang subdomain khác (`worldcup.vtv.vn`), httpx mặc định không tự theo redirect. Đã thêm `follow_redirects=True` cho `httpx.Client()` ở cả 3 nơi crawl (`article.py`/`listing.py`/`sitemap.py`, cùng nguyên nhân gốc), 3 test mới, verify bằng dữ liệu thật (crawl lại đúng URL đã lỗi, thành công). Đã push `main`
```

Thay bằng (thêm 1 dòng mới ngay sau, giữ nguyên dòng cũ):
```
- **Bug thật phát hiện + đã sửa (2026-07-09):** khi user tự đọc CSV kết quả verify Slice 3, phát hiện 1 bài VTV bị `status="error"` dù URL vẫn hợp lệ khi truy cập tay — nguyên nhân: VTV trả `301 redirect` sang subdomain khác (`worldcup.vtv.vn`), httpx mặc định không tự theo redirect. Đã thêm `follow_redirects=True` cho `httpx.Client()` ở cả 3 nơi crawl (`article.py`/`listing.py`/`sitemap.py`, cùng nguyên nhân gốc), 3 test mới, verify bằng dữ liệu thật (crawl lại đúng URL đã lỗi, thành công). Đã push `main`
- **Bỏ dedup toàn cục theo `url_hash` (2026-07-09) — giải quyết dứt điểm vấn đề "job mồ côi" + "report rỗng âm thầm":** qua thảo luận sâu với user (đọc kết quả verify Slice 3), phát hiện 2 vấn đề cùng gốc rễ (`articles.url_hash` UNIQUE toàn cục): (1) job fail/cancel giữa chừng để lại dữ liệu "mồ côi" không gắn được vào job mới, (2) job mới trùng khoảng ngày với job cũ (dù job cũ **thành công**) bị skip hết, báo `status="completed"` nhưng report **rỗng hoàn toàn**, không cảnh báo. Cân nhắc 5 phương án (retry đúng `job_id` / minh bạch số liệu / content-hash so sánh nội dung / chặn tạo job trùng / bỏ dedup hoàn toàn) — user chọn phương án triệt để nhất: **bỏ hẳn dedup xuyên job**, mỗi job luôn crawl + phân tích AI lại từ đầu (migration `0009` xoá `articles_url_hash_key`, `_crawl_sources()` chỉ còn chống trùng trong phạm vi 1 job qua `set()` cục bộ). Đánh đổi chấp nhận: tốn AI chạy lại khi job trùng phạm vi (kể cả bài không đổi nội dung), bảng `articles` phình to hơn theo thời gian — user ưu tiên đúng đắn dữ liệu hơn tiết kiệm tài nguyên. Tác dụng phụ có lợi: tự động mở khả năng bắt được nội dung bài viết đã thay đổi (đính chính/cập nhật) mà không cần cơ chế riêng
```

- [ ] **Step 4.2: Xoá bullet "Vấn đề cần làm rõ" về job mồ côi**

Tìm:
```
### Vấn đề cần làm rõ (chưa chốt)
- **Chưa có cơ chế resume job — dữ liệu "mồ côi" khi job fail/cancel giữa lúc phân tích AI (phát hiện Slice 3, 2026-07-08):** `articles.url_hash` unique toàn cục (không theo `job_id`) khiến job mới tạo cùng nguồn/khoảng ngày tự động skip mọi URL đã crawl từ job cũ (dù job cũ fail/cancel) — các bài đó vĩnh viễn không gắn được vào job mới, report job mới thiếu bài mà không ai biết trừ khi so sánh tay. Đã cân nhắc 5 phương án (đổi dedup theo job / "nhận nuôi" bài mồ côi / cho phép retry đúng `job_id` cũ / dọn rác định kỳ / rollback xóa sạch khi fail) — phương án chọn cho tương lai: **retry đúng `job_id` cũ** (`POST /api/reports/{job_id}/retry`), vì `_crawl_sources`/`_analyze_articles` đã tự resumable sẵn (dedup URL + chỉ xử lý `status="pending_analysis"`), chi phí thấp hơn hẳn 4 phương án còn lại. Chưa implement — để dành 1 slice riêng (gợi ý Slice 5 "Error handling đầy đủ"), không làm trong Slice 3. Xem thêm [10 · Error Handling](.claude/rules/10-error-handling.md)
- **Số nguồn ước tính ở Slice 2**
```

Thay bằng:
```
### Vấn đề cần làm rõ (chưa chốt)
- **Số nguồn ước tính ở Slice 2**
```

(Xoá hẳn bullet về "chưa có cơ chế resume job" — đã giải quyết, xem "Đã hoàn thành".)

- [ ] **Step 4.3: Cập nhật "Bước tiếp theo"**

Tìm:
```
4. Cân nhắc mở slice riêng cho cơ chế resume job (retry đúng `job_id` cũ) — xem "Vấn đề cần làm rõ"
```

Xoá hẳn dòng này (mục 4) — vấn đề đã giải quyết, không còn là việc cần làm tiếp theo.

- [ ] **Step 4.4: Thêm dòng vào bảng "Quyết định quan trọng"**

Tìm:
```
| `httpx.Client()` ở cả 3 nơi crawl (`article.py`/`listing.py`/`sitemap.py`) thêm `follow_redirects=True` | Bug thật phát hiện khi user tự đọc kết quả verify Slice 3 (2026-07-09): 1 bài VTV bị đánh dấu `status="error"` dù URL vẫn hợp lệ khi truy cập tay — nguyên nhân là VTV trả `301` sang subdomain khác (`worldcup.vtv.vn`, có vẻ do site đang làm microsite riêng cho World Cup 2026), nhưng httpx mặc định KHÔNG tự theo redirect (khác hành vi trình duyệt), response nhận được là trang redirect rỗng nên không tìm thấy title/content — không có exception nào được raise (301 không phải lỗi HTTP) nên retry cũng không kích hoạt. Sửa cả 3 nơi cùng lúc vì cùng 1 nguyên nhân gốc (cùng thiếu tham số này), tránh để lại lỗ hổng tương tự ở listing-page/sitemap. Verify bằng dữ liệu thật: gọi lại đúng URL đã lỗi trước đó, crawl thành công |
```

Thêm ngay sau (dòng mới):
```
| Bỏ UNIQUE constraint `articles.url_hash`, `_crawl_sources()` chỉ dedup trong phạm vi 1 job (không xuyên job) | Quyết định của user sau khi đọc kỹ hệ quả 2 vấn đề (job mồ côi + report rỗng âm thầm khi job mới trùng khoảng ngày job cũ) — cân nhắc 5 phương án, chọn hướng triệt để nhất thay vì các giải pháp tình thế (retry job_id, minh bạch số liệu, content-hash). Đánh đổi: tốn AI chạy lại khi job trùng phạm vi, chấp nhận vì ưu tiên đúng đắn dữ liệu cho production. Vẫn giữ `set()` cục bộ chống trùng URL trong 1 job (một số nguồn sitemap/listing có thể vô tình trả về trùng URL) |
```

- [ ] **Step 4.5: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: CLAUDE.md — ghi nhận quyết định bỏ dedup toàn cục theo url_hash

Xoá mục "Vấn đề cần làm rõ" về job mồ côi (đã giải quyết), xoá bước
tiếp theo về cơ chế resume job (không còn cần), thêm bullet "Đã hoàn
thành" + dòng quyết định quan trọng ghi lại đầy đủ lý do và đánh đổi.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — Verify thật với dữ liệu thật

- [ ] **Step 5.1: Restart `celery-worker`** (bài học cũ — volume mount không tự nạp code mới)

```bash
docker compose restart celery-worker
```

- [ ] **Step 5.2: Chọn 1 job thật đã chạy thành công trước đó để tái sử dụng khoảng ngày**

Dùng lại chính xác `source_ids`/`date_from`/`date_to` của job Giai đoạn A Slice 3 đã verify thành công (`source_ids=[VTV, VOV]`, `date_from=2026-06-01`, `date_to=2026-07-08`, job cũ `2324df79...`, đã có 5 bài `status="analyzed"` trong DB).

- [ ] **Step 5.3: Tạo job mới (job C) với đúng tham số đó**

```bash
curl -s -X POST http://localhost:8000/api/reports/create \
  -H "Content-Type: application/json" \
  -d '{
    "source_ids": ["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"],
    "date_from": "2026-06-01",
    "date_to": "2026-07-08"
  }'
```

- [ ] **Step 5.4: Poll tới `completed`, kiểm tra bằng SQL trực tiếp:**

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

- [ ] **Step 5.5: Kiểm tra report job C không rỗng**

```bash
docker compose exec postgres psql -U ngs -d ngs_monitor -c "SELECT status FROM jobs WHERE job_id = '<job_C_id>';"
docker compose exec backend python3 -c "
import json
d = json.load(open('storage/<job_C_id>.json'))
print('số bài trong report:', len(d['articles']))
"
```

Expected: `status=completed`, số bài trong report **> 0** (không rỗng như hành vi cũ sẽ gây ra).

---

## Task 6 — Regression cuối cùng

- [ ] **Step 6.1: Chạy toàn bộ test suite**

```bash
docker compose exec backend pytest backend/tests/ -v
```

Expected: tất cả PASS.

- [ ] **Step 6.2: Nếu có regression** — sửa ngay trước khi coi plan này hoàn thành.

---

## Self-review checklist

### Spec coverage
- [x] Bỏ UNIQUE constraint DB → Task 1
- [x] Bỏ check DB toàn cục, giữ dedup nội bộ 1 job qua `set()` → Task 2
- [x] Đơn giản hoá hash `failed_locs` → Task 2 Step 2.3
- [x] Cập nhật 4 rule doc (03/04/06/10) → Task 3
- [x] Cập nhật CLAUDE.md (Đã hoàn thành, xoá Vấn đề cần làm rõ, xoá Bước tiếp theo, thêm bảng quyết định) → Task 4
- [x] Verify dữ liệu thật (crawl lại đúng bài đã crawl trước đó) → Task 5
- [x] Xác nhận không test cũ nào cần xoá (đã rà soát trong spec, không có task xoá test vì không có gì để xoá) → ghi rõ trong Task 2, không tạo task thừa

### Placeholder scan
Không còn "TBD"/"TODO" — mọi step có code/lệnh cụ thể.

### Type consistency
`seen_urls: set[str]` khai báo ở Task 2 Step 2.3 dùng nhất quán trong cùng đoạn code, không xuất hiện ở nơi khác cần khớp tên.

### Rủi ro đã biết
- Chi phí AI tăng khi job trùng phạm vi ngày — đã là đánh đổi được user chấp nhận rõ ràng, không phải rủi ro ẩn.
- Bảng `articles` phình to theo thời gian (nhiều dòng trùng URL khác `job_id`) — chấp nhận được ở giai đoạn hiện tại, có thể cần dọn dẹp định kỳ trong tương lai nếu bảng quá lớn (ngoài phạm vi plan này).
