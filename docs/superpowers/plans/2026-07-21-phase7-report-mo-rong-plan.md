# Phase 7 — Report mở rộng — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xóa hẳn mô hình `jobs` on-demand, thay bằng `campaigns` (`mode=ONE_SHOT`/`CONTINUOUS`) cho toàn bộ luồng report; thêm 3 định dạng xuất mới (PDF/Excel/CSV) bên cạnh DOCX/JSON hiện có.

**Architecture:** Tách "chọn bài nào" (Job filter theo `job_id`, Campaign filter theo `campaign_articles` + khoảng ngày `published_at`) khỏi lõi tổng hợp (`aggregate_basic` nhận sẵn `article_ids`) và lõi sinh file (mỗi generator nhận `date_from/date_to/aggregates/output_path`, không phụ thuộc Job hay Campaign). ONE_SHOT dùng Celery `chord` để crawl ngay lập tức mọi Source rồi tự chuyển `COMPLETED`; sinh báo cáo (gồm cả bước AI phân tích các bài còn tồn đọng) luôn là hành động thủ công qua `POST /api/campaigns/{id}/reports`, dùng chung cho `ONE_SHOT` và `CONTINUOUS`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Celery 5.4 (`chord`/`group`), python-docx (có sẵn), WeasyPrint (PDF mới), openpyxl (Excel mới), `csv` chuẩn, React + AntD (frontend).

## Global Constraints

- Comment giải thích logic quan trọng bằng tiếng Việt (rule 13-workflow.md).
- TDD bắt buộc — viết test fail trước, code sau (rule 13-workflow.md).
- Không phá vỡ test đang pass ở bất kỳ task nào — mọi thay đổi signature phải cập nhật TẤT CẢ call site trong cùng task.
- `db_session` fixture (`backend/tests/conftest.py`) tự rollback sau mỗi test — dùng `db_session.flush()`/`db_session.commit()` như code thật, không cần dọn tay.
- Permission check qua `require_permission(resource, action)` — tái dùng permission `campaign.*`/`report.*` đã seed sẵn, không tạo permission mới trong plan này.
- Mọi Celery task mới đăng ký qua import trong `backend/workers/celery_app.py` (theo đúng pattern `report_job`/`continuous_crawl`/`scheduler` hiện có).
- Frontend: chỉ dùng `fetch` thuần qua `authFetch` (`frontend/src/lib/api.ts`) — không thêm `react-query`/`zustand`.

---

### Task 1: `aggregate_basic` — tách khỏi `Job`, nhận `article_ids` thay vì `job_id`

**Files:**
- Modify: `backend/report/aggregator.py`
- Modify: `backend/workers/report_job.py:254-267` (`_generate_report`)
- Modify: `backend/tests/test_aggregator.py`
- Test: `backend/tests/test_aggregator.py`

**Interfaces:**
- Produces: `aggregate_basic(db: Session, article_ids: list[uuid.UUID]) -> dict` (thay `aggregate_basic(db, job_id)`) — trả về đúng shape dict như cũ (`articles`, `sentiment_counts`, `emotion_counts`, `source_counts`, `topic_counts`, `keyword_counts`, `monthly_counts`, `summary_stats`).

- [ ] **Step 1: Sửa test hiện có để gọi theo signature mới**

Trong `backend/tests/test_aggregator.py`, đổi mọi lời gọi `aggregate_basic(db_session, job.job_id)` thành `aggregate_basic(db_session, [article1.article_id, article2.article_id])` (liệt kê đúng article_id đã tạo trong từng test — đọc toàn bộ file, có nhiều test case tương tự, sửa hết).

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_aggregator.py -v`
Expected: FAIL — `TypeError: aggregate_basic() takes 2 positional arguments but 3 were given` (hoặc lỗi tương tự vì hàm chưa đổi).

- [ ] **Step 3: Sửa `aggregate_basic`**

```python
# backend/report/aggregator.py
from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Article, ArticleAnalysis, Source

TOP_KEYWORDS_LIMIT = 20
UNKNOWN_EMOTION_LABEL = "Không xác định"


def aggregate_basic(db: Session, article_ids: list[UUID]) -> dict:
    # Tách rời "chọn bài nào" (do caller quyết định — Job lọc theo job_id, Campaign lọc
    # qua campaign_articles + khoảng ngày) khỏi lõi tổng hợp này — chỉ nhận sẵn danh sách
    # article_id, không tự query theo job_id/campaign_id nữa (Phase 7).
    if not article_ids:
        rows = []
    else:
        rows = db.execute(
            select(Article, ArticleAnalysis, Source)
            .join(ArticleAnalysis, ArticleAnalysis.article_id == Article.article_id)
            .join(Source, Source.source_id == Article.source_id)
            .where(Article.article_id.in_(article_ids))
        ).all()

    articles = []
    sentiment_counts: Counter = Counter()
    emotion_counts: Counter = Counter()
    source_counts: Counter = Counter()
    topic_counts: Counter = Counter()
    keyword_counts: Counter = Counter()
    monthly_counts: Counter = Counter()
    needs_review_count = 0

    for article, analysis, source in rows:
        sentiment_counts[analysis.sentiment] += 1
        emotion_counts[analysis.emotion or UNKNOWN_EMOTION_LABEL] += 1
        source_counts[source.group_name] += 1
        for topic in analysis.topics:
            topic_counts[topic] += 1
        for keyword in analysis.keywords:
            keyword_counts[keyword] += 1
        if article.published_at is not None:
            monthly_counts[article.published_at.strftime("%Y-%m")] += 1
        if analysis.needs_review:
            needs_review_count += 1

        articles.append(
            {
                "title": article.title,
                "url": article.url,
                "source": source.name,
                "published_at": article.published_at,
                "sentiment": analysis.sentiment,
                "emotion": analysis.emotion,
                "topics": analysis.topics,
                "confidence": analysis.confidence,
                "needs_review": analysis.needs_review,
                "summary": analysis.summary,
            }
        )

    sorted_keywords = sorted(keyword_counts.items(), key=lambda kv: kv[1], reverse=True)[:TOP_KEYWORDS_LIMIT]

    return {
        "articles": articles,
        "sentiment_counts": dict(sentiment_counts),
        "emotion_counts": dict(emotion_counts),
        "source_counts": dict(sorted(source_counts.items(), key=lambda kv: kv[1], reverse=True)),
        "topic_counts": dict(sorted(topic_counts.items(), key=lambda kv: kv[1], reverse=True)),
        "keyword_counts": dict(sorted_keywords),
        "monthly_counts": dict(sorted(monthly_counts.items())),
        "summary_stats": {
            "Tổng số bài": len(rows),
            "Tổng số cơ quan": len(source_counts),
            "Số bài cần review (needs_review)": needs_review_count,
        },
    }
```

- [ ] **Step 4: Sửa call site trong `report_job.py` để không phá vỡ luồng Job hiện có (sẽ xóa hẳn ở Task 13)**

```python
# backend/workers/report_job.py — trong _generate_report(db, job), thay dòng
#   aggregates = aggregate_basic(db, job.job_id)
# bằng:
def _generate_report(db, job: Job) -> None:
    article_ids = [row[0] for row in db.query(Article.article_id).filter_by(job_id=job.job_id).all()]
    aggregates = aggregate_basic(db, article_ids)
    storage_path = os.environ.get("STORAGE_PATH", "./storage")
    os.makedirs(storage_path, exist_ok=True)
    output_docx = os.path.join(storage_path, f"{job.job_id}.docx")
    output_json = os.path.join(storage_path, f"{job.job_id}.json")

    generate_docx(job, aggregates, output_docx)
    export_json(job, aggregates, output_json)

    job.output_docx = output_docx
    job.output_json = output_json
    db.add(ReportHistory(job_id=job.job_id, file_path=output_docx))
    db.commit()
```

(Giữ nguyên `generate_docx(job, ...)`/`export_json(job, ...)` ở bước này — sửa 2 hàm đó ở Task 2.)

- [ ] **Step 5: Chạy lại test aggregator + test_report_job.py**

Run: `docker compose exec backend pytest backend/tests/test_aggregator.py backend/tests/test_report_job.py -v`
Expected: PASS toàn bộ.

- [ ] **Step 6: Commit**

```bash
git add backend/report/aggregator.py backend/workers/report_job.py backend/tests/test_aggregator.py
git commit -m "refactor: aggregate_basic nhận article_ids thay vì job_id, tách khỏi Job (Phase 7)"
```

---

### Task 2: `docx_generator` — tách khỏi `Job`, nhận `date_from`/`date_to` thay vì object `job`

**Files:**
- Modify: `backend/report/docx_generator.py`
- Modify: `backend/workers/report_job.py:254-267` (`_generate_report`)
- Modify: `backend/tests/test_docx_generator.py`
- Test: `backend/tests/test_docx_generator.py`

**Interfaces:**
- Consumes: `aggregate_basic()` output shape từ Task 1.
- Produces: `generate_docx(date_from, date_to, aggregates: dict, output_path: str) -> None`, `export_json(report_id: str, date_from, date_to, aggregates: dict, output_path: str) -> None`.

- [ ] **Step 1: Sửa test hiện có để gọi theo signature mới**

Đọc `backend/tests/test_docx_generator.py`, đổi mọi lời gọi `generate_docx(job, aggregates, path)` → `generate_docx(job.date_from, job.date_to, aggregates, path)` (hoặc dùng object giả `date_from`/`date_to` trực tiếp nếu test không tạo `Job` thật), và `export_json(job, aggregates, path)` → `export_json(str(job.job_id), job.date_from, job.date_to, aggregates, path)`.

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_docx_generator.py -v`
Expected: FAIL — signature mismatch.

- [ ] **Step 3: Sửa `docx_generator.py`**

```python
# backend/report/docx_generator.py
import json

from docx import Document


def generate_docx(date_from, date_to, aggregates: dict, output_path: str) -> None:
    doc = Document()
    doc.add_heading("Báo cáo NGS Monitor", level=1)
    doc.add_paragraph(f"Khoảng thời gian: {date_from} – {date_to}")

    doc.add_heading("Bảng 3.1. Số lượng nội dung theo cơ quan", level=2)
    _add_count_table(doc, "Cơ quan", aggregates["source_counts"])

    doc.add_heading("Bảng 3.2 / 3.7. Số lượng nội dung theo chủ đề", level=2)
    _add_count_table(doc, "Chủ đề", aggregates["topic_counts"])

    doc.add_heading("Bảng 3.8. Top từ khóa", level=2)
    _add_count_table(doc, "Từ khóa", aggregates["keyword_counts"])

    doc.add_heading("Thống kê số lượng nội dung theo tháng (tương ứng Hình 3.2 gốc, dạng bảng)", level=2)
    _add_count_table(doc, "Tháng", aggregates["monthly_counts"])

    doc.add_heading("Bảng 3.13. Kết quả phân tích sắc thái cảm xúc (Sentiment Analysis)", level=2)
    _add_count_table(doc, "Sentiment", aggregates["sentiment_counts"])

    doc.add_heading("Bảng 3.15. Kết quả phân tích cảm xúc (Emotion Analysis)", level=2)
    _add_count_table(doc, "Emotion", aggregates["emotion_counts"])

    doc.add_heading("Bảng 3.17. Thống kê tổng hợp", level=2)
    _add_count_table(doc, "Chỉ số", aggregates["summary_stats"])

    doc.add_heading("Danh sách bài viết", level=2)
    table = doc.add_table(rows=1, cols=6)
    header = table.rows[0].cells
    for i, name in enumerate(["Tiêu đề", "URL", "Sentiment", "Emotion", "Confidence", "Needs review"]):
        header[i].text = name
    for article in aggregates["articles"]:
        cells = table.add_row().cells
        cells[0].text = article["title"] or ""
        cells[1].text = article["url"] or ""
        cells[2].text = article["sentiment"] or ""
        cells[3].text = article["emotion"] or ""
        cells[4].text = str(article["confidence"])
        cells[5].text = str(article["needs_review"])

    doc.save(output_path)


def _add_count_table(doc: Document, label_column: str, counts: dict) -> None:
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = label_column
    table.rows[0].cells[1].text = "Số lượng"
    for key, count in counts.items():
        cells = table.add_row().cells
        cells[0].text = str(key)
        cells[1].text = str(count)


def export_json(report_id: str, date_from, date_to, aggregates: dict, output_path: str) -> None:
    data = {
        "report_id": report_id,
        "date_from": str(date_from),
        "date_to": str(date_to),
        **aggregates,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
```

- [ ] **Step 4: Sửa call site trong `report_job.py`**

```python
# backend/workers/report_job.py — trong _generate_report, thay 2 dòng gọi generate_docx/export_json:
    generate_docx(job.date_from, job.date_to, aggregates, output_docx)
    export_json(str(job.job_id), job.date_from, job.date_to, aggregates, output_json)
```

- [ ] **Step 5: Chạy lại toàn bộ test liên quan**

Run: `docker compose exec backend pytest backend/tests/test_docx_generator.py backend/tests/test_report_job.py backend/tests/test_aggregator.py -v`
Expected: PASS toàn bộ.

- [ ] **Step 6: Commit**

```bash
git add backend/report/docx_generator.py backend/workers/report_job.py backend/tests/test_docx_generator.py
git commit -m "refactor: generate_docx/export_json nhận date_from/date_to thay vì object Job (Phase 7)"
```

---

### Task 3: `pdf_generator.py` mới (WeasyPrint)

**Files:**
- Create: `backend/report/pdf_generator.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/Dockerfile`
- Test: `backend/tests/test_pdf_generator.py`

**Interfaces:**
- Consumes: `aggregate_basic()` output shape (Task 1).
- Produces: `generate_pdf(date_from, date_to, aggregates: dict, output_path: str) -> None`.

- [ ] **Step 1: Thêm dependency**

Trong `backend/requirements.txt`, thêm dòng:
```
weasyprint==62.3
```

- [ ] **Step 2: Thêm system lib cần cho WeasyPrint vào Dockerfile**

Sửa `backend/Dockerfile` dòng 3 (WeasyPrint cần Pango/Cairo/GDK-Pixbuf ở tầng OS, không cài được qua pip riêng):

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    libffi-dev shared-mime-info \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 3: Viết test fail trước**

```python
# backend/tests/test_pdf_generator.py
import os
import uuid

from backend.report.pdf_generator import generate_pdf


def test_generate_pdf_creates_valid_pdf_file(tmp_path):
    aggregates = {
        "articles": [{"title": "Bài 1", "url": "https://vtv.vn/a1", "sentiment": "negative",
                      "emotion": "Fear", "confidence": 0.9, "needs_review": False}],
        "sentiment_counts": {"negative": 1},
        "emotion_counts": {"Fear": 1},
        "source_counts": {"VTV": 1},
        "topic_counts": {"A": 1},
        "keyword_counts": {"kw1": 1},
        "monthly_counts": {"2026-06": 1},
        "summary_stats": {"Tổng số bài": 1},
    }
    output_path = str(tmp_path / f"{uuid.uuid4()}.pdf")

    generate_pdf("2026-06-01", "2026-06-30", aggregates, output_path)

    assert os.path.exists(output_path)
    with open(output_path, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-"
```

