# Slice 4 — Report đầy đủ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mở rộng `aggregate_basic()` để tính đủ số liệu GROUP BY nguồn/chủ đề/tháng/sentiment/emotion, dựng lại `generate_docx()` theo đúng cấu trúc bảng của `sample_report_form.docx` (chỉ những bảng có dữ liệu thật), và chặn giá trị `emotion` ngoài enum chuẩn lọt vào báo cáo.

**Architecture:** Toàn bộ tính toán gộp số liệu vẫn nằm ở tầng Python (`Counter` trên kết quả 1 câu query JOIN 3 bảng có sẵn — không thêm câu query SQL GROUP BY riêng, giữ đúng phong cách hiện có của `aggregator.py`). `docx_generator.py` chỉ thêm heading/bảng mới bằng đúng pattern `doc.add_table()` đã dùng — không đổi engine sinh file, không thêm biểu đồ. Validate `emotion` được chặn sớm nhất có thể — ngay sau khi parse JSON ở `ollama_client.py` — để `aggregator`/`docx_generator` không bao giờ phải tự xử lý giá trị rác.

**Tech Stack:** Python, SQLAlchemy, python-docx, pytest, Postgres (test qua `docker compose exec backend pytest`).

---

## Bối cảnh & quyết định đã chốt (đọc trước khi code)

**Đã hỏi lại user 2 câu trước khi viết plan này (không tự đoán):**

1. **Phạm vi bảng:** `sample_report_form.docx` có nhiều bảng cần dữ liệu hệ thống không thu thập (hashtag, engagement/tương tác, nền tảng mạng xã hội, chính sách cụ thể — MVP chỉ crawl website, không có social media). User chọn: **chỉ làm bảng khớp dữ liệu thật, bỏ hẳn các bảng thiếu dữ liệu** (không để trống/N-A).
2. **Biểu đồ:** Form gốc có nhiều Bar/Pie/Timeline chart nhúng trong docx. Tech stack chưa có thư viện vẽ chart nào. User chọn: **không vẽ chart, chỉ bảng số liệu dạng text/table** — không thêm dependency mới (matplotlib...).

**Bảng nào được làm, bảng nào bị bỏ (đối chiếu `sample_report_form.docx`):**

| Bảng gốc | Xử lý | Lý do |
|---|---|---|
| Bảng 3.1 (theo cơ quan) | **Làm** — group theo `sources.group_name` | `group_name` khớp khái niệm "cơ quan" (1 cơ quan có thể có nhiều kênh, VD BoCongAn + CAND cùng `group_name="Bộ Công an"`) — đúng cách sidebar FE đã group (xem `09-frontend-ui.md`). Không dùng `source.name` (đó là "kênh", không phải "cơ quan") |
| Bảng 3.2 + 3.7 (theo chủ đề / Top chủ đề) | **Làm 1 lần, dùng chung** | Cùng 1 dữ liệu (đếm theo `topics[]`, chỉ 8 nhóm chuẩn) — "Top 20" và "theo chủ đề" ra cùng 1 bảng vì chỉ có 8 giá trị có thể, làm 2 bảng giống hệt nhau sẽ dư thừa |
| Bảng 3.8 (Top từ khóa) | **Làm** — top 20 keyword theo tần suất | Có `article_analysis.keywords[]` |
| Hình 3.2 (diễn biến theo tháng) | **Làm dạng bảng** (không phải hình/chart) | Đúng quyết định "không vẽ chart" — số liệu vẫn thể hiện được qua bảng đếm theo `YYYY-MM` |
| Bảng 3.13 (Sentiment Analysis) | **Làm** — đã có sẵn từ Slice 1, chỉ đổi heading cho khớp số bảng | |
| Bảng 3.15 (Emotion Analysis) | **Làm** — đã có sẵn, thêm nhãn `"Không xác định"` cho `emotion=NULL` | Xem mục validate emotion bên dưới |
| Bảng 3.17 (Thống kê tổng hợp) | **Làm** — tự định nghĩa 3 chỉ số: tổng bài, tổng cơ quan, số bài cần review | Form gốc không liệt kê cột cụ thể cho bảng này — chọn 3 chỉ số suy ra trực tiếp từ dữ liệu đã có, không suy diễn |
| Bảng 3.3, 3.4, 3.5, 3.6, 3.9, 3.10, 3.11, 3.12, 3.14, 3.16 (bản "tương tác cao") | **Bỏ** | Cần chính sách cụ thể / mô tả công nghệ tĩnh / định dạng media / nền tảng social / hashtag / engagement — không có trường dữ liệu tương ứng trong DB (đúng lựa chọn của user ở câu hỏi 1) |
| Danh sách bài viết (record-level, đã có Slice 1) | **Giữ, chuyển xuống cuối tài liệu** | Sample form nhắc "Lưu toàn bộ dữ liệu ở mức bản ghi" ở cuối cùng — khớp thứ tự tổng quan → chi tiết của form gốc |

