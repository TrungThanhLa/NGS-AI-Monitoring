# Kế hoạch triển khai Slice 5 — Lịch sử báo cáo + Playwright JS-render Fallback

> **Dành cho agent thực thi:** SUB-SKILL BẮT BUỘC: dùng superpowers:subagent-driven-development (khuyến nghị) hoặc superpowers:executing-plans để thực thi kế hoạch này theo từng task. Các bước dùng cú pháp checkbox (`- [ ]`) để theo dõi tiến độ.

**Mục tiêu:** Hoàn thành 2 hạng mục còn lại của Slice 5 — endpoint `GET /api/reports/history` (+ trang FE) và engine crawl dự phòng Playwright cho JS-render — để có thể tick xong Slice 5 trong `CLAUDE.md`.

**Kiến trúc:** 2 nhóm tính năng độc lập, không dùng chung code, có thể làm theo thứ tự bất kỳ hoặc giao cho 2 agent khác nhau chạy song song:
- **Nhóm A (Lịch sử báo cáo):** 1 endpoint read-only mới trong `backend/routers/reports.py` hiện có, join `report_history` + `jobs` + `sources`, không cần bảng/migration mới (model `ReportHistory` và bảng `report_history` đã có sẵn, đã được ghi vào ở `backend/workers/report_job.py:227`). Kèm 1 trang Next.js mới gọi endpoint này.
- **Nhóm B (Playwright):** engine crawl thứ 3 bên cạnh engine httpx hiện có (`backend/crawler/article.py`) và Crawl4AI (`backend/crawler/crawl4ai_client.py`), bật qua `parsing_rules.engine = "playwright"`. Khác với Crawl4AI (tự nhận diện nội dung), Playwright **chỉ thay bước fetch** — dùng trình duyệt headless render trang rồi đưa HTML đã render cho đúng helper trích xuất CSS selector (`_extract`) mà engine httpx đang dùng. Điểm này đã được bạn xác nhận trước đó: Playwright tái dùng selector trong `parsing_rules` thay vì tự nhận diện nội dung, khớp với cách tech-stack doc nhóm chung "httpx + BeautifulSoup + Playwright" thành 1 pipeline fetch.

**Tech Stack:** FastAPI + SQLAlchemy (Nhóm A), Next.js/React/Tailwind (FE Nhóm A), `playwright` (sync API) + BeautifulSoup (Nhóm B), pytest cho cả 2 nhóm.

## Ràng buộc chung

- Codebase hiện tại **không dùng Pydantic response model** ở bất kỳ đâu — mọi endpoint trả về dict dựng tay (`backend/routers/reports.py`). Làm theo đúng convention này, không tạo `backend/schemas/`.
- **Không có pattern phân trang** ở bất kỳ đâu trong API. `report_history` chỉ có đúng 1 dòng/job hoàn thành thành công (insert 1 lần trong `_generate_report()`, `backend/workers/report_job.py:227`), nên khác với `articles` (đã được CLAUDE.md cảnh báo phình to không giới hạn), bảng này giữ nhỏ — không cần phân trang cho MVP.
- Test backend chạy vào **DB Postgres thật** qua fixture `db_session` (`backend/tests/conftest.py:6-13`), không mock. Mọi test insert dữ liệu phải dọn dẹp trong `try/finally` (xem bất kỳ test nào trong `backend/tests/test_reports_router.py`).
- Mọi hàm engine crawl phải trả về đúng 1 shape dict: `{"url", "url_hash", "title", "content_raw", "author", "published_at", "crawl_duration_seconds"}`, hoặc `None` nếu lỗi — `backend/workers/report_job.py` phụ thuộc vào shape này bất kể engine nào tạo ra.
- Comment tiếng Việt chỉ dùng cho logic không hiển nhiên, đúng style hiện có của file (xem `backend/crawler/crawl4ai_client.py:12-14` để tham khảo giọng văn/độ dài).
- Chính sách mặc định theo rule [10 · Error Handling](.claude/rules/10-error-handling.md): crawler timeout/bị block ở 1 bài viết → retry 3 lần exponential backoff, sau đó `status="error"`. Crawl4AI là ngoại lệ duy nhất đã ghi rõ (không retry). Playwright không được ghi là ngoại lệ, nên áp dụng đúng chính sách retry 3 lần mặc định.