- [ ] **Step 4: Chạy test để xác nhận FAIL**

Run: `docker compose exec backend pip install weasyprint==62.3 && pytest backend/tests/test_pdf_generator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.report.pdf_generator'`.

- [ ] **Step 5: Viết `pdf_generator.py`**

```python
# backend/report/pdf_generator.py
from weasyprint import HTML


def _render_count_table(label_column: str, counts: dict) -> str:
    rows = "".join(f"<tr><td>{key}</td><td>{count}</td></tr>" for key, count in counts.items())
    return f"<table border='1' cellspacing='0' cellpadding='4'><tr><th>{label_column}</th><th>Số lượng</th></tr>{rows}</table>"


def generate_pdf(date_from, date_to, aggregates: dict, output_path: str) -> None:
    # Dùng WeasyPrint render PDF từ HTML thuần (không cần template file riêng) — tái dùng
    # đúng cấu trúc bảng như docx_generator.py, giữ số liệu nhất quán giữa các định dạng.
    articles_rows = "".join(
        f"<tr><td>{a['title'] or ''}</td><td>{a['url'] or ''}</td><td>{a['sentiment'] or ''}</td>"
        f"<td>{a['emotion'] or ''}</td><td>{a['confidence']}</td><td>{a['needs_review']}</td></tr>"
        for a in aggregates["articles"]
    )
    html = f"""
    <html><head><meta charset="utf-8"><style>
      body {{ font-family: sans-serif; font-size: 12px; }}
      table {{ border-collapse: collapse; margin-bottom: 16px; width: 100%; }}
      td, th {{ border: 1px solid #ccc; padding: 4px; }}
      h1 {{ font-size: 18px; }} h2 {{ font-size: 14px; }}
    </style></head><body>
      <h1>Báo cáo NGS Monitor</h1>
      <p>Khoảng thời gian: {date_from} – {date_to}</p>
      <h2>Số lượng nội dung theo cơ quan</h2>{_render_count_table("Cơ quan", aggregates["source_counts"])}
      <h2>Số lượng nội dung theo chủ đề</h2>{_render_count_table("Chủ đề", aggregates["topic_counts"])}
      <h2>Top từ khóa</h2>{_render_count_table("Từ khóa", aggregates["keyword_counts"])}
      <h2>Thống kê theo tháng</h2>{_render_count_table("Tháng", aggregates["monthly_counts"])}
      <h2>Sentiment Analysis</h2>{_render_count_table("Sentiment", aggregates["sentiment_counts"])}
      <h2>Emotion Analysis</h2>{_render_count_table("Emotion", aggregates["emotion_counts"])}
      <h2>Thống kê tổng hợp</h2>{_render_count_table("Chỉ số", aggregates["summary_stats"])}
      <h2>Danh sách bài viết</h2>
      <table><tr><th>Tiêu đề</th><th>URL</th><th>Sentiment</th><th>Emotion</th><th>Confidence</th><th>Needs review</th></tr>
        {articles_rows}</table>
    </body></html>
    """
    HTML(string=html).write_pdf(output_path)
```

- [ ] **Step 6: Chạy lại test để xác nhận PASS**

Run: `docker compose exec backend pytest backend/tests/test_pdf_generator.py -v`
Expected: PASS.

- [ ] **Step 7: Rebuild image backend (đã đổi Dockerfile + requirements) rồi chạy lại toàn bộ test suite**

Run: `docker compose build backend && docker compose exec backend pytest backend/tests/ -v`
Expected: PASS toàn bộ (không có test nào khác bị ảnh hưởng).

- [ ] **Step 8: Commit**

```bash
git add backend/report/pdf_generator.py backend/requirements.txt backend/Dockerfile backend/tests/test_pdf_generator.py
git commit -m "feat: thêm generate_pdf (WeasyPrint) cho báo cáo (Phase 7)"
```

---

### Task 4: `excel_generator.py` mới (openpyxl)

**Files:**
- Create: `backend/report/excel_generator.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_excel_generator.py`

**Interfaces:**
- Consumes: `aggregate_basic()` output shape (Task 1).
- Produces: `generate_excel(date_from, date_to, aggregates: dict, output_path: str) -> None`.

- [ ] **Step 1: Thêm dependency**

Trong `backend/requirements.txt`, thêm dòng:
```
openpyxl==3.1.5
```

- [ ] **Step 2: Viết test fail trước**

```python
# backend/tests/test_excel_generator.py
import os
import uuid

import openpyxl

from backend.report.excel_generator import generate_excel


def test_generate_excel_creates_readable_workbook_with_expected_sheets(tmp_path):
    aggregates = {
        "articles": [{"title": "Bài 1", "url": "https://vtv.vn/a1", "sentiment": "negative",
                      "emotion": "Fear", "confidence": 0.9, "needs_review": False}],
        "sentiment_counts": {"negative": 1},
        "emotion_counts": {"Fear": 1},
        "source_counts": {"VTV": 1},
        "topic_counts": {"A": 1},
        "keyword_counts": {"kw1": 1},
        "monthly_counts": {"2026-06": 1},
        "summary_stats": {"Tổng số bài": 1},
    }
    output_path = str(tmp_path / f"{uuid.uuid4()}.xlsx")

    generate_excel("2026-06-01", "2026-06-30", aggregates, output_path)

    assert os.path.exists(output_path)
    wb = openpyxl.load_workbook(output_path)
    assert "Bài viết" in wb.sheetnames
    assert "Tổng hợp" in wb.sheetnames
    articles_sheet = wb["Bài viết"]
    assert articles_sheet.cell(row=1, column=1).value == "Tiêu đề"
    assert articles_sheet.cell(row=2, column=1).value == "Bài 1"
```

- [ ] **Step 3: Chạy test để xác nhận FAIL**

Run: `docker compose exec backend pip install openpyxl==3.1.5 && pytest backend/tests/test_excel_generator.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Viết `excel_generator.py`**

```python
# backend/report/excel_generator.py
import openpyxl


def _write_count_sheet(wb, title: str, label_column: str, counts: dict) -> None:
    sheet = wb.create_sheet(title)
    sheet.append([label_column, "Số lượng"])
    for key, count in counts.items():
        sheet.append([str(key), count])


def generate_excel(date_from, date_to, aggregates: dict, output_path: str) -> None:
    # 1 sheet riêng cho từng bảng thống kê (giữ đúng cấu trúc như docx_generator.py) +
    # 1 sheet "Bài viết" liệt kê chi tiết — dùng openpyxl thuần, không cần template file.
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # bỏ sheet mặc định trống

    info_sheet = wb.create_sheet("Tổng quan")
    info_sheet.append(["Báo cáo NGS Monitor"])
    info_sheet.append(["Khoảng thời gian", f"{date_from} – {date_to}"])

    _write_count_sheet(wb, "Theo cơ quan", "Cơ quan", aggregates["source_counts"])
    _write_count_sheet(wb, "Theo chủ đề", "Chủ đề", aggregates["topic_counts"])
    _write_count_sheet(wb, "Top từ khóa", "Từ khóa", aggregates["keyword_counts"])
    _write_count_sheet(wb, "Theo tháng", "Tháng", aggregates["monthly_counts"])
    _write_count_sheet(wb, "Sentiment", "Sentiment", aggregates["sentiment_counts"])
    _write_count_sheet(wb, "Emotion", "Emotion", aggregates["emotion_counts"])
    _write_count_sheet(wb, "Tổng hợp", "Chỉ số", aggregates["summary_stats"])

    articles_sheet = wb.create_sheet("Bài viết")
    articles_sheet.append(["Tiêu đề", "URL", "Sentiment", "Emotion", "Confidence", "Needs review"])
    for article in aggregates["articles"]:
        articles_sheet.append(
            [
                article["title"] or "",
                article["url"] or "",
                article["sentiment"] or "",
                article["emotion"] or "",
                article["confidence"],
                article["needs_review"],
            ]
        )

    wb.save(output_path)
```

- [ ] **Step 5: Chạy lại test để xác nhận PASS**

Run: `docker compose exec backend pytest backend/tests/test_excel_generator.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/report/excel_generator.py backend/requirements.txt backend/tests/test_excel_generator.py
git commit -m "feat: thêm generate_excel (openpyxl) cho báo cáo (Phase 7)"
```

---

### Task 5: `csv_generator.py` mới (csv chuẩn)

**Files:**
- Create: `backend/report/csv_generator.py`
- Test: `backend/tests/test_csv_generator.py`

**Interfaces:**
- Consumes: `aggregate_basic()` output shape (Task 1).
- Produces: `generate_csv(date_from, date_to, aggregates: dict, output_path: str) -> None`.

- [ ] **Step 1: Viết test fail trước**

```python
# backend/tests/test_csv_generator.py
import csv
import os
import uuid

from backend.report.csv_generator import generate_csv


