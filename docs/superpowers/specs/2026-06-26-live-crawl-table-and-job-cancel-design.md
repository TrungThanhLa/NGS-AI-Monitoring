# Design: Bảng crawl trực tiếp + Hủy job + Giới hạn bài test + Benchmark thời gian

## Bối cảnh

Sau khi verify Slice 1 (walking skeleton VTV) bằng dữ liệu thật, phát hiện các thiếu sót khi dùng thật trên `localhost:3000`:

1. Khi job đang chạy, người dùng chỉ thấy số đếm (`crawled`, `analyzed`) ở `GET /api/reports/{job_id}/status`, không thấy được **bài nào** đã crawl — không tự kiểm chứng được trên site thật (vtv.vn) là crawler có lấy đúng/lấy có thật hay không.
2. Không có cách nào hủy 1 job đang chạy. Vì sitemap VTV là sitemap toàn site (không lọc theo "tin giả"), 1 khoảng ngày hẹp vẫn có thể ra hàng chục/hàng trăm bài → nếu chọn sai khoảng ngày, job có thể chạy rất lâu (AI qwen3:8b CPU-only ~60-120s/bài) mà không có cách dừng giữa đường, tốn tài nguyên.
3. AI chạy local (qwen3:8b, CPU-only) mất ~60-120s/bài — test thử với khoảng ngày rộng (VD vài ngày) dễ ra hàng chục/trăm bài, khiến 1 lần test mất hàng giờ. Cần cách giới hạn số bài xử lý mỗi lần test, không ảnh hưởng đến hành vi production.
4. Cần đo benchmark thời gian xử lý thật mỗi bài (crawl/phân tích) để biết tốc độ hệ thống — không thể lấy từ Flower vì Flower đo theo **1 Celery task** (cả job, không tách theo từng bài, vì Slice 1 dùng 1 task tuần tự duy nhất), không có granularity theo từng bài viết.

## Quyết định đã chốt qua trao đổi

- Bảng crawl: dùng chung nhịp polling 3s đã có (rule 09), không thêm WebSocket/SSE.
- Cột hiển thị cơ bản: title + url + status — tối giản, đủ để click link kiểm tra trên site thật.
- Cancel: chỉ làm nút "Cancel" thường trực trong lúc job `pending`/`running`. **Không** tự hủy khi reload/đóng tab (giữ đúng rule 04: job chạy nền độc lập FE, người dùng được phép đóng browser rồi quay lại xem sau).
- Mapping `job_id` ↔ Celery `task_id`: lưu **`celery_task_id` thật vào DB** (không suy ra `task_id = job_id` theo quy ước), vì quy ước ngầm có rủi ro lệch mapping khi Slice 3 sau này thêm nhiều task/chuỗi task — lúc đó cancel sẽ revoke nhầm ID không tồn tại, set `status="cancelled"` trong DB nhưng job thật vẫn chạy ngầm (silent failure, không có lỗi nào báo ra).
- Giới hạn số bài/job: làm bằng **biến env** (`MAX_ARTICLES_PER_JOB`), không đưa lên UI thật — vì đây là nhu cầu test/dev, không phải nhu cầu của nhà nghiên cứu dùng sản phẩm; nếu lộ lên UI thật có rủi ro tạo báo cáo thiếu dữ liệu mà người dùng không biết (vi phạm rule 11: "Mọi kết luận trong báo cáo phải có nguồn dữ liệu thực tế").
- Benchmark thời gian: đo **thật** quanh phần xử lý (loại trừ `time.sleep` rate-limit), lưu 2 giá trị đo được — `crawl_duration_seconds` (bảng `articles`), `analysis_duration_seconds` (bảng `article_analysis`). **Không** lưu thêm cột "tổng thời gian" vì là giá trị suy ra được (`crawl + analysis`) — tính ngay trong response API, tránh dữ liệu trùng lặp có thể lệch.

## Phần 1 — Bảng crawl trực tiếp (kèm benchmark thời gian)

**Schema (gộp vào migration `0003`, xem Phần 2):**
- `articles.crawl_duration_seconds` (Float, nullable) — thời gian thật đo quanh `fetch_article()` (fetch HTTP + parse HTML), **không** tính `time.sleep(delay_seconds)` rate-limit
- `article_analysis.analysis_duration_seconds` (Float, nullable) — thời gian thật đo quanh lệnh gọi Ollama trong `analyze_article()`

