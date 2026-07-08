# Design: Slice 3 (AI pipeline đầy đủ) — batch/concurrency + track model + verify dữ liệu thật

## Bối cảnh

Roadmap Slice 3 (CLAUDE.md) liệt kê 3 việc: "prompt phân loại đầy đủ 8 nhóm", "batch processing + tối ưu tốc độ", "đánh giá & tinh chỉnh prompt trên dữ liệu thật". Khảo sát code hiện tại (`backend/ai/ollama_client.py`, `backend/ai/prompts/v1.py`) cho thấy phần đầu tiên **đã làm xong từ Slice 1** — `v1.py` đã có đủ 8 nhóm chủ đề + keyword + sentiment + emotion + retry JSON 1 lần + ngưỡng `confidence < 0.6`, chỉ chưa được đánh giá bằng dữ liệu thật (log CLAUDE.md ghi rõ "chưa cần tối ưu prompt 8 nhóm" ở Slice 1). Vì vậy phạm vi thật sự mới của Slice 3 chỉ còn 2 việc: cơ chế xử lý song song + đánh giá dữ liệu thật.

Trao đổi với user làm rõ thêm 1 nhu cầu chưa có trong roadmap: user dự định chuyển từ chạy AI local (laptop, CPU-only, `qwen3:8b`) sang chạy trên server có GPU (16–24GB VRAM) trong tương lai, muốn thiết kế "công tắc" để chuyển đổi bằng cấu hình (`.env`) thay vì sửa code. Ngoài ra do lo ngại chạy AI liên tục nhiều giờ hại phần cứng laptop, mẫu dữ liệu verify được giảm từ ước tính ban đầu 50 bài xuống 15 bài, chia làm 2 giai đoạn.

## Quyết định đã chốt qua trao đổi

- **Không viết `v2.py` trước.** Giữ nguyên prompt `v1.py` — chỉ viết bản mới nếu bước đọc kết quả 15 bài (Phần 3) phát hiện lỗi hệ thống rõ ràng (VD AI luôn trả cùng 1 nhóm chủ đề bất kể nội dung).
- **"Công tắc" song song = 1 biến số cấu hình (`AI_CONCURRENCY`), không phải 2 nhánh code khác nhau.** Cùng 1 đường code, đổi hành vi bằng số — tránh phải bảo trì 2 code path "local" vs "server".
- **Mặc định `AI_CONCURRENCY=1`** — cho ra đúng hành vi tuần tự hiện tại (an toàn, không thay đổi kết quả/tốc độ trên laptop). Chỉ nên tăng khi có GPU thật.
- **Không benchmark `AI_CONCURRENCY=2/4` trên laptop lần này.** Lý do: user lo ngại chạy AI liên tục hại phần cứng; việc đo tốc độ song song thật cần GPU thật để có ý nghĩa (CPU-only 1 model instance khó tận dụng song song, thậm chí có thể chậm hơn do tranh chấp CPU). Để lại đo khi có server.
- **Ghi lại tên model đã dùng** — thêm cột `article_analysis.ai_model`, đọc từ `OLLAMA_MODEL` tại thời điểm gọi. Lý do: nếu sau này đổi model trên server, cần phân biệt được bản ghi cũ (local, `qwen3:8b`) và bản ghi mới (server, model khác) để không lẫn dữ liệu khi so sánh/tổng hợp — nhất quán với cách `prompt_version` đã làm.
- **Ghi DB vẫn tuần tự sau khi có kết quả AI song song** — không chuyển sang SQLAlchemy async. Các coroutine chỉ gọi HTTP tới Ollama (I/O-bound), không đụng DB; sau khi `asyncio.gather` xong mới lặp tuần tự để insert `ArticleAnalysis` bằng session đồng bộ hiện có. Giảm rủi ro không cần thiết.
- **Mỗi bài lỗi vẫn cô lập riêng khi chạy song song** — dùng `asyncio.gather(..., return_exceptions=True)`, giữ đúng hành vi error-handling đã có (`httpx.HTTPError`/`ValueError` → `status="error"`, không làm hỏng cả batch).
- **Verify 2 giai đoạn thay vì 1 lần 15 bài:**
  - Giai đoạn A (smoke test, `MAX_ARTICLES_PER_JOB=5`): xác nhận luồng end-to-end không lỗi/crash trước, chi phí AI runtime thấp (~7-8 phút ở `AI_CONCURRENCY=1`, ~90s/bài).
  - Giai đoạn B (verify chính thức, `MAX_ARTICLES_PER_JOB=15`): chỉ chạy nếu Giai đoạn A không lỗi. Đây mới là tiêu chí verify Slice 3 chính thức ghi vào CLAUDE.md (thay cho "≥50 bài" ước tính ban đầu trong roadmap).
