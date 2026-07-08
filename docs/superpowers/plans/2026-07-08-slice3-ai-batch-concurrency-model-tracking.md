# Slice 3 — AI batch/concurrency + track model + verify dữ liệu thật (2 giai đoạn)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuyển `analyze_article()`/`_analyze_articles()` sang xử lý bất đồng bộ có giới hạn song song qua biến `AI_CONCURRENCY` (mặc định `1` = đúng hành vi tuần tự hiện tại), ghi lại tên model AI đã dùng (`ai_model`) để chuẩn bị cho việc đổi model khi chuyển sang server GPU sau này, và verify pipeline hoạt động đúng trên dữ liệu thật (2 giai đoạn: smoke test 5 bài → verify chính thức 15 bài).

**Architecture:** `analyze_article()` (`backend/ai/ollama_client.py`) chuyển từ `httpx.Client` sync sang `httpx.AsyncClient` async, giữ nguyên toàn bộ logic hiện có (retry JSON, truncate, threshold). Thêm `analyze_articles_batch()` bọc `asyncio.Semaphore(AI_CONCURRENCY)` quanh nhiều lệnh gọi `analyze_article()` chạy song song qua `asyncio.gather(..., return_exceptions=True)` — mỗi bài lỗi cô lập riêng, không làm hỏng cả batch. `_analyze_articles()` (`backend/workers/report_job.py`) gọi batch này qua `asyncio.run(...)`, ghi DB tuần tự sau khi có kết quả (không chuyển sang SQLAlchemy async). Thêm cột `ai_model` (migration `0008`) song song `prompt_version` đã có.

Xem đầy đủ bối cảnh + quyết định đã chốt qua trao đổi tại spec: `docs/superpowers/specs/2026-07-08-slice3-ai-batch-model-tracking-design.md`.

**Tech Stack:** Python, asyncio, httpx.AsyncClient, pytest, unittest.mock.AsyncMock, Alembic

---

## Mapping file → trách nhiệm sau khi sửa

| File | Thay đổi |
|---|---|
| `backend/alembic/versions/0008_add_ai_model_column.py` | Migration mới — thêm cột `ai_model` NOT NULL (backfill `qwen3:8b`) |
| `backend/models/article_analysis.py` | Thêm `ai_model = Column(String(255), nullable=False)` |
| `backend/ai/ollama_client.py` | `analyze_article()` → async + gắn `ai_model`; thêm `analyze_articles_batch()` |
| `backend/tests/test_ollama_client.py` | Chuyển toàn bộ sang gọi qua `asyncio.run(...)`; thêm test `ai_model` + test batch/concurrency/isolation lỗi |
| `backend/workers/report_job.py` | `_analyze_articles()` gọi `analyze_articles_batch()`, đọc `AI_CONCURRENCY`, insert `ai_model` |
| `backend/tests/test_report_job.py` | Đổi patch target sang `analyze_articles_batch`; thêm test `ai_model`, concurrency env, exception không xác định propagate |
| `.env` / `.env.example` | Thêm `AI_CONCURRENCY=1` |
| `backend/scripts/__init__.py` | Mới (package rỗng) |
| `backend/scripts/export_analysis_csv.py` | Script export CSV để đọc lướt kết quả AI (Giai đoạn B) |
| `backend/tests/test_export_analysis_csv.py` | Test script export |
| `CLAUDE.md` | Cập nhật roadmap Slice 3 (tick `[x]`), verify "15 bài" thay "≥50 bài", thêm quyết định + checklist chuyển server |

---

## Task 1 — Migration `0008`: thêm cột `ai_model`

**Files:**
- Create: `backend/alembic/versions/0008_add_ai_model_column.py`
- Modify: `backend/models/article_analysis.py`

- [ ] **Step 1.1: Viết migration**

```python
"""thêm ai_model vào article_analysis — track model AI đã dùng, chuẩn bị đổi model khi chuyển server GPU

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("article_analysis", sa.Column("ai_model", sa.String(255)))
    # Backfill: mọi bản ghi trước migration này đều chạy bằng qwen3:8b (model duy nhất
    # từng dùng, xem Quick Reference CLAUDE.md) — không có model nào khác để suy luận.
    op.execute(sa.text("UPDATE article_analysis SET ai_model = 'qwen3:8b' WHERE ai_model IS NULL"))
    op.alter_column("article_analysis", "ai_model", nullable=False)


def downgrade():
    op.drop_column("article_analysis", "ai_model")
```

- [ ] **Step 1.2: Cập nhật model**

Tìm trong `backend/models/article_analysis.py`:
```python
    # Version của prompt (backend/ai/prompts/vN.py) đã sinh ra bản phân tích này —
    # cần để không lẫn kết quả giữa các lần tinh chỉnh prompt ở Slice 3+.
    prompt_version = Column(Integer, nullable=False)
```