def test_generate_csv_writes_article_rows_with_header(tmp_path):
    aggregates = {
        "articles": [
            {"title": "Bài 1", "url": "https://vtv.vn/a1", "sentiment": "negative",
             "emotion": "Fear", "confidence": 0.9, "needs_review": False},
            {"title": "Bài 2", "url": "https://vtv.vn/a2", "sentiment": "positive",
             "emotion": "Trust", "confidence": 0.8, "needs_review": True},
        ],
        "sentiment_counts": {}, "emotion_counts": {}, "source_counts": {},
        "topic_counts": {}, "keyword_counts": {}, "monthly_counts": {}, "summary_stats": {},
    }
    output_path = str(tmp_path / f"{uuid.uuid4()}.csv")

    generate_csv("2026-06-01", "2026-06-30", aggregates, output_path)

    assert os.path.exists(output_path)
    with open(output_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["Tiêu đề", "URL", "Sentiment", "Emotion", "Confidence", "Needs review"]
    assert rows[1] == ["Bài 1", "https://vtv.vn/a1", "negative", "Fear", "0.9", "False"]
    assert len(rows) == 3  # header + 2 bài
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_csv_generator.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Viết `csv_generator.py`**

```python
# backend/report/csv_generator.py
import csv


def generate_csv(date_from, date_to, aggregates: dict, output_path: str) -> None:
    # CSV chỉ xuất danh sách bài viết chi tiết (không xuất các bảng thống kê tổng hợp —
    # CSV là định dạng phẳng 1 bảng, không hợp để nhồi nhiều bảng khác nhau như
    # docx/pdf/excel; người cần số liệu tổng hợp dùng 1 trong 3 định dạng kia).
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Tiêu đề", "URL", "Sentiment", "Emotion", "Confidence", "Needs review"])
        for article in aggregates["articles"]:
            writer.writerow(
                [
                    article["title"] or "",
                    article["url"] or "",
                    article["sentiment"] or "",
                    article["emotion"] or "",
                    article["confidence"],
                    article["needs_review"],
                ]
            )
```

- [ ] **Step 4: Chạy lại test để xác nhận PASS**

Run: `docker compose exec backend pytest backend/tests/test_csv_generator.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/report/csv_generator.py backend/tests/test_csv_generator.py
git commit -m "feat: thêm generate_csv cho báo cáo (Phase 7)"
```

---

### Task 6: Migration 0020 — mở rộng `report_history` (additive, không đụng `jobs`)

**Files:**
- Create: `backend/alembic/versions/0020_add_campaign_report_columns.py`
- Modify: `backend/models/report_history.py`

**Interfaces:**
- Produces: cột mới `report_history.campaign_id` (UUID, nullable — sẽ NOT NULL ở Task 14), `report_history.format` (`docx|json|pdf|xlsx|csv`, default `'docx'`), `report_history.status` (`pending|running|completed|failed`, default `'completed'` — an toàn cho dòng cũ do luồng Job ghi), `report_history.error_log` (Text, nullable).

- [ ] **Step 1: Viết migration**

```python
# backend/alembic/versions/0020_add_campaign_report_columns.py
"""thêm campaign_id/format/status/error_log vào report_history — chuẩn bị cho luồng
báo cáo theo Campaign (Phase 7), CHƯA đụng bảng jobs/report_history.job_id (giữ additive,
để luồng Job cũ vẫn chạy được cho tới khi cutover ở migration 0021)

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "report_history",
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.campaign_id"), nullable=True),
    )
    op.add_column("report_history", sa.Column("format", sa.String(20), server_default="docx", nullable=False))
    # status mặc định 'completed' — an toàn cho các dòng report_history cũ do luồng Job
    # (report_job.py) ghi trực tiếp sau khi file đã sinh xong, không qua polling
    op.add_column("report_history", sa.Column("status", sa.String(20), server_default="completed", nullable=False))
    op.add_column("report_history", sa.Column("error_log", sa.Text))


def downgrade():
    op.drop_column("report_history", "error_log")
    op.drop_column("report_history", "status")
    op.drop_column("report_history", "format")
    op.drop_column("report_history", "campaign_id")
```

- [ ] **Step 2: Chạy migration + round-trip**

Run: `docker compose exec backend alembic upgrade head && docker compose exec backend alembic downgrade -1 && docker compose exec backend alembic upgrade head`
Expected: cả 2 lệnh chạy sạch, không lỗi.

- [ ] **Step 3: Cập nhật model `ReportHistory`**

```python
# backend/models/report_history.py
import uuid

from sqlalchemy import Column, ForeignKey, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class ReportHistory(Base):
    __tablename__ = "report_history"

    report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.job_id"))  # [SẼ XÓA ở Task 14]
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.campaign_id"))
    format = Column(String(20), server_default="docx")
    file_path = Column(Text, nullable=False)
    status = Column(String(20), server_default="completed")
    error_log = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
```

- [ ] **Step 4: Chạy toàn bộ test suite để xác nhận không có gì hỏng**

Run: `docker compose exec backend pytest backend/tests/ -v`
Expected: PASS toàn bộ.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0020_add_campaign_report_columns.py backend/models/report_history.py
git commit -m "feat: migration 0020 - thêm campaign_id/format/status/error_log vào report_history (Phase 7)"
```

---

### Task 7: `backend/workers/campaign_tasks.py` — Celery task `generate_campaign_report`

**Files:**
- Create: `backend/workers/campaign_tasks.py`
- Modify: `backend/workers/celery_app.py`
- Test: `backend/tests/test_campaign_tasks.py`

**Interfaces:**
- Consumes: `aggregate_basic(db, article_ids)` (Task 1), `generate_docx/export_json` (Task 2), `generate_pdf` (Task 3), `generate_excel` (Task 4), `generate_csv` (Task 5), `analyze_article()` (có sẵn, `backend/ai/ollama_client.py`).
- Produces: `resolve_campaign_article_ids(db, campaign_id, date_from, date_to) -> list[uuid.UUID]`, `generate_campaign_report(report_id: str, campaign_id: str, date_from: str, date_to: str, format: str) -> None` (Celery task, tên `"campaign_tasks.generate_campaign_report"`).

- [ ] **Step 1: Viết test fail trước cho `resolve_campaign_article_ids`**

```python
# backend/tests/test_campaign_tasks.py
import uuid
from datetime import date, datetime

from backend.models import Article, Campaign, CampaignArticle, Source
from backend.workers.campaign_tasks import resolve_campaign_article_ids


def _make_campaign(db_session):
    c = Campaign(name=f"C-{uuid.uuid4()}", start_date="2026-06-01", status="ACTIVE")
    db_session.add(c)
    db_session.flush()
    return c


def _make_source(db_session):
    s = Source(name="S", domain=f"s-{uuid.uuid4()}.example", group_name="G")
    db_session.add(s)
    db_session.flush()
    return s


def test_resolve_campaign_article_ids_filters_by_published_at_range(db_session):
    campaign = _make_campaign(db_session)
    source = _make_source(db_session)
    in_range = Article(
        source_id=source.source_id, url="https://x.vn/a1", url_hash=f"h-{uuid.uuid4()}",
        published_at=datetime(2026, 6, 15), status="analyzed",
    )
    out_of_range = Article(
        source_id=source.source_id, url="https://x.vn/a2", url_hash=f"h-{uuid.uuid4()}",
        published_at=datetime(2026, 7, 15), status="analyzed",
    )
    db_session.add_all([in_range, out_of_range])
    db_session.flush()
    db_session.add(CampaignArticle(campaign_id=campaign.campaign_id, article_id=in_range.article_id))
    db_session.add(CampaignArticle(campaign_id=campaign.campaign_id, article_id=out_of_range.article_id))
    db_session.commit()

    result = resolve_campaign_article_ids(db_session, campaign.campaign_id, date(2026, 6, 1), date(2026, 6, 30))

    assert result == [in_range.article_id]


def test_resolve_campaign_article_ids_excludes_articles_from_other_campaigns(db_session):
    campaign_a = _make_campaign(db_session)
    campaign_b = _make_campaign(db_session)
    source = _make_source(db_session)
    article = Article(
        source_id=source.source_id, url="https://x.vn/a1", url_hash=f"h-{uuid.uuid4()}",
        published_at=datetime(2026, 6, 15), status="analyzed",
    )
    db_session.add(article)
    db_session.flush()
    db_session.add(CampaignArticle(campaign_id=campaign_b.campaign_id, article_id=article.article_id))
    db_session.commit()

    result = resolve_campaign_article_ids(db_session, campaign_a.campaign_id, date(2026, 6, 1), date(2026, 6, 30))

    assert result == []
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_campaign_tasks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.workers.campaign_tasks'`.

- [ ] **Step 3: Viết `resolve_campaign_article_ids`, `_analyze_pending_articles`, `generate_campaign_report`**

Lưu ý thiết kế quan trọng trước khi viết: `report_history` (Task 6) không có cột `date_from`/`date_to`/`campaign_id` sẵn để task tự đọc lại — Celery task phải nhận đủ tham số qua `args` lúc `.delay(...)` (xem Task 8), không dựa vào việc đọc lại context từ DB.

```python
# backend/workers/campaign_tasks.py
import asyncio
import logging
import os
import uuid
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai.ollama_client import analyze_article
from backend.db import SessionLocal
from backend.models import Article, ArticleAnalysis, CampaignArticle, ReportHistory
from backend.report.aggregator import aggregate_basic
from backend.report.csv_generator import generate_csv
from backend.report.docx_generator import export_json, generate_docx
from backend.report.excel_generator import generate_excel
from backend.report.pdf_generator import generate_pdf
from backend.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_GENERATORS = {
    "docx": lambda date_from, date_to, aggregates, path: generate_docx(date_from, date_to, aggregates, path),
    "pdf": lambda date_from, date_to, aggregates, path: generate_pdf(date_from, date_to, aggregates, path),
    "xlsx": lambda date_from, date_to, aggregates, path: generate_excel(date_from, date_to, aggregates, path),
    "csv": lambda date_from, date_to, aggregates, path: generate_csv(date_from, date_to, aggregates, path),
}


def resolve_campaign_article_ids(db: Session, campaign_id, date_from: date, date_to: date) -> list[uuid.UUID]:
    """Chỉ lấy bài đã match từ khóa của Campaign này (qua campaign_articles — BR-CAMP-03
    áp dụng đồng nhất mọi mode, không đọc thẳng articles theo source_id), lọc theo
    published_at thật của bài (giữ đúng ý nghĩa date_from/date_to như luồng Job cũ), không
    phải matched_at (thời điểm hệ thống ghi nhận match)."""
    rows = (
        db.execute(
            select(Article.article_id)
            .join(CampaignArticle, CampaignArticle.article_id == Article.article_id)
            .where(
                CampaignArticle.campaign_id == campaign_id,
                Article.published_at.isnot(None),
                Article.published_at >= date_from,
                Article.published_at <= date_to,
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


def _analyze_pending_articles(db: Session, article_ids: list[uuid.UUID]) -> None:
    """Batch AI-analyze mọi bài còn pending_analysis trong phạm vi report — tuần tự
    (không dùng analyze_articles_batch có concurrency, vì đây là hành động thủ công 1
    lần/Campaign, không cần tối ưu như luồng Job cũ). Lỗi AI (timeout/JSON hỏng) → skip
    đúng 1 bài (status='error'), không chặn các bài còn lại (rule 10)."""
    pending = db.query(Article).filter(Article.article_id.in_(article_ids), Article.status == "pending_analysis").all()
    for article in pending:
        try:
            result = asyncio.run(analyze_article(article.title or "", article.content_raw or ""))
        except (ValueError, httpx.HTTPError):
            logger.exception("AI phân tích lỗi cho bài %s (report campaign)", article.url)
            article.status = "error"
            db.commit()
            continue

        db.add(
            ArticleAnalysis(
                article_id=article.article_id,
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


@celery_app.task(name="campaign_tasks.generate_campaign_report")
def generate_campaign_report(report_id: str, campaign_id: str, date_from: str, date_to: str, format: str) -> None:
    """report_id trỏ tới 1 dòng report_history đã tạo sẵn (status='pending') lúc
    POST /api/campaigns/{id}/reports — task này cập nhật status ngay trên dòng đó để FE
    polling theo report_id (GET /api/campaigns/{id}/reports/{report_id})."""
    db = SessionLocal()
    try:
        report = db.get(ReportHistory, uuid.UUID(report_id))
        if report is None:
            return
        report.status = "running"
        db.commit()

        parsed_date_from = date.fromisoformat(date_from)
        parsed_date_to = date.fromisoformat(date_to)
        campaign_uuid = uuid.UUID(campaign_id)

        article_ids = resolve_campaign_article_ids(db, campaign_uuid, parsed_date_from, parsed_date_to)
        _analyze_pending_articles(db, article_ids)

        # Đọc lại article_ids SAU khi AI chạy xong — _analyze_pending_articles chỉ đổi
        # status của bài đã pending, không đổi tập article_ids đã resolve, nhưng
        # aggregate_basic cần bài đã có ArticleAnalysis (INNER JOIN) nên gọi lại
        # aggregate_basic với đúng article_ids ban đầu là đủ, không cần resolve lại.
        aggregates = aggregate_basic(db, article_ids)

        storage_path = os.environ.get("STORAGE_PATH", "./storage")
        os.makedirs(storage_path, exist_ok=True)
        extension = "json" if format == "json" else format
        output_path = os.path.join(storage_path, f"{report_id}.{extension}")

        if format == "json":
            export_json(report_id, parsed_date_from, parsed_date_to, aggregates, output_path)
        else:
            _GENERATORS[format](parsed_date_from, parsed_date_to, aggregates, output_path)

        report.file_path = output_path
        report.status = "completed"
        db.commit()
    except Exception as exc:
        logger.exception("generate_campaign_report thất bại cho report_id=%s", report_id)
        db.rollback()
        report = db.get(ReportHistory, uuid.UUID(report_id))
        if report is not None:
            report.status = "failed"
            report.error_log = str(exc)
            db.commit()
    finally:
        db.close()
```

- [ ] **Step 4: Đăng ký task trong `celery_app.py`**

```python
# backend/workers/celery_app.py — thêm dòng import cuối file
from backend.workers import campaign_tasks  # noqa: E402,F401  đăng ký task generate_campaign_report
```

- [ ] **Step 5: Chạy lại test `test_campaign_tasks.py`**

Run: `docker compose exec backend pytest backend/tests/test_campaign_tasks.py -v`
Expected: PASS (2 test `resolve_campaign_article_ids`).

- [ ] **Step 6: Viết thêm test tích hợp cho `generate_campaign_report` (mock `analyze_article`, gọi task trực tiếp không qua Celery broker)**

```python
# backend/tests/test_campaign_tasks.py — thêm cuối file
import json
from unittest.mock import patch

from backend.models import ReportHistory
from backend.workers.campaign_tasks import generate_campaign_report


def test_generate_campaign_report_analyzes_pending_and_writes_json(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    campaign = _make_campaign(db_session)
    source = _make_source(db_session)
    article = Article(
        source_id=source.source_id, url="https://x.vn/a1", url_hash=f"h-{uuid.uuid4()}",
        title="Bài test", content_raw="Nội dung test",
        published_at=datetime(2026, 6, 15), status="pending_analysis",
    )
    db_session.add(article)
    db_session.flush()
    db_session.add(CampaignArticle(campaign_id=campaign.campaign_id, article_id=article.article_id))
    report = ReportHistory(campaign_id=campaign.campaign_id, file_path="", status="pending", format="json")
    db_session.add(report)
    db_session.commit()

    fake_result = {
        "topics": ["A"], "keywords": [], "sentiment": "neutral", "emotion": "Trust",
        "confidence": 0.9, "needs_review": False, "summary": "tóm tắt",
        "prompt_version": 1, "ai_model": "qwen3:8b", "analysis_duration_seconds": 1.0,
    }
    with patch("backend.workers.campaign_tasks.SessionLocal", return_value=db_session), \
         patch("backend.workers.campaign_tasks.analyze_article", return_value=_async_result(fake_result)):
        generate_campaign_report.run(
            str(report.report_id), str(campaign.campaign_id), "2026-06-01", "2026-06-30", "json"
        )

    db_session.refresh(report)
    assert report.status == "completed"
    with open(report.file_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["summary_stats"]["Tổng số bài"] == 1


async def _async_result(value):
    return value
```

**Lưu ý viết thật:** `patch("backend.workers.campaign_tasks.SessionLocal", return_value=db_session)` chỉ đúng nếu `db_session.close()` trong `finally` không phá transaction test — vì `db_session` fixture tự rollback theo savepoint (xem `conftest.py`), việc task tự gọi `db.close()` ở cuối là an toàn (đóng đúng connection thật nhưng transaction/savepoint của fixture vẫn còn nguyên tới khi fixture teardown). Nếu chạy thử thấy lỗi "connection already closed" ở fixture teardown, đổi cách patch: dùng `monkeypatch.setattr(campaign_tasks, "SessionLocal", lambda: db_session)` và trong task tạm bỏ `db.close()` cuối cùng qua 1 flag test — **ưu tiên cách đầu tiên trước, chỉ đổi nếu thật sự lỗi khi chạy**.

- [ ] **Step 7: Chạy test để xác nhận PASS**

Run: `docker compose exec backend pytest backend/tests/test_campaign_tasks.py -v`
Expected: PASS toàn bộ.

- [ ] **Step 8: Commit**

```bash
git add backend/workers/campaign_tasks.py backend/workers/celery_app.py backend/tests/test_campaign_tasks.py
git commit -m "feat: Celery task generate_campaign_report - batch AI + sinh report theo Campaign (Phase 7)"
```

---

### Task 8: API `POST/GET /api/campaigns/{id}/reports`, `GET /api/campaigns/{id}/reports/{report_id}`

**Files:**
- Modify: `backend/routers/campaigns.py`
- Test: `backend/tests/test_campaigns_router.py`

**Interfaces:**
- Consumes: `generate_campaign_report` Celery task (Task 7).
- Produces: `POST /api/campaigns/{campaign_id}/reports` → `{report_id, status}` (202), `GET /api/campaigns/{campaign_id}/reports` → `{reports: [...]}`, `GET /api/campaigns/{campaign_id}/reports/{report_id}` → chi tiết 1 report (dùng cho polling), `GET /api/campaigns/{campaign_id}/reports/{report_id}/download` → file.

- [ ] **Step 1: Viết test fail trước**

```python
# backend/tests/test_campaigns_router.py — thêm cuối file
from unittest.mock import patch

from backend.models import CampaignArticle, CampaignSource, ReportHistory


def test_create_campaign_report_dispatches_celery_task_and_returns_pending(app_client, admin_user, source, keyword, db_session):
    campaign = Campaign(
        name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id, mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    with patch("backend.routers.campaigns.generate_campaign_report") as mock_task:
        response = app_client.post(
            f"/api/campaigns/{campaign.campaign_id}/reports",
            json={"date_from": "2026-06-01", "date_to": "2026-06-30", "format": "docx"},
        )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    mock_task.delay.assert_called_once()

    report = db_session.get(ReportHistory, uuid.UUID(body["report_id"]))
    assert report.campaign_id == campaign.campaign_id
    assert report.format == "docx"
    assert report.status == "pending"


def test_create_campaign_report_rejects_invalid_format(app_client, admin_user, db_session):
    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id)
    db_session.add(campaign)
    db_session.commit()

    response = app_client.post(
        f"/api/campaigns/{campaign.campaign_id}/reports",
        json={"date_from": "2026-06-01", "date_to": "2026-06-30", "format": "exe"},
    )

    assert response.status_code == 400


def test_get_campaign_report_status_returns_report_row(app_client, admin_user, db_session):
    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id)
    db_session.add(campaign)
    db_session.flush()
    report = ReportHistory(campaign_id=campaign.campaign_id, file_path="", status="running", format="pdf")
    db_session.add(report)
    db_session.commit()

    response = app_client.get(f"/api/campaigns/{campaign.campaign_id}/reports/{report.report_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_list_campaign_reports_sorted_newest_first(app_client, admin_user, db_session):
    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id)
    db_session.add(campaign)
    db_session.flush()
    r1 = ReportHistory(campaign_id=campaign.campaign_id, file_path="a", status="completed", format="docx")
    db_session.add(r1)
    db_session.commit()
    r2 = ReportHistory(campaign_id=campaign.campaign_id, file_path="b", status="completed", format="pdf")
    db_session.add(r2)
    db_session.commit()

    response = app_client.get(f"/api/campaigns/{campaign.campaign_id}/reports")

    ids = [r["report_id"] for r in response.json()["reports"]]
    assert ids == [str(r2.report_id), str(r1.report_id)]
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_campaigns_router.py -k campaign_report -v`
Expected: FAIL — 404 (route chưa tồn tại).

- [ ] **Step 3: Thêm endpoint vào `campaigns.py`**

```python
# backend/routers/campaigns.py — thêm import ở đầu file
import uuid
from datetime import date

from fastapi.responses import FileResponse

from backend.models import Campaign, CampaignArticle, CampaignKeyword, CampaignSource, Keyword, ReportHistory, Source, User
from backend.workers.campaign_tasks import generate_campaign_report

_VALID_FORMATS = {"docx", "json", "pdf", "xlsx", "csv"}
_MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "json": "application/json",
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
}


def _serialize_report(report: ReportHistory) -> dict:
    return {
        "report_id": str(report.report_id),
        "campaign_id": str(report.campaign_id),
        "format": report.format,
        "status": report.status,
        "error_log": report.error_log,
        "file_path": report.file_path,
        "created_at": report.created_at,
    }


class CreateCampaignReportRequest(BaseModel):
    date_from: str
    date_to: str
    format: str = "docx"


@router.post("/{campaign_id}/reports", status_code=202)
def create_campaign_report(
    campaign_id: str,
    payload: CreateCampaignReportRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("report", "create")),
):
    campaign = _get_campaign_or_404(db, campaign_id)
    if payload.format not in _VALID_FORMATS:
        raise HTTPException(status_code=400, detail=f"format phải là 1 trong {_VALID_FORMATS}")

    report = ReportHistory(
        campaign_id=campaign.campaign_id,
        file_path="",
        format=payload.format,
        status="pending",
    )
    db.add(report)
    db.commit()

    generate_campaign_report.delay(
        str(report.report_id), str(campaign.campaign_id), payload.date_from, payload.date_to, payload.format
    )

    return {"report_id": str(report.report_id), "status": report.status}


@router.get("/{campaign_id}/reports")
def list_campaign_reports(
    campaign_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("report", "view")),
):
    _get_campaign_or_404(db, campaign_id)
    rows = (
        db.query(ReportHistory)
        .filter_by(campaign_id=uuid.UUID(campaign_id))
        .order_by(ReportHistory.created_at.desc())
        .all()
    )
    return {"reports": [_serialize_report(r) for r in rows]}


@router.get("/{campaign_id}/reports/{report_id}")
def get_campaign_report(
    campaign_id: str,
    report_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("report", "view")),
):
    _get_campaign_or_404(db, campaign_id)
    try:
        report = db.get(ReportHistory, uuid.UUID(report_id))
    except ValueError:
        report = None
    if report is None or str(report.campaign_id) != campaign_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy báo cáo")
    return _serialize_report(report)


@router.get("/{campaign_id}/reports/{report_id}/download")
def download_campaign_report(
    campaign_id: str,
    report_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("report", "view")),
):
    _get_campaign_or_404(db, campaign_id)
    try:
        report = db.get(ReportHistory, uuid.UUID(report_id))
    except ValueError:
        report = None
    if report is None or str(report.campaign_id) != campaign_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy báo cáo")
    if report.status != "completed":
        raise HTTPException(status_code=400, detail="Báo cáo chưa hoàn thành")

    return FileResponse(
        report.file_path,
        filename=f"{report_id}.{report.format}",
        media_type=_MEDIA_TYPES[report.format],
    )
```

- [ ] **Step 4: Chạy lại test để xác nhận PASS**

Run: `docker compose exec backend pytest backend/tests/test_campaigns_router.py -v`
Expected: PASS toàn bộ (bao gồm cả test cũ không liên quan).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/campaigns.py backend/tests/test_campaigns_router.py
git commit -m "feat: API POST/GET /api/campaigns/{id}/reports - tạo và theo dõi báo cáo theo Campaign (Phase 7)"
```

---

### Task 9: `mark_crawl_done` — Celery chord callback cho ONE_SHOT

**Files:**
- Modify: `backend/workers/campaign_tasks.py`
- Test: `backend/tests/test_campaign_tasks.py`

**Interfaces:**
- Produces: `mark_crawl_done(results, campaign_id: str) -> None` (Celery task, tên `"campaign_tasks.mark_crawl_done"` — nhận `results` là kết quả trả về của các `crawl_task` con trong `chord`, không dùng tới nhưng bắt buộc phải nhận theo đúng chữ ký callback của Celery `chord`).

- [ ] **Step 1: Viết test fail trước**

```python
# backend/tests/test_campaign_tasks.py — thêm cuối file
from backend.workers.campaign_tasks import mark_crawl_done


def test_mark_crawl_done_sets_campaign_completed(db_session, monkeypatch):
    campaign = _make_campaign(db_session)
    campaign.status = "ACTIVE"
    db_session.commit()

    monkeypatch.setattr("backend.workers.campaign_tasks.SessionLocal", lambda: db_session)
    mark_crawl_done.run([], str(campaign.campaign_id))

    db_session.refresh(campaign)
    assert campaign.status == "COMPLETED"
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_campaign_tasks.py -k mark_crawl_done -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Viết `mark_crawl_done`**

```python
# backend/workers/campaign_tasks.py — thêm import Campaign vào dòng import models đã có, và thêm hàm cuối file
from backend.models import Campaign  # thêm vào import models hiện có ở đầu file


@celery_app.task(name="campaign_tasks.mark_crawl_done")
def mark_crawl_done(results, campaign_id: str) -> None:
    """Callback của Celery chord — chạy SAU KHI toàn bộ crawl_task con (1 task/Source)
    trong group đã xong (kể cả khi 1 vài task con lỗi, xem Task 10 — chord vẫn chạy
    callback vì crawl_task tự bắt lỗi nội bộ, không propagate exception ra ngoài group).
    Chỉ đánh dấu COMPLETED — KHÔNG chạm AI/report (đó là hành động thủ công riêng,
    xem Task 7/8)."""
    db = SessionLocal()
    try:
        campaign = db.get(Campaign, uuid.UUID(campaign_id))
        if campaign is None:
            return
        campaign.status = "COMPLETED"
        db.commit()
    finally:
        db.close()
```

- [ ] **Step 4: Chạy lại test để xác nhận PASS**

Run: `docker compose exec backend pytest backend/tests/test_campaign_tasks.py -v`
Expected: PASS toàn bộ.

- [ ] **Step 5: Commit**

```bash
git add backend/workers/campaign_tasks.py backend/tests/test_campaign_tasks.py
git commit -m "feat: Celery task mark_crawl_done - chord callback đánh dấu ONE_SHOT COMPLETED sau khi crawl xong (Phase 7)"
```

---

### Task 10: `POST /api/campaigns/{id}/activate` — dispatch chord cho `mode=ONE_SHOT`

**Files:**
- Modify: `backend/routers/campaigns.py`
- Test: `backend/tests/test_campaigns_router.py`

**Interfaces:**
- Consumes: `continuous_crawl.crawl_task` (có sẵn, `backend/workers/continuous_crawl.py`), `campaign_tasks.mark_crawl_done` (Task 9).

- [ ] **Step 1: Viết test fail trước**

```python
# backend/tests/test_campaigns_router.py — thêm cuối file
from unittest.mock import MagicMock, patch


def test_activate_one_shot_campaign_dispatches_chord(app_client, admin_user, source, keyword, db_session):
    campaign = Campaign(
        name="C", start_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.commit()

    with patch("backend.routers.campaigns.chord") as mock_chord:
        mock_chord.return_value.return_value = MagicMock()
        response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"
    mock_chord.assert_called_once()


def test_activate_continuous_campaign_does_not_dispatch_chord(app_client, admin_user, source, keyword, db_session):
    campaign = Campaign(
        name="C", start_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.commit()

    with patch("backend.routers.campaigns.chord") as mock_chord:
        response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 200
    mock_chord.assert_not_called()
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_campaigns_router.py -k activate_one_shot -v`
Expected: FAIL — `mock_chord.assert_called_once()` fail vì `chord` chưa được gọi.

- [ ] **Step 3: Sửa `activate_campaign`**

```python
# backend/routers/campaigns.py — thêm import ở đầu file
from celery import chord

from backend.workers import continuous_crawl
```

```python
# backend/routers/campaigns.py — sửa lại activate_campaign, thêm dispatch chord sau khi commit status=ACTIVE
@router.post("/{campaign_id}/activate")
def activate_campaign(
    campaign_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("campaign", "update")),
):
    campaign = _get_campaign_or_404(db, campaign_id)

    if campaign.status not in ("DRAFT", "PAUSED"):
        raise HTTPException(
            status_code=400,
            detail=f"Không thể kích hoạt chiến dịch đang ở trạng thái {campaign.status}",
        )

    # BR-CAMP-03: chỉ chuyển ACTIVE khi có >=1 nguồn VÀ >=1 từ khóa — áp dụng ĐỒNG NHẤT
    # cho mọi mode, kể cả ONE_SHOT (không có ngoại lệ — Phase 7 quyết định: báo cáo luôn
    # đọc qua campaign_articles đã match từ khóa, không đọc thẳng articles theo source_id)
    has_source = db.query(CampaignSource).filter_by(campaign_id=campaign.campaign_id).first() is not None
    has_keyword = db.query(CampaignKeyword).filter_by(campaign_id=campaign.campaign_id).first() is not None
    if not (has_source and has_keyword):
        raise HTTPException(
            status_code=400,
            detail="Chiến dịch cần ít nhất 1 nguồn dữ liệu và 1 từ khóa để kích hoạt (BR-CAMP-03)",
        )

    old_status = campaign.status
    campaign.status = "ACTIVE"

    log_action(
        db,
        user_id=current_user.user_id,
        action="UPDATE",
        entity_type="campaign",
        entity_id=campaign.campaign_id,
        old_value={"status": old_status},
        new_value={"status": "ACTIVE"},
        request=request,
    )
    db.commit()

    # ONE_SHOT: crawl NGAY toàn bộ Source đã chọn, không đợi Celery Beat (BR-CAMP-07 —
    # "không đăng ký Celery Beat"). Dùng chord: group các crawl_task (1/Source) chạy
    # song song, callback mark_crawl_done chỉ chạy SAU KHI TẤT CẢ đã xong.
    if campaign.mode == "ONE_SHOT":
        source_ids = _campaign_source_ids(db, campaign.campaign_id)
        chord(
            (continuous_crawl.crawl_task.s(sid) for sid in source_ids),
            mark_crawl_done.s(str(campaign.campaign_id)),
        ).apply_async()

    return _serialize_campaign(db, campaign)
```

Thêm import `mark_crawl_done` (Task 9) vào đầu file:

```python
from backend.workers.campaign_tasks import generate_campaign_report, mark_crawl_done
```

- [ ] **Step 4: Chạy lại test để xác nhận PASS**

Run: `docker compose exec backend pytest backend/tests/test_campaigns_router.py -v`
Expected: PASS toàn bộ.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/campaigns.py backend/tests/test_campaigns_router.py
git commit -m "feat: activate ONE_SHOT Campaign dispatch chord crawl ngay lập tức, không đợi Beat (Phase 7, BR-CAMP-07)"
```

---

### Task 11: `scheduler.py` — Beat chỉ phục vụ `mode=CONTINUOUS`

**Files:**
- Modify: `backend/workers/scheduler.py:13-19` (`list_due_sources`)
- Test: `backend/tests/test_scheduler.py`

- [ ] **Step 1: Viết test fail trước**

```python
# backend/tests/test_scheduler.py — thêm cuối file
def test_list_due_sources_excludes_source_only_watched_by_one_shot_campaign(db_session):
    campaign = _make_campaign(db_session)
    campaign.mode = "ONE_SHOT"
    db_session.commit()
    source = _make_source(db_session, status="ACTIVE", last_crawled_at=None, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session)

    assert source.source_id not in {s.source_id for s in due}


def test_list_due_sources_includes_source_watched_by_continuous_campaign_even_if_also_one_shot(db_session):
    continuous = _make_campaign(db_session)
    one_shot = _make_campaign(db_session)
    one_shot.mode = "ONE_SHOT"
    db_session.commit()
    source = _make_source(db_session, status="ACTIVE", last_crawled_at=None, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=continuous.campaign_id, source_id=source.source_id))
    db_session.add(CampaignSource(campaign_id=one_shot.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session)

    assert source.source_id in {s.source_id for s in due}
```

(`_make_campaign` mặc định `mode` không truyền — kiểm tra `Campaign.mode` server_default là `"CONTINUOUS"`, đúng model hiện có, không cần sửa fixture.)

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_scheduler.py -k one_shot -v`
Expected: FAIL — source bị Beat bắt trùng dù chỉ thuộc Campaign ONE_SHOT.

- [ ] **Step 3: Sửa `list_due_sources`**

```python
# backend/workers/scheduler.py — sửa watched_source_ids trong list_due_sources
    watched_source_ids = (
        db.query(CampaignSource.source_id)
        .join(Campaign, Campaign.campaign_id == CampaignSource.campaign_id)
        .filter(Campaign.status == "ACTIVE", Campaign.mode == "CONTINUOUS")
        .distinct()
        .all()
    )
```

(Chỉ đổi dòng `.filter(...)` — thêm điều kiện `Campaign.mode == "CONTINUOUS"`, giữ nguyên toàn bộ phần còn lại của hàm.)

- [ ] **Step 4: Chạy lại toàn bộ `test_scheduler.py`**

Run: `docker compose exec backend pytest backend/tests/test_scheduler.py -v`
Expected: PASS toàn bộ (bao gồm cả 5 test cũ).

- [ ] **Step 5: Commit**

```bash
git add backend/workers/scheduler.py backend/tests/test_scheduler.py
git commit -m "fix: Beat chỉ crawl Source thuộc Campaign CONTINUOUS, không đụng Source chỉ thuộc ONE_SHOT (Phase 7)"
```

---

### Task 12: `continuous_crawl.py` — `maybe_analyze_article` chỉ chạy khi có Campaign `CONTINUOUS` match

**Files:**
- Modify: `backend/workers/continuous_crawl.py:216-248` (`maybe_analyze_article`)
- Test: `backend/tests/test_continuous_crawl.py`

**Interfaces:**
- Produces: `maybe_analyze_article(db, article: Article) -> None` (giữ nguyên chữ ký, đổi hành vi bên trong).

- [ ] **Step 1: Đọc test hiện có để nắm fixture pattern**

Run: `docker compose exec backend cat backend/tests/test_continuous_crawl.py | grep -n "def test_maybe_analyze\|def _make_campaign\|def _make_source" `

(Dùng để tái dùng đúng fixture/helper đã có trong file, không tạo trùng.)

- [ ] **Step 2: Viết test fail trước**

```python
# backend/tests/test_continuous_crawl.py — thêm cuối file (điều chỉnh tên helper theo đúng tên đã có trong file, xem Step 1)
from unittest.mock import AsyncMock, patch

from backend.models import Campaign, CampaignSource, SystemSetting
from backend.workers.continuous_crawl import maybe_analyze_article


def test_maybe_analyze_article_skips_when_only_one_shot_campaign_matches(db_session):
    db_session.add(SystemSetting(setting_key="AI_AUTO_TRIGGER", setting_value="true"))
    source = _make_source(db_session)  # dùng đúng helper đã có trong file
    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", mode="ONE_SHOT")
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    article = Article(source_id=source.source_id, url="https://x.vn/a", url_hash="h1", title="T", content_raw="C")
    db_session.add(article)
    db_session.commit()

    with patch("backend.workers.continuous_crawl.analyze_article", new=AsyncMock()) as mock_analyze:
        maybe_analyze_article(db_session, article)

    mock_analyze.assert_not_called()
    assert article.status == "pending_analysis"


def test_maybe_analyze_article_runs_when_continuous_campaign_matches(db_session):
    db_session.add(SystemSetting(setting_key="AI_AUTO_TRIGGER", setting_value="true"))
    source = _make_source(db_session)
    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", mode="CONTINUOUS")
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    article = Article(source_id=source.source_id, url="https://x.vn/a", url_hash="h1", title="T", content_raw="C")
    db_session.add(article)
    db_session.commit()

    fake_result = {
        "topics": ["A"], "keywords": [], "sentiment": "neutral", "emotion": "Trust",
        "confidence": 0.9, "needs_review": False, "summary": "s",
        "prompt_version": 1, "ai_model": "qwen3:8b", "analysis_duration_seconds": 1.0,
    }
    with patch("backend.workers.continuous_crawl.analyze_article", new=AsyncMock(return_value=fake_result)):
        maybe_analyze_article(db_session, article)

    assert article.status == "analyzed"
```

- [ ] **Step 3: Chạy test để xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_continuous_crawl.py -k maybe_analyze_article_skips -v`
Expected: FAIL — hiện tại hàm chạy AI vô điều kiện khi `AI_AUTO_TRIGGER=true`, không phân biệt mode.

- [ ] **Step 4: Sửa `maybe_analyze_article`**

```python
# backend/workers/continuous_crawl.py — thay thế toàn bộ hàm maybe_analyze_article
def _has_continuous_campaign_match(db, article: Article) -> bool:
    return (
        db.query(CampaignArticle)
        .join(Campaign, Campaign.campaign_id == CampaignArticle.campaign_id)
        .filter(
            CampaignArticle.article_id == article.article_id,
            Campaign.status == "ACTIVE",
            Campaign.mode == "CONTINUOUS",
        )
        .first()
        is not None
    )


def maybe_analyze_article(db, article: Article) -> None:
    """Nếu AI_AUTO_TRIGGER=true VÀ bài này match ít nhất 1 Campaign CONTINUOUS đang
    ACTIVE, phân tích AI ngay (per-article). AI_AUTO_TRIGGER KHÔNG áp dụng cho Campaign
    ONE_SHOT (Phase 7, BR-CAMP-07) — ONE_SHOT luôn phân tích thủ công qua
    generate_campaign_report (backend/workers/campaign_tasks.py) khi người dùng bấm
    "Tạo báo cáo", tránh AI chạy nền liên tục không kiểm soát khi có nhiều Campaign
    ONE_SHOT chạy song song."""
    if not get_bool_setting(db, "AI_AUTO_TRIGGER"):
        return
    if not _has_continuous_campaign_match(db, article):
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

Thêm `Campaign` vào import models đã có ở đầu file (`from backend.models import (Article, Campaign, CampaignArticle, ...)`).

**Lưu ý quan trọng:** `match_campaigns_for_article` chạy TRƯỚC `maybe_analyze_article` trong `crawl_task` (thứ tự có sẵn, không đổi) — nên tại thời điểm `maybe_analyze_article` chạy, `campaign_articles` đã có đủ dữ liệu match của bài này, `_has_continuous_campaign_match` đọc đúng.

- [ ] **Step 5: Chạy lại toàn bộ `test_continuous_crawl.py`**

Run: `docker compose exec backend pytest backend/tests/test_continuous_crawl.py -v`
Expected: PASS toàn bộ.

- [ ] **Step 6: Commit**

```bash
git add backend/workers/continuous_crawl.py backend/tests/test_continuous_crawl.py
git commit -m "fix: maybe_analyze_article chỉ chạy khi có Campaign CONTINUOUS match, bỏ qua ONE_SHOT (Phase 7)"
```

---

### Task 13: Xóa hẳn luồng `Job` — router, worker, test liên quan

**Files:**
- Delete: `backend/routers/reports.py`
- Delete: `backend/workers/report_job.py`
- Delete: `backend/tests/test_reports_router.py`
- Delete: `backend/tests/test_report_job.py`
- Modify: `backend/main.py`
- Modify: `backend/workers/celery_app.py`
- Modify: `backend/tests/test_aggregator.py`, `backend/tests/test_docx_generator.py` (bỏ import `Job` không còn dùng nếu còn sót)

- [ ] **Step 1: Gỡ đăng ký router/worker trước khi xóa file (tránh ImportError khi chạy test giữa chừng)**

```python
# backend/main.py — bỏ import và include_router của reports
from backend.routers import (
    audit_logs,
    auth,
    campaigns,
    contents,
    keywords,
    roles,
    sources,
    system_settings,
    users,
)
```

Xóa dòng `app.include_router(reports.router)`.

```python
# backend/workers/celery_app.py — xóa dòng
from backend.workers import report_job  # noqa: E402,F401  đăng ký task run_report_job
```

- [ ] **Step 2: Xóa file**

```bash
git rm backend/routers/reports.py backend/workers/report_job.py backend/tests/test_reports_router.py backend/tests/test_report_job.py
```

- [ ] **Step 3: Chạy toàn bộ test suite, xác nhận không còn tham chiếu vỡ**

Run: `docker compose exec backend pytest backend/tests/ -v`
Expected: PASS toàn bộ — nếu có lỗi `ImportError`/`ModuleNotFoundError` ở file nào khác còn import `reports`/`report_job`, sửa file đó (grep trước: `grep -rn "routers.reports\|workers.report_job\|routers import reports" backend/ --include=*.py`).

- [ ] **Step 4: Xóa file `.docx`/`.json` cũ do luồng Job sinh ra trong `storage/` (dọn dẹp, không phải bước migration DB)**

Run: `docker compose exec backend find storage/ -maxdepth 1 -name "*.docx" -o -name "*.json" | head -20` (kiểm tra trước những gì sẽ xóa)
Run: `docker compose exec backend sh -c 'find storage/ -maxdepth 1 -regextype posix-extended -regex ".*/[0-9a-f-]{36}\.(docx|json)$" -delete'` (chỉ xóa file có tên đúng dạng UUID — không đụng file khác nếu storage/ có nội dung khác)

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/workers/celery_app.py
git commit -m "refactor: xóa hẳn router/worker luồng Job on-demand, thay hoàn toàn bằng Campaign (Phase 7)"
```

---

### Task 14: Migration 0021 — hard-delete dữ liệu `jobs` cũ + xóa bảng `jobs` + đổi `report_history`/dedup

**Files:**
- Create: `backend/alembic/versions/0021_drop_jobs_and_finalize_campaign_reports.py`

**Interfaces:**
- Produces: xóa bảng `jobs`; xóa cột `articles.job_id`, `article_analysis.job_id`, `report_history.job_id`; `report_history.campaign_id` → `NOT NULL`; đổi `UNIQUE(job_id, url_hash)` trên `articles` (migration 0009) → `UNIQUE(source_id, url_hash)` toàn bảng, drop partial index `articles_source_id_url_hash_continuous_key` (Phase 3) vì đã dư thừa.

- [ ] **Step 1: Kiểm tra thủ công số lượng dữ liệu jobs hiện có trước khi viết migration (an toàn dữ liệu)**

Run: `docker compose exec backend python -c "
from backend.db import SessionLocal
from backend.models import Job
db = SessionLocal()
print('Số lượng jobs:', db.query(Job).count())
"`
Expected: số nhỏ (dữ liệu test, đã xác nhận với user) — nếu số này LỚN bất thường (VD >5), DỪNG LẠI, báo cho user trước khi tiếp tục viết migration xóa.

- [ ] **Step 2: Viết migration với guard an toàn tự động (không chỉ dựa vào bước kiểm tra thủ công ở Step 1)**

```python
# backend/alembic/versions/0021_drop_jobs_and_finalize_campaign_reports.py
"""xóa hẳn bảng jobs + mọi dữ liệu liên quan (hard-delete, đã xác nhận với user —
dữ liệu test, chấp nhận mất, không backup) — thay thế hoàn toàn bằng campaigns
(mode=ONE_SHOT/CONTINUOUS). Đổi report_history.campaign_id thành NOT NULL, đổi dedup
articles từ UNIQUE(job_id, url_hash) sang UNIQUE(source_id, url_hash) toàn bảng (Phase 7)

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

# Ngưỡng an toàn — nếu số dòng jobs vượt quá, migration DỪNG LẠI thay vì xóa mù quáng.
# Giá trị nhỏ vì tại thời điểm viết migration này, dữ liệu jobs chỉ là dữ liệu test
# (đã xác nhận với user 2026-07-21) — production thật với nhiều dữ liệu hơn ngưỡng này
# phải dừng lại để người vận hành tự quyết định (export trước, hay nâng ngưỡng có chủ đích).
_MAX_SAFE_JOBS_ROW_COUNT = 5


def upgrade():
    conn = op.get_bind()
    jobs_count = conn.execute(sa.text("SELECT COUNT(*) FROM jobs")).scalar()
    if jobs_count > _MAX_SAFE_JOBS_ROW_COUNT:
        raise RuntimeError(
            f"Migration 0021 dừng lại: bảng jobs có {jobs_count} dòng, vượt ngưỡng an toàn "
            f"{_MAX_SAFE_JOBS_ROW_COUNT}. Đây có thể là dữ liệu thật, không phải dữ liệu test. "
            "Xác nhận lại với người vận hành / backup thủ công trước khi chạy lại migration này."
        )

    # Xóa theo đúng thứ tự phụ thuộc FK: article_analysis -> articles -> report_history -> jobs
    op.execute("DELETE FROM article_analysis WHERE job_id IS NOT NULL")
    op.execute("DELETE FROM articles WHERE job_id IS NOT NULL")
    op.execute("DELETE FROM report_history WHERE job_id IS NOT NULL")

    op.drop_column("report_history", "job_id")
    op.alter_column("report_history", "campaign_id", nullable=False)

    op.drop_column("article_analysis", "job_id")

    # Dedup articles: đổi từ UNIQUE(job_id, url_hash) [migration 0009] sang
    # UNIQUE(source_id, url_hash) toàn bảng — partial index (source_id, url_hash)
    # WHERE job_id IS NULL [migration 0018] giờ dư thừa vì job_id sắp bị xóa hẳn.
    op.drop_constraint("articles_job_id_url_hash_key", "articles", type_="unique")
    op.drop_index("articles_source_id_url_hash_continuous_key", table_name="articles")
    op.drop_column("articles", "job_id")
    op.create_unique_constraint("articles_source_id_url_hash_key", "articles", ["source_id", "url_hash"])

    op.drop_table("jobs")


def downgrade():
    # Downgrade khôi phục CẤU TRÚC bảng jobs (rỗng) + cột job_id — KHÔNG khôi phục được
    # dữ liệu đã hard-delete ở upgrade() (đã chấp nhận đánh đổi này khi quyết định
    # hard-delete thay vì backup, xem design doc mục "Data Model"). Downgrade chỉ để đảm
    # bảo round-trip schema sạch cho môi trường CHƯA từng chạy upgrade() với dữ liệu thật.
    op.create_table(
        "jobs",
        sa.Column("job_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_ids", sa.dialects.postgresql.ARRAY(sa.dialects.postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column("date_from", sa.Date, nullable=False),
        sa.Column("date_to", sa.Date, nullable=False),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("output_docx", sa.Text),
        sa.Column("output_json", sa.Text),
        sa.Column("error_log", sa.Text),
        sa.Column("celery_task_id", sa.String(255)),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("completed_at", sa.TIMESTAMP),
    )

    op.drop_constraint("articles_source_id_url_hash_key", "articles", type_="unique")
    op.add_column("articles", sa.Column("job_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.job_id")))
    op.create_unique_constraint("articles_job_id_url_hash_key", "articles", ["job_id", "url_hash"])
    op.create_index(
        "articles_source_id_url_hash_continuous_key", "articles", ["source_id", "url_hash"],
        unique=True, postgresql_where=sa.text("job_id IS NULL"),
    )

    op.add_column("article_analysis", sa.Column("job_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.job_id")))

    op.alter_column("report_history", "campaign_id", nullable=True)
    op.add_column("report_history", sa.Column("job_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.job_id")))
```

- [ ] **Step 3: Chạy migration**

Run: `docker compose exec backend alembic upgrade head`
Expected: chạy sạch. Nếu raise `RuntimeError` vì `jobs_count` vượt ngưỡng, DỪNG — báo user, không tự ý sửa `_MAX_SAFE_JOBS_ROW_COUNT` để né qua.

- [ ] **Step 4: Chạy round-trip downgrade/upgrade**

Run: `docker compose exec backend alembic downgrade -1 && docker compose exec backend alembic upgrade head`
Expected: chạy sạch (không còn dữ liệu jobs thật để khôi phục — bảng jobs rỗng sau downgrade, đúng như thiết kế).

- [ ] **Step 5: Chạy toàn bộ test suite**

Run: `docker compose exec backend pytest backend/tests/ -v`
Expected: FAIL ở các file còn import `Job`/dùng cột `job_id` trong model — sang Task 15 để sửa model trước khi test này pass hoàn toàn. Ghi nhận danh sách lỗi cụ thể ở bước này để đối chiếu sau Task 15.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/0021_drop_jobs_and_finalize_campaign_reports.py
git commit -m "feat: migration 0021 - xóa hẳn bảng jobs + dữ liệu liên quan, dedup articles chuyển UNIQUE(source_id, url_hash) toàn bảng (Phase 7)"
```

---

### Task 15: Cập nhật SQLAlchemy models — xóa `Job`, gỡ `job_id` khỏi `Article`/`ArticleAnalysis`/`ReportHistory`

**Files:**
- Delete: `backend/models/jobs.py`
- Modify: `backend/models/articles.py`
- Modify: `backend/models/article_analysis.py`
- Modify: `backend/models/report_history.py`
- Modify: `backend/models/__init__.py`
- Modify: `backend/workers/continuous_crawl.py` (bỏ `job_id=None` khỏi các `Article(...)`/`ArticleAnalysis(...)` — không còn cột này)
- Modify: `backend/workers/campaign_tasks.py` (bỏ `job_id=None` khỏi `ArticleAnalysis(...)` nếu Task 7 có viết — kiểm tra lại)

- [ ] **Step 1: Sửa `articles.py`**

```python
# backend/models/articles.py
import uuid

from sqlalchemy import Column, Float, ForeignKey, String, TIMESTAMP, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


VALID_REVIEW_STATUSES = {"NEW", "REVIEWED", "NEED_VERIFY", "VERIFIED", "NOT_RELEVANT", "CASE_CREATED"}


class Article(Base):
    __tablename__ = "articles"
    # UNIQUE(source_id, url_hash) toàn bảng (migration 0021) — thay thế hoàn toàn
    # UNIQUE(job_id, url_hash) [migration 0009] sau khi jobs bị xóa (Phase 7). Dedup
    # toàn cục theo Source, đúng nghĩa duy nhất còn lại của hệ thống (Phase 3 continuous
    # crawl đã dùng cơ chế này, giờ áp dụng cho MỌI dòng, không chỉ dòng job_id IS NULL).
    __table_args__ = (UniqueConstraint("source_id", "url_hash", name="articles_source_id_url_hash_key"),)

    article_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.source_id"))
    url = Column(Text, nullable=False)
    url_hash = Column(String(64), nullable=False, index=True)
    title = Column(Text)
    content_raw = Column(Text)
    author = Column(Text)
    published_at = Column(TIMESTAMP)
    crawled_at = Column(TIMESTAMP, server_default=func.now())
    status = Column(String(50), server_default="pending_analysis")
    crawl_duration_seconds = Column(Float)

    review_status = Column(String(50), server_default="NEW", nullable=False)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"))
    reviewed_at = Column(TIMESTAMP)
    reviewer_note = Column(Text)
    deleted_at = Column(TIMESTAMP)
```

- [ ] **Step 2: Sửa `article_analysis.py`** — xóa dòng `job_id = Column(...)`.

- [ ] **Step 3: Sửa `report_history.py`** — xóa dòng `job_id = Column(...)`, `campaign_id` đổi `nullable=False`:

```python
# backend/models/report_history.py
import uuid

from sqlalchemy import Column, ForeignKey, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class ReportHistory(Base):
    __tablename__ = "report_history"

    report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.campaign_id"), nullable=False)
    format = Column(String(20), server_default="docx")
    file_path = Column(Text, nullable=False)
    status = Column(String(20), server_default="completed")
    error_log = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
```

- [ ] **Step 4: Xóa `backend/models/jobs.py`, sửa `backend/models/__init__.py`**

```bash
git rm backend/models/jobs.py
```

```python
# backend/models/__init__.py
from backend.models.article_analysis import ArticleAnalysis
from backend.models.articles import Article
from backend.models.audit_log import AuditLog
from backend.models.campaign_article_keywords import CampaignArticleKeyword
from backend.models.campaign_articles import CampaignArticle
from backend.models.campaign_keywords import CampaignKeyword
from backend.models.campaign_sources import CampaignSource
from backend.models.campaigns import Campaign
from backend.models.crawl_queue import CrawlQueue
from backend.models.keywords import Keyword
from backend.models.permissions import Permission
from backend.models.report_history import ReportHistory
from backend.models.role_permissions import RolePermission
from backend.models.roles import Role
from backend.models.sources import Source
from backend.models.system_settings import SystemSetting
from backend.models.user_roles import UserRole
from backend.models.users import User

__all__ = [
    "Source",
    "Article",
    "ArticleAnalysis",
    "ReportHistory",
    "User",
    "Role",
    "Permission",
    "UserRole",
    "RolePermission",
    "AuditLog",
    "Campaign",
    "Keyword",
    "CampaignKeyword",
    "CampaignSource",
    "CrawlQueue",
    "SystemSetting",
    "CampaignArticle",
    "CampaignArticleKeyword",
]
```

- [ ] **Step 5: Bỏ `job_id=None` khỏi mọi `Article(...)`/`ArticleAnalysis(...)` còn sót**

Run: `grep -rn "job_id" backend/workers/continuous_crawl.py backend/workers/campaign_tasks.py`

Xóa từng dòng `job_id=None,` tìm thấy trong constructor `Article(...)` (hàm `fetch_pending_urls`) và `ArticleAnalysis(...)` (hàm `maybe_analyze_article`, `_analyze_pending_articles`).

- [ ] **Step 6: Chạy toàn bộ test suite**

Run: `docker compose exec backend pytest backend/tests/ -v`
Expected: PASS toàn bộ. Sửa tiếp bất kỳ test nào còn tạo `Article(job_id=...)`/`ArticleAnalysis(job_id=...)`/import `Job` (grep: `grep -rln "job_id\|models import.*Job\b\|from backend.models.jobs" backend/tests/`), bỏ tham số/import đó.

- [ ] **Step 7: `docker compose build backend` lại lần cuối để chắc chắn image khớp code + chạy full test suite qua Docker thật**

Run: `docker compose build backend && docker compose up -d && docker compose exec backend pytest backend/tests/ -v`
Expected: PASS toàn bộ.

- [ ] **Step 8: Commit**

```bash
git add backend/models/ backend/workers/continuous_crawl.py backend/workers/campaign_tasks.py backend/tests/
git commit -m "refactor: xóa model Job, gỡ cột job_id khỏi Article/ArticleAnalysis/ReportHistory (Phase 7 cutover hoàn tất)"
```

---

### Task 16: FE `CampaignForm.tsx` — nối API thật, thêm bước chọn nguồn + từ khóa

**Files:**
- Modify: `frontend/src/pages/Campaigns/CampaignForm.tsx`
- Modify: `frontend/src/pages/Campaigns/index.tsx` (Task 17, không đụng ở đây)

**Interfaces:**
- Consumes: `POST /api/campaigns`, `PUT /api/campaigns/{id}`, `GET /api/campaigns/{id}`, `GET /api/sources`, `GET /api/keywords` (đã có sẵn, `backend/routers/keywords.py`).

- [ ] **Step 1: Viết lại `CampaignForm.tsx`**

```tsx
// frontend/src/pages/Campaigns/CampaignForm.tsx
import { App, Button, Card, DatePicker, Form, Input, Radio, Select, Space } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import PageHeader from '@/components/common/PageHeader'
import { authFetch } from '@/lib/api'
import { useAuth } from '@/lib/auth' // giả định context auth hiện có cung cấp user_id đang đăng nhập — kiểm tra tên hook thật trong frontend/src/lib/ trước khi dùng, đổi lại nếu khác tên
import dayjs from 'dayjs'
import { useEffect, useState } from 'react'

type SourceOption = { source_id: string; name: string; source_group: string | null }
type KeywordOption = { keyword_id: string; keyword: string }

export default function CampaignForm() {
  const { id } = useParams()
  const isEdit = !!id
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const { user } = useAuth()

  const [sources, setSources] = useState<SourceOption[]>([])
  const [keywords, setKeywords] = useState<KeywordOption[]>([])
  const [loading, setLoading] = useState(isEdit)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    authFetch('/api/sources').then((r) => r.json()).then((d) => setSources(d.sources ?? []))
    authFetch('/api/keywords').then((r) => r.json()).then((d) => setKeywords(d.keywords ?? []))
  }, [])

  useEffect(() => {
    if (!isEdit) return
    authFetch(`/api/campaigns/${id}`)
      .then((r) => r.json())
      .then((c) =>
        form.setFieldsValue({
          name: c.name,
          description: c.description,
          objective: c.objective,
          mode: c.mode,
          start_date: c.start_date ? dayjs(c.start_date) : null,
          end_date: c.end_date ? dayjs(c.end_date) : null,
          source_ids: c.source_ids,
          keyword_ids: c.keyword_ids,
        })
      )
      .finally(() => setLoading(false))
  }, [id, isEdit, form])

  async function handleFinish(values: any) {
    setSubmitting(true)
    try {
      const payload = {
        name: values.name,
        description: values.description,
        objective: values.objective,
        mode: values.mode,
        start_date: values.start_date.format('YYYY-MM-DD'),
        end_date: values.end_date ? values.end_date.format('YYYY-MM-DD') : null,
        source_ids: values.source_ids ?? [],
        keyword_ids: values.keyword_ids ?? [],
        owner_id: user.user_id,
      }
      const res = await authFetch(isEdit ? `/api/campaigns/${id}` : '/api/campaigns', {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        message.error(body.detail || 'Lưu chiến dịch thất bại')
        return
      }
      message.success(isEdit ? 'Đã cập nhật chiến dịch' : 'Đã tạo chiến dịch (trạng thái Nháp)')
      const saved = await res.json()
      navigate(`/campaigns/${saved.campaign_id}`)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return null

  return (
    <div>
      <PageHeader
        title={isEdit ? 'Chỉnh sửa chiến dịch' : 'Tạo chiến dịch mới'}
        breadcrumbs={[
          { title: 'Tổng quan', href: '/' },
          { title: 'Chiến dịch giám sát', href: '/campaigns' },
          { title: isEdit ? 'Chỉnh sửa' : 'Tạo mới' },
        ]}
      />

      <Card style={{ borderRadius: 12, maxWidth: 720 }}>
        <Form form={form} layout="vertical" onFinish={handleFinish} initialValues={{ mode: 'CONTINUOUS' }}>
          <Form.Item name="name" label="Tên chiến dịch" rules={[{ required: true, message: 'Vui lòng nhập tên chiến dịch' }]}>
            <Input placeholder="Nhập tên chiến dịch" />
          </Form.Item>

          <Form.Item name="description" label="Mô tả">
            <Input.TextArea rows={3} placeholder="Mô tả mục tiêu và phạm vi giám sát" />
          </Form.Item>

          <Form.Item name="mode" label="Chế độ">
            <Radio.Group>
              <Radio.Button value="CONTINUOUS">Giám sát liên tục</Radio.Button>
              <Radio.Button value="ONE_SHOT">Tạo báo cáo nhanh (1 lần)</Radio.Button>
            </Radio.Group>
          </Form.Item>

          <Space style={{ width: '100%' }}>
            <Form.Item name="start_date" label="Ngày bắt đầu" style={{ flex: 1 }} rules={[{ required: true, message: 'Bắt buộc' }]}>
              <DatePicker style={{ width: '100%' }} format="DD/MM/YYYY" />
            </Form.Item>
            <Form.Item name="end_date" label="Ngày kết thúc" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} format="DD/MM/YYYY" />
            </Form.Item>
          </Space>

          <Form.Item name="source_ids" label="Nguồn dữ liệu" extra="Cần ít nhất 1 nguồn để kích hoạt (BR-CAMP-03)">
            <Select
              mode="multiple"
              placeholder="Chọn nguồn"
              options={sources.map((s) => ({ value: s.source_id, label: `${s.name}${s.source_group ? ` (${s.source_group})` : ''}` }))}
            />
          </Form.Item>

          <Form.Item name="keyword_ids" label="Từ khóa giám sát" extra="Cần ít nhất 1 từ khóa để kích hoạt (BR-CAMP-03)">
            <Select mode="multiple" placeholder="Chọn từ khóa" options={keywords.map((k) => ({ value: k.keyword_id, label: k.keyword }))} />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0 }}>
            <Space>
              <Button type="primary" htmlType="submit" loading={submitting}>
                {isEdit ? 'Lưu thay đổi' : 'Tạo chiến dịch'}
              </Button>
              <Button onClick={() => navigate('/campaigns')}>Hủy</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
```

**Lưu ý bắt buộc kiểm tra trước khi implement thật:** tên hook/context cung cấp user đang đăng nhập (`useAuth`) là GIẢ ĐỊNH trong plan này — chạy `grep -rn "user_id\|useAuth\|AuthContext" frontend/src/lib/ frontend/src/App.tsx` để tìm tên thật (rất có thể là `frontend/src/lib/api.ts` hoặc 1 context riêng), sửa lại import cho khớp trước khi code.

- [ ] **Step 2: Chạy dev server, kiểm tra thủ công**

Run: `docker compose up -d frontend` (hoặc `npm run dev` trong `frontend/` nếu chạy local) — mở `/campaigns/new`, tạo 1 Campaign thật với ≥1 nguồn + ≥1 từ khóa, xác nhận chuyển hướng sang `/campaigns/{id}` sau khi tạo thành công.
Expected: tạo thành công, không lỗi console.

- [ ] **Step 3: `npm run build` xác nhận không lỗi TypeScript**

Run: `cd frontend && npm run build`
Expected: build thành công.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Campaigns/CampaignForm.tsx
git commit -m "feat: CampaignForm nối API thật, thêm chọn nguồn + từ khóa (Phase 7)"
```

---

### Task 17: FE `Campaigns/index.tsx` — nối API thật

**Files:**
- Modify: `frontend/src/pages/Campaigns/index.tsx`

**Interfaces:**
- Consumes: `GET /api/campaigns?status=&keyword=`.

- [ ] **Step 1: Viết lại `index.tsx`**

```tsx
// frontend/src/pages/Campaigns/index.tsx
import { useEffect, useState } from 'react'
import { Button, Card, Input, Select, Space, Table, Tag } from 'antd'
import { PlusOutlined, SearchOutlined, EyeOutlined, EditOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import StatusTag from '@/components/common/StatusTag'
import PageHeader from '@/components/common/PageHeader'
import { authFetch } from '@/lib/api'
import dayjs from 'dayjs'

type CampaignRow = {
  campaign_id: string
  code: string | null
  name: string
  status: string
  start_date: string
  end_date: string | null
  source_ids: string[]
  keyword_ids: string[]
}

const STATUS_OPTIONS = [
  { value: '', label: 'Tất cả trạng thái' },
  { value: 'DRAFT', label: 'Nháp' },
  { value: 'ACTIVE', label: 'Đang hoạt động' },
  { value: 'PAUSED', label: 'Tạm dừng' },
  { value: 'COMPLETED', label: 'Hoàn thành' },
  { value: 'ARCHIVED', label: 'Lưu trữ' },
]

export default function CampaignsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<CampaignRow[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<string>('')

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    if (keyword) params.set('keyword', keyword)
    authFetch(`/api/campaigns?${params.toString()}`)
      .then((r) => (r.ok ? r.json() : { campaigns: [] }))
      .then((d) => setData(d.campaigns ?? []))
      .finally(() => setIsLoading(false))
  }, [status, keyword])

  const columns = [
    { title: 'Mã', dataIndex: 'code', key: 'code', width: 120, render: (v: string | null) => (v ? <Tag>{v}</Tag> : '—') },
    {
      title: 'Tên chiến dịch',
      dataIndex: 'name',
      key: 'name',
      render: (v: string, r: CampaignRow) => (
        <a onClick={() => navigate(`/campaigns/${r.campaign_id}`)} style={{ color: '#0B1F3A', fontWeight: 500 }}>
          {v}
        </a>
      ),
    },
    { title: 'Trạng thái', dataIndex: 'status', key: 'status', render: (v: string) => <StatusTag type="campaign" value={v} /> },
    { title: 'Số nguồn', render: (_: unknown, r: CampaignRow) => r.source_ids.length },
    { title: 'Số từ khóa', render: (_: unknown, r: CampaignRow) => r.keyword_ids.length },
    { title: 'Ngày bắt đầu', dataIndex: 'start_date', render: (v: string) => (v ? dayjs(v).format('DD/MM/YYYY') : '—') },
    { title: 'Ngày kết thúc', dataIndex: 'end_date', render: (v: string | null) => (v ? dayjs(v).format('DD/MM/YYYY') : '—') },
    {
      title: 'Thao tác',
      key: 'actions',
      width: 120,
      render: (_: unknown, r: CampaignRow) => (
        <Space>
          <Button type="text" icon={<EyeOutlined />} onClick={() => navigate(`/campaigns/${r.campaign_id}`)} />
          <Button type="text" icon={<EditOutlined />} onClick={() => navigate(`/campaigns/${r.campaign_id}/edit`)} />
        </Space>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="Chiến dịch giám sát"
        subtitle="Quản lý các chiến dịch giám sát thông tin"
        breadcrumbs={[{ title: 'Tổng quan', href: '/' }, { title: 'Chiến dịch giám sát' }]}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/campaigns/new')}>
            Tạo chiến dịch
          </Button>
        }
      />

      <Card style={{ borderRadius: 12 }}>
        <Space style={{ marginBottom: 16 }}>
          <Input
            placeholder="Tìm kiếm chiến dịch..."
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 280 }}
            allowClear
          />
          <Select value={status} onChange={(v) => setStatus(v)} options={STATUS_OPTIONS} style={{ width: 180 }} />
        </Space>

        <Table
          columns={columns}
          dataSource={data}
          rowKey="campaign_id"
          loading={isLoading}
          pagination={{ pageSize: 20, showTotal: (t) => `Tổng ${t} chiến dịch` }}
        />
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Kiểm tra thủ công `/campaigns`**

Xác nhận danh sách hiện đúng Campaign vừa tạo ở Task 16, filter theo trạng thái/tên hoạt động đúng.

- [ ] **Step 3: `npm run build`**

Run: `cd frontend && npm run build`
Expected: build thành công.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Campaigns/index.tsx
git commit -m "feat: Campaigns list nối API thật GET /api/campaigns (Phase 7)"
```

---

### Task 18: FE `CampaignDetail.tsx` — nối API thật + activate/pause + "Tạo báo cáo"

**Files:**
- Modify: `frontend/src/pages/Campaigns/CampaignDetail.tsx`

**Interfaces:**
- Consumes: `GET /api/campaigns/{id}`, `POST /api/campaigns/{id}/activate`, `POST /api/campaigns/{id}/pause`, `POST /api/campaigns/{id}/reports`, `GET /api/campaigns/{id}/reports`, `GET /api/campaigns/{id}/reports/{report_id}`, `GET /api/campaigns/{id}/reports/{report_id}/download`.

- [ ] **Step 1: Viết lại `CampaignDetail.tsx`**

```tsx
// frontend/src/pages/Campaigns/CampaignDetail.tsx
import { useEffect, useState } from 'react'
import { App, Button, Card, Col, DatePicker, Descriptions, Row, Select, Space, Table, Tag } from 'antd'
import { EditOutlined, ArrowLeftOutlined, PlusOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import StatusTag from '@/components/common/StatusTag'
import PageHeader from '@/components/common/PageHeader'
import LoadingState from '@/components/common/LoadingState'
import { authFetch } from '@/lib/api'
import dayjs, { Dayjs } from 'dayjs'

type Campaign = {
  campaign_id: string
  code: string | null
  name: string
  description: string | null
  status: string
  mode: string
  start_date: string
  end_date: string | null
  source_ids: string[]
  keyword_ids: string[]
  created_at: string
}

type ReportRow = {
  report_id: string
  format: string
  status: string
  created_at: string
}

const FORMAT_OPTIONS = [
  { value: 'docx', label: 'Word (.docx)' },
  { value: 'pdf', label: 'PDF' },
  { value: 'xlsx', label: 'Excel (.xlsx)' },
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON (raw data)' },
]

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { message } = App.useApp()

  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [reports, setReports] = useState<ReportRow[]>([])
  const [reportRange, setReportRange] = useState<[Dayjs, Dayjs] | null>(null)
  const [reportFormat, setReportFormat] = useState('docx')
  const [creatingReport, setCreatingReport] = useState(false)

  function loadCampaign() {
    authFetch(`/api/campaigns/${id}`).then((r) => r.json()).then(setCampaign)
  }
  function loadReports() {
    authFetch(`/api/campaigns/${id}/reports`).then((r) => r.json()).then((d) => setReports(d.reports ?? []))
  }

  useEffect(() => {
    loadCampaign()
    loadReports()
  }, [id])

  // Polling danh sách report mỗi 3s khi có report đang pending/running — dừng khi
  // không còn report nào ở 2 trạng thái đó (giống pattern polling job cũ, ReportCreate.tsx)
  useEffect(() => {
    const active = reports.some((r) => r.status === 'pending' || r.status === 'running')
    if (!active) return
    const interval = setInterval(loadReports, 3000)
    return () => clearInterval(interval)
  }, [reports])

  if (!campaign) return <LoadingState />

  async function handleActivate() {
    const res = await authFetch(`/api/campaigns/${id}/activate`, { method: 'POST' })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      message.error(body.detail || 'Kích hoạt thất bại')
      return
    }
    message.success('Đã kích hoạt chiến dịch')
    loadCampaign()
  }

  async function handlePause() {
    const res = await authFetch(`/api/campaigns/${id}/pause`, { method: 'POST' })
    if (res.ok) {
      message.success('Đã tạm dừng chiến dịch')
      loadCampaign()
    }
  }

  async function handleCreateReport() {
    if (!reportRange) return
    setCreatingReport(true)
    try {
      const res = await authFetch(`/api/campaigns/${id}/reports`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date_from: reportRange[0].format('YYYY-MM-DD'),
          date_to: reportRange[1].format('YYYY-MM-DD'),
          format: reportFormat,
        }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        message.error(body.detail || 'Tạo báo cáo thất bại')
        return
      }
      message.success('Đang tạo báo cáo...')
      loadReports()
    } finally {
      setCreatingReport(false)
    }
  }

  async function handleDownload(reportId: string, format: string) {
    const res = await authFetch(`/api/campaigns/${id}/reports/${reportId}/download`)
    if (!res.ok) return
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${reportId}.${format}`
    link.click()
    window.URL.revokeObjectURL(url)
  }

  return (
    <div>
      <PageHeader
        title={campaign.name}
        breadcrumbs={[
          { title: 'Tổng quan', href: '/' },
          { title: 'Chiến dịch giám sát', href: '/campaigns' },
          { title: campaign.name },
        ]}
        extra={
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/campaigns')}>
              Quay lại
            </Button>
            <Button icon={<EditOutlined />} onClick={() => navigate(`/campaigns/${id}/edit`)}>
              Chỉnh sửa
            </Button>
            {(campaign.status === 'DRAFT' || campaign.status === 'PAUSED') && (
              <Button type="primary" onClick={handleActivate}>
                Kích hoạt
              </Button>
            )}
            {campaign.status === 'ACTIVE' && <Button onClick={handlePause}>Tạm dừng</Button>}
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="Thông tin chiến dịch" style={{ borderRadius: 12 }}>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="Mã chiến dịch">
                <Tag>{campaign.code ?? '—'}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Trạng thái">
                <StatusTag type="campaign" value={campaign.status} />
              </Descriptions.Item>
              <Descriptions.Item label="Chế độ">{campaign.mode === 'ONE_SHOT' ? 'Tạo báo cáo nhanh' : 'Giám sát liên tục'}</Descriptions.Item>
              <Descriptions.Item label="Ngày tạo">{dayjs(campaign.created_at).format('DD/MM/YYYY HH:mm')}</Descriptions.Item>
              <Descriptions.Item label="Ngày bắt đầu">{dayjs(campaign.start_date).format('DD/MM/YYYY')}</Descriptions.Item>
              <Descriptions.Item label="Ngày kết thúc">{campaign.end_date ? dayjs(campaign.end_date).format('DD/MM/YYYY') : '—'}</Descriptions.Item>
              <Descriptions.Item label="Mô tả" span={2}>{campaign.description ?? '—'}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Thống kê" style={{ borderRadius: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Từ khóa giám sát</span>
                <Tag color="blue">{campaign.keyword_ids.length}</Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Nguồn dữ liệu</span>
                <Tag color="green">{campaign.source_ids.length}</Tag>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card title="Báo cáo" style={{ borderRadius: 12, marginTop: 16 }}>
        <Space style={{ marginBottom: 16 }} wrap>
          <DatePicker.RangePicker
            value={reportRange}
            onChange={(v) => setReportRange(v as [Dayjs, Dayjs] | null)}
            format="DD/MM/YYYY"
          />
          <Select value={reportFormat} onChange={setReportFormat} options={FORMAT_OPTIONS} style={{ width: 180 }} />
          <Button type="primary" icon={<PlusOutlined />} loading={creatingReport} disabled={!reportRange} onClick={handleCreateReport}>
            Tạo báo cáo
          </Button>
        </Space>

        <Table<ReportRow>
          rowKey="report_id"
          dataSource={reports}
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: 'Chưa có báo cáo nào.' }}
          columns={[
            { title: 'Ngày tạo', dataIndex: 'created_at', render: (v: string) => new Date(v).toLocaleString('vi-VN') },
            { title: 'Định dạng', dataIndex: 'format', render: (v: string) => <Tag>{v.toUpperCase()}</Tag> },
            {
              title: 'Trạng thái',
              dataIndex: 'status',
              render: (s: string) => (
                <Tag color={s === 'completed' ? 'green' : s === 'failed' ? 'red' : 'blue'}>{s}</Tag>
              ),
            },
            {
              title: 'Tải về',
              render: (_v, r) =>
                r.status === 'completed' ? (
                  <Button type="link" onClick={() => handleDownload(r.report_id, r.format)}>
                    Tải xuống
                  </Button>
                ) : (
                  '-'
                ),
            },
          ]}
        />
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Kiểm tra thủ công**

