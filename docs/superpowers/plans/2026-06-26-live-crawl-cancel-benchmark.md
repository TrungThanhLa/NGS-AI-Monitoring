# Bảng crawl trực tiếp + Hủy job + Giới hạn bài test + Benchmark thời gian — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho phép người dùng (1) xem trực tiếp danh sách bài đã crawl kèm thời gian xử lý thật trong lúc job chạy, (2) hủy job đang chạy bằng nút Cancel, (3) giới hạn số bài/job qua biến env để test nhanh hơn — dựa trên spec đã chốt tại `docs/superpowers/specs/2026-06-26-live-crawl-table-and-job-cancel-design.md`.

**Architecture:** Thêm 3 cột DB mới (`jobs.celery_task_id`, `articles.crawl_duration_seconds`, `article_analysis.analysis_duration_seconds`) qua 1 migration. `crawler/article.py` và `ai/ollama_client.py` tự đo thời gian xử lý thật bằng `time.perf_counter()` và trả kèm trong dict kết quả. `workers/report_job.py` lưu các giá trị này khi insert, và enforce giới hạn `MAX_ARTICLES_PER_JOB` (đọc từ env) khi crawl. `routers/reports.py` thêm `GET /articles` (đọc bảng live) và `POST /cancel` (revoke Celery task + set status). Frontend polling 3s hiện có được mở rộng gọi thêm `/articles` và hiện nút Cancel.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Celery, pytest, Next.js/React (không thêm lib mới).

---

## Task 1: Migration + Models — 3 cột mới

**Files:**
- Create: `backend/alembic/versions/0003_add_celery_task_id_and_duration_columns.py`
- Modify: `backend/models/jobs.py`
- Modify: `backend/models/articles.py`
- Modify: `backend/models/article_analysis.py`

- [ ] **Step 1: Tạo migration**

Tạo file `backend/alembic/versions/0003_add_celery_task_id_and_duration_columns.py`:

```python
"""thêm celery_task_id (jobs) và duration columns (articles, article_analysis)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("celery_task_id", sa.String(255)))
    op.add_column("articles", sa.Column("crawl_duration_seconds", sa.Float))
    op.add_column("article_analysis", sa.Column("analysis_duration_seconds", sa.Float))


def downgrade():
    op.drop_column("article_analysis", "analysis_duration_seconds")
    op.drop_column("articles", "crawl_duration_seconds")
    op.drop_column("jobs", "celery_task_id")
```

- [ ] **Step 2: Cập nhật model `Job`**

Trong `backend/models/jobs.py`, thêm dòng sau `error_log = Column(Text)` (dòng 20):

```python
    celery_task_id = Column(String(255))
```

- [ ] **Step 3: Cập nhật model `Article`**

Trong `backend/models/articles.py`, sửa dòng import (dòng 3) từ:
```python
from sqlalchemy import Column, ForeignKey, String, TIMESTAMP, Text
```
thành:
```python
from sqlalchemy import Column, Float, ForeignKey, String, TIMESTAMP, Text
```

Thêm dòng sau `status = Column(String(50), server_default="pending_analysis")` (dòng 23):
```python
    crawl_duration_seconds = Column(Float)
```

- [ ] **Step 4: Cập nhật model `ArticleAnalysis`**

Trong `backend/models/article_analysis.py`, thêm dòng sau `analyzed_at = Column(TIMESTAMP, server_default=func.now())` (dòng 26):
```python
    analysis_duration_seconds = Column(Float)
```

- [ ] **Step 5: Chạy migration thật, verify**