Thay bằng:
```python
    # Version của prompt (backend/ai/prompts/vN.py) đã sinh ra bản phân tích này —
    # cần để không lẫn kết quả giữa các lần tinh chỉnh prompt ở Slice 3+.
    prompt_version = Column(Integer, nullable=False)
    # Tên model AI đã dùng (VD "qwen3:8b") — cần để không lẫn dữ liệu khi sau này đổi
    # model trên server GPU (xem CLAUDE.md, Slice 3).
    ai_model = Column(String(255), nullable=False)
```

- [ ] **Step 1.3: Chạy migration thật**

```bash
docker compose exec backend sh -c "cd /app/backend && alembic upgrade head"
```

- [ ] **Step 1.4: Verify DB**

```bash
docker compose exec postgres psql -U ngs -d ngs_monitor -c "\d article_analysis"
```

Expected: có cột `ai_model` kiểu `character varying(255)`, `not null`.

- [ ] **Step 1.5: Commit**

```bash
git add backend/alembic/versions/0008_add_ai_model_column.py backend/models/article_analysis.py
git commit -m "$(cat <<'EOF'
feat: thêm cột ai_model vào article_analysis

Track tên model AI đã dùng cho từng bài phân tích, song song prompt_version
đã có — chuẩn bị cho việc đổi model khi chuyển từ laptop (qwen3:8b CPU-only)
sang server GPU sau này, tránh lẫn dữ liệu giữa các model khác nhau khi
so sánh/tổng hợp báo cáo.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — `ollama_client.py`: chuyển `analyze_article()` sang async + gắn `ai_model`

**Files:**
- Modify: `backend/ai/ollama_client.py`
- Modify: `backend/tests/test_ollama_client.py`

- [ ] **Step 2.1: Viết lại toàn bộ `test_ollama_client.py` (gọi qua `asyncio.run`, thêm assertion `ai_model`)**

```python
import asyncio
import json

import httpx
import pytest

from backend.ai.ollama_client import analyze_article
from backend.ai.prompts.v1 import PROMPT_VERSION

VALID_JSON = """{
  "topics": ["Tin giả và thông tin sai lệch"],
  "keywords": ["deepfake", "lừa đảo"],
  "sentiment": "negative",
  "emotion": "Fear",
  "confidence": 0.85,
  "summary": "Tóm tắt bài viết."
}"""


def _client_with_responses(responses: list[str]) -> httpx.AsyncClient:
    state = {"i": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        text = responses[min(state["i"], len(responses) - 1)]
        state["i"] += 1
        return httpx.Response(200, json={"response": text})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_parses_valid_json_response_and_attaches_prompt_version(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:8b")
    client = _client_with_responses([VALID_JSON])

    result = asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))

    assert result["topics"] == ["Tin giả và thông tin sai lệch"]
    assert result["sentiment"] == "negative"
    assert result["emotion"] == "Fear"
    assert result["confidence"] == 0.85
    assert result["prompt_version"] == PROMPT_VERSION
    assert result["needs_review"] is False
    assert result["ai_model"] == "qwen3:8b"


def test_strips_markdown_code_fence_around_json():
    fenced = f"```json\n{VALID_JSON}\n```"
    client = _client_with_responses([fenced])

    result = asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))

    assert result["sentiment"] == "negative"


def test_flags_needs_review_when_confidence_below_threshold():
    low_confidence = VALID_JSON.replace('"confidence": 0.85', '"confidence": 0.4')
    client = _client_with_responses([low_confidence])

    result = asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))

    assert result["needs_review"] is True


def test_retries_once_on_invalid_json_then_succeeds():
    client = _client_with_responses(["không phải json", VALID_JSON])

    result = asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))

    assert result["sentiment"] == "negative"


def test_raises_after_invalid_json_twice():
    client = _client_with_responses(["không phải json", "vẫn không phải json"])

    with pytest.raises(ValueError):
        asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))


def test_returns_analysis_duration_seconds():
    client = _client_with_responses([VALID_JSON])

    result = asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))

    assert result["analysis_duration_seconds"] > 0


def test_truncates_content_at_sentence_boundary_not_mid_word(monkeypatch):
    monkeypatch.setenv("AI_MAX_CONTENT_LENGTH", "20")
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["prompt"] = json.loads(request.content)["prompt"]
        return httpx.Response(200, json={"response": VALID_JSON})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    content = "Câu đầu tiên ngắn. Câu thứ hai dài hơn nhiều và sẽ bị cắt bỏ."
    asyncio.run(analyze_article("Tiêu đề", content, client=client))

    assert "Câu đầu tiên ngắn." in captured["prompt"]
    assert "Câu thứ hai" not in captured["prompt"]