**Validate `emotion` (bug đã biết từ Slice 3 — 1 bài AI trả `"Neutral"`, ngoài 6 nhóm `Trust/Fear/Anger/Surprise/Sadness/Happy`):**
- Validate ngay sau khi parse JSON trong `analyze_article()` (`backend/ai/ollama_client.py`), **không retry gọi lại AI** — khác với case JSON không hợp lệ (vốn đã có retry 1 lần). Lý do: đây là JSON hợp lệ, chỉ 1 field có giá trị ngoài enum — retry cả request sẽ tốn thêm 1 lượt gọi AI chậm (CPU-only, có lúc >120s) chỉ để sửa 1 field, trong khi `topics`/`sentiment`/`confidence`/`summary` vẫn dùng được ngay, không nên vứt bỏ theo kiểu "invalid JSON → skip cả bài"
- Nếu `emotion` không thuộc `EMOTION_GROUPS` → set `emotion = None`, force `needs_review = True` (dù `confidence` cao), log `logger.warning` kèm giá trị gốc AI trả về (để có dấu vết theo dõi tần suất, xem "Vấn đề cần làm rõ" ở CLAUDE.md) — không raise, không làm fail bài
- `article_analysis.emotion` (DB) đã `nullable` sẵn (không có `NOT NULL`) — không cần migration
- Ở tầng aggregate, `emotion=NULL` được gộp vào nhãn hiển thị `"Không xác định"` thay vì bị bỏ sót khỏi Bảng 3.15 (đúng nguyên tắc "mọi kết luận phải có nguồn dữ liệu thực tế" — không được âm thầm biến mất 1 bài khỏi thống kê)

**Dọn dẹp không liên quan Slice 4 nhưng gộp vào plan này theo yêu cầu user:**
- Hằng số `ESTIMATED_SECONDS_PER_ARTICLE` đã bị xoá khỏi `frontend/components/SummaryCard.tsx` từ commit `87d23f6` (2026-07-01, "Modified SummaryCard component to remove estimated article display for clarity") nhưng CLAUDE.md chưa được cập nhật theo — vẫn còn 1 bullet nhắc tới hằng số này ở mục "Vấn đề cần làm rõ". Xoá bullet đó (Task 1)
- **Không đụng tới** `docs/superpowers/plans/2026-06-29-slice2-multi-source.md` dù file này cũng nhắc tên hằng số — đây là plan lịch sử đã thực thi xong (giống git history), sửa lại sẽ giống viết lại lịch sử. Nếu user muốn dọn cả file này, cần xác nhận thêm

**Điều tra lỗi "File format is not supported" khi mở file `.docx` trong `storage/` — không tìm thấy bug trong code:**
Đã kiểm tra toàn bộ file `.docx` thật trong `storage/` bằng 3 lớp độc lập: `file` (nhận diện đúng "Microsoft Word 2007+"), `zipfile.testzip()` (toàn vẹn ZIP, không lỗi), và mở bằng `python-docx` (`Document(...)` load thành công, đọc được paragraphs/tables). Kiểm tra sâu hơn: toàn bộ XML part bên trong (`document.xml`, `[Content_Types].xml`, các `.rels`...) đều well-formed, `[Content_Types].xml` khai đủ Content-Type cho mọi part, không thiếu quan hệ nào. Kết luận: **file `.docx` do `generate_docx()` sinh ra hợp lệ 100%, không có lỗi code.** Lỗi trong ảnh (icon "không hỗ trợ" kiểu GTK/GNOME) nhiều khả năng đến từ việc double-click mở file bằng ứng dụng không hỗ trợ `.docx` trên máy bạn (VD trình xem ảnh mặc định của Ubuntu/GNOME thay vì LibreOffice Writer) — không phải lỗi sinh file. Đề xuất: thử "Open With → LibreOffice Writer" (chuột phải vào file) thay vì double-click mặc định; nếu vẫn lỗi, báo lại kèm tên ứng dụng đã dùng để điều tra tiếp — **không đưa fix vào plan này vì chưa xác nhận được đây là bug**.

---

## File Structure