```bash
docker compose exec backend sh -c "cd /app/backend && alembic upgrade head"
docker compose exec postgres psql -U ngs -d ngs_monitor -c "\d jobs" | grep celery_task_id
docker compose exec postgres psql -U ngs -d ngs_monitor -c "\d articles" | grep crawl_duration_seconds
docker compose exec postgres psql -U ngs -d ngs_monitor -c "\d article_analysis" | grep analysis_duration_seconds
```
Expected: cả 3 lệnh `grep` đều ra đúng tên cột tương ứng.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/0003_add_celery_task_id_and_duration_columns.py backend/models/jobs.py backend/models/articles.py backend/models/article_analysis.py
git commit -m "feat: thêm celery_task_id và duration columns cho job cancel + benchmark"
```

---

## Task 2: `crawler/article.py` — đo `crawl_duration_seconds`

**Files:**
- Modify: `backend/crawler/article.py`
- Test: `backend/tests/test_article.py`

- [ ] **Step 1: Viết test fail trước**

Thêm vào cuối `backend/tests/test_article.py`:

```python
def test_returns_crawl_duration_seconds_excluding_outer_sleep():
    client = _client_returning(FIXTURE_HTML)

    result = fetch_article(ARTICLE_URL, VTV_PARSING_RULES, client=client)

    assert result["crawl_duration_seconds"] > 0
    assert result["crawl_duration_seconds"] < 1.0
```

- [ ] **Step 2: Verify test fail**

```bash
docker compose exec backend python -m pytest backend/tests/test_article.py::test_returns_crawl_duration_seconds_excluding_outer_sleep -v
```
Expected: FAIL với `KeyError: 'crawl_duration_seconds'`

- [ ] **Step 3: Implement**

Trong `backend/crawler/article.py`, sửa hàm `fetch_article` (dòng 25-70):

```python
def fetch_article(
    url: str,
    parsing_rules: dict,
    client: httpx.Client | None = None,
    max_retries: int | None = None,
    retry_backoff_seconds: float | None = None,
) -> dict | None:
    owns_client = client is None
    client = client or httpx.Client(timeout=int(os.environ.get("CRAWLER_TIMEOUT_SECONDS", "30")))
    if max_retries is None:
        max_retries = int(os.environ.get("CRAWLER_MAX_RETRIES", "3"))

    try:
        start = time.perf_counter()
        response = None
        for attempt in range(max_retries):
            try:
                response = client.get(url)
                break
            except httpx.HTTPError:
                if attempt < max_retries - 1:
                    backoff = retry_backoff_seconds if retry_backoff_seconds is not None else 2**attempt
                    time.sleep(backoff)
        if response is None:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        title = _extract(soup, parsing_rules["title"])
        content_raw = _extract(soup, parsing_rules["content"])
        if not title or not content_raw:
            return None

        author = _extract(soup, parsing_rules.get("author", ""))
        date_raw = _extract(soup, parsing_rules.get("date", ""))
        published_at = datetime.fromisoformat(date_raw) if date_raw else None

        return {
            "url": url,
            "url_hash": compute_url_hash(url),
            "title": title,
            "content_raw": content_raw,
            "author": author,
            "published_at": published_at,
            "crawl_duration_seconds": time.perf_counter() - start,
        }
    finally:
        if owns_client:
            client.close()
```

- [ ] **Step 4: Verify test pass + chạy lại toàn bộ file**

```bash
docker compose exec backend python -m pytest backend/tests/test_article.py -v
```
Expected: 4 test PASS (3 cũ + 1 mới)

- [ ] **Step 5: Commit**

```bash
git add backend/crawler/article.py backend/tests/test_article.py
git commit -m "feat: đo crawl_duration_seconds thật trong fetch_article"
```

---

## Task 3: `ai/ollama_client.py` — đo `analysis_duration_seconds`

**Files:**
- Modify: `backend/ai/ollama_client.py`
- Test: `backend/tests/test_ollama_client.py`

- [ ] **Step 1: Viết test fail trước**

Thêm vào cuối `backend/tests/test_ollama_client.py`:

```python
def test_returns_analysis_duration_seconds():
    client = _client_with_responses([VALID_JSON])

    result = analyze_article("Tiêu đề", "Nội dung bài viết", client=client)

    assert result["analysis_duration_seconds"] > 0