```

- [ ] **Step 2.2: Chạy để xác nhận FAIL** (expected — `analyze_article` vẫn là hàm sync, không `await` được, và chưa có `ai_model`)

```bash
docker compose exec backend pytest backend/tests/test_ollama_client.py -v
```

- [ ] **Step 2.3: Viết lại `analyze_article()` trong `backend/ai/ollama_client.py` — chuyển async + gắn `ai_model`**

Tìm:
```python
def analyze_article(title: str, content: str, client: httpx.Client | None = None) -> dict:
    owns_client = client is None
    client = client or httpx.Client(timeout=int(os.environ.get("AI_TIMEOUT_SECONDS", "360")))

    max_content_length = int(os.environ.get("AI_MAX_CONTENT_LENGTH", "5000"))
    confidence_threshold = float(os.environ.get("AI_CONFIDENCE_THRESHOLD", "0.6"))
    prompt = CLASSIFICATION_PROMPT.format(
        title=title,
        content_snippet=_truncate_at_sentence_boundary(content, max_content_length),
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

Thay bằng:
```python
async def analyze_article(title: str, content: str, client: httpx.AsyncClient | None = None) -> dict:
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=int(os.environ.get("AI_TIMEOUT_SECONDS", "360")))

    max_content_length = int(os.environ.get("AI_MAX_CONTENT_LENGTH", "5000"))
    confidence_threshold = float(os.environ.get("AI_CONFIDENCE_THRESHOLD", "0.6"))
    prompt = CLASSIFICATION_PROMPT.format(
        title=title,
        content_snippet=_truncate_at_sentence_boundary(content, max_content_length),
        topic_list="\n".join(f"- {t}" for t in TOPIC_GROUPS),
    )

    try:
        start = time.perf_counter()
        result = None
        last_error: Exception | None = None
        for _attempt in range(2):
            response = await client.post(
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
        result["ai_model"] = os.environ["OLLAMA_MODEL"]
        result["analysis_duration_seconds"] = time.perf_counter() - start
        return result
    finally:
        if owns_client:
            await client.aclose()
```

- [ ] **Step 2.4: Chạy lại test — phải PASS**

```bash
docker compose exec backend pytest backend/tests/test_ollama_client.py -v
```

- [ ] **Step 2.5: Commit**

```bash
git add backend/ai/ollama_client.py backend/tests/test_ollama_client.py
git commit -m "$(cat <<'EOF'
refactor: chuyển analyze_article() sang async + gắn ai_model vào kết quả

Chuẩn bị cho analyze_articles_batch() (task kế tiếp) — cần async để chạy
nhiều lệnh gọi Ollama song song qua asyncio.gather. Hành vi/logic giữ
nguyên hoàn toàn (retry JSON, truncate câu, threshold needs_review).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — `ollama_client.py`: thêm `analyze_articles_batch()`

**Files:**
- Modify: `backend/ai/ollama_client.py`
- Modify: `backend/tests/test_ollama_client.py`

- [ ] **Step 3.1: Thêm test batch vào cuối `test_ollama_client.py`**

Thêm import `asyncio` đã có sẵn từ Task 2 — chỉ cần thêm import hàm mới:

Tìm:
```python
from backend.ai.ollama_client import analyze_article
```

Thay bằng:
```python
from backend.ai.ollama_client import analyze_article, analyze_articles_batch
```

Thêm vào cuối file:
```python
def test_analyze_articles_batch_respects_concurrency_limit():
    state = {"current": 0, "max_seen": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        state["current"] += 1
        state["max_seen"] = max(state["max_seen"], state["current"])
        await asyncio.sleep(0.05)
        state["current"] -= 1
        return httpx.Response(200, json={"response": VALID_JSON})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    articles = [(f"Tiêu đề {i}", "Nội dung") for i in range(6)]

    results = asyncio.run(analyze_articles_batch(articles, concurrency=2, client=client))

    assert len(results) == 6
    assert all(isinstance(r, dict) for r in results)
    assert state["max_seen"] == 2


def test_analyze_articles_batch_isolates_single_failure_from_others():
    call_count = {"i": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        idx = call_count["i"]
        call_count["i"] += 1
        # 2 lệnh gọi đầu (bài đầu tiên, retry 1 lần) trả JSON lỗi -> ValueError,
        # các lệnh gọi sau (bài 2, 3) trả JSON hợp lệ.
        if idx < 2:
            return httpx.Response(200, json={"response": "không phải json"})
        return httpx.Response(200, json={"response": VALID_JSON})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    articles = [("Bài lỗi", "Nội dung"), ("Bài ổn 1", "Nội dung"), ("Bài ổn 2", "Nội dung")]

    # concurrency=1 để đảm bảo thứ tự gọi đúng như handler giả lập ở trên
    results = asyncio.run(analyze_articles_batch(articles, concurrency=1, client=client))

    assert isinstance(results[0], ValueError)
    assert isinstance(results[1], dict)
    assert isinstance(results[2], dict)
```

- [ ] **Step 3.2: Chạy để xác nhận FAIL** (expected — `analyze_articles_batch` chưa tồn tại)

```bash
docker compose exec backend pytest backend/tests/test_ollama_client.py -v
```

- [ ] **Step 3.3: Thêm `analyze_articles_batch()` vào `backend/ai/ollama_client.py`**

Tìm:
```python
import json
import os
import re
import time

import httpx
```

Thay bằng:
```python
import asyncio
import json
import os
import re
import time

import httpx
```

Thêm vào cuối file (sau `analyze_article`):
```python


async def analyze_articles_batch(
    articles: list[tuple[str, str]],
    concurrency: int,
    client: httpx.AsyncClient | None = None,
) -> list[dict | Exception]:
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=int(os.environ.get("AI_TIMEOUT_SECONDS", "360")))
    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded(title: str, content: str) -> dict:
        async with semaphore:
            return await analyze_article(title, content, client=client)

    try:
        tasks = [_bounded(title, content) for title, content in articles]
        # return_exceptions=True: 1 bài lỗi (JSON không hợp lệ / lỗi HTTP) không được raise
        # ra ngoài làm hỏng cả batch — trả về Exception ngay đúng vị trí bài đó, để caller
        # (_analyze_articles trong report_job.py) tự quyết định insert status="error".
        return await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        if owns_client:
            await client.aclose()
```

- [ ] **Step 3.4: Chạy lại test — phải PASS**

```bash
docker compose exec backend pytest backend/tests/test_ollama_client.py -v
```

- [ ] **Step 3.5: Commit**

```bash
git add backend/ai/ollama_client.py backend/tests/test_ollama_client.py
git commit -m "$(cat <<'EOF'
feat: thêm analyze_articles_batch() — xử lý AI song song có giới hạn

Bọc asyncio.Semaphore quanh nhiều lệnh gọi analyze_article() chạy đồng
thời qua asyncio.gather(return_exceptions=True) — mỗi bài lỗi cô lập
riêng, không làm hỏng cả batch. Chưa được gọi ở đâu (nối vào report_job
ở task kế tiếp).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — `report_job.py`: dùng `analyze_articles_batch()` + `AI_CONCURRENCY` + `ai_model`

**Files:**
- Modify: `backend/workers/report_job.py`
- Modify: `backend/tests/test_report_job.py`

- [ ] **Step 4.1: Sửa test hiện có + thêm test mới trong `test_report_job.py`**

Tìm:
```python
import uuid
from datetime import date, datetime
from unittest.mock import patch

import httpx

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

from backend.models import Article, ArticleAnalysis, Job, Source
from backend.workers.report_job import _analyze_articles, _crawl_sources
```

Tìm toàn bộ hàm `test_analyze_articles_marks_error_on_http_timeout_and_continues`:
```python
def test_analyze_articles_marks_error_on_http_timeout_and_continues(db_session):
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        source_id=source.source_id,
        url="https://example.test/slow-article",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Title",
        content_raw="Content",
        status="pending_analysis",
    )
    db_session.add(article)
    db_session.commit()

    try:
        with patch("backend.workers.report_job.analyze_article", side_effect=httpx.ReadTimeout("timed out")):
            _analyze_articles(db_session, job)

        db_session.refresh(article)
        assert article.status == "error"
        assert db_session.query(ArticleAnalysis).filter_by(article_id=article.article_id).count() == 0
    finally:
        db_session.delete(article)
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()
```

Thay bằng (đổi patch target sang `analyze_articles_batch`, trả list chứa Exception thay vì `side_effect` raise trực tiếp — đúng hợp đồng mới của hàm batch) và thêm 4 test mới ngay sau:
```python
def test_analyze_articles_marks_error_on_http_timeout_and_continues(db_session):
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        source_id=source.source_id,
        url="https://example.test/slow-article",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Title",
        content_raw="Content",
        status="pending_analysis",
    )
    db_session.add(article)
    db_session.commit()

    try:
        with patch(
            "backend.workers.report_job.analyze_articles_batch",
            AsyncMock(return_value=[httpx.ReadTimeout("timed out")]),
        ):
            _analyze_articles(db_session, job)

        db_session.refresh(article)
        assert article.status == "error"
        assert db_session.query(ArticleAnalysis).filter_by(article_id=article.article_id).count() == 0
    finally:
        db_session.delete(article)
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_analyze_articles_inserts_ai_model_from_result(db_session):
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        source_id=source.source_id,
        url="https://example.test/ok-article",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Title",
        content_raw="Content",
        status="pending_analysis",
    )
    db_session.add(article)
    db_session.commit()

    fake_result = {
        "topics": ["Tin giả và thông tin sai lệch"],
        "keywords": ["deepfake"],
        "sentiment": "negative",
        "emotion": "Fear",
        "confidence": 0.85,
        "needs_review": False,
        "summary": "Tóm tắt.",
        "prompt_version": 1,
        "ai_model": "qwen3:8b",
        "analysis_duration_seconds": 1.23,
    }

    try:
        with patch(
            "backend.workers.report_job.analyze_articles_batch",
            AsyncMock(return_value=[fake_result]),
        ):
            _analyze_articles(db_session, job)

        db_session.refresh(article)
        assert article.status == "analyzed"
        analysis = db_session.query(ArticleAnalysis).filter_by(article_id=article.article_id).one()
        assert analysis.ai_model == "qwen3:8b"
    finally:
        db_session.query(ArticleAnalysis).filter_by(article_id=article.article_id).delete()
        db_session.delete(article)
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_analyze_articles_reraises_unexpected_exception_type(db_session):
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        source_id=source.source_id,
        url="https://example.test/bug-article",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Title",
        content_raw="Content",
        status="pending_analysis",
    )
    db_session.add(article)
    db_session.commit()

    try:
        with patch(
            "backend.workers.report_job.analyze_articles_batch",
            AsyncMock(return_value=[RuntimeError("bug không lường trước")]),
        ), pytest.raises(RuntimeError):
            _analyze_articles(db_session, job)
    finally:
        db_session.delete(article)
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_analyze_articles_passes_ai_concurrency_env_var_to_batch(db_session, monkeypatch):
    monkeypatch.setenv("AI_CONCURRENCY", "3")

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        source_id=source.source_id,
        url="https://example.test/concurrency-article",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Title",
        content_raw="Content",
        status="pending_analysis",
    )
    db_session.add(article)
    db_session.commit()

    fake_batch = AsyncMock(return_value=[httpx.ReadTimeout("timed out")])

    try:
        with patch("backend.workers.report_job.analyze_articles_batch", fake_batch):
            _analyze_articles(db_session, job)

        assert fake_batch.call_args.kwargs["concurrency"] == 3
    finally:
        db_session.delete(article)
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_analyze_articles_defaults_ai_concurrency_to_1_when_env_unset(db_session, monkeypatch):
    monkeypatch.delenv("AI_CONCURRENCY", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        source_id=source.source_id,
        url="https://example.test/default-concurrency-article",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Title",
        content_raw="Content",
        status="pending_analysis",
    )
    db_session.add(article)
    db_session.commit()

    fake_batch = AsyncMock(return_value=[httpx.ReadTimeout("timed out")])

    try:
        with patch("backend.workers.report_job.analyze_articles_batch", fake_batch):
            _analyze_articles(db_session, job)

        assert fake_batch.call_args.kwargs["concurrency"] == 1
    finally:
        db_session.delete(article)
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()
```

- [ ] **Step 4.2: Chạy để xác nhận FAIL** (expected — `report_job.py` vẫn import/gọi `analyze_article`, chưa có `analyze_articles_batch`/`AI_CONCURRENCY`/`ai_model`)

```bash
docker compose exec backend pytest backend/tests/test_report_job.py -v
```

- [ ] **Step 4.3: Sửa `backend/workers/report_job.py`**

Tìm:
```python
import logging
import os
import time
from datetime import datetime

import httpx

from backend.ai.ollama_client import analyze_article
from backend.crawler.article import compute_url_hash
```

Thay bằng:
```python
import asyncio
import logging
import os
import time
from datetime import datetime

import httpx

from backend.ai.ollama_client import analyze_articles_batch
from backend.crawler.article import compute_url_hash
```

Tìm:
```python
def _analyze_articles(db, job: Job) -> None:
    pending = db.query(Article).filter_by(job_id=job.job_id, status="pending_analysis").all()
    for article in pending:
        try:
            result = analyze_article(article.title, article.content_raw)
        except (ValueError, httpx.HTTPError):
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

Thay bằng:
```python
def _analyze_articles(db, job: Job) -> None:
    pending = db.query(Article).filter_by(job_id=job.job_id, status="pending_analysis").all()
    if not pending:
        return

    # AI_CONCURRENCY: số bài AI xử lý đồng thời trong job này — mặc định 1, cho ra đúng
    # hành vi tuần tự cũ (an toàn cho CPU-only). Chỉ tăng khi chạy trên hạ tầng có GPU
    # (xem CLAUDE.md — checklist chuyển sang server).
    concurrency = int(os.environ.get("AI_CONCURRENCY", "1"))
    results = asyncio.run(
        analyze_articles_batch([(a.title, a.content_raw) for a in pending], concurrency=concurrency)
    )

    for article, result in zip(pending, results):
        if isinstance(result, (ValueError, httpx.HTTPError)):
            logger.error("AI phân tích lỗi cho bài %s", article.url, exc_info=result)
            article.status = "error"
            db.commit()
            continue
        if isinstance(result, Exception):
            # Lỗi không thuộc loại đã biết (JSON không hợp lệ / lỗi HTTP) — không nuốt âm
            # thầm, để job fail rõ ràng thay vì báo completed sai (xem 10-error-handling.md)
            raise result

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
                ai_model=result["ai_model"],
                analysis_duration_seconds=result.get("analysis_duration_seconds"),
            )
        )
        article.status = "analyzed"
        db.commit()