- Modify: `CLAUDE.md` — xoá bullet `ESTIMATED_SECONDS_PER_ARTICLE`, tick checklist Slice 4, cập nhật "Trạng thái hiện tại"/"Đã hoàn thành"/"Bước tiếp theo" sau khi verify xong
- Modify: `backend/ai/ollama_client.py` — validate `emotion` theo `EMOTION_GROUPS`
- Modify: `backend/ai/prompts/v1.py` — không đổi nội dung, chỉ cần import `EMOTION_GROUPS` đã có sẵn (không cần sửa file này)
- Test: `backend/tests/test_ollama_client.py` — thêm test validate emotion
- Modify: `backend/report/aggregator.py` — thêm `source_counts`, `topic_counts`, `keyword_counts`, `monthly_counts`, `summary_stats`, gộp nhãn `emotion=NULL`
- Test: `backend/tests/test_aggregator.py` — thêm test cho từng field mới
- Modify: `backend/report/docx_generator.py` — thêm bảng mới, đổi heading khớp số bảng sample form, chuyển "Danh sách bài viết" xuống cuối
- Test: `backend/tests/test_docx_generator.py` — cập nhật fixture `AGGREGATES`, thêm test cho bảng mới + thứ tự + regression `export_json`

---

## Task 1: Dọn `ESTIMATED_SECONDS_PER_ARTICLE` khỏi CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Xoá bullet lỗi thời**

Tìm và xoá dòng sau trong mục "Vấn đề cần làm rõ (chưa chốt)":

```markdown
- **Hằng số `ESTIMATED_SECONDS_PER_ARTICLE = 90` ở `SummaryCard.tsx`** là ước lượng thô, chưa có benchmark thật trên nhiều nguồn — cần điều chỉnh lại khi Slice 3 có dữ liệu benchmark thật trên ≥50 bài
```

Xoá luôn dòng số 3 tương ứng trong mục "Bước tiếp theo":

```markdown
3. Theo dõi giá trị `emotion` ngoài enum (`"Neutral"`, phát hiện Slice 3) — nếu lặp lại, cân nhắc validate hoặc tinh chỉnh prompt
```

(dòng này sẽ được thay bằng ghi chú "đã validate" ở Task 6 — xoá tạm ở bước này để tránh trùng lặp khi viết lại "Bước tiếp theo" cuối plan)

- [ ] **Step 2: Verify không còn tham chiếu nào trong file đang sống**

Run: `grep -n "ESTIMATED_SECONDS_PER_ARTICLE" CLAUDE.md`
Expected: không có output (0 dòng khớp)

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: xoá tham chiếu ESTIMATED_SECONDS_PER_ARTICLE đã lỗi thời khỏi CLAUDE.md"
```

---

## Task 2: Validate `emotion` trả về từ AI đúng enum chuẩn

**Files:**
- Modify: `backend/ai/ollama_client.py`
- Test: `backend/tests/test_ollama_client.py`

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `backend/tests/test_ollama_client.py`:

```python
def test_sets_emotion_none_and_needs_review_when_emotion_outside_enum():
    invalid_emotion_json = VALID_JSON.replace('"emotion": "Fear"', '"emotion": "Neutral"')
    client = _client_with_responses([invalid_emotion_json])

    result = asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))

    assert result["emotion"] is None
    assert result["needs_review"] is True
    # Các field khác vẫn giữ nguyên — không vứt bỏ cả bài chỉ vì 1 field sai enum
    assert result["sentiment"] == "negative"
    assert result["topics"] == ["Tin giả và thông tin sai lệch"]


def test_keeps_needs_review_true_when_both_low_confidence_and_invalid_emotion():
    bad = VALID_JSON.replace('"emotion": "Fear"', '"emotion": "Neutral"').replace(
        '"confidence": 0.85', '"confidence": 0.3'
    )
    client = _client_with_responses([bad])

    result = asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))

    assert result["emotion"] is None
    assert result["needs_review"] is True


def test_does_not_retry_ai_call_when_only_emotion_is_invalid():
    # Chỉ 1 lần gọi trong danh sách response — nếu code lỡ retry sẽ IndexError
    # (MockTransport handler dùng min(i, len-1) nên thực ra không crash, thay vào đó
    # đếm số lần gọi thật để khẳng định không có lệnh gọi thứ 2)
    call_count = {"i": 0}

    async def handler(request):
        call_count["i"] += 1
        return httpx.Response(200, json={"response": VALID_JSON.replace('"emotion": "Fear"', '"emotion": "Neutral"')})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))

    assert call_count["i"] == 1
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `docker compose exec backend pytest backend/tests/test_ollama_client.py -k "emotion_outside_enum or both_low_confidence_and_invalid or does_not_retry" -v`
Expected: FAIL — `assert result["emotion"] is None` thất bại vì `result["emotion"] == "Neutral"` (chưa validate)

