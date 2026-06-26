# NGS Monitor — CLAUDE.md

Web application thu thập và phân tích nội dung truyền thông phòng chống tin giả
tại Việt Nam. AI chạy local, output là file báo cáo Word (.docx).

## Rules

<!-- Core — luôn áp dụng -->
- [01 · Project Overview](.claude/rules/01-project-overview.md)
- [02 · Tech Stack](.claude/rules/02-tech-stack.md)
- [03 · Database Schema](.claude/rules/03-database-schema.md)
- [04 · Business Flow](.claude/rules/04-business-flow.md)
- [10 · Error Handling](.claude/rules/10-error-handling.md)
- [11 · Core Principles](.claude/rules/11-core-principles.md)
- [12 · Response Format](.claude/rules/12-response-format.md)
- [13 · Workflow](.claude/rules/13-workflow.md)

<!-- Feature-specific — đọc khi làm task liên quan -->
- [05 · API Contracts](.claude/rules/05-api-contracts.md)
- [06 · Crawler Strategy](.claude/rules/06-crawler-strategy.md)
- [07 · AI Pipeline](.claude/rules/07-ai-pipeline.md)
- [08 · DOCX Report](.claude/rules/08-docx-report.md)
- [09 · Frontend UI](.claude/rules/09-frontend-ui.md)

## Nguyên tắc hành vi khi code

> Bổ sung (không thay thế) cho [11 · Core Principles](.claude/rules/11-core-principles.md) (nguyên tắc nghiệp vụ/dữ liệu) và [13 · Workflow](.claude/rules/13-workflow.md) (quy trình EPCC).

### 1. Suy nghĩ trước khi code — không tự giả định
Khi yêu cầu chưa rõ (CSS selector cho nguồn mới, ngưỡng confidence đặc biệt, placeholder DOCX chưa định nghĩa...), dừng lại và hỏi thay vì đoán.
- Nêu rõ giả định trước khi code; nếu có điểm chưa chắc — hỏi lại user
- Nếu có nhiều cách hiểu yêu cầu, trình bày các cách hiểu — không tự chọn 1 cách rồi im lặng code
- Nếu có cách làm đơn giản hơn cách user đề xuất, nói rõ và đề xuất — không ngại phản biện
- Đây là phần mở rộng cho bước Explore của EPCC ([13 · Workflow](.claude/rules/13-workflow.md))

### 2. Tối giản — không thêm thứ ngoài yêu cầu
Theo đúng nguyên tắc MVP-first đã có ([11 · Core Principles](.claude/rules/11-core-principles.md)): mọi đoạn code mới phải là lượng code tối thiểu giải quyết đúng yêu cầu.
- Không thêm feature, config, hay "khả năng mở rộng" nếu không được yêu cầu rõ
- Không tạo abstraction (lớp trừu tượng/helper dùng chung) cho code chỉ dùng 1 lần
- Không viết error handling cho tình huống không thể xảy ra trong context hiện tại (xem case đã định nghĩa ở [10 · Error Handling](.claude/rules/10-error-handling.md))
- Ngoại lệ: thiết kế linh hoạt đã chốt trong schema (VD: `sources.parsing_rules` JSONB) là quyết định kiến trúc có chủ đích — không tính là "thêm ngoài yêu cầu"

### 3. Sửa đúng phạm vi — không "tiện tay" sửa thêm
Chỉ đụng vào phần code liên quan trực tiếp tới yêu cầu.
- Không "cải thiện" code/comment/format ở đoạn không liên quan
- Không refactor code đang chạy tốt nếu không được yêu cầu
- Giữ đúng style hiện có của file, kể cả quy ước comment tiếng Việt giải thích logic quan trọng ([13 · Workflow](.claude/rules/13-workflow.md))
- Phát hiện dead code không liên quan tới task → báo cho user biết, không tự xóa
- Chỉ dọn import/biến/function không dùng nữa nếu chính thay đổi của bạn gây ra — không dọn dead code có từ trước