- **Không đổi FE, không đổi API contract** — Slice 3 là thay đổi nội bộ pipeline AI, không có endpoint mới.

## Phần 1 — Track model đã dùng (`ai_model`)

**Schema — migration `0008_add_ai_model_column.py`:**
- `ALTER TABLE article_analysis ADD COLUMN ai_model VARCHAR(255)` — thêm dạng nullable trước
- `UPDATE article_analysis SET ai_model = 'qwen3:8b' WHERE ai_model IS NULL` — backfill dữ liệu cũ (mọi bản ghi trước migration này đều chạy bằng `qwen3:8b`, xem Quick Reference CLAUDE.md)
- `ALTER TABLE article_analysis ALTER COLUMN ai_model SET NOT NULL` — khoá NOT NULL sau khi backfill, nhất quán với `prompt_version`

**`backend/models/article_analysis.py`:**
- Thêm `ai_model = Column(String(255), nullable=False)` cạnh `prompt_version`

**`backend/ai/ollama_client.py`:**
- `analyze_article()` (sau khi chuyển async, xem Phần 2) gắn `result["ai_model"] = os.environ["OLLAMA_MODEL"]` vào kết quả trả về — cùng chỗ đang gắn `result["prompt_version"]`

**`backend/workers/report_job.py`:**
- `_analyze_articles`: thêm `ai_model=result["ai_model"]` khi insert `ArticleAnalysis`

## Phần 2 — Batch/concurrency qua `AI_CONCURRENCY`

**`.env` / `.env.example`:**
- Thêm `AI_CONCURRENCY=1` — số bài AI xử lý đồng thời trong 1 job. Comment rõ: chỉ tăng khi chạy trên hạ tầng có GPU, cần benchmark lại trước khi đổi trên môi trường mới (rủi ro chậm hơn nếu tăng trên CPU-only).

**`backend/ai/ollama_client.py`:**
- Chuyển `analyze_article()` từ `httpx.Client` (sync) sang `httpx.AsyncClient` (async) — hàm thành `async def analyze_article(...)`. Giữ nguyên toàn bộ logic hiện có (retry 1 lần khi JSON lỗi, truncate tại ranh giới câu, `needs_review`, `prompt_version`, `analysis_duration_seconds`), chỉ đổi `client.post` → `await client.post`.
- Thêm hàm mới `async def analyze_articles_batch(articles: list[tuple[str, str]], concurrency: int) -> list[dict | Exception]`:
  - Tạo 1 `httpx.AsyncClient` dùng chung cho cả batch (tái sử dụng connection, tránh mở/đóng client N lần)
  - `asyncio.Semaphore(concurrency)` bọc quanh từng lệnh gọi `analyze_article` để giới hạn số request đồng thời
  - `asyncio.gather(*tasks, return_exceptions=True)` — mỗi phần tử kết quả là `dict` (thành công) hoặc `Exception` (lỗi bài đó, không raise ra ngoài làm hỏng cả batch)

**`backend/workers/report_job.py`:**
- `_analyze_articles`: đổi từ vòng lặp `for article in pending: analyze_article(...)` sang:
  1. Lấy toàn bộ `pending` (giữ nguyên query hiện có)
  2. `results = asyncio.run(analyze_articles_batch([(a.title, a.content_raw) for a in pending], concurrency=int(os.environ.get("AI_CONCURRENCY", "1"))))`
  3. Lặp tuần tự qua `zip(pending, results)`, insert `ArticleAnalysis` như cũ nếu là `dict`, set `status="error"` như cũ nếu là `Exception` (giữ đúng logging hiện có: `logger.exception(...)`)
- Không đổi hành vi khi `AI_CONCURRENCY=1` — 1 semaphore slot nghĩa là các request vẫn chạy tuần tự về mặt hiệu quả (đúng ý "công tắc mặc định = hành vi cũ").

**Test tồn tại cần cập nhật (`backend/tests/test_ollama_client.py`):**
- Đổi `httpx.Client` + `httpx.MockTransport` (sync) sang `httpx.AsyncClient` + `httpx.MockTransport` (async), test chạy qua `pytest.mark.asyncio` hoặc `asyncio.run(...)` trong test — giữ nguyên toàn bộ assertion hiện có, chỉ đổi cách gọi.