---

## Nhóm A — Lịch sử báo cáo

### Task A1: Endpoint `GET /api/reports/history`

**File:**
- Sửa: `backend/routers/reports.py:12` (import), thêm route mới (đề xuất đặt sau route `/create`, trước `/{job_id}/status` — chỉ để dễ đọc, thứ tự route không ảnh hưởng chức năng vì `/history` là 1 segment path duy nhất, không thể trùng với bất kỳ route `/{job_id}/...` nào)
- Test: `backend/tests/test_reports_router.py` (thêm test vào cuối file — dự án này giữ 1 file test/router)

**Interface:**
- Sinh ra: `GET /api/reports/history` → `{"history": [{"report_id": str, "job_id": str, "file_path": str, "created_at": datetime, "date_from": date, "date_to": date, "job_status": str, "source_names": list[str]}]}`, sắp xếp theo `created_at` giảm dần.

- [ ] **Bước 1: Viết test (fail trước)**

Thêm `ReportHistory` vào import hiện có ở dòng 9 của `backend/tests/test_reports_router.py`:

```python
from backend.models import Article, ArticleAnalysis, Job, ReportHistory, Source
```

Thêm các test sau vào cuối file:

```python
def test_history_returns_empty_list_when_no_reports(app_client):
    response = app_client.get("/api/reports/history")

    assert response.status_code == 200
    assert response.json() == {"history": []}


def test_history_returns_report_with_source_names_and_date_range(app_client, db_session, active_source):
    job = Job(
        source_ids=[active_source.source_id],
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        status="completed",
    )
    db_session.add(job)
    db_session.flush()

    report = ReportHistory(job_id=job.job_id, file_path="/storage/report.docx")
    db_session.add(report)
    db_session.commit()

    try:
        response = app_client.get("/api/reports/history")

        assert response.status_code == 200
        body = response.json()["history"]
        assert len(body) == 1
        entry = body[0]
        assert entry["report_id"] == str(report.report_id)
        assert entry["job_id"] == str(job.job_id)
        assert entry["file_path"] == "/storage/report.docx"
        assert entry["date_from"] == "2026-06-01"
        assert entry["date_to"] == "2026-06-30"
        assert entry["job_status"] == "completed"
        assert entry["source_names"] == [active_source.name]
    finally:
        db_session.delete(report)
        db_session.delete(job)
        db_session.commit()


def test_history_returns_empty_source_names_when_job_has_no_sources(app_client, db_session):
    job = Job(source_ids=[], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30), status="completed")
    db_session.add(job)
    db_session.flush()

    report = ReportHistory(job_id=job.job_id, file_path="/storage/report-no-source.docx")
    db_session.add(report)
    db_session.commit()

    try:
        response = app_client.get("/api/reports/history")

        body = response.json()["history"]
        entry = next(e for e in body if e["report_id"] == str(report.report_id))
        assert entry["source_names"] == []
    finally:
        db_session.delete(report)
        db_session.delete(job)
        db_session.commit()


def test_history_orders_by_created_at_desc(app_client, db_session):
    job1 = Job(source_ids=[], date_from=date(2026, 1, 1), date_to=date(2026, 1, 31), status="completed")
    job2 = Job(source_ids=[], date_from=date(2026, 2, 1), date_to=date(2026, 2, 28), status="completed")
    db_session.add_all([job1, job2])
    db_session.flush()

    report1 = ReportHistory(job_id=job1.job_id, file_path="/storage/r1.docx")
    db_session.add(report1)
    db_session.commit()
    report2 = ReportHistory(job_id=job2.job_id, file_path="/storage/r2.docx")
    db_session.add(report2)
    db_session.commit()

    try:
        response = app_client.get("/api/reports/history")

        body = response.json()["history"]
        report_ids = [entry["report_id"] for entry in body]
        assert report_ids.index(str(report2.report_id)) < report_ids.index(str(report1.report_id))
    finally:
        db_session.delete(report1)
        db_session.delete(report2)
        db_session.delete(job1)
        db_session.delete(job2)
        db_session.commit()
```

- [ ] **Bước 2: Chạy test để xác nhận fail**