### 4. Làm theo tiêu chí xác minh được — verify trước khi báo "xong"
Mọi task phải quy về tiêu chí kiểm tra được, không dừng ở "chạy được là xong".
- "Thêm validate nguồn" → viết test case cho input không hợp lệ, rồi làm nó pass
- "Sửa bug crawler/AI pipeline" → viết test reproduce lỗi trước, rồi mới fix
- "Refactor parser/aggregator" → đảm bảo test pass cả trước và sau khi sửa
- Với task nhiều bước, nêu ngắn gọn plan dạng: `1. [Bước] → verify: [cách kiểm tra]`
- Vẫn phải tuân thủ bước Commit của EPCC: lint + type check + test với ít nhất 1 nguồn dữ liệu thật trước khi commit ([13 · Workflow](.claude/rules/13-workflow.md))

## Quick Reference

| Thứ cần nhớ | Giá trị |
|---|---|
| AI model | `qwen3:8b` via Ollama |
| DB | PostgreSQL — 5 bảng chính |
| Confidence threshold | `0.6` — dưới này → `needs_review=true` |
| Crawler strategy | Sitemap XML → fallback listing page |
| Delay giữa request | 1–2 giây |
| Job queue | Celery + Redis |
| Sinh báo cáo | python-docx + template |

## Trạng thái dự án & Quyết định quan trọng

> Cập nhật mục này khi có tiến độ hoặc quyết định mới — đây là log tổng hợp, không thay thế checklist chi tiết ở Roadmap dưới.

### Đã hoàn thành
- Xác định scope MVP, tech stack, business flow 8 bước, DB schema 5 bảng, API contract, rule crawler/AI/DOCX/FE (rules 01–09)
- Pilot test thật ngoài code: khảo sát 40 kênh, crawl thử được 11/40 (`Bao_cao_Du_lieu_Thuc_22-06-2026.docx`)
- **Slice 0 + Slice 1** (walking skeleton VTV) và **phần mở rộng** (bảng crawl trực tiếp/benchmark, Cancel, giới hạn test, khôi phục F5, fix 2 bug error-handling) — **đã merge `main`**, verify thật với dữ liệu VTV (104 bài crawl thật, AI phân tích thật qua `qwen3:8b`, DOCX/JSON hợp lệ), 32 unit test pass. Chi tiết từng phần xem Roadmap Slice 1 và bảng "Quyết định quan trọng" dưới

### Trạng thái hiện tại
- Slice 0 + Slice 1 (gồm phần mở rộng): hoàn thành, đã merge `main`
- Slice 2–6: chưa bắt đầu

### Bước tiếp theo
1. Xử lý vấn đề tồn đọng ở "Vấn đề cần làm rõ" dưới (lỗi sub-sitemap vô hình trên UI, `AI_MAX_CONTENT_LENGTH` cắt cứng)
2. Bắt đầu Slice 2: nhiều nguồn + listing-page fallback — chi tiết ở Roadmap dưới

### Quyết định quan trọng & lý do
| Quyết định | Lý do |
|---|---|
| Không build social media (Facebook/YouTube/TikTok/Zalo) trong MVP | Các nền tảng này cần API có xác thực riêng, không crawl mở được; nội dung là video ngắn/dài, không hợp với pipeline text-crawl → AI-classify hiện tại. Pilot test chỉ 11/40 kênh khảo sát (toàn website) crawl được — phần social media để dành cho phase sau |
| Output báo cáo chỉ gồm `Report.docx` + `JSON raw data` | `sample_report_form.docx` có liệt kê thêm Dataset.csv, Summary.xlsx, Chart.png, WordCloud.png... nhưng không có task tương ứng trong breakdown gốc — không build thêm để tránh scope creep |
| Thêm field `emotion` (6 lớp) vào AI output, lấy cùng 1 lần gọi với `sentiment` | Báo cáo cần Bảng 3.15 (Emotion Analysis) tách biệt với sentiment 3 lớp; gộp vào 1 lần gọi Ollama để tránh tốn thêm round-trip |
| Admin UI (Slice 6) chỉ CRUD metadata nguồn (name/URL/active toggle), không cho thêm parsing rule qua UI | Mỗi nguồn mới có cấu trúc HTML khác nhau, cần dev viết CSS selector tay (`sources.parsing_rules`) — không tự động hóa qua UI ở MVP |
| Đổi roadmap từ 24-task/5-phase (theo layer kỹ thuật) sang Slice 0 + 6 vertical slice (đầu-cuối) | Muốn chứng minh pipeline chạy thật càng sớm càng tốt (Slice 1), giảm rủi ro phát hiện lỗi tích hợp muộn; tổng scope/timeline không đổi, chỉ đổi thứ tự đóng gói |
| Slice 1: 1 Celery task tuần tự duy nhất (`workers/report_job.py`), không tách `crawl_worker.py`/`ai_worker.py` riêng | Đơn giản, dễ debug cho walking skeleton; tách task riêng + batch parallelism để dành cho Slice 3 ("Batch processing + tối ưu tốc độ") |
| `celery_task_id` tự sinh `uuid.uuid4()` + commit DB trước khi gọi Celery, không suy ra từ `job_id` | Tránh lệch mapping khi sau này có nhiều task/job (Slice 3) và tránh race condition (Cancel đọc `None` nếu task đã chạy trước khi DB commit) |
| Giới hạn `MAX_ARTICLES_PER_JOB` chỉ qua biến env, không đưa lên UI thật | Nhu cầu test/dev (AI local rất chậm), không phải nhu cầu nhà nghiên cứu; lộ lên UI có rủi ro tạo báo cáo thiếu dữ liệu mà người dùng không biết |
| Khôi phục job sau F5 dùng `sessionStorage`, không dùng `localStorage` | Chỉ cần sống qua reload trong cùng tab, tự dọn khi đóng tab — tránh "job ma" lưu nhiều ngày |
| AI timeout (>120s) chỉ skip 1 bài, không fail cả job | Bug thật: code cũ chỉ bắt `ValueError`, không bắt `httpx.HTTPError` (timeout) → fail cả job, mất báo cáo của các bài đã phân tích xong |
| Crawler lỗi (hết retry) vẫn insert row `Article` với `status="error"` | Trước đây bỏ qua âm thầm, không log/lưu gì — giờ hiện được trên bảng crawl trực tiếp ở FE |