Vào `/campaigns/{id}` của Campaign vừa tạo (Task 16), bấm "Kích hoạt", xác nhận trạng thái đổi sang ACTIVE. Với Campaign `mode=ONE_SHOT`, xác nhận sau vài chục giây (tùy số nguồn) trạng thái tự chuyển COMPLETED (F5 lại trang để thấy — trang này chưa polling trạng thái Campaign, chỉ polling report). Bấm "Tạo báo cáo" với 1 khoảng ngày, xác nhận thấy dòng report mới với status chuyển pending → running → completed, tải file thành công.

- [ ] **Step 3: `npm run build`**

Run: `cd frontend && npm run build`
Expected: build thành công.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Campaigns/CampaignDetail.tsx
git commit -m "feat: CampaignDetail nối API thật - activate/pause + tạo và tải báo cáo đa định dạng (Phase 7)"
```

---

### Task 19: FE `ReportCreate.tsx` — rewire sang `POST /api/campaigns` (mode=ONE_SHOT)

**Files:**
- Modify: `frontend/src/pages/Reports/ReportCreate.tsx`

**Interfaces:**
- Consumes: `POST /api/campaigns`, `POST /api/campaigns/{id}/activate`, `GET /api/campaigns/{id}`, `GET /api/campaigns/{id}/reports`, `POST /api/campaigns/{id}/reports`, `GET /api/keywords`.

- [ ] **Step 1: Viết lại `ReportCreate.tsx`**

Giữ nguyên toàn bộ UI chọn nguồn/ngày (`SourceSidebar`/`SummaryCard`/preset ngày) — chỉ đổi phần logic submit/polling. Thêm 1 `Select` chọn từ khóa (bắt buộc ≥1, theo BR-CAMP-03 áp dụng đồng nhất — xem Task 10) ngay dưới phần chọn nguồn.

```tsx
// frontend/src/pages/Reports/ReportCreate.tsx
import { useEffect, useState } from "react";
import { Button, Card, DatePicker, Space, Table, Tag, Alert, Select, Popconfirm, Typography } from "antd";
import dayjs, { Dayjs } from "dayjs";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import PermissionGuard from "@/components/common/PermissionGuard";
import { authFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth"; // xem lưu ý Task 16 về tên hook thật
import SourceSidebar, { SourceItem } from "./SourceSidebar";
import SummaryCard from "./SummaryCard";

const CAMPAIGN_ID_STORAGE_KEY = "ngs_monitor_one_shot_campaign_id";

const DATE_PRESETS = [
  { label: "Hôm nay", days: 0 },
  { label: "7 ngày", days: 7 },
  { label: "30 ngày", days: 30 },
  { label: "90 ngày", days: 90 },
  { label: "150 ngày", days: 150 },
];

function todayMinus(days: number): Dayjs {
  return dayjs().subtract(days, "day");
}

type CampaignStatus = {
  campaign_id: string;
  status: string;
};

type KeywordOption = { keyword_id: string; keyword: string };

const statusColor: Record<string, string> = {
  DRAFT: "default",
  ACTIVE: "blue",
  COMPLETED: "green",
  ARCHIVED: "default",
};

export default function ReportCreate() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [dateFrom, setDateFrom] = useState<Dayjs>(todayMinus(7));
  const [dateTo, setDateTo] = useState<Dayjs>(todayMinus(0));
  const [campaign, setCampaign] = useState<CampaignStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [keywords, setKeywords] = useState<KeywordOption[]>([]);
  const [selectedKeywordIds, setSelectedKeywordIds] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    authFetch("/api/sources").then((res) => (res.ok ? res.json() : { sources: [] })).then((data) => setSources(data.sources ?? []));
    authFetch("/api/keywords").then((res) => (res.ok ? res.json() : { keywords: [] })).then((data) => setKeywords(data.keywords ?? []));
  }, []);

  function toggleSource(sourceId: string) {
    setSelectedSourceIds((prev) => (prev.includes(sourceId) ? prev.filter((id) => id !== sourceId) : [...prev, sourceId]));
  }

  function applyPreset(days: number) {
    setDateFrom(todayMinus(days));
    setDateTo(todayMinus(0));
  }

  const parsedDayCount = dateTo.diff(dateFrom, "day");
  const dayCount = Number.isFinite(parsedDayCount) ? Math.max(1, parsedDayCount) : 1;

  function updateCampaignStatus(data: CampaignStatus) {
    setCampaign(data);
    if (data.status !== "ACTIVE") {
      sessionStorage.removeItem(CAMPAIGN_ID_STORAGE_KEY);
    }
  }

  useEffect(() => {
    const savedId = sessionStorage.getItem(CAMPAIGN_ID_STORAGE_KEY);
    if (!savedId) return;
    authFetch(`/api/campaigns/${savedId}`).then((res) => {
      if (!res.ok) {
        sessionStorage.removeItem(CAMPAIGN_ID_STORAGE_KEY);
        return;
      }
      res.json().then(updateCampaignStatus);
    });
  }, []);

  useEffect(() => {
    if (!campaign || campaign.status !== "ACTIVE") return;
    let cancelled = false;
    const interval = setInterval(async () => {
      const res = await authFetch(`/api/campaigns/${campaign.campaign_id}`);
      if (cancelled || !res.ok) return;
      updateCampaignStatus(await res.json());
    }, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [campaign?.campaign_id, campaign?.status]);

  // Tạo Campaign mode=ONE_SHOT rồi activate ngay — thay thế POST /api/reports/create cũ
  // (Phase 7). Chặn double-click bằng `submitting`, lưu campaign_id vào sessionStorage
  // để effect khôi phục sau F5 tìm lại được (giữ đúng pattern job cũ).
  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const createRes = await authFetch("/api/campaigns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: `Báo cáo nhanh ${dayjs().format("DD/MM/YYYY HH:mm")}`,
          mode: "ONE_SHOT",
          owner_id: user.user_id,
          start_date: dateFrom.format("YYYY-MM-DD"),
          end_date: dateTo.format("YYYY-MM-DD"),
          source_ids: selectedSourceIds,
          keyword_ids: selectedKeywordIds,
        }),
      });
      if (!createRes.ok) {
        const body = await createRes.json().catch(() => ({}));
        setError(body.detail || "Tạo chiến dịch thất bại");
        return;
      }
      const created = await createRes.json();

      const activateRes = await authFetch(`/api/campaigns/${created.campaign_id}/activate`, { method: "POST" });
      if (!activateRes.ok) {
        const body = await activateRes.json().catch(() => ({}));
        setError(body.detail || "Kích hoạt thất bại");
        return;
      }
      const activated = await activateRes.json();
      sessionStorage.setItem(CAMPAIGN_ID_STORAGE_KEY, activated.campaign_id);
      updateCampaignStatus(activated);
    } finally {
      setSubmitting(false);
    }
  }

  const campaignActive = campaign?.status === "ACTIVE";
  const disabled =
    !dateFrom ||
    !dateTo ||
    dateFrom.isAfter(dateTo) ||
    selectedSourceIds.length === 0 ||
    selectedKeywordIds.length === 0 ||
    campaignActive ||
    submitting;

  return (
    <div>
      <PageHeader
        title="Tạo báo cáo nhanh"
        breadcrumbs={[{ title: "Tổng quan", href: "/" }, { title: "Báo cáo", href: "/reports" }, { title: "Tạo mới" }]}
      />

      <Card style={{ borderRadius: 12 }}>
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <SourceSidebar sources={sources} selectedIds={selectedSourceIds} onToggle={toggleSource} />
            <div>
              <Space style={{ marginBottom: 8 }}>
                {DATE_PRESETS.map((preset) => (
                  <Button key={preset.days} size="small" onClick={() => applyPreset(preset.days)}>
                    {preset.label}
                  </Button>
                ))}
              </Space>
              <Space style={{ display: "flex", marginBottom: 12 }}>
                <div>
                  <Typography.Text>Từ ngày</Typography.Text>
                  <DatePicker value={dateFrom} onChange={(v) => v && setDateFrom(v)} style={{ display: "block" }} />
                </div>
                <div>
                  <Typography.Text>Đến ngày</Typography.Text>
                  <DatePicker value={dateTo} onChange={(v) => v && setDateTo(v)} style={{ display: "block" }} />
                </div>
              </Space>
              <Typography.Text>Từ khóa (bắt buộc ≥1)</Typography.Text>
              <Select
                mode="multiple"
                style={{ width: "100%", marginBottom: 12 }}
                placeholder="Chọn từ khóa cần theo dõi"
                value={selectedKeywordIds}
                onChange={setSelectedKeywordIds}
                options={keywords.map((k) => ({ value: k.keyword_id, label: k.keyword }))}
              />
              <SummaryCard sourceCount={selectedSourceIds.length} dayCount={dayCount} />
            </div>
          </div>

          <Space>
            <PermissionGuard permission="report.create">
              <Button type="primary" disabled={disabled} loading={submitting} onClick={handleSubmit}>
                Tạo báo cáo
              </Button>
            </PermissionGuard>
            <Button onClick={() => navigate("/reports")}>Hủy</Button>
          </Space>

          {error && <Alert type="error" message={error} showIcon />}

          {campaign && (
            <div>
              <Space align="center">
                <Tag color={statusColor[campaign.status]}>{campaign.status}</Tag>
                <Typography.Text>
                  {campaign.status === "ACTIVE" && "Đang crawl toàn bộ nguồn đã chọn..."}
                  {campaign.status === "COMPLETED" && "Crawl xong — vào trang chiến dịch để tạo báo cáo."}
                </Typography.Text>
              </Space>
              {campaign.status === "COMPLETED" && (
                <div style={{ marginTop: 8 }}>
                  <Button type="link" onClick={() => navigate(`/campaigns/${campaign.campaign_id}`)}>
                    Đến trang chiến dịch để tạo báo cáo →
                  </Button>
                </div>
              )}
            </div>
          )}
        </Space>
      </Card>
    </div>
  );
}
```

**Lưu ý quan trọng:** trang này KHÔNG còn tự sinh báo cáo — sau khi Campaign `COMPLETED`, người dùng phải sang `/campaigns/{id}` để bấm "Tạo báo cáo" (đúng thiết kế Task 9/18 — tách rời crawl xong khỏi sinh báo cáo). Đây là thay đổi UX có chủ đích so với hành vi cũ, đã note rõ trong `Typography.Text` ở trên.

- [ ] **Step 2: Kiểm tra thủ công golden path**

Vào `/reports/create`, chọn ≥1 nguồn + ≥1 từ khóa + khoảng ngày, bấm "Tạo báo cáo", xác nhận chuyển sang trạng thái ACTIVE rồi tự COMPLETED sau khi crawl xong, bấm link sang trang Campaign để tạo báo cáo thật.

- [ ] **Step 3: `npm run build`**

Run: `cd frontend && npm run build`
Expected: build thành công.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Reports/ReportCreate.tsx
git commit -m "refactor: ReportCreate tạo Campaign mode=ONE_SHOT thay vì POST /api/reports/create (Phase 7)"
```