Chạy: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_reports_router.py -k history -v`
Kỳ vọng: FAIL với `404 Not Found` (route chưa tồn tại) ở cả 4 test mới.

- [ ] **Bước 3: Implement endpoint**

Trong `backend/routers/reports.py`, sửa import ở dòng 12 thành:

```python
from backend.models import Article, ArticleAnalysis, Job, ReportHistory, Source
```

Thêm route sau (đặt sau `create_report`, tức sau dòng 72, trước `get_report_status`):

```python
@router.get("/history")
def get_report_history(db: Session = Depends(get_db)):
    rows = (
        db.query(ReportHistory, Job)
        .join(Job, Job.job_id == ReportHistory.job_id)
        .order_by(ReportHistory.created_at.desc())
        .all()
    )

    all_source_ids = {source_id for _, job in rows for source_id in (job.source_ids or [])}
    sources_by_id = {}
    if all_source_ids:
        sources_by_id = {
            source.source_id: source.name
            for source in db.query(Source).filter(Source.source_id.in_(all_source_ids)).all()
        }

    history = [
        {
            "report_id": str(report.report_id),
            "job_id": str(job.job_id),
            "file_path": report.file_path,
            "created_at": report.created_at,
            "date_from": job.date_from,
            "date_to": job.date_to,
            "job_status": job.status,
            "source_names": [
                sources_by_id[source_id] for source_id in (job.source_ids or []) if source_id in sources_by_id
            ],
        }
        for report, job in rows
    ]

    return {"history": history}
```

- [ ] **Bước 4: Chạy test để xác nhận pass**

Chạy: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_reports_router.py -v`
Kỳ vọng: tất cả test PASS (4 test mới + toàn bộ test cũ trong file vẫn xanh).

- [ ] **Bước 5: Commit**

```bash
git add backend/routers/reports.py backend/tests/test_reports_router.py
git commit -m "feat: add GET /api/reports/history endpoint"
```

---

### Task A2: Cập nhật docs API contract cho endpoint lịch sử

**File:**
- Sửa: `.claude/rules/05-api-contracts.md:9` và comment "chưa code" ở đó
- Sửa: `CLAUDE.md` checkbox roadmap "Trang lịch sử báo cáo"

**Interface:**
- Nhận vào: shape response được sinh ra ở Task A1.

- [ ] **Bước 1: Ghi lại response shape**

Trong `.claude/rules/05-api-contracts.md`, sửa:

```
GET  /api/reports/history            # Lịch sử báo cáo (chưa code — Slice 5)
```

thành:

```
GET  /api/reports/history            # Lịch sử báo cáo, sắp xếp mới nhất trước
```

và thêm 1 subsection mới (theo đúng style subsection `/articles` hiện có) ghi lại response shape:

```markdown
### GET /api/reports/history — Response
```json
{
  "history": [
    {
      "report_id": "uuid",
      "job_id": "uuid",
      "file_path": "/storage/....docx",
      "created_at": "2026-07-13T10:00:00Z",
      "date_from": "2026-01-01",
      "date_to": "2026-05-30",
      "job_status": "completed",
      "source_names": ["VTV News", "VOV"]
    }
  ]
}
```
- Sắp xếp theo `created_at` giảm dần (mới nhất trước)
- Không phân trang — `report_history` chỉ có 1 dòng/job hoàn thành thành công, không phình to như `articles`
- `source_names` rỗng nếu job không còn nguồn nào khớp (hiếm, `jobs.source_ids` không có FK cứng tới `sources`)
```

Đây chỉ là sửa doc markdown thuần túy — không cần test cho bước này.

- [ ] **Bước 2: Cập nhật checklist trong CLAUDE.md**

Trong `CLAUDE.md`, mục Slice 5, sửa:
```
- [ ] Trang lịch sử báo cáo (`GET /api/reports/history`)
```
thành:
```
- [x] Trang lịch sử báo cáo (`GET /api/reports/history`)
```
Chỉ tick khi Task A3 (trang FE) cũng đã xong và verify tay — xem Bước 4 của Task A3.

- [ ] **Bước 3: Commit**