### Vấn đề cần làm rõ (chưa chốt)
- **Số nguồn ước tính ở Slice 2** ghi "8–10 nguồn thực tế" nhưng theo `content_survey.docx` thực tế là ~11–12 nguồn, khớp pilot test 11/40 — chưa sửa số trong roadmap
- **Lỗi sub-sitemap (khác lỗi article) vẫn vô hình trên UI** — hết retry chỉ log server, không có URL cụ thể để tạo row `status="error"` — chưa quyết định có cần làm thêm hay log server là đủ
- **`AI_MAX_CONTENT_LENGTH=2000` cắt cứng nội dung gửi AI** — bài dài hơn 2000 ký tự mất phần cuối — chưa quyết định giữ nguyên, tóm tắt trước khi cắt, hay tăng giới hạn

## Roadmap — Vertical Slices

> Cập nhật trạng thái tại đây khi có tiến độ mới — tick `[x]` khi hoàn thành.
> Mỗi slice (trừ Slice 0) là 1 lát cắt **đầu-cuối** (DB → crawler → AI → report → FE) chạy được thật với dữ liệu thật, không chỉ 1 layer kỹ thuật. Mở rộng dần theo số nguồn/tính năng, không làm hết 1 layer rồi mới sang layer khác. Tổng scope và ước tính thời gian giữ nguyên so với breakdown cũ — chỉ đổi **thứ tự đóng gói** công việc.

### Slice 0 — Hạ tầng nền (prerequisite, không phải vertical slice)
- [x] Khởi tạo project, cấu trúc thư mục, Docker Compose
- [x] Thiết kế & migrate Database schema (5 bảng, gồm field `emotion` và `prompt_version`)
- [x] Setup Celery + Redis + Flower
- [x] Setup Ollama + pull model `qwen3:8b`
- **Verify:** `docker-compose up` chạy đủ service; DB có đủ 5 bảng; Celery worker nhận và chạy được 1 task test; `curl` Ollama trả response cho 1 prompt test — **đã chạy thật và pass cả 7 service (`docker compose ps` → healthy), bao gồm test healthcheck dependency khi Redis down (2026-06-25)**