---

### Task 20: FE `Reports/index.tsx` — danh sách lịch sử báo cáo theo Campaign

**Files:**
- Modify: `frontend/src/pages/Reports/index.tsx`
- Modify: `backend/routers/campaigns.py` (thêm 1 endpoint tổng hợp toàn hệ thống, không giới hạn theo 1 campaign_id)

**Interfaces:**
- Consumes: `GET /api/reports-history` (mới, top-level — khác với `GET /api/campaigns/{id}/reports` đã có ở Task 8, vì trang `/reports` cần xem TOÀN BỘ báo cáo mọi Campaign, không phải của 1 Campaign cụ thể).

- [ ] **Step 1: Viết test fail trước cho endpoint mới**

```python
# backend/tests/test_campaigns_router.py — thêm cuối file (endpoint đặt trong campaigns.py nhưng path riêng /api/reports-history)
def test_list_all_reports_history_includes_campaign_name(app_client, admin_user, db_session):
    campaign = Campaign(name="Chiến dịch ABC", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id)
    db_session.add(campaign)
    db_session.flush()
    db_session.add(ReportHistory(campaign_id=campaign.campaign_id, file_path="a.docx", format="docx", status="completed"))
    db_session.commit()

    response = app_client.get("/api/reports-history")

    assert response.status_code == 200
    rows = response.json()["history"]
    assert rows[0]["campaign_name"] == "Chiến dịch ABC"
    assert rows[0]["format"] == "docx"
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_campaigns_router.py -k list_all_reports_history -v`
Expected: FAIL — 404.