```

- [ ] **Step 4.4: Chạy lại test — phải PASS**

```bash
docker compose exec backend pytest backend/tests/test_report_job.py -v
```

- [ ] **Step 4.5: Commit**

```bash
git add backend/workers/report_job.py backend/tests/test_report_job.py
git commit -m "$(cat <<'EOF'
feat: _analyze_articles dùng analyze_articles_batch qua AI_CONCURRENCY

Nối analyze_articles_batch() (task trước) vào report_job.py — mặc định
AI_CONCURRENCY=1 giữ đúng hành vi tuần tự cũ. Ghi thêm ai_model khi insert
ArticleAnalysis. Exception không thuộc (ValueError, httpx.HTTPError) được
raise lại thay vì nuốt âm thầm, giữ đúng hành vi lỗi-không-lường-trước
làm fail cả job như code cũ.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — Thêm biến `AI_CONCURRENCY`

**Files:**
- Modify: `.env`
- Modify: `.env.example`

- [ ] **Step 5.1: Sửa `.env.example`**

Tìm:
```
AI_CONFIDENCE_THRESHOLD=0.6
AI_MAX_CONTENT_LENGTH=5000
AI_TIMEOUT_SECONDS=360
```

Thay bằng:
```
AI_CONFIDENCE_THRESHOLD=0.6
AI_MAX_CONTENT_LENGTH=5000
AI_TIMEOUT_SECONDS=360
# Số bài AI xử lý đồng thời trong 1 job. Mặc định 1 = tuần tự, an toàn cho CPU-only
# (laptop). Chỉ tăng khi chạy trên hạ tầng có GPU — tăng trên CPU-only có thể LÀM CHẬM
# hơn (tranh chấp CPU giữa các request), không tự nhiên nhanh hơn. Benchmark lại trước
# khi đổi trên môi trường mới.
AI_CONCURRENCY=1
```