**`backend/crawler/article.py`:**
- `fetch_article()` đo `time.time()` trước/sau phần `client.get(url)` + parse, trả thêm `crawl_duration_seconds` trong dict kết quả

**`backend/ai/ollama_client.py`:**
- `analyze_article()` đo `time.time()` quanh lệnh gọi Ollama (không tính thời gian build prompt, không đáng kể), trả thêm `analysis_duration_seconds`

**`backend/workers/report_job.py`:**
- Lưu `crawl_duration_seconds` khi insert `Article`, lưu `analysis_duration_seconds` khi insert `ArticleAnalysis`

**Backend — `backend/routers/reports.py`:**
- Thêm `GET /api/reports/{job_id}/articles`
- Query: `Article` LEFT JOIN `ArticleAnalysis` theo `article_id`, lấy `title, url, status, crawl_duration_seconds, analysis_duration_seconds`, sắp theo `crawled_at`
- 404 nếu `job_id` không tồn tại (đồng nhất với 2 endpoint còn lại)
- Response: `{"articles": [{"title", "url", "status", "crawl_duration_seconds", "analysis_duration_seconds", "total_duration_seconds"}, ...]}` — `total_duration_seconds` tính ngay trong response (`crawl + analysis` nếu cả 2 có giá trị, `None` nếu bài chưa được phân tích)

**Frontend — `frontend/app/page.tsx`:**
- Trong `useEffect` polling hiện có (interval 3s), gọi thêm `fetch(.../articles)` song song với `/status`, lưu vào state `articles: Article[]`
- Render `<table>` dưới phần progress: cột Tiêu đề (link `<a href={url} target="_blank" rel="noopener">`), Trạng thái, Thời gian crawl, Thời gian phân tích, Tổng thời gian — 2 cột thời gian sau hiển thị "-" khi giá trị là `None` (bài chưa phân tích xong)
- Không cần test riêng cho phần render — verify bằng cách chạy thật + nhìn bảng cập nhật theo crawl

## Phần 2 — Hủy job

**Schema — migration `0003_add_celery_task_id_and_duration_columns.py`** (gộp cả cột Phần 1 + Phần 2 vì cùng 1 lô tính năng):
- `ALTER TABLE jobs ADD COLUMN celery_task_id VARCHAR(255)` (nullable)
- `ALTER TABLE articles ADD COLUMN crawl_duration_seconds FLOAT` (nullable)
- `ALTER TABLE article_analysis ADD COLUMN analysis_duration_seconds FLOAT` (nullable)
- Tất cả nullable — job/bài viết cũ trước migration không có giá trị, không sao vì chỉ ảnh hưởng dữ liệu mới

**Model:**
- `backend/models/jobs.py`: thêm `celery_task_id = Column(String(255))`
- `backend/models/articles.py`: thêm `crawl_duration_seconds = Column(Float)`
- `backend/models/article_analysis.py`: thêm `analysis_duration_seconds = Column(Float)`

**Backend — `backend/routers/reports.py`:**
- `create_report`: đổi `run_report_job.delay(str(job.job_id))` → `result = run_report_job.delay(str(job.job_id))`, sau đó `job.celery_task_id = result.id; db.commit()`
- Thêm `POST /api/reports/{job_id}/cancel`:
  - 404 nếu job không tồn tại
  - 400 nếu `job.status` không thuộc `("pending", "running")` (đã completed/failed/cancelled thì không cho hủy nữa)
  - Nếu `job.celery_task_id` có giá trị → gọi `celery_app.control.revoke(job.celery_task_id, terminate=True)` (đã verify thực tế trong phiên làm việc trước: lệnh này dừng được task đang crawl giữa loop trong ~1-2s)
  - Nếu `job.celery_task_id` là `None` (job tạo trước migration 0003, hoặc trường hợp hiếm `create_report` chưa kịp lưu) → bỏ qua bước revoke, chỉ set status — tránh gọi `revoke(None, ...)` gây lỗi
  - Set `job.status = "cancelled"`, commit, trả `{"job_id": ..., "status": "cancelled"}`

**Worker — `backend/workers/report_job.py`:**
- Không cần sửa gì — task bị kill bằng SIGTERM (không phải Python exception) nên không tự set được status; cancel endpoint tự set `status="cancelled"` là đủ, task chết giữa đường để lại `articles`/`article_analysis` đã insert dở (chấp nhận được, không cần rollback — dữ liệu dở vẫn là dữ liệu thật, không sai)