- [ ] **Step 3: Thêm router mới `backend/routers/report_history.py`** (endpoint không nằm dưới `/api/campaigns/{id}`, nên tách router riêng thay vì nhét vào `campaigns.py`)

```python
# backend/routers/report_history.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.auth.dependencies import require_permission
from backend.db import get_db
from backend.models import Campaign, ReportHistory, User

router = APIRouter(prefix="/api/reports-history", tags=["reports-history"])


@router.get("")
def list_all_reports_history(db: Session = Depends(get_db), _user: User = Depends(require_permission("report", "view"))):
    rows = (
        db.query(ReportHistory, Campaign)
        .join(Campaign, Campaign.campaign_id == ReportHistory.campaign_id)
        .order_by(ReportHistory.created_at.desc())
        .all()
    )
    return {
        "history": [
            {
                "report_id": str(report.report_id),
                "campaign_id": str(campaign.campaign_id),
                "campaign_name": campaign.name,
                "format": report.format,
                "status": report.status,
                "created_at": report.created_at,
            }
            for report, campaign in rows
        ]
    }
```

Đăng ký router trong `backend/main.py`:

```python
from backend.routers import (
    audit_logs,
    auth,
    campaigns,
    contents,
    keywords,
    report_history,
    roles,
    sources,
    system_settings,
    users,
)
```