- [ ] **Step 5.2: Sửa `.env`** (áp dụng cùng thay đổi, không có comment vì `.env` không commit)

Tìm:
```
AI_CONFIDENCE_THRESHOLD=0.6
AI_MAX_CONTENT_LENGTH=5000
AI_TIMEOUT_SECONDS=360
```

Thay bằng:
```
AI_CONFIDENCE_THRESHOLD=0.6
AI_MAX_CONTENT_LENGTH=5000
AI_TIMEOUT_SECONDS=360
AI_CONCURRENCY=1
```

- [ ] **Step 5.3: Restart để nạp env mới**

```bash
docker compose restart backend celery-worker
```

- [ ] **Step 5.4: Commit** (chỉ `.env.example` — `.env` bị gitignore)

```bash
git add .env.example
git commit -m "$(cat <<'EOF'
feat: thêm AI_CONCURRENCY vào .env.example

Công tắc số bài AI xử lý song song, mặc định 1 (tuần tự, an toàn CPU-only).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — Script export CSV để đọc lướt kết quả (Giai đoạn B)

**Files:**
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/export_analysis_csv.py`
- Test: `backend/tests/test_export_analysis_csv.py`

- [ ] **Step 6.1: Tạo package rỗng**

```bash
touch backend/scripts/__init__.py
```