- [ ] **Step 3: Implement validate**

Sửa `backend/ai/ollama_client.py`:

```python
import asyncio
import json
import logging
import os
import re
import time

import httpx

from backend.ai.prompts.v1 import CLASSIFICATION_PROMPT, EMOTION_GROUPS, PROMPT_VERSION, TOPIC_GROUPS

logger = logging.getLogger(__name__)

JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
```

(chỉ thêm `import logging`, `logger = logging.getLogger(__name__)`, và import thêm `EMOTION_GROUPS` — các dòng khác giữ nguyên)

Sửa đoạn cuối `analyze_article()` — tìm dòng:

```python
        result["needs_review"] = result.get("confidence", 1.0) < confidence_threshold
        result["prompt_version"] = PROMPT_VERSION
```

Thay bằng:

```python
        result["needs_review"] = result.get("confidence", 1.0) < confidence_threshold
        if result.get("emotion") not in EMOTION_GROUPS:
            logger.warning(
                "AI trả về emotion ngoài enum chuẩn %s: %r (tiêu đề bài: %r) — set emotion=None, needs_review=True",
                EMOTION_GROUPS,
                result.get("emotion"),
                title,
            )
            result["emotion"] = None
            result["needs_review"] = True
        result["prompt_version"] = PROMPT_VERSION
```

- [ ] **Step 4: Chạy lại test để xác nhận pass**

Run: `docker compose exec backend pytest backend/tests/test_ollama_client.py -v`
Expected: toàn bộ PASS (test cũ lẫn test mới — `VALID_JSON` dùng `emotion="Fear"` hợp lệ nên không bị ảnh hưởng)

- [ ] **Step 5: Commit**

```bash
git add backend/ai/ollama_client.py backend/tests/test_ollama_client.py
git commit -m "fix: validate AI emotion đúng enum chuẩn, tránh giá trị rác (VD Neutral) lọt vào article_analysis"
```

---

## Task 3: Mở rộng `aggregate_basic()` — GROUP BY nguồn/chủ đề/tháng + tổng hợp

**Files:**
- Modify: `backend/report/aggregator.py`
- Test: `backend/tests/test_aggregator.py`

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `backend/tests/test_aggregator.py` (giữ nguyên import ở đầu file, thêm `from datetime import date, datetime` nếu chưa có `datetime`):