### Slice 1 — "1 nguồn, đầu-cuối" (walking skeleton)
Mục tiêu: chứng minh toàn bộ pipeline chạy thông từ FE đến file kết quả, với phạm vi hẹp nhất (1 nguồn, vài bài).
- [x] API `POST /api/reports/create` (1 source_id, date range) → tạo Job, đẩy Celery queue
- [x] Crawler: sitemap parser cho 1 nguồn thật (VD VTV) + article parser (httpx + BeautifulSoup) + dedup SHA256 + lưu `articles`
- [x] AI: gọi Ollama, parse JSON, lưu `article_analysis` (đủ field kể cả `emotion`, chưa cần tối ưu prompt 8 nhóm)
- [x] Report: DOCX cơ bản (vài bảng chính) + export JSON raw data
- [x] FE tối giản: 1 form chọn nguồn (hardcode) + date range → submit → polling status → download
- **Verify:** chạy thử với 1 nguồn thực tế, ra được ≥1 file `.docx` + `.json` hợp lệ; `jobs.status` chuyển đúng `pending → running → completed` — **đã chạy thật, 104 bài crawl thật từ VTV, AI phân tích thật qua `qwen3:8b`, DOCX/JSON hợp lệ, 32 unit test pass**
- **Mở rộng thêm sau khi verify** (đã merge `main` cùng đợt): bảng crawl trực tiếp + benchmark thời gian, hủy job (Cancel), giới hạn `MAX_ARTICLES_PER_JOB`, khôi phục job sau F5, fix AI timeout/crawler error-handling — xem "Quyết định quan trọng & lý do" ở trên

### Slice 2 — Nhiều nguồn + listing-page fallback
- [ ] Listing page crawler (fallback khi nguồn không có sitemap)
- [ ] Config & test 8–10 nguồn thực tế (VTV, VOV, QĐND, BCA...)
- [ ] FE: sidebar chọn nhiều nguồn (search, group theo nhóm kênh), tag nguồn đã chọn, summary card ước tính số bài/thời gian, preset ngày (7/30/90/150), warning khi ≥5 nguồn & ≥60 ngày
- **Verify:** crawl thành công ≥8 nguồn thực tế (cả sitemap và fallback listing); test trùng URL bị dedup đúng (không insert lại)

### Slice 3 — AI pipeline đầy đủ
- [ ] Prompt phân loại đầy đủ 8 nhóm chủ đề + keyword + sentiment + `emotion` (6 lớp)
- [ ] Batch processing + tối ưu tốc độ
- [ ] Đánh giá & tinh chỉnh prompt trên dữ liệu thật
- **Verify:** chạy AI trên ≥50 bài thực tế; `confidence < 0.6` → `needs_review=true` đúng ngưỡng; JSON lỗi → retry 1 lần → skip nếu vẫn lỗi (test case JSON không hợp lệ)

### Slice 4 — Report đầy đủ
- [ ] Aggregate query đầy đủ: GROUP BY nguồn/chủ đề/tháng/sentiment/emotion
- [ ] Build DOCX template đầy đủ theo `sample_report_form.docx` + placeholder map
- [ ] Kiểm tra output với dữ liệu thật
- **Verify:** file `.docx` sinh ra khớp cấu trúc `sample_report_form.docx`; số liệu từng bảng khớp với query DB trực tiếp (so sánh tay ít nhất 2-3 bảng)

### Slice 5 — UX & vận hành hoàn chỉnh
- [x] Job status polling + progress UI chi tiết (`crawled/analyzed/total_estimated`) — đã làm ở Slice 1, mở rộng thêm bảng crawl trực tiếp + Cancel (xem Slice 1)
- [ ] Trang lịch sử báo cáo (`GET /api/reports/history`)
- [ ] Error handling đầy đủ theo [10 · Error Handling](.claude/rules/10-error-handling.md) (retry, timeout, JS-render fallback Playwright) — **đã làm trước 1 phần:** AI timeout chỉ skip 1 bài (không fail cả job), crawler lỗi hiện `status="error"` trên UI; **còn thiếu:** lỗi sub-sitemap vẫn vô hình trên UI, JS-render fallback Playwright chưa làm
- **Verify:** giả lập timeout/JSON lỗi/nguồn bị block → job xử lý đúng theo bảng error-handling, không crash toàn job

### Slice 6 — Admin UI quản lý nguồn
- [ ] CRUD metadata nguồn (name/URL/active toggle) — không tự thêm parsing rule mới qua UI
- **Verify:** thêm/sửa/xoá nguồn qua UI; nguồn mới active hiển thị đúng ở sidebar chọn nguồn (Slice 2)

**Timeline (không đổi so với breakdown cũ):**
- Best case: ~7 tuần
- Realistic: 9–10 tuần (khuyến nghị dùng để plan)
- Worst case: 11–12 tuần