- [ ] **Step 6.2: Viết failing test**

```python
import csv
import uuid
from datetime import date

from backend.models import Article, ArticleAnalysis, Job, Source
from backend.scripts.export_analysis_csv import export_analysis_csv


def test_export_analysis_csv_writes_expected_row(db_session, tmp_path):
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        source_id=source.source_id,
        url="https://example.test/bai-viet",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Tiêu đề test",
        content_raw="Nội dung",
        status="analyzed",
    )
    db_session.add(article)
    db_session.flush()

    analysis = ArticleAnalysis(
        article_id=article.article_id,
        job_id=job.job_id,
        topics=["Tin giả và thông tin sai lệch"],
        keywords=["deepfake"],
        sentiment="negative",
        emotion="Fear",
        confidence=0.85,
        needs_review=False,
        summary="Tóm tắt.",
        prompt_version=1,
        ai_model="qwen3:8b",
    )
    db_session.add(analysis)
    db_session.commit()

    output_path = tmp_path / "export.csv"

    try:
        export_analysis_csv(str(job.job_id), str(output_path))

        with open(output_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 1
        assert rows[0]["title"] == "Tiêu đề test"
        assert rows[0]["url"] == "https://example.test/bai-viet"
        assert rows[0]["sentiment"] == "negative"
        assert rows[0]["ai_model"] == "qwen3:8b"
    finally:
        db_session.delete(analysis)
        db_session.delete(article)
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()
```