```python
def test_source_counts_grouped_by_group_name_not_individual_source(db_session):
    source1 = Source(name="Báo CAND", domain=f"cand-{uuid.uuid4()}.example", group_name="Bộ Công an")
    source2 = Source(name="Cổng BCA", domain=f"bca-{uuid.uuid4()}.example", group_name="Bộ Công an")
    db_session.add_all([source1, source2])
    db_session.flush()

    job = Job(source_ids=[source1.source_id, source2.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    a1 = Article(job_id=job.job_id, source_id=source1.source_id, url="https://cand.vn/a1", url_hash=f"h-{uuid.uuid4()}", title="Bài 1")
    a2 = Article(job_id=job.job_id, source_id=source2.source_id, url="https://bca.gov.vn/a1", url_hash=f"h-{uuid.uuid4()}", title="Bài 2")
    db_session.add_all([a1, a2])
    db_session.flush()

    db_session.add_all(
        [
            ArticleAnalysis(article_id=a1.article_id, job_id=job.job_id, topics=["A"], keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b"),
            ArticleAnalysis(article_id=a2.article_id, job_id=job.job_id, topics=["A"], keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b"),
        ]
    )
    db_session.flush()

    result = aggregate_basic(db_session, job.job_id)

    assert result["source_counts"] == {"Bộ Công an": 2}


def test_topic_counts_counts_each_topic_across_multi_topic_articles(db_session):
    source = Source(name="Test", domain=f"t-{uuid.uuid4()}.example", group_name="Test")
    db_session.add(source)
    db_session.flush()
    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    a1 = Article(job_id=job.job_id, source_id=source.source_id, url="https://x/a1", url_hash=f"h-{uuid.uuid4()}", title="Bài 1")
    a2 = Article(job_id=job.job_id, source_id=source.source_id, url="https://x/a2", url_hash=f"h-{uuid.uuid4()}", title="Bài 2")
    db_session.add_all([a1, a2])
    db_session.flush()

    db_session.add_all(
        [
            ArticleAnalysis(
                article_id=a1.article_id, job_id=job.job_id,
                topics=["Tin giả và thông tin sai lệch", "Cảnh báo lừa đảo, giả mạo trên không gian mạng"],
                keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b",
            ),
            ArticleAnalysis(
                article_id=a2.article_id, job_id=job.job_id, topics=["Tin giả và thông tin sai lệch"],
                keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b",
            ),
        ]
    )
    db_session.flush()

    result = aggregate_basic(db_session, job.job_id)

    assert result["topic_counts"] == {
        "Tin giả và thông tin sai lệch": 2,
        "Cảnh báo lừa đảo, giả mạo trên không gian mạng": 1,
    }


def test_keyword_counts_caps_at_top_20(db_session):
    source = Source(name="Test", domain=f"t-{uuid.uuid4()}.example", group_name="Test")
    db_session.add(source)
    db_session.flush()
    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    for i in range(22):
        article = Article(
            job_id=job.job_id, source_id=source.source_id, url=f"https://x/a{i}",
            url_hash=f"h-{uuid.uuid4()}", title=f"Bài {i}",
        )
        db_session.add(article)
        db_session.flush()
        db_session.add(
            ArticleAnalysis(
                article_id=article.article_id, job_id=job.job_id, topics=["A"], keywords=[f"keyword-{i}"],
                sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b",
            )
        )
    db_session.flush()

    result = aggregate_basic(db_session, job.job_id)

    assert len(result["keyword_counts"]) == 20


def test_monthly_counts_groups_by_year_month_and_ignores_missing_published_at(db_session):
    source = Source(name="Test", domain=f"t-{uuid.uuid4()}.example", group_name="Test")
    db_session.add(source)
    db_session.flush()
    job = Job(source_ids=[source.source_id], date_from=date(2026, 5, 1), date_to=date(2026, 7, 1))
    db_session.add(job)
    db_session.flush()

    a1 = Article(job_id=job.job_id, source_id=source.source_id, url="https://x/a1", url_hash=f"h-{uuid.uuid4()}", title="Bài 1", published_at=datetime(2026, 6, 5))
    a2 = Article(job_id=job.job_id, source_id=source.source_id, url="https://x/a2", url_hash=f"h-{uuid.uuid4()}", title="Bài 2", published_at=datetime(2026, 6, 20))
    a3 = Article(job_id=job.job_id, source_id=source.source_id, url="https://x/a3", url_hash=f"h-{uuid.uuid4()}", title="Bài không rõ ngày đăng")
    db_session.add_all([a1, a2, a3])
    db_session.flush()

    db_session.add_all(
        [
            ArticleAnalysis(article_id=a1.article_id, job_id=job.job_id, topics=["A"], keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b"),
            ArticleAnalysis(article_id=a2.article_id, job_id=job.job_id, topics=["A"], keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b"),
            ArticleAnalysis(article_id=a3.article_id, job_id=job.job_id, topics=["A"], keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b"),
        ]
    )
    db_session.flush()

    result = aggregate_basic(db_session, job.job_id)

    assert result["monthly_counts"] == {"2026-06": 2}
    assert sum(result["monthly_counts"].values()) == 2  # bài a3 (published_at=None) bị bỏ qua, không phải 3


def test_emotion_counts_labels_null_emotion_as_khong_xac_dinh(db_session):
    source = Source(name="Test", domain=f"t-{uuid.uuid4()}.example", group_name="Test")
    db_session.add(source)
    db_session.flush()
    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article = Article(job_id=job.job_id, source_id=source.source_id, url="https://x/a1", url_hash=f"h-{uuid.uuid4()}", title="Bài 1")
    db_session.add(article)
    db_session.flush()

    db_session.add(
        ArticleAnalysis(
            article_id=article.article_id, job_id=job.job_id, topics=["A"], keywords=[],
            sentiment="negative", emotion=None, needs_review=True, confidence=0.9, prompt_version=1, ai_model="qwen3:8b",
        )
    )
    db_session.flush()

    result = aggregate_basic(db_session, job.job_id)

    assert result["emotion_counts"] == {"Không xác định": 1}


def test_summary_stats_counts_total_articles_sources_and_needs_review(db_session):
    source1 = Source(name="A", domain=f"a-{uuid.uuid4()}.example", group_name="Nhóm A")
    source2 = Source(name="B", domain=f"b-{uuid.uuid4()}.example", group_name="Nhóm B")
    db_session.add_all([source1, source2])
    db_session.flush()
    job = Job(source_ids=[source1.source_id, source2.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    a1 = Article(job_id=job.job_id, source_id=source1.source_id, url="https://x/a1", url_hash=f"h-{uuid.uuid4()}", title="Bài 1")
    a2 = Article(job_id=job.job_id, source_id=source2.source_id, url="https://x/a2", url_hash=f"h-{uuid.uuid4()}", title="Bài 2")
    db_session.add_all([a1, a2])
    db_session.flush()

    db_session.add_all(
        [
            ArticleAnalysis(article_id=a1.article_id, job_id=job.job_id, topics=["A"], keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, needs_review=True, prompt_version=1, ai_model="qwen3:8b"),
            ArticleAnalysis(article_id=a2.article_id, job_id=job.job_id, topics=["A"], keywords=[], sentiment="negative", emotion="Fear", confidence=0.95, needs_review=False, prompt_version=1, ai_model="qwen3:8b"),
        ]
    )
    db_session.flush()

    result = aggregate_basic(db_session, job.job_id)

    assert result["summary_stats"] == {
        "Tổng số bài": 2,
        "Tổng số cơ quan": 2,
        "Số bài cần review (needs_review)": 1,
    }
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `docker compose exec backend pytest backend/tests/test_aggregator.py -v`
Expected: 6 test mới FAIL với `KeyError: 'source_counts'` (hoặc tương tự cho từng field chưa tồn tại)

- [ ] **Step 3: Implement**

Thay toàn bộ nội dung `backend/report/aggregator.py`:

```python
from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Article, ArticleAnalysis, Source