```bash
git add .claude/rules/05-api-contracts.md CLAUDE.md
git commit -m "docs: document GET /api/reports/history contract"
```
(Commit chung với Task A3, hoặc gộp vào commit của task đó — việc tick checkbox CLAUDE.md phụ thuộc vào trang FE đã tồn tại.)

---

### Task A3: Trang lịch sử báo cáo ở Frontend

**File:**
- Tạo mới: `frontend/app/history/page.tsx`

**Interface:**
- Nhận vào: `GET {API_BASE}/api/reports/history` (Task A1), `GET {API_BASE}/api/reports/{job_id}/download` (đã có sẵn).

- [ ] **Bước 1: Tạo trang**

Tạo `frontend/app/history/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type HistoryEntry = {
  report_id: string;
  job_id: string;
  file_path: string;
  created_at: string;
  date_from: string;
  date_to: string;
  job_status: string;
  source_names: string[];
};

export default function HistoryPage() {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/reports/history`)
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => setHistory(data.history ?? []))
      .catch(() => setError("Không tải được lịch sử báo cáo"));
  }, []);

  return (
    <main className="p-8 max-w-4xl">
      <h1 className="text-2xl font-bold mb-4">Lịch sử báo cáo</h1>

      {error && <p className="text-red-600">{error}</p>}
      {!error && history.length === 0 && <p>Chưa có báo cáo nào.</p>}

      {history.length > 0 && (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b text-left">
              <th className="p-1">Ngày tạo</th>
              <th className="p-1">Nguồn</th>
              <th className="p-1">Khoảng thời gian</th>
              <th className="p-1">Trạng thái</th>
              <th className="p-1">Tải về</th>
            </tr>
          </thead>
          <tbody>
            {history.map((entry) => (
              <tr key={entry.report_id} className="border-b">
                <td className="p-1">{new Date(entry.created_at).toLocaleString("vi-VN")}</td>
                <td className="p-1">{entry.source_names.join(", ") || "-"}</td>
                <td className="p-1">
                  {entry.date_from} → {entry.date_to}
                </td>
                <td className="p-1">{entry.job_status}</td>
                <td className="p-1">
                  <a className="text-blue-600 underline" href={`${API_BASE}/api/reports/${entry.job_id}/download`}>
                    Tải DOCX
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
```

- [ ] **Bước 2: Chạy backend + tạo ít nhất 1 job hoàn thành thật**

Nếu DB dev chưa có job nào `completed` kèm dòng `report_history`, chạy 1 job thật end-to-end trước (theo đúng workflow của dự án — test với dữ liệu thật trước khi coi là xong):

```bash
docker compose up -d
curl -X POST http://localhost:8000/api/reports/create \
  -H "Content-Type: application/json" \
  -d '{"source_ids": ["<1 source_id active thật lấy từ GET /api/sources>"], "date_from": "2026-06-01", "date_to": "2026-06-07"}'
```
Poll `GET /api/reports/{job_id}/status` cho tới khi `"status": "completed"`.

- [ ] **Bước 3: Chạy frontend dev server và kiểm tra trên trình duyệt**

```bash
cd frontend && npm run dev
```
Mở `http://localhost:3000/history` trên trình duyệt. Xác nhận:
- Job hoàn thành ở Bước 2 hiển thị đúng tên nguồn, khoảng ngày, và link "Tải DOCX" hoạt động.
- Với DB không có job hoàn thành nào (VD DB mới), trang hiển thị "Chưa có báo cáo nào." thay vì bảng rỗng hoặc crash.

- [ ] **Bước 4: Commit**

```bash
git add frontend/app/history/page.tsx CLAUDE.md .claude/rules/05-api-contracts.md
git commit -m "feat: add report history page at /history"
```

---

## Nhóm B — Playwright JS-render Fallback

### Task B1: Thêm dependency `playwright` + bước cài trình duyệt trong Docker

**File:**
- Sửa: `backend/requirements.txt:14` (sau dòng `crawl4ai==0.9.0`)
- Sửa: `backend/Dockerfile:8` (sau dòng `pip install`)

**Interface:**
- Sinh ra: `playwright` import được qua `from playwright.sync_api import sync_playwright, Error as PlaywrightError` trong container backend và bất kỳ venv dev local nào chạy `pip install -r backend/requirements.txt`.

- [ ] **Bước 1: Resolve và pin đúng version tương thích**

Trong 1 venv Python 3.12 đã cài sẵn `backend/requirements.txt` hiện tại, chạy:

```bash
pip install playwright
pip show playwright | grep Version
```

Kỳ vọng: in ra dòng version, VD `Version: 1.47.0` (dùng đúng version thực tế resolve được — pin đúng giá trị đó, không đoán).

- [ ] **Bước 2: Pin version vào requirements.txt**

Thêm dòng sau vào `backend/requirements.txt` (sau dòng 13, `crawl4ai==0.9.0`), dùng đúng version resolve được ở Bước 1:

```
playwright==<version-đã-resolve>
```

- [ ] **Bước 3: Thêm bước cài browser binary vào Dockerfile**

Trong `backend/Dockerfile`, sau dòng 8 (`RUN pip install --no-cache-dir -r backend/requirements.txt`), thêm:

```dockerfile
RUN python -m playwright install --with-deps chromium
```

- [ ] **Bước 4: Verify image build được**

```bash
docker compose build backend celery-worker
```
Kỳ vọng: build thành công, không lỗi apt/pip, image có sẵn chromium.

- [ ] **Bước 5: Commit**

```bash
git add backend/requirements.txt backend/Dockerfile
git commit -m "chore: add playwright dependency and chromium install for JS-render fallback"
```

---

### Task B2: Engine `fetch_article_playwright()`

**File:**
- Tạo mới: `backend/crawler/playwright_client.py`
- Test: `backend/tests/test_playwright_client.py`

**Interface:**
- Nhận vào: `_extract(soup, selector)` và `compute_url_hash(url)` từ `backend/crawler/article.py` (có sẵn, không đổi — `_extract` ở `article.py:14-22`, `compute_url_hash` ở `article.py:10-11`).
- Sinh ra: `fetch_article_playwright(url: str, parsing_rules: dict, renderer=None, max_retries: int | None = None, retry_backoff_seconds: float | None = None) -> dict | None`, trả về đúng shape dict như `fetch_article()`/`fetch_article_crawl4ai()` (xem phần Ràng buộc chung), hoặc `None` nếu lỗi. `renderer` là tham số `Callable[[str], str]` có thể inject để test, theo đúng pattern tham số `runner` của `fetch_article_crawl4ai` (`crawl4ai_client.py:30-31`).

- [ ] **Bước 1: Viết test (fail trước)**

Tạo `backend/tests/test_playwright_client.py`:

```python
from backend.crawler.article import compute_url_hash
from backend.crawler.playwright_client import PlaywrightError, fetch_article_playwright

URL = "https://vtv.vn/bai-viet-test.htm"

PARSING_RULES = {"title": "h1.title", "content": "div.content", "author": "span.author", "date": "meta.published"}

HTML = """
<html><body>
<h1 class="title">Tiêu đề bài viết</h1>
<div class="content">Nội dung bài viết.</div>
<span class="author">Tác giả A</span>
<meta class="published" content="2026-06-25T16:19:00">
</body></html>
"""


def _fake_renderer(html=HTML, fail_times=0):
    calls = {"count": 0}

    def renderer(url):
        calls["count"] += 1
        if calls["count"] <= fail_times:
            raise PlaywrightError("simulated render failure")
        return html

    renderer.calls = calls
    return renderer


def test_extracts_title_content_author_date_and_url_hash():
    result = fetch_article_playwright(URL, PARSING_RULES, renderer=_fake_renderer())

    assert result["title"] == "Tiêu đề bài viết"
    assert result["content_raw"] == "Nội dung bài viết."
    assert result["author"] == "Tác giả A"
    assert result["published_at"].isoformat() == "2026-06-25T16:19:00"
    assert result["url"] == URL
    assert result["url_hash"] == compute_url_hash(URL)


def test_returns_none_when_title_selector_does_not_match():
    html = HTML.replace('class="title"', 'class="not-title"')

    result = fetch_article_playwright(URL, PARSING_RULES, renderer=_fake_renderer(html=html))

    assert result is None


def test_returns_none_when_content_selector_does_not_match():
    html = HTML.replace('class="content"', 'class="not-content"')

    result = fetch_article_playwright(URL, PARSING_RULES, renderer=_fake_renderer(html=html))

    assert result is None


def test_returns_crawl_duration_seconds():
    result = fetch_article_playwright(URL, PARSING_RULES, renderer=_fake_renderer())

    assert result["crawl_duration_seconds"] > 0


def test_retries_on_render_error_then_succeeds():
    renderer = _fake_renderer(fail_times=2)

    result = fetch_article_playwright(URL, PARSING_RULES, renderer=renderer, retry_backoff_seconds=0)

    assert result["title"] == "Tiêu đề bài viết"
    assert renderer.calls["count"] == 3


def test_returns_none_after_exhausting_retries():
    renderer = _fake_renderer(fail_times=5)

    result = fetch_article_playwright(
        URL, PARSING_RULES, renderer=renderer, max_retries=3, retry_backoff_seconds=0
    )

    assert result is None
    assert renderer.calls["count"] == 3
```

- [ ] **Bước 2: Chạy test để xác nhận fail**

Chạy: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_playwright_client.py -v`
Kỳ vọng: FAIL với `ModuleNotFoundError: No module named 'backend.crawler.playwright_client'`.

- [ ] **Bước 3: Implement engine**

Tạo `backend/crawler/playwright_client.py`:

```python
import os
import time
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from backend.crawler.article import _extract, compute_url_hash


def _render_html(url: str) -> str:
    timeout_ms = int(os.environ.get("CRAWLER_TIMEOUT_SECONDS", "30")) * 1000
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(url, timeout=timeout_ms)
            return page.content()
        finally:
            browser.close()


def fetch_article_playwright(
    url: str,
    parsing_rules: dict,
    renderer=None,
    max_retries: int | None = None,
    retry_backoff_seconds: float | None = None,
) -> dict | None:
    renderer = renderer or _render_html
    if max_retries is None:
        max_retries = int(os.environ.get("CRAWLER_MAX_RETRIES", "3"))

    start = time.perf_counter()
    html = None
    for attempt in range(max_retries):
        try:
            html = renderer(url)
            break
        except PlaywrightError:
            if attempt < max_retries - 1:
                backoff = retry_backoff_seconds if retry_backoff_seconds is not None else 2**attempt
                time.sleep(backoff)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
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
```

Lưu ý: đoạn này cố tình import helper `_extract` "private" từ `article.py` thay vì viết lại logic trích xuất CSS selector — `fetch_article()` (httpx) và `fetch_article_playwright()` phải hiểu `parsing_rules` giống hệt nhau vì cả 2 đều là engine dựa trên selector, chỉ khác bước fetch.

- [ ] **Bước 4: Chạy test để xác nhận pass**

Chạy: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_playwright_client.py -v`
Kỳ vọng: cả 6 test PASS.

- [ ] **Bước 5: Commit**

```bash
git add backend/crawler/playwright_client.py backend/tests/test_playwright_client.py
git commit -m "feat: add fetch_article_playwright JS-render engine"
```

---

### Task B3: Nối engine `"playwright"` vào dispatch

**File:**
- Sửa: `backend/crawler/crawl4ai_client.py:61-64` (`fetch_article_dispatch`)
- Test: `backend/tests/test_crawl4ai_client.py` (thêm test dispatch)

**Interface:**
- Nhận vào: `fetch_article_playwright(url, parsing_rules)` từ Task B2.
- Sinh ra: `fetch_article_dispatch(url, parsing_rules)` nay route thêm `parsing_rules.get("engine") == "playwright"` sang engine mới. Không đổi nhánh `"crawl4ai"` hay nhánh mặc định httpx hiện có, và không đổi call site ở `backend/workers/report_job.py:120` (nó gọi `fetch_article_dispatch` vô điều kiện — việc chọn engine nằm hoàn toàn trong hàm này).

- [ ] **Bước 1: Viết test (fail trước)**

Thêm vào cuối `backend/tests/test_crawl4ai_client.py`:

```python
def test_dispatch_calls_playwright_when_engine_configured(monkeypatch):
    captured = {}

    def fake_fetch_playwright(url, parsing_rules):
        captured["called_with"] = (url, parsing_rules)
        return {"title": "fake-playwright"}

    monkeypatch.setattr("backend.crawler.crawl4ai_client.fetch_article_playwright", fake_fetch_playwright)

    parsing_rules = {"engine": "playwright", "title": "h1"}
    result = fetch_article_dispatch(URL, parsing_rules)

    assert captured["called_with"] == (URL, parsing_rules)
    assert result == {"title": "fake-playwright"}
```

- [ ] **Bước 2: Chạy test để xác nhận fail**

Chạy: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_crawl4ai_client.py -k playwright -v`
Kỳ vọng: FAIL — `AttributeError` (module chưa có attribute `fetch_article_playwright`) hoặc dispatch rơi xuống nhánh httpx (`fake_fetch_playwright` không được gọi).

- [ ] **Bước 3: Nối nhánh dispatch**

Trong `backend/crawler/crawl4ai_client.py`, thêm import (sau dòng 10):

```python
from backend.crawler.playwright_client import fetch_article_playwright
```

Thay hàm `fetch_article_dispatch` (dòng 61-64) thành:

```python
def fetch_article_dispatch(url: str, parsing_rules: dict) -> dict | None:
    engine = parsing_rules.get("engine")
    if engine == "crawl4ai":
        return fetch_article_crawl4ai(url)
    if engine == "playwright":
        return fetch_article_playwright(url, parsing_rules)
    return fetch_article(url, parsing_rules)
```

- [ ] **Bước 4: Chạy test để xác nhận pass**

Chạy: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_crawl4ai_client.py backend/tests/test_playwright_client.py -v`
Kỳ vọng: tất cả test PASS, kể cả toàn bộ test cũ trong `test_crawl4ai_client.py`.

- [ ] **Bước 5: Commit**

```bash
git add backend/crawler/crawl4ai_client.py backend/tests/test_crawl4ai_client.py
git commit -m "feat: wire playwright engine into fetch_article_dispatch"
```

---

### Task B4: Verify bằng 1 nguồn JS thật, sau đó cập nhật docs

Workflow của dự án yêu cầu test với ít nhất 1 nguồn thật trước khi coi công việc crawler là xong — xem [13 · Workflow](.claude/rules/13-workflow.md). Vì hiện chưa có nguồn nào cấu hình `engine="playwright"` (theo [11 · Core Principles](.claude/rules/11-core-principles.md), chỉ Admin mới cấu hình `sources` — kế hoạch này không tự thêm nguồn mới), việc verify ở đây nghĩa là chứng minh engine hoạt động độc lập với 1 trang JS-render thật, không phải gắn vào 1 nguồn production.

**File:**
- Sửa: `.claude/rules/06-crawler-strategy.md` (phần docs engine)
- Sửa: `.claude/rules/10-error-handling.md:16` (dòng JS-render)
- Sửa: `CLAUDE.md` (checkbox Slice 5 + dòng log "Đã hoàn thành")

- [ ] **Bước 1: Verify tay với 1 trang JS-render thật**

Chạy script ad-hoc sau (không commit — chỉ để verify, dùng xong bỏ) nhắm vào 1 trang thật cần JS render, hoặc bất kỳ URL bài viết thật nào, để xác nhận engine hoạt động ngoài phạm vi mock:

```bash
cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -c "
from backend.crawler.playwright_client import fetch_article_playwright
result = fetch_article_playwright(
    'https://vtv.vn/bai-viet-test.htm',  # thay bằng URL bài viết thật
    {'title': 'h1.title', 'content': 'div.article-content'},  # thay bằng CSS selector thật đã verify tay
)
print(result)
"
```
Kỳ vọng: trả về dict có `title`/`content_raw` không rỗng, không phải `None`. Chỉnh URL và selector theo 1 nguồn thật bạn có quyền truy cập, verify selector bằng tay (devtools trình duyệt) trước — đúng mức độ cẩn trọng đã áp dụng cho mọi nguồn khác trong dự án (xem các ghi chú verify từng nguồn trong CLAUDE.md).

- [ ] **Bước 2: Cập nhật docs crawler strategy**

Trong `.claude/rules/06-crawler-strategy.md`, ở phần "Fetch article content — 2 engine", đổi heading và thêm bullet thứ 3 mô tả engine mới, theo đúng style bullet của `"engine": "crawl4ai"` hiện có:

```markdown
## Fetch article content — 3 engine (httpx mặc định / Crawl4AI / Playwright tùy chọn)
```

Thêm sau bullet Crawl4AI:

```markdown
- **`"engine": "playwright"`** — `fetch_article_playwright()` (`crawler/playwright_client.py`), dùng Playwright (headless Chromium) để render trang có JavaScript rồi lấy HTML đã render, sau đó parse bằng **đúng CSS selector khai trong `parsing_rules`** (`title`/`content`/`author`/`date`) — khác với Crawl4AI (tự nhận diện nội dung), Playwright chỉ thay bước fetch, không thay bước parse. Admin phải khai CSS selector khi cấu hình nguồn dùng engine này, giống engine mặc định httpx. Có retry 3 lần exponential backoff giống httpx (không phải ngoại lệ như Crawl4AI).
```

Cập nhật đoạn code mẫu `fetch_article_dispatch` trong file đó cho khớp phiên bản 3 nhánh ở Task B3.

- [ ] **Bước 3: Cập nhật docs error-handling**

Trong `.claude/rules/10-error-handling.md`, sửa dòng:
```
| Website dùng JavaScript render | Playwright thay thế httpx cho nguồn đó (chưa code — Slice 5) |
```
thành:
```
| Website dùng JavaScript render | Playwright thay thế httpx cho nguồn đó qua `parsing_rules.engine="playwright"` — retry 3 lần exponential backoff như httpx (không phải ngoại lệ như Crawl4AI) |
```

- [ ] **Bước 4: Cập nhật CLAUDE.md**

Tick checkbox Slice 5:
```
- [x] Error handling đầy đủ theo [10 · Error Handling](.claude/rules/10-error-handling.md) (retry, timeout, JS-render fallback Playwright) — hoàn thành
```
Và thêm 1 dòng dưới "Đã hoàn thành" tóm tắt việc này (1 dòng, đúng style ngắn gọn của các mục hiện có), VD:
```
- **Playwright JS-render fallback (2026-07-13):** `fetch_article_playwright()` — thay bước fetch bằng headless Chromium, tái dùng CSS selector `parsing_rules` giống engine httpx (không tự nhận diện nội dung như Crawl4AI); bật qua `parsing_rules.engine="playwright"`
```

- [ ] **Bước 5: Commit**

```bash
git add .claude/rules/06-crawler-strategy.md .claude/rules/10-error-handling.md CLAUDE.md
git commit -m "docs: document playwright JS-render fallback engine"
```

---

## Ghi chú tự rà soát (Self-Review)

- **Độ phủ spec:** Cả 2 hạng mục còn lại của Slice 5 đều được cover — `GET /api/reports/history` (Nhóm A, Task A1-A3) và "JS-render fallback Playwright" (Nhóm B, Task B1-B4). Bullet Slice 5 còn lại ("Job status polling... progress UI") đã `[x]` sẵn trong CLAUDE.md, ngoài phạm vi kế hoạch này.
- **Không có placeholder:** mọi bước đều có code/lệnh chạy được thật, không để sót "TBD"/"thêm error handling" chưa cụ thể.
- **Đã kiểm tra tính nhất quán type/tên:** chữ ký hàm `fetch_article_playwright(url, parsing_rules, renderer=None, max_retries=None, retry_backoff_seconds=None)` giống hệt nhau giữa Task B2 (định nghĩa) và Task B3 (nơi gọi trong dispatch, chỉ truyền `url, parsing_rules` — khớp với cách gọi 2 tham số vị trí đã dùng cho `fetch_article` trong dispatch hiện có). Import `ReportHistory` được thêm nhất quán ở cả `reports.py` và `test_reports_router.py`.
- **Phụ thuộc thứ tự:** Task B3 phụ thuộc B2 (import `fetch_article_playwright`); B1 phải xong trước khi B2/B3 chạy được thật trong môi trường thật (import sẽ lỗi nếu chưa cài dependency), dù test của B2 dùng dependency injection (`renderer=`) nên về mặt kỹ thuật có thể viết/review trước khi B1 xong — chỉ là chưa chạy thật được. Các task Nhóm A hoàn toàn độc lập với Nhóm B.