```

- [ ] **Step 2: Verify test fail**

```bash
docker compose exec backend python -m pytest backend/tests/test_ollama_client.py::test_returns_analysis_duration_seconds -v
```
Expected: FAIL với `KeyError: 'analysis_duration_seconds'`

- [ ] **Step 3: Implement**

Trong `backend/ai/ollama_client.py`, thêm `import time` vào đầu file (sau dòng `import re`, dòng 3):
```python
import time
```

Sửa hàm `analyze_article` (dòng 19-53) — thêm đo thời gian:

```python
def analyze_article(title: str, content: str, client: httpx.Client | None = None) -> dict:
    owns_client = client is None
    client = client or httpx.Client(timeout=int(os.environ.get("AI_TIMEOUT_SECONDS", "120")))

    max_content_length = int(os.environ.get("AI_MAX_CONTENT_LENGTH", "2000"))
    confidence_threshold = float(os.environ.get("AI_CONFIDENCE_THRESHOLD", "0.6"))
    prompt = CLASSIFICATION_PROMPT.format(
        title=title,
        content_snippet=content[:max_content_length],
        topic_list="\n".join(f"- {t}" for t in TOPIC_GROUPS),
    )

    try:
        start = time.perf_counter()
        result = None
        last_error: Exception | None = None
        for _attempt in range(2):
            response = client.post(
                f"{os.environ['OLLAMA_BASE_URL']}/api/generate",
                json={"model": os.environ["OLLAMA_MODEL"], "prompt": prompt, "stream": False},
            )
            raw = response.json()["response"]
            try:
                result = _parse_json_response(raw)
                break
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = exc
        if result is None:
            raise ValueError("Ollama trả về JSON không hợp lệ sau khi retry") from last_error

        result["needs_review"] = result.get("confidence", 1.0) < confidence_threshold
        result["prompt_version"] = PROMPT_VERSION
        result["analysis_duration_seconds"] = time.perf_counter() - start
        return result
    finally:
        if owns_client:
            client.close()
```

- [ ] **Step 4: Verify test pass + chạy lại toàn bộ file**

```bash
docker compose exec backend python -m pytest backend/tests/test_ollama_client.py -v
```
Expected: 6 test PASS (5 cũ + 1 mới)

- [ ] **Step 5: Commit**

```bash
git add backend/ai/ollama_client.py backend/tests/test_ollama_client.py
git commit -m "feat: đo analysis_duration_seconds thật trong analyze_article"
```

---

## Task 4: `workers/report_job.py` — lưu duration + giới hạn `MAX_ARTICLES_PER_JOB`

**Files:**
- Modify: `backend/workers/report_job.py`
- Create: `backend/tests/test_report_job.py`

- [ ] **Step 1: Viết test fail trước**

Tạo `backend/tests/test_report_job.py`:

```python
import uuid
from datetime import date
from unittest.mock import patch

from backend.models import Article, Job, Source
from backend.workers.report_job import _crawl_sources


def test_crawl_sources_stops_at_max_articles_per_job_limit(db_session, monkeypatch):
    monkeypatch.setenv("MAX_ARTICLES_PER_JOB", "2")

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    candidates = [{"url": f"https://example.test/article-{i}", "lastmod": date(2026, 6, 1)} for i in range(5)]

    def fake_fetch_article(url, parsing_rules, **kwargs):
        return {
            "url": url,
            "url_hash": f"hash-{url}",
            "title": "Title",
            "content_raw": "Content",
            "author": None,
            "published_at": None,
            "crawl_duration_seconds": 0.01,
        }

    with patch("backend.workers.report_job.get_article_urls", return_value=candidates), patch(
        "backend.workers.report_job.fetch_article", side_effect=fake_fetch_article
    ), patch("backend.workers.report_job.time.sleep"):
        _crawl_sources(db_session, job)

    count = db_session.query(Article).filter_by(job_id=job.job_id).count()
    assert count == 2

    db_session.query(Article).filter_by(job_id=job.job_id).delete()
    db_session.delete(job)
    db_session.delete(source)
    db_session.commit()