Thêm `app.include_router(report_history.router)`.

- [ ] **Step 4: Chạy lại test**

Run: `docker compose exec backend pytest backend/tests/test_campaigns_router.py -v`
Expected: PASS toàn bộ.

- [ ] **Step 5: Viết lại `frontend/src/pages/Reports/index.tsx`**

```tsx
// frontend/src/pages/Reports/index.tsx
import { useEffect, useState } from "react";
import { Alert, Button, Card, Table, Tag } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import { authFetch } from "@/lib/api";

type HistoryEntry = {
  report_id: string;
  campaign_id: string;
  campaign_name: string;
  format: string;
  status: string;
  created_at: string;
};

export default function ReportsPage() {
  const navigate = useNavigate();
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    authFetch("/api/reports-history")
      .then((res) => {
        if (!res.ok) throw new Error();
        return res.json();
      })
      .then((data) => setHistory(data.history ?? []))
      .catch(() => setError("Không tải được lịch sử báo cáo"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <PageHeader
        title="Báo cáo"
        subtitle="Xem và tải báo cáo giám sát"
        breadcrumbs={[{ title: "Tổng quan", href: "/" }, { title: "Báo cáo" }]}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/reports/create")}>
            Tạo báo cáo nhanh
          </Button>
        }
      />

      <Card style={{ borderRadius: 12 }}>
        {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
        <Table<HistoryEntry>
          loading={loading}
          rowKey="report_id"
          dataSource={history}
          locale={{ emptyText: "Chưa có báo cáo nào." }}
          columns={[
            { title: "Ngày tạo", dataIndex: "created_at", render: (v: string) => new Date(v).toLocaleString("vi-VN") },
            {
              title: "Chiến dịch",
              render: (_v, e) => (
                <a onClick={() => navigate(`/campaigns/${e.campaign_id}`)}>{e.campaign_name}</a>
              ),
            },
            { title: "Định dạng", dataIndex: "format", render: (v: string) => <Tag>{v.toUpperCase()}</Tag> },
            {
              title: "Trạng thái",
              dataIndex: "status",
              render: (s: string) => <Tag color={s === "completed" ? "green" : s === "failed" ? "red" : "blue"}>{s}</Tag>,
            },
          ]}
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  );
}
```