**Frontend — `frontend/app/page.tsx`:**
- Hiện nút "Cancel" khi `status === "pending" || status === "running"`
- Bấm → `POST .../cancel` → cập nhật state `status` thành `"cancelled"` ngay (không cần đợi tick poll kế tiếp)
- `status === "cancelled"` → hiển thị dòng chữ thông báo đã hủy, ẩn nút Cancel, ẩn link download

## Phần 3 — Giới hạn số bài crawl/phân tích (test-only, qua env)

**`.env` / `.env.example`:**
- Thêm `MAX_ARTICLES_PER_JOB=` (để trống = không giới hạn, mặc định production)

**`backend/workers/report_job.py`:**
- `_crawl_sources`: đọc `max_articles_raw = os.environ.get("MAX_ARTICLES_PER_JOB")`; parse thành `int` nếu là chuỗi số dương, coi như **không giới hạn** nếu để trống/không set/không parse được/`<= 0` (tránh trường hợp `"0"` hoặc giá trị sai format làm job không crawl được bài nào)
- Nếu có giới hạn hợp lệ: đếm tổng số `Article` đã insert cho job (tính trên toàn job, không phải riêng từng nguồn — vì Slice 1 chỉ có 1 nguồn, không cần phân biệt phức tạp ở bước này) và dừng sớm (break khỏi cả loop candidate URL và loop source) khi đạt giới hạn
- Không sửa `_analyze_articles` — bước này tự nhiên chỉ thấy đúng số bài đã bị giới hạn ở bước crawl, không cần check thêm
- Không sửa API contract, không sửa DB, không sửa FE — đây là cờ vận hành (operational flag) chỉ đọc từ env lúc chạy

## Test cases (TDD)

| Module | Test | Verify |
|---|---|---|
| `routers/reports.py` | `GET /articles` trả đúng list theo `job_id` kèm `crawl_duration_seconds`/`analysis_duration_seconds`/`total_duration_seconds`, 404 khi job không tồn tại | status code + nội dung response |
| `routers/reports.py` | `GET /articles` — bài chưa phân tích thì `analysis_duration_seconds`/`total_duration_seconds` là `None` | nội dung response |
| `crawler/article.py` | `fetch_article()` trả `crawl_duration_seconds` > 0, không tính thời gian sleep bên ngoài | mock httpx trả response ngay, assert duration nhỏ (không lẫn sleep của caller) |
| `ai/ollama_client.py` | `analyze_article()` trả `analysis_duration_seconds` > 0 | mock response, assert có field này |
| `workers/report_job.py` | `_crawl_sources` dừng đúng khi đạt `MAX_ARTICLES_PER_JOB` | set env test, mock nhiều candidate URL, assert số `Article` insert đúng bằng giới hạn |
| `routers/reports.py` | `POST /cancel` khi job `running` → gọi `celery_app.control.revoke` đúng `celery_task_id`, set status `cancelled` | mock `revoke`, assert được gọi với đúng arg + status DB sau khi gọi |
| `routers/reports.py` | `POST /cancel` khi job đã `completed` → 400, không gọi `revoke` | status code 400 + mock không bị gọi |
| `routers/reports.py` | `POST /cancel` khi job không tồn tại → 404 | status code |
| `routers/reports.py` | `POST /cancel` khi `job.celery_task_id` là `None` → không gọi `revoke`, vẫn set status `cancelled` | mock không bị gọi + status DB |
| `routers/reports.py` | `create_report` lưu đúng `celery_task_id` vào DB sau khi tạo job | query lại Job, assert `celery_task_id` khớp với mock `.delay()` trả về |

## Verify cuối (dữ liệu thật)

1. Set `MAX_ARTICLES_PER_JOB=3`, tạo job thật với khoảng ngày rộng → job chỉ crawl đúng 3 bài rồi chuyển sang phân tích, không chạy hàng giờ như lần verify Slice 1 trước
2. Trong lúc job `running`, gọi `GET /articles` thấy danh sách bài tăng dần kèm `crawl_duration_seconds`/`analysis_duration_seconds` thật, click link mở đúng bài thật trên vtv.vn
3. Tạo job khác, bấm Cancel giữa lúc đang crawl → `status` chuyển `cancelled` trong vài giây, `docker compose logs celery-worker` thấy dòng `Terminating ...`, job không tiếp tục crawl thêm sau đó
4. Test trên FE thật (`localhost:3000`): bảng cập nhật theo polling kèm đủ 5 cột (title/status/crawl/phân tích/tổng), nút Cancel ẩn/hiện đúng theo trạng thái