```

- [ ] **Step 2: Verify test fail**

```bash
docker compose exec backend python -m pytest backend/tests/test_report_job.py -v
```
Expected: FAIL — `count == 5` thực tế (chưa có giới hạn), assert `count == 2` fail

- [ ] **Step 3: Implement**

Trong `backend/workers/report_job.py`, thêm hàm `_parse_max_articles` trước `_crawl_sources` (trước dòng 18):

```python
def _parse_max_articles(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None
```

Thay toàn bộ hàm `_crawl_sources` (dòng 18-50) thành:

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
            candidates = get_article_urls(source, job.date_from, job.date_to)
        except Exception:
            logger.exception("Lỗi lấy sitemap cho nguồn %s", source.domain)
            continue

        for candidate in candidates:
            if max_articles is not None and crawled_count() >= max_articles:
                break

            url_hash = compute_url_hash(candidate["url"])
            if db.query(Article).filter_by(url_hash=url_hash).first() is not None:
                continue

            parsed = fetch_article(candidate["url"], source.parsing_rules)
            time.sleep(delay_seconds)
            if parsed is None:
                continue

            db.add(
                Article(
                    job_id=job.job_id,
                    source_id=source.source_id,
                    url=parsed["url"],
                    url_hash=parsed["url_hash"],
                    title=parsed["title"],
                    content_raw=parsed["content_raw"],
                    author=parsed["author"],
                    published_at=parsed["published_at"],
                    crawl_duration_seconds=parsed.get("crawl_duration_seconds"),
                )
            )
            db.commit()
```

Trong hàm `_analyze_articles` (dòng 53-79), thêm `analysis_duration_seconds=result.get("analysis_duration_seconds")` vào constructor `ArticleAnalysis(...)`:

```python
def _analyze_articles(db, job: Job) -> None:
    pending = db.query(Article).filter_by(job_id=job.job_id, status="pending_analysis").all()
    for article in pending:
        try:
            result = analyze_article(article.title, article.content_raw)
        except ValueError:
            logger.exception("AI phân tích lỗi cho bài %s", article.url)
            article.status = "error"
            db.commit()
            continue

        db.add(
            ArticleAnalysis(
                article_id=article.article_id,
                job_id=job.job_id,
                topics=result["topics"],
                keywords=result.get("keywords", []),
                sentiment=result["sentiment"],
                emotion=result["emotion"],
                confidence=result["confidence"],
                needs_review=result["needs_review"],
                summary=result.get("summary"),
                prompt_version=result["prompt_version"],
                analysis_duration_seconds=result.get("analysis_duration_seconds"),
            )
        )
        article.status = "analyzed"
        db.commit()
```

- [ ] **Step 4: Verify test pass**

```bash
docker compose exec backend python -m pytest backend/tests/test_report_job.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/workers/report_job.py backend/tests/test_report_job.py
git commit -m "feat: giới hạn MAX_ARTICLES_PER_JOB + lưu duration vào articles/article_analysis"
```

---

## Task 5: `routers/reports.py` — `GET /articles`, lưu `celery_task_id`, `POST /cancel`

**Files:**
- Modify: `backend/routers/reports.py`
- Modify: `backend/tests/test_reports_router.py`

- [ ] **Step 1: Viết test fail trước (toàn bộ test mới + sửa test cũ)**

Trong `backend/tests/test_reports_router.py`, sửa dòng import (dòng 9) từ:
```python
from backend.models import Job, Source
```
thành:
```python
from backend.models import Article, ArticleAnalysis, Job, Source
```

Sửa test `test_create_returns_job_id_and_triggers_celery_task` (dòng 64-80) thành:

```python
def test_create_returns_job_id_and_triggers_celery_task(app_client, active_source, db_session):
    with patch("backend.routers.reports.run_report_job") as mock_task:
        mock_task.delay.return_value.id = "fake-task-id"
        response = app_client.post(
            "/api/reports/create",
            json={"source_ids": [str(active_source.source_id)], "date_from": "2026-06-01", "date_to": "2026-06-30"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert "job_id" in body
    mock_task.delay.assert_called_once_with(body["job_id"])

    job = db_session.get(Job, uuid.UUID(body["job_id"]))
    assert job is not None
    assert job.celery_task_id == "fake-task-id"
    db_session.delete(job)
    db_session.commit()
```

Thêm vào cuối file các test mới:

```python
def test_articles_returns_list_with_durations(app_client, db_session):
    job = Job(source_ids=[], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30), status="running")
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        url="https://vtv.vn/bai-1",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Bài 1",
        status="analyzed",
        crawl_duration_seconds=1.5,
    )
    db_session.add(article)
    db_session.flush()

    db_session.add(
        ArticleAnalysis(
            article_id=article.article_id,
            job_id=job.job_id,
            topics=["A"],
            sentiment="negative",
            emotion="Fear",
            confidence=0.9,
            prompt_version=1,
            analysis_duration_seconds=67.0,
        )
    )
    db_session.commit()

    response = app_client.get(f"/api/reports/{job.job_id}/articles")

    assert response.status_code == 200
    body = response.json()["articles"]
    assert len(body) == 1
    assert body[0]["title"] == "Bài 1"
    assert body[0]["crawl_duration_seconds"] == 1.5
    assert body[0]["analysis_duration_seconds"] == 67.0
    assert body[0]["total_duration_seconds"] == 68.5

    db_session.query(ArticleAnalysis).filter_by(article_id=article.article_id).delete()
    db_session.delete(article)
    db_session.delete(job)
    db_session.commit()


def test_articles_shows_null_durations_when_not_yet_analyzed(app_client, db_session):
    job = Job(source_ids=[], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30), status="running")
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        url="https://vtv.vn/bai-2",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Bài 2",
        status="pending_analysis",
        crawl_duration_seconds=2.0,
    )
    db_session.add(article)
    db_session.commit()

    response = app_client.get(f"/api/reports/{job.job_id}/articles")

    body = response.json()["articles"]
    assert body[0]["crawl_duration_seconds"] == 2.0
    assert body[0]["analysis_duration_seconds"] is None
    assert body[0]["total_duration_seconds"] is None

    db_session.delete(article)
    db_session.delete(job)
    db_session.commit()


def test_articles_returns_404_when_job_does_not_exist(app_client):
    response = app_client.get(f"/api/reports/{uuid.uuid4()}/articles")

    assert response.status_code == 404


def test_cancel_revokes_celery_task_and_sets_cancelled(app_client, db_session):
    job = Job(
        source_ids=[],
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        status="running",
        celery_task_id="fake-task-id",
    )
    db_session.add(job)
    db_session.commit()

    with patch("backend.routers.reports.celery_app") as mock_celery_app:
        response = app_client.post(f"/api/reports/{job.job_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    mock_celery_app.control.revoke.assert_called_once_with("fake-task-id", terminate=True)

    db_session.refresh(job)
    assert job.status == "cancelled"

    db_session.delete(job)
    db_session.commit()


def test_cancel_returns_400_when_job_already_completed(app_client, db_session):
    job = Job(
        source_ids=[],
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        status="completed",
        celery_task_id="fake-task-id",
    )
    db_session.add(job)
    db_session.commit()

    with patch("backend.routers.reports.celery_app") as mock_celery_app:
        response = app_client.post(f"/api/reports/{job.job_id}/cancel")

    assert response.status_code == 400
    mock_celery_app.control.revoke.assert_not_called()

    db_session.delete(job)
    db_session.commit()


def test_cancel_returns_404_when_job_does_not_exist(app_client):
    response = app_client.post(f"/api/reports/{uuid.uuid4()}/cancel")

    assert response.status_code == 404


def test_cancel_skips_revoke_when_celery_task_id_is_none(app_client, db_session):
    job = Job(source_ids=[], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30), status="pending")
    db_session.add(job)
    db_session.commit()

    with patch("backend.routers.reports.celery_app") as mock_celery_app:
        response = app_client.post(f"/api/reports/{job.job_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    mock_celery_app.control.revoke.assert_not_called()

    db_session.delete(job)
    db_session.commit()
```

- [ ] **Step 2: Verify test fail**

```bash
docker compose exec backend python -m pytest backend/tests/test_reports_router.py -v
```
Expected: test cũ `test_create_returns_job_id_and_triggers_celery_task` FAIL (`AttributeError: 'Job' object has no attribute 'celery_task_id'` đã có cột rồi nên thực ra fail vì giá trị `None != "fake-task-id"`); các test mới FAIL với `404`/`AttributeError` (endpoint `/articles`, `/cancel` chưa tồn tại)

- [ ] **Step 3: Implement**

Thay toàn bộ nội dung `backend/routers/reports.py`:

```python
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


class CreateReportRequest(BaseModel):
    source_ids: list[UUID]
    date_from: date
    date_to: date


@router.post("/create")
def create_report(payload: CreateReportRequest, db: Session = Depends(get_db)):
    if payload.date_from >= payload.date_to:
        raise HTTPException(status_code=400, detail="date_from phải nhỏ hơn date_to")

    sources = db.query(Source).filter(Source.source_id.in_(payload.source_ids)).all()
    if len(sources) != len(payload.source_ids):
        raise HTTPException(status_code=400, detail="Có source_id không tồn tại")
    if any(not source.is_active for source in sources):
        raise HTTPException(status_code=400, detail="Có nguồn không active")

    job = Job(source_ids=payload.source_ids, date_from=payload.date_from, date_to=payload.date_to)
    db.add(job)
    db.commit()

    result = run_report_job.delay(str(job.job_id))
    job.celery_task_id = result.id
    db.commit()

    return {"job_id": str(job.job_id), "status": job.status}


@router.get("/{job_id}/status")
def get_report_status(job_id: UUID, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")

    crawled = db.query(Article).filter_by(job_id=job_id).count()
    analyzed = db.query(ArticleAnalysis).filter_by(job_id=job_id).count()

    return {
        "job_id": str(job.job_id),
        "status": job.status,
        "progress": {"crawled": crawled, "analyzed": analyzed, "total_estimated": crawled},
        "error_log": job.error_log,
        "created_at": job.created_at,
    }


@router.get("/{job_id}/articles")
def get_report_articles(job_id: UUID, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")

    rows = (
        db.query(Article, ArticleAnalysis)
        .outerjoin(ArticleAnalysis, ArticleAnalysis.article_id == Article.article_id)
        .filter(Article.job_id == job_id)
        .order_by(Article.crawled_at)
        .all()
    )

    articles = []
    for article, analysis in rows:
        analysis_duration = analysis.analysis_duration_seconds if analysis else None
        total_duration = None
        if article.crawl_duration_seconds is not None and analysis_duration is not None:
            total_duration = article.crawl_duration_seconds + analysis_duration
        articles.append(
            {
                "title": article.title,
                "url": article.url,
                "status": article.status,
                "crawl_duration_seconds": article.crawl_duration_seconds,
                "analysis_duration_seconds": analysis_duration,
                "total_duration_seconds": total_duration,
            }
        )

    return {"articles": articles}


@router.post("/{job_id}/cancel")
def cancel_report(job_id: UUID, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    if job.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail="Job không ở trạng thái có thể hủy")

    if job.celery_task_id:
        celery_app.control.revoke(job.celery_task_id, terminate=True)

    job.status = "cancelled"
    db.commit()

    return {"job_id": str(job.job_id), "status": job.status}


@router.get("/{job_id}/download")
def download_report(job_id: UUID, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job chưa hoàn thành")

    return FileResponse(
        job.output_docx,
        filename=f"{job_id}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
```

- [ ] **Step 4: Verify test pass + chạy lại toàn bộ test suite backend**

```bash
docker compose exec backend python -m pytest backend/tests -v
```
Expected: tất cả PASS (20 test cũ + test mới của Task 2-5)

- [ ] **Step 5: Commit**

```bash
git add backend/routers/reports.py backend/tests/test_reports_router.py
git commit -m "feat: thêm GET /articles và POST /cancel, lưu celery_task_id khi tạo job"
```

---

## Task 6: `.env` / `.env.example` — `MAX_ARTICLES_PER_JOB`

**Files:**
- Modify: `.env`
- Modify: `.env.example`

- [ ] **Step 1: Thêm biến env**

Trong cả `.env` và `.env.example`, thêm dòng sau `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`:

```env
MAX_ARTICLES_PER_JOB=
```

- [ ] **Step 2: Verify**

```bash
grep MAX_ARTICLES_PER_JOB .env .env.example
```
Expected: cả 2 file đều có dòng này

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "feat: thêm MAX_ARTICLES_PER_JOB cho test/dev (.env không commit, đã gitignore)"
```

Lưu ý: `.env` đã nằm trong `.gitignore`, lệnh `git add` ở Step 3 chỉ thêm `.env.example` — không cần `git add .env`.

---

## Task 7: Frontend — bảng crawl trực tiếp + nút Cancel

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Thay toàn bộ nội dung file**

```tsx
"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
// UUID cố định seed sẵn cho nguồn VTV ở migration 0002_seed_vtv_source.py
const VTV_SOURCE_ID = "00000000-0000-0000-0000-000000000001";

function todayMinus(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

type JobStatus = {
  job_id: string;
  status: string;
  progress: { crawled: number; analyzed: number; total_estimated: number };
  error_log?: string;
};

type CrawledArticle = {
  title: string;
  url: string;
  status: string;
  crawl_duration_seconds: number | null;
  analysis_duration_seconds: number | null;
  total_duration_seconds: number | null;
};

function formatSeconds(value: number | null): string {
  return value === null ? "-" : `${value.toFixed(1)}s`;
}

export default function Home() {
  const [dateFrom, setDateFrom] = useState(todayMinus(7));
  const [dateTo, setDateTo] = useState(todayMinus(0));
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [articles, setArticles] = useState<CrawledArticle[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const activeStatuses = ["pending", "running"];
    if (!jobId || !status || !activeStatuses.includes(status.status)) return;
    const interval = setInterval(async () => {
      const [statusRes, articlesRes] = await Promise.all([
        fetch(`${API_BASE}/api/reports/${jobId}/status`),
        fetch(`${API_BASE}/api/reports/${jobId}/articles`),
      ]);
      if (statusRes.ok) setStatus(await statusRes.json());
      if (articlesRes.ok) setArticles((await articlesRes.json()).articles);
    }, 3000);
    return () => clearInterval(interval);
  }, [jobId, status?.status]);

  async function handleSubmit() {
    setError(null);
    const res = await fetch(`${API_BASE}/api/reports/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_ids: [VTV_SOURCE_ID], date_from: dateFrom, date_to: dateTo }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Tạo báo cáo thất bại");
      return;
    }
    const data = await res.json();
    setJobId(data.job_id);
    setArticles([]);
    setStatus({ job_id: data.job_id, status: data.status, progress: { crawled: 0, analyzed: 0, total_estimated: 0 } });
  }

  async function handleCancel() {
    if (!status) return;
    const res = await fetch(`${API_BASE}/api/reports/${status.job_id}/cancel`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      setStatus({ ...status, status: data.status });
    }
  }

  const disabled = !dateFrom || !dateTo || dateFrom >= dateTo;
  const canCancel = status?.status === "pending" || status?.status === "running";

  return (
    <main className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold mb-4">NGS Monitor</h1>

      <div className="mb-4">
        <label className="block font-medium">Nguồn dữ liệu</label>
        <p>VTV News</p>
      </div>

      <div className="mb-4 flex gap-4">
        <div>
          <label className="block font-medium">Từ ngày</label>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div>
          <label className="block font-medium">Đến ngày</label>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
      </div>

      <button
        className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
        disabled={disabled}
        onClick={handleSubmit}
      >
        Tạo báo cáo
      </button>

      {error && <p className="text-red-600 mt-4">{error}</p>}

      {status && (
        <div className="mt-6">
          <p>Trạng thái: {status.status}</p>
          <p>
            Đã crawl: {status.progress.crawled} bài — Đã phân tích: {status.progress.analyzed} bài
          </p>
          {canCancel && (
            <button className="bg-red-600 text-white px-3 py-1 rounded mt-2" onClick={handleCancel}>
              Cancel
            </button>
          )}
          {status.status === "completed" && (
            <a className="text-blue-600 underline" href={`${API_BASE}/api/reports/${status.job_id}/download`}>
              Tải báo cáo DOCX
            </a>
          )}
          {status.status === "failed" && <p className="text-red-600">Lỗi: {status.error_log}</p>}
          {status.status === "cancelled" && <p className="text-gray-600">Job đã bị hủy.</p>}
        </div>
      )}

      {articles.length > 0 && (
        <table className="mt-6 w-full text-sm border-collapse">
          <thead>
            <tr className="border-b text-left">
              <th className="p-1">Tiêu đề</th>
              <th className="p-1">Trạng thái</th>
              <th className="p-1">Crawl</th>
              <th className="p-1">Phân tích</th>
              <th className="p-1">Tổng</th>
            </tr>
          </thead>
          <tbody>
            {articles.map((a) => (
              <tr key={a.url} className="border-b">
                <td className="p-1">
                  <a href={a.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">
                    {a.title}
                  </a>
                </td>
                <td className="p-1">{a.status}</td>
                <td className="p-1">{formatSeconds(a.crawl_duration_seconds)}</td>
                <td className="p-1">{formatSeconds(a.analysis_duration_seconds)}</td>
                <td className="p-1">{formatSeconds(a.total_duration_seconds)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Rebuild + restart frontend, verify SSR render**

```bash
docker compose build frontend
docker compose up -d frontend
curl -s http://localhost:3000/ | grep -o "Cancel\|Tiêu đề" | sort -u
```
Expected: lệnh `curl | grep` không ra gì bất thường (button Cancel và bảng chỉ render khi có `status`/`articles`, nên SSR ban đầu sẽ không thấy — chỉ cần `curl` trả `200` và không có lỗi build)

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/
```
Expected: `200`

- [ ] **Step 3: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat: thêm bảng crawl trực tiếp (kèm benchmark) và nút Cancel vào FE"
```

---

## Task 8: Rebuild toàn bộ + Verify cuối với dữ liệu thật

**Files:** không tạo/sửa file mới — chỉ build/run/verify

- [ ] **Step 1: Restart backend + celery-worker để nhận code mới (bind mount, không cần rebuild image), rồi chạy migration mới**

```bash
docker compose up -d backend celery-worker
docker compose exec backend sh -c "cd /app/backend && alembic upgrade head"
docker compose restart celery-worker
```

- [ ] **Step 2: Chạy lại toàn bộ test suite backend**

```bash
docker compose exec backend python -m pytest backend/tests -v
```
Expected: tất cả test PASS (không còn cái nào FAIL)

- [ ] **Step 3: Verify thật — giới hạn số bài**

```bash
sed -i 's/^MAX_ARTICLES_PER_JOB=.*/MAX_ARTICLES_PER_JOB=3/' .env
docker compose up -d backend celery-worker
curl -s -X POST http://localhost:8000/api/reports/create -H "Content-Type: application/json" -d '{"source_ids": ["00000000-0000-0000-0000-000000000001"], "date_from": "2026-06-20", "date_to": "2026-06-25"}'
```
Ghi lại `job_id` trả về, đợi vài giây rồi:
```bash
curl -s http://localhost:8000/api/reports/<job_id>/status
```
Expected: `progress.crawled` dừng lại ở đúng `3`, không tiếp tục tăng sau khi đạt giới hạn (so với lần verify Slice 1 trước crawl được 104 bài)

- [ ] **Step 4: Verify thật — bảng `/articles` có duration**

```bash
curl -s http://localhost:8000/api/reports/<job_id>/articles
```
Expected: JSON có `crawl_duration_seconds` > 0 cho từng bài; `analysis_duration_seconds`/`total_duration_seconds` là `null` cho tới khi AI xử lý xong, sau đó có giá trị > 0

- [ ] **Step 5: Verify thật — Cancel**

```bash
curl -s -X POST http://localhost:8000/api/reports/create -H "Content-Type: application/json" -d '{"source_ids": ["00000000-0000-0000-0000-000000000001"], "date_from": "2026-06-01", "date_to": "2026-06-25"}'
```
Ghi lại `job_id` mới, ngay sau đó:
```bash
curl -s -X POST http://localhost:8000/api/reports/<job_id_moi>/cancel
docker compose logs celery-worker --tail 5
curl -s http://localhost:8000/api/reports/<job_id_moi>/status
```
Expected: response cancel trả `{"job_id": ..., "status": "cancelled"}`; log celery-worker có dòng `Terminating ...`; gọi `/status` sau đó vẫn thấy `status: cancelled`, `progress.crawled` không tăng thêm nữa

- [ ] **Step 6: Verify FE thật trên `localhost:3000`**

Tự mở `localhost:3000`, bấm "Tạo báo cáo", quan sát bảng 5 cột cập nhật theo polling, bấm nút "Cancel" giữa lúc đang chạy, xác nhận trạng thái chuyển đúng.

- [ ] **Step 7: Trả `MAX_ARTICLES_PER_JOB` về rỗng cho môi trường dùng thật (không để sót giá trị test)**

```bash
sed -i 's/^MAX_ARTICLES_PER_JOB=.*/MAX_ARTICLES_PER_JOB=/' .env
docker compose up -d backend celery-worker
```

Không cần commit ở Task này — `.env` không nằm trong git.