TOP_KEYWORDS_LIMIT = 20
UNKNOWN_EMOTION_LABEL = "Không xác định"


def aggregate_basic(db: Session, job_id: UUID) -> dict:
    rows = db.execute(
        select(Article, ArticleAnalysis, Source)
        .join(ArticleAnalysis, ArticleAnalysis.article_id == Article.article_id)
        .join(Source, Source.source_id == Article.source_id)
        .where(Article.job_id == job_id)
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

- [ ] **Step 4: Chạy lại toàn bộ test aggregator**

Run: `docker compose exec backend pytest backend/tests/test_aggregator.py -v`
Expected: toàn bộ PASS (7 test — 1 test cũ + 6 test mới)

- [ ] **Step 5: Commit**

```bash
git add backend/report/aggregator.py backend/tests/test_aggregator.py
git commit -m "feat: mở rộng aggregate_basic() — group theo cơ quan/chủ đề/từ khóa/tháng + thống kê tổng hợp"
```

---

## Task 4: Mở rộng `generate_docx()` — bảng đầy đủ theo `sample_report_form.docx`

**Files:**
- Modify: `backend/report/docx_generator.py`
- Test: `backend/tests/test_docx_generator.py`

- [ ] **Step 1: Cập nhật fixture + viết test thất bại**

Thay `AGGREGATES` ở đầu `backend/tests/test_docx_generator.py`:

```python
AGGREGATES = {
    "articles": [
        {
            "title": "Cảnh báo deepfake mới",
            "url": "https://vtv.vn/bai-1",
            "source": "VTV News",
            "published_at": datetime(2026, 6, 23, 10, 0, 0),
            "sentiment": "negative",
            "emotion": "Fear",
            "topics": ["AI, Deepfake và công nghệ tạo sinh"],
            "confidence": 0.9,
            "needs_review": False,
            "summary": "Tóm tắt bài viết.",
        }
    ],
    "sentiment_counts": {"negative": 1},
    "emotion_counts": {"Fear": 1},
    "source_counts": {"VTV": 1},
    "topic_counts": {"AI, Deepfake và công nghệ tạo sinh": 1},
    "keyword_counts": {"deepfake": 1},
    "monthly_counts": {"2026-06": 1},
    "summary_stats": {"Tổng số bài": 1, "Tổng số cơ quan": 1, "Số bài cần review (needs_review)": 0},
}
```

Thêm test mới vào cuối file:

```python
def test_generate_docx_includes_new_aggregate_tables(tmp_path):
    output_path = tmp_path / "report.docx"

    generate_docx(_fake_job(), AGGREGATES, str(output_path))

    doc = docx.Document(str(output_path))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    table_text = "\n".join(cell.text for table in doc.tables for row in table.rows for cell in row.cells)
    combined = full_text + "\n" + table_text

    assert "Bảng 3.1" in combined
    assert "VTV" in table_text
    assert "AI, Deepfake và công nghệ tạo sinh" in table_text
    assert "deepfake" in table_text
    assert "2026-06" in table_text
    assert "Tổng số bài" in table_text


def test_article_list_appears_after_aggregate_tables(tmp_path):
    output_path = tmp_path / "report.docx"

    generate_docx(_fake_job(), AGGREGATES, str(output_path))

    doc = docx.Document(str(output_path))
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]

    assert headings.index("Bảng 3.1. Số lượng nội dung theo cơ quan") < headings.index("Danh sách bài viết")


def test_export_json_includes_new_aggregate_fields(tmp_path):
    output_path = tmp_path / "report.json"
    job = _fake_job()

    export_json(job, AGGREGATES, str(output_path))

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["source_counts"] == {"VTV": 1}
    assert data["topic_counts"] == {"AI, Deepfake và công nghệ tạo sinh": 1}
    assert data["keyword_counts"] == {"deepfake": 1}
    assert data["monthly_counts"] == {"2026-06": 1}
    assert data["summary_stats"]["Tổng số bài"] == 1
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `docker compose exec backend pytest backend/tests/test_docx_generator.py -v`
Expected: `test_generate_docx_writes_readable_file_with_article_title` và test mới đều FAIL — `generate_docx()` hiện tại không đọc các key mới, sẽ raise `KeyError`

- [ ] **Step 3: Implement**

Thay toàn bộ nội dung `backend/report/docx_generator.py`:

```python
import json

from docx import Document


def generate_docx(job, aggregates: dict, output_path: str) -> None:
    doc = Document()
    doc.add_heading("Báo cáo NGS Monitor", level=1)
    doc.add_paragraph(f"Khoảng thời gian: {job.date_from} – {job.date_to}")

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


def export_json(job, aggregates: dict, output_path: str) -> None:
    data = {
        "job_id": str(job.job_id),
        "date_from": str(job.date_from),
        "date_to": str(job.date_to),
        **aggregates,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
```

- [ ] **Step 4: Chạy lại toàn bộ test docx_generator**

Run: `docker compose exec backend pytest backend/tests/test_docx_generator.py -v`
Expected: toàn bộ PASS (5 test — 2 test cũ + 3 test mới)

- [ ] **Step 5: Chạy toàn bộ test suite backend để chắc chắn không phá vỡ chỗ khác**

Run: `docker compose exec backend pytest backend/tests/ -v`
Expected: toàn bộ PASS (bao gồm `test_report_job.py` — vốn gọi `_generate_report()` end-to-end qua `aggregate_basic()` + `generate_docx()` thật, không mock)

- [ ] **Step 6: Commit**

```bash
git add backend/report/docx_generator.py backend/tests/test_docx_generator.py
git commit -m "feat: dựng lại generate_docx() theo cấu trúc bảng đầy đủ của sample_report_form.docx"
```

---

## Task 5: Verify thật với dữ liệu thật

**Không có file code ở task này — chỉ chạy job thật + đối chiếu tay, đúng tiêu chí Verify của Slice 4 trong CLAUDE.md ("số liệu từng bảng khớp với query DB trực tiếp, so sánh tay ít nhất 2-3 bảng").**

- [ ] **Step 1: Đảm bảo service đang chạy**

```bash
docker compose up -d
docker compose restart celery-worker   # bắt buộc — celery-worker không tự nạp lại code .py đã sửa (xem CLAUDE.md, phát hiện 2026-07-08)
docker compose ps
```

Expected: toàn bộ service `healthy`/`running`

- [ ] **Step 2: Tạo job thật qua API** (VTV — nguồn ổn định nhất, đã verify nhiều lần)

```bash
curl -s -X POST http://localhost:8000/api/reports/create \
  -H "Content-Type: application/json" \
  -d '{"source_ids": ["<VTV_SOURCE_ID>"], "date_from": "2026-06-01", "date_to": "2026-07-08"}'
```

Lấy `VTV_SOURCE_ID` qua `curl http://localhost:8000/api/sources`. Ghi lại `job_id` trả về.

- [ ] **Step 3: Polling tới khi `completed`**

```bash
curl -s http://localhost:8000/api/reports/<job_id>/status
```

Expected: `status: "completed"` sau vài phút, `progress.crawled == progress.analyzed`

- [ ] **Step 4: Tải file docx + json, mở kiểm tra bằng LibreOffice Writer (không double-click mặc định — xem phần điều tra lỗi ở đầu plan)**

```bash
curl -s http://localhost:8000/api/reports/<job_id>/download -o /tmp/verify_slice4.docx
```

Mở `/tmp/verify_slice4.docx` bằng LibreOffice Writer, xác nhận đủ các heading: "Bảng 3.1...", "Bảng 3.2 / 3.7...", "Bảng 3.8...", "...theo tháng...", "Bảng 3.13...", "Bảng 3.15...", "Bảng 3.17...", "Danh sách bài viết" (đúng thứ tự này).

- [ ] **Step 5: Đối chiếu tay ít nhất 2-3 bảng với query DB trực tiếp**

Ví dụ đối chiếu Bảng 3.1 (theo cơ quan):

```bash
docker compose exec db psql -U <user> -d ngs_monitor -c "
SELECT s.group_name, COUNT(*)
FROM articles a
JOIN article_analysis aa ON aa.article_id = a.article_id
JOIN sources s ON s.source_id = a.source_id
WHERE a.job_id = '<job_id>'
GROUP BY s.group_name;
"
```

So số liệu trả về với bảng "Bảng 3.1" trong file docx — phải khớp chính xác.

Lặp lại tương tự cho Bảng 3.13 (`GROUP BY aa.sentiment`) và Bảng 3.15 (`GROUP BY COALESCE(aa.emotion, 'Không xác định')`).

- [ ] **Step 6: Ghi lại kết quả verify** (không commit code ở bước này, chỉ note để đưa vào Task 6)

Ghi lại: `job_id` đã dùng, số bài crawl/phân tích, 2-3 bảng đã đối chiếu tay + kết quả khớp/không khớp, có gặp `emotion` ngoài enum trong lần chạy này không (nếu có, xác nhận `needs_review=true` + `emotion=NULL` đúng như Task 2).

---

## Task 6: Cập nhật CLAUDE.md sau khi verify xong

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Tick checklist Slice 4**

Trong mục `### Slice 4 — Report đầy đủ`, đổi cả 3 dòng từ `- [ ]` sang `- [x]`.

- [ ] **Step 2: Thêm entry vào "Đã hoàn thành"**

Thêm 1 bullet mới (theo đúng văn phong các bullet trước đó — ngày tháng, kết quả verify thật cụ thể từ Task 5, không viết chung chung):

```markdown
- **Slice 4 (Report đầy đủ) — hoàn thành (<ngày thật thực hiện>):** mở rộng `aggregate_basic()` thêm `source_counts`/`topic_counts`/`keyword_counts`/`monthly_counts`/`summary_stats`, dựng lại `generate_docx()` theo đúng cấu trúc bảng của `sample_report_form.docx` (chỉ bảng khớp dữ liệu thật — bỏ hẳn bảng cần hashtag/engagement/nền tảng social/chính sách cụ thể, không có trong DB; không vẽ chart — chỉ bảng số liệu, xem lý do ở plan). Đồng thời sửa bug đã biết từ Slice 3: validate `emotion` AI trả về đúng 6 nhóm enum chuẩn ngay ở `ollama_client.py`, giá trị ngoài enum (VD `"Neutral"`) → `emotion=None` + `needs_review=true` + log warning, không còn lọt thẳng vào DB/report. **Đã verify job thật** (job `<job_id thật>`, nguồn VTV, <ngày>): đối chiếu tay Bảng 3.1/3.13/3.15 với query DB trực tiếp khớp chính xác.
```

- [ ] **Step 3: Cập nhật "Bước tiếp theo"**

Xoá dòng cũ "Bắt đầu Slice 4..." (đã xong), đổi số thứ tự các mục còn lại (bocongan.gov.vn verify) cho liền mạch.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: cập nhật CLAUDE.md — Slice 4 hoàn thành, ghi nhận kết quả verify thật"
```

---

## Self-Review Checklist (đã tự chạy trước khi giao plan)

- **Spec coverage:** roadmap Slice 4 yêu cầu (1) aggregate đầy đủ GROUP BY nguồn/chủ đề/tháng/sentiment/emotion → Task 3; (2) DOCX template đầy đủ theo `sample_report_form.docx` → Task 4; (3) verify khớp số liệu → Task 5. Cộng thêm 2 yêu cầu phát sinh của user: validate emotion (Task 2), dọn `ESTIMATED_SECONDS_PER_ARTICLE` (Task 1). Điều tra lỗi docx — đã làm, không phát sinh task vì không tìm thấy bug.
- **Placeholder scan:** không còn "TBD"/"tương tự Task N" — mọi step đều có code đầy đủ.
- **Type consistency:** `aggregate_basic()` trả `dict` với đúng 9 key được dùng nhất quán ở Task 3 (định nghĩa) và Task 4 (tiêu thụ trong `generate_docx`/test); `_add_count_table(doc, label_column, counts)` cùng chữ ký ở mọi lần gọi trong Task 4.