## Phần 3 — Verify dữ liệu thật (2 giai đoạn)

**Giai đoạn A — smoke test:**
1. Set `MAX_ARTICLES_PER_JOB=5`, `AI_CONCURRENCY=1`
2. Tạo 1 job thật qua `POST /api/reports/create` với vài `source_ids` (trong số 7 nguồn đã verify) + khoảng ngày đủ rộng để ra đúng 5 bài
3. Xác nhận: `status=completed`, không có exception trong log `celery-worker`, mỗi `article_analysis` có `ai_model='qwen3:8b'`, DOCX/JSON hợp lệ
4. Nếu lỗi → sửa code, lặp lại Giai đoạn A (không sang Giai đoạn B) cho tới khi qua

**Giai đoạn B — verify chính thức (chỉ chạy khi Giai đoạn A pass):**
1. Set `MAX_ARTICLES_PER_JOB=15`
2. Tạo job thật trải trên nhiều nguồn hơn (VD 4-5/7 nguồn) để có đa dạng nội dung
3. Chạy `backend/scripts/export_analysis_csv.py <job_id>` — script nhỏ, không phải endpoint API, đọc thẳng DB qua `SessionLocal`, export `title, url, topics, keywords, sentiment, emotion, confidence, needs_review, summary, ai_model` ra file CSV trong `storage/` (hoặc đường dẫn truyền vào)
4. User đọc lướt CSV, xác nhận không có lệch hệ thống rõ ràng (VD luôn cùng 1 topic, luôn cùng 1 sentiment bất kể nội dung khác nhau). Nếu có → quyết định viết `v2.py` (ngoài phạm vi spec này, sẽ mở task riêng)
5. Đây là tiêu chí verify Slice 3 chính thức — cập nhật CLAUDE.md: sửa dòng verify Slice 3 từ "≥50 bài" thành "15 bài (giảm từ 50, tránh chạy AI liên tục hại phần cứng laptop — xem quyết định)", tick `[x]` 2 mục "batch processing" và "đánh giá & tinh chỉnh" sau khi Giai đoạn B pass.

## Test cases (TDD)

| Module | Test | Verify |
|---|---|---|
| `ai/ollama_client.py` | `analyze_article()` (async) vẫn parse JSON đúng, retry 1 lần khi lỗi, gắn `prompt_version`/`ai_model`/`analysis_duration_seconds` | mock `httpx.AsyncClient` + `MockTransport`, assert như test hiện có nhưng qua async |
| `ai/ollama_client.py` | `analyze_articles_batch()` giới hạn đúng số request đồng thời theo `concurrency` | mock client đếm số request đang "in-flight" cùng lúc, assert không vượt quá `concurrency` |
| `ai/ollama_client.py` | `analyze_articles_batch()` — 1 bài lỗi (JSON invalid 2 lần / HTTP error) không làm hỏng kết quả các bài khác trong batch | mock 1 response lỗi giữa nhiều response hợp lệ, assert list kết quả có đúng 1 `Exception` ở đúng vị trí, các phần tử khác vẫn là `dict` hợp lệ |
| `workers/report_job.py` | `_analyze_articles` — bài có kết quả `dict` → insert `ArticleAnalysis` với `ai_model` đúng, bài có kết quả `Exception` → `status="error"` | mock `analyze_articles_batch` trả list trộn dict/Exception, assert DB sau khi chạy |
| `workers/report_job.py` | `_analyze_articles` với `AI_CONCURRENCY` không set/rỗng → mặc định `1`, không lỗi | set env rỗng, assert không raise |
| `alembic/versions/0008_*` | Migration thêm `ai_model` NOT NULL, backfill đúng giá trị cho dữ liệu cũ | chạy `upgrade`/`downgrade` trên DB test, assert schema + dữ liệu backfill |

## Verify cuối (dữ liệu thật) — tóm tắt

1. Unit test + migration test pass (bảng trên)
2. Giai đoạn A (5 bài, `AI_CONCURRENCY=1`) — job `completed`, không exception, `ai_model` đúng
3. Giai đoạn B (15 bài) — job `completed`, CSV export đọc được, user đọc lướt xác nhận không lệch hệ thống rõ ràng
4. `docker compose restart celery-worker` trước cả 2 lần chạy thật (bài học từ Slice 2 — volume mount không tự nạp code mới)