(Không có nút "Tải về" trực tiếp ở trang này nữa — bấm vào tên Chiến dịch để sang `CampaignDetail` tải file, tránh trùng lặp logic download đã có ở Task 18.)

- [ ] **Step 6: Kiểm tra thủ công `/reports`**

Xác nhận danh sách hiện đúng báo cáo đã tạo ở Task 18/19, click tên Campaign điều hướng đúng.

- [ ] **Step 7: `npm run build`**

Run: `cd frontend && npm run build`
Expected: build thành công.

- [ ] **Step 8: Commit**

```bash
git add backend/routers/report_history.py backend/main.py backend/tests/test_campaigns_router.py frontend/src/pages/Reports/index.tsx
git commit -m "feat: trang /reports liệt kê lịch sử báo cáo theo Campaign qua GET /api/reports-history (Phase 7)"
```

---

## Sau khi hoàn thành toàn bộ Task

- [ ] Chạy full test suite lần cuối: `docker compose exec backend pytest backend/tests/ -v` — PASS 100%.
- [ ] `cd frontend && npm run build` — PASS, không lỗi TypeScript.
- [ ] Smoke test thật qua Docker (rule 13, bắt buộc trước khi coi Phase 7 hoàn thành): tạo 1 Campaign `ONE_SHOT` với ≥1 nguồn thật (VD VTV News) + ≥1 từ khóa thật trên UI thật → activate → xác nhận crawl chạy ngay (không đợi 30 phút) → COMPLETED → vào `CampaignDetail` bấm "Tạo báo cáo" cả 4 định dạng lần lượt (docx/pdf/xlsx/csv) → tải về, mở thử từng file xác nhận đọc được và số liệu khớp nhau.
- [ ] Cập nhật `CLAUDE.md` mục "Trạng thái dự án" — thêm entry Phase 7 hoàn thành, theo đúng format các Phase trước (tóm tắt đã code gì, 2 quyết định quan trọng: hard-delete dữ liệu jobs cũ, ONE_SHOT không tự động AI/report).
- [ ] Cập nhật rule 05/08/16 — bỏ đánh dấu `[SẼ XÓA]`/`[CHƯA CODE]` cho các mục đã xong ở Phase 7 (`jobs`/`/api/reports/*` xóa hẳn, `report_history.campaign_id`, PDF/Excel/CSV).