- [ ] **Step 6.3: Chạy để xác nhận FAIL** (expected — module `export_analysis_csv` chưa tồn tại)

```bash
docker compose exec backend pytest backend/tests/test_export_analysis_csv.py -v
```

- [ ] **Step 6.4: Viết `backend/scripts/export_analysis_csv.py`**

```python
import csv
import sys

from backend.db import SessionLocal
from backend.models import Article, ArticleAnalysis


def export_analysis_csv(job_id: str, output_path: str) -> None:
    db = SessionLocal()
    try:
        rows = (
            db.query(Article, ArticleAnalysis)
            .join(ArticleAnalysis, ArticleAnalysis.article_id == Article.article_id)
            .filter(Article.job_id == job_id)
            .all()
        )
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "title", "url", "topics", "keywords", "sentiment", "emotion",
                    "confidence", "needs_review", "summary", "ai_model",
                ]
            )
            for article, analysis in rows:
                writer.writerow(
                    [
                        article.title,
                        article.url,
                        ";".join(analysis.topics or []),
                        ";".join(analysis.keywords or []),
                        analysis.sentiment,
                        analysis.emotion,
                        analysis.confidence,
                        analysis.needs_review,
                        analysis.summary,
                        analysis.ai_model,
                    ]
                )
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m backend.scripts.export_analysis_csv <job_id> <output_path>")
        sys.exit(1)
    export_analysis_csv(sys.argv[1], sys.argv[2])
```

- [ ] **Step 6.5: Chạy lại test — phải PASS**

```bash
docker compose exec backend pytest backend/tests/test_export_analysis_csv.py -v
```

- [ ] **Step 6.6: Commit**

```bash
git add backend/scripts/__init__.py backend/scripts/export_analysis_csv.py backend/tests/test_export_analysis_csv.py
git commit -m "$(cat <<'EOF'
feat: thêm script export_analysis_csv để đọc lướt kết quả AI

Dùng ở bước verify Giai đoạn B (15 bài thật) — export topic/sentiment/
emotion/confidence/summary/ai_model ra CSV để đọc thủ công, không cần
build tool đánh giá riêng.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7 — Regression: chạy toàn bộ test suite

- [ ] **Step 7.1: Chạy toàn bộ**

```bash
docker compose exec backend pytest backend/tests/ -v
```

Expected: tất cả PASS, không có test nào bị lỗi do đổi `analyze_article` sang async hay thêm cột `ai_model`.

- [ ] **Step 7.2: Nếu có regression** — sửa ngay, không sang Task 8 cho tới khi toàn bộ suite pass.

---

## Task 8 — Verify thật, Giai đoạn A (smoke test 5 bài)

- [ ] **Step 8.1: Restart `celery-worker`** (bài học từ Slice 2 — volume mount không tự nạp code Python mới)

```bash
docker compose restart celery-worker
```

- [ ] **Step 8.2: Set giới hạn 5 bài**

Sửa `.env`: `MAX_ARTICLES_PER_JOB=5`, giữ `AI_CONCURRENCY=1`, rồi:

```bash
docker compose restart backend celery-worker
```

- [ ] **Step 8.3: Tạo job thật** — `POST /api/reports/create` với 2-3 `source_ids` (trong 7 nguồn đã verify), khoảng ngày đủ rộng để ra 5 bài

- [ ] **Step 8.4: Poll tới `completed`, kiểm tra:**
  - `status=completed`, không có exception trong `docker compose logs celery-worker`
  - `docker compose exec postgres psql -U ngs -d ngs_monitor -c "SELECT ai_model, prompt_version FROM article_analysis WHERE job_id = '<job_id>';"` → mọi dòng `ai_model='qwen3:8b'`
  - `.docx`/`.json` sinh ra hợp lệ (không rỗng)

- [ ] **Step 8.5: Nếu lỗi** — sửa code, quay lại Step 8.1, lặp lại Giai đoạn A (không sang Task 9) cho tới khi qua.

---

## Task 9 — Verify thật, Giai đoạn B (15 bài chính thức)

- [ ] **Step 9.1: Set giới hạn 15 bài**

Sửa `.env`: `MAX_ARTICLES_PER_JOB=15`, rồi:

```bash
docker compose restart backend celery-worker
```

- [ ] **Step 9.2: Tạo job thật** — trải trên 4-5/7 nguồn đã verify, khoảng ngày đủ rộng để ra 15 bài

- [ ] **Step 9.3: Poll tới `completed`**

- [ ] **Step 9.4: Export CSV**

```bash
docker compose exec backend python -m backend.scripts.export_analysis_csv <job_id> /app/storage/slice3-verify.csv
docker compose cp $(docker compose ps -q backend):/app/storage/slice3-verify.csv ./slice3-verify.csv
```

- [ ] **Step 9.5: Đọc lướt `slice3-verify.csv`** — xác nhận không lệch hệ thống rõ ràng (VD luôn cùng 1 topic/sentiment bất kể nội dung khác nhau). Nếu có lệch → ghi lại làm task riêng viết `v2.py` (ngoài phạm vi plan này).

---

## Task 10 — Cập nhật CLAUDE.md + Commit cuối

- [ ] **Step 10.1: Tick `[x]` 2 mục Slice 3** — "batch processing + tối ưu tốc độ" và "đánh giá & tinh chỉnh prompt trên dữ liệu thật"

- [ ] **Step 10.2: Sửa dòng Verify Slice 3** — đổi "≥50 bài" thành "15 bài (giảm từ 50 — chạy AI liên tục hại phần cứng laptop CPU-only, xem quyết định)"

- [ ] **Step 10.3: Thêm dòng vào bảng "Quyết định quan trọng"**:
  - `AI_CONCURRENCY` (mặc định 1) là công tắc song song duy nhất — cùng 1 code path, không tách nhánh "local"/"server"; lý do: tránh bảo trì 2 luồng code, dễ đổi bằng cấu hình khi chuyển hạ tầng
  - Thêm cột `ai_model` — track model đã dùng, chuẩn bị đổi model khi chuyển server GPU
  - Verify giảm 50→15 bài, chia 2 giai đoạn (smoke 5 bài rồi mới 15 bài chính thức) — lý do tránh chạy AI liên tục hại phần cứng laptop

- [ ] **Step 10.4: Thêm mục "Checklist khi chuyển sang server GPU" (ghi chú, chưa làm)** — đổi `OLLAMA_MODEL`, tăng `AI_CONCURRENCY` + `OLLAMA_NUM_PARALLEL` (biến env của chính container `ollama`), benchmark lại tốc độ trước khi dùng thật, cân nhắc hạ `AI_TIMEOUT_SECONDS`

- [ ] **Step 10.5: Ghi kết quả Giai đoạn A/B (Task 8, 9) vào "Trạng thái hiện tại"** — job_id, số bài, kết luận đọc CSV

- [ ] **Step 10.6: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: cập nhật CLAUDE.md — Slice 3 hoàn thành (batch/concurrency + ai_model + verify 15 bài)

Ghi kết quả verify thật Giai đoạn A (5 bài smoke test) + Giai đoạn B
(15 bài chính thức), quyết định AI_CONCURRENCY là công tắc duy nhất
(không tách nhánh code), checklist khi chuyển sang server GPU sau này.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-review checklist

### Spec coverage
- [x] Prompt 8 nhóm giữ nguyên, không viết `v2.py` trước → không có task nào đổi `v1.py`, đúng quyết định trong spec
- [x] `AI_CONCURRENCY` mặc định 1, 1 code path duy nhất → Task 2-4
- [x] Không benchmark 2/4 trên laptop → không có task benchmark concurrency > 1 trong plan
- [x] Track `ai_model` → Task 1 (schema) + Task 2 (gắn giá trị) + Task 4 (insert)
- [x] Ghi DB tuần tự sau khi có kết quả song song, không dùng SQLAlchemy async → Task 4 (`asyncio.run(...)` rồi `for` loop `db.commit()` tuần tự bình thường)
- [x] Mỗi bài lỗi cô lập riêng → Task 3 test `isolates_single_failure`, Task 4 xử lý `isinstance(result, Exception)`
- [x] Verify 2 giai đoạn (5 bài rồi 15 bài) → Task 8, Task 9
- [x] Script export CSV, không phải endpoint API → Task 6
- [x] Cập nhật CLAUDE.md verify "15 bài" thay "≥50 bài" → Task 10

### Placeholder scan
- Không còn "TBD"/"TODO" nào trong plan — mọi step đều có code đầy đủ hoặc lệnh chạy cụ thể.

### Type consistency
- `analyze_articles_batch(articles: list[tuple[str, str]], concurrency: int, client=None) -> list[dict | Exception]` dùng nhất quán ở Task 3 (định nghĩa), Task 4 (gọi trong `report_job.py`), test ở cả 2 task.
- `result["ai_model"]` (Task 2 gắn vào dict trả về của `analyze_article`) khớp với `ai_model=result["ai_model"]` khi insert `ArticleAnalysis` (Task 4) và cột `ai_model` (Task 1).

### Rủi ro đã biết
- Nhớ `docker compose restart celery-worker` sau mỗi lần sửa code Python trong `backend/` trước khi verify thật (bài học từ Slice 2/TinGia) — đã nhắc lại ở Task 8 Step 8.1.
- `AI_CONCURRENCY > 1` chưa được benchmark trên phần cứng thật nào (kể cả CPU) trong plan này — chỉ đảm bảo code đúng ở `concurrency=1`. Việc tăng thật để dùng production trên server GPU cần benchmark riêng, ngoài phạm vi plan này.
