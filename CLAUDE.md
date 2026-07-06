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
- Scope MVP, tech stack, business flow 8 bước, DB schema 5 bảng, API contract, rule crawler/AI/DOCX/FE (rules 01–09) đã chốt
- Pilot test thật: khảo sát 40 kênh, crawl được 11/40 (làm nền cho quyết định "không build social media")
- Slice 0 + Slice 1 (walking skeleton VTV + mở rộng: crawl trực tiếp/benchmark, Cancel, giới hạn job, khôi phục F5, fix timeout/error-handling) — đã merge `main`, verify thật với VTV
- Crawl4AI (engine fetch thay thế httpx) — bật theo nguồn qua `parsing_rules.engine`, không đổi hành vi nguồn không khai engine (VTV)

### Trạng thái hiện tại
- Slice 0 + Slice 1 (gồm phần mở rộng): hoàn thành, đã merge `main`
- Crawl4AI engine: code xong, verify thật trên VTV/VOV qua lời gọi hàm trực tiếp — nay đã dùng thật cho 5/6 nguồn cấu hình ở Slice 2 (xem dưới)
- Slice 2: code xong + **đã verify job thật end-to-end với 2 nguồn mới (VOV, BoCongAn)** — xem kết quả chi tiết ở dòng Verify Slice 2 dưới
- Slice 3–6: chưa bắt đầu

### Bước tiếp theo
1. Bắt đầu Slice 3 (AI pipeline đầy đủ: prompt 8 nhóm + batch processing)

### Quyết định quan trọng & lý do
| Quyết định | Lý do |
|---|---|
| Không build social media (Facebook/YouTube/TikTok/Zalo) trong MVP | Cần API xác thực riêng, nội dung video không hợp pipeline text-crawl → AI-classify hiện tại; pilot test chỉ 11/40 kênh (toàn website) crawl được |
| Output báo cáo chỉ gồm `Report.docx` + `JSON raw data` | Tránh scope creep so với các file phụ liệt kê trong `sample_report_form.docx` (Dataset.csv, Chart.png...) |
| `emotion` (6 lớp) lấy cùng 1 lần gọi Ollama với `sentiment` | Báo cáo cần Bảng 3.15 tách biệt sentiment 3 lớp; gộp vào 1 lần gọi để tránh round-trip thứ 2 |
| Admin UI (Slice 6) chỉ CRUD metadata nguồn, không cho thêm parsing rule qua UI | Mỗi nguồn có cấu trúc HTML khác nhau, cần dev viết CSS selector tay — không tự động hóa ở MVP |
| Slice 1: 1 Celery task tuần tự (`workers/report_job.py`), không tách `crawl_worker`/`ai_worker` riêng | Đơn giản, dễ debug cho walking skeleton; tách task + batch parallelism để dành Slice 3 |
| `celery_task_id` tự sinh `uuid.uuid4()`, không suy từ `job_id` | Tránh race condition: Cancel đọc `None` nếu task chạy trước khi DB commit |
| `MAX_ARTICLES_PER_JOB` chỉ qua biến env, không đưa lên UI | Nhu cầu test/dev (AI local chậm), không phải nhu cầu người dùng — lộ lên UI có rủi ro báo cáo thiếu dữ liệu mà không ai biết |
| `AI_MAX_CONTENT_LENGTH`=5000, `AI_TIMEOUT_SECONDS`=360 (tạm thời) | Giảm tần suất AI timeout đã từng xảy ra thật ở mức 2000/120 — cần điều chỉnh lại khi có benchmark thật (Slice 3) |
| Crawl4AI bật theo nguồn qua `parsing_rules.engine == "crawl4ai"`, không thêm cột `crawler_engine` riêng | Tái dùng JSONB linh hoạt đã chốt sẵn — không cần migration; nguồn không khai `engine` (VTV) không bị ảnh hưởng |
| Hậu xử lý regex-trim content Crawl4AI tại marker `"Tin liên quan"`/`"Bình luận"` | `fit_markdown` mặc định dính nhiều rác (box bài liên quan/bình luận) — convention phổ biến báo điện tử VN, verify trên nhiều site |
| Hạ `lxml` xuống `~5.3` trong `requirements.txt` | `crawl4ai==0.9.0` yêu cầu `lxml~=5.3`, xung đột với `6.1.1` khi build Docker |
| `celery-worker`/`flower` phải rebuild riêng khi đổi `requirements.txt` | 3 service build image riêng dù chung Dockerfile — quên rebuild từng gây `ModuleNotFoundError` lúc worker start thật |
| Tổng quát hóa `sitemap.py` để nhận sitemap phẳng + nhiều pattern tên sub-sitemap | Mỗi nguồn có cấu trúc URL khác nhau (VOV/VietnamPlus/CAND dùng pattern khác VTV, BoCongAn không có index) — code cũ trả 0 bài cho các nguồn này |
| Lọc lại theo `published_at` thật sau khi fetch bài, không chỉ tin sitemap `<lastmod>` | Một số nguồn (VD bocongan.gov.vn) ghi `<lastmod>` giống nhau cho mọi URL, không phải ngày đăng thật |
| Listing-page crawler chỉ hỗ trợ 1 trang, không phân trang | YAGNI — nguồn duy nhất cần đến (tingia.gov.vn) không có phân trang thật; mở rộng khi có nguồn thật cần |
| `_SITEMAP_DATE_PATTERNS`: dict domain → regex riêng (thay 2 regex chung `_DATE_RANGE_RE`/`_YEAR_MONTH_RE`) | Mỗi site có format URL khác nhau, dễ false-positive nếu dùng chung; thêm nguồn mới = thêm 1 entry, không ảnh hưởng site khác. Domain không khai pattern → fetch-all an toàn |
| Sub-sitemap không khớp pattern của domain → bỏ qua hoàn toàn, KHÔNG fallback fetch-all | Bug thật: fallback fetch-all mặc định từng làm crawl nhầm trang danh mục (`categories.xml`...) của VietnamPlus như bài viết thật |

### Vấn đề cần làm rõ (chưa chốt)
- **Số nguồn ước tính ở Slice 2** ghi "8–10 nguồn thực tế" nhưng theo `content_survey.docx` thực tế là ~11–12 nguồn, khớp pilot test 11/40 — chưa sửa số trong roadmap
- **Số nguồn Slice 2 chỉ đạt 6 (không phải 8–10)** — đã xác nhận 6 nguồn crawl được thật (VTV+VOV+VietnamPlus+CAND+BoCongAn+TinGia); qdnd.vn bị loại do lỗi redirect-loop chưa rõ nguyên nhân (xem bảng quyết định); chinhphu.vn/mod.gov.vn/bvhttdl.gov.vn không có bài chuyên tin giả theo khảo sát thật — người dùng xác nhận 6 nguồn là đủ cho slice này, không ép đủ số
- **Hằng số `ESTIMATED_SECONDS_PER_ARTICLE = 90` ở `SummaryCard.tsx`** là ước lượng thô, chưa có benchmark thật trên nhiều nguồn — cần điều chỉnh lại khi Slice 3 có dữ liệu benchmark thật trên ≥50 bài
- **Nhánh lọc `published_at` thật sau fetch cho BoCongAn (Task 3) chưa được verify với trường hợp thật sự bị loại bỏ** — lần verify job thật (2026-06-30, xem Verify Slice 2) chỉ lấy được 4 URL đầu của sitemap phẳng (đều là trang tĩnh, `published_at=NULL`, không kích hoạt điều kiện lọc); cần chạy lại với `MAX_ARTICLES_PER_JOB` cao hơn hoặc trỏ thẳng vào URL bài tin theo ngày thật (nằm sau trong 500 URL của sitemap) để xác nhận nhánh lọc thật sự loại đúng bài ngoài khoảng ngày

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
- [x] Listing page crawler (fallback khi nguồn không có sitemap) — `backend/crawler/listing.py`, phạm vi 1 trang không phân trang (YAGNI, chỉ tingia.gov.vn cần đến hiện tại)
- [x] Config & test 6 nguồn thực tế (VTV, VOV, VietnamPlus, CAND, BoCongAn, TinGia — ít hơn ước tính gốc 8–10, xem "Vấn đề cần làm rõ" dưới) — toàn bộ 5 nguồn mới dùng engine Crawl4AI (`parsing_rules.engine = "crawl4ai"`), không viết CSS selector tay
- [x] FE: sidebar chọn nhiều nguồn (search, group theo nhóm kênh), tag nguồn đã chọn, summary card ước tính số bài/thời gian, preset ngày (7/30/90/150), warning khi ≥5 nguồn & ≥60 ngày
- **Verify:** crawl thành công 6 nguồn thực tế đã config (cả sitemap và fallback listing); test trùng URL bị dedup đúng (không insert lại) — **đã verify ở mức unit test + migration thật** (sitemap/listing parser, dispatch chiến lược, lọc ngày đăng thật sau fetch, seed 6 nguồn qua `alembic upgrade head`) **và đã chạy job thật end-to-end với 2 nguồn mới (2026-06-30):** gọi `POST /api/reports/create` với cả 2 `source_ids` (VOV + BoCongAn) trong 1 request (`MAX_ARTICLES_PER_JOB=4` để giới hạn thời gian chạy AI CPU-only) — job này (`32f0bcaa...`) tự "đói" hết quota ở VOV trước (do `MAX_ARTICLES_PER_JOB` là giới hạn toàn job, tính theo thứ tự `source_ids`, xem `_crawl_sources` trong `report_job.py`): 4 bài sitemap-index lastmod-đáng-tin của VOV crawl thành công + AI phân tích xong cả 4 (`status=completed`), BoCongAn chưa được chạm tới trong job này (log worker xác nhận sitemap BoCongAn chưa từng được fetch ở job `32f0bcaa`). Để có dữ liệu thật từ BoCongAn, tạo thêm 1 job riêng chỉ với `source_ids=[BoCongAn]` (`job e4a6b316...`): 4 bài sitemap phẳng (không có index, đúng nhánh code mới — xem Task 1) crawl thành công + AI phân tích xong cả 4 (`status=completed`). Cả 2 job sinh `.docx` hợp lệ (`file` xác nhận `Microsoft Word 2007+`, không rỗng) + `.json` hợp lệ. Không có article nào lỗi (`status="error"`), không có exception trong log worker. **Giới hạn thật của lần verify này (ghi nhận trung thực):** do `MAX_ARTICLES_PER_JOB=4`, 4 URL đầu crawl được từ sitemap phẳng của BoCongAn đều là trang tĩnh (trang chủ, trang lãnh đạo, infographic — không phải bài tin theo ngày) nên `published_at` rút ra được là `NULL` cho cả 4 bài; nhánh lọc lại theo `published_at` thật sau fetch (an toàn hơn tin `<lastmod>` giả — xem Task 3) có chạy nhưng **không có cơ hội thật sự loại bỏ bài nào** trong lần verify này (vì điều kiện `if published_at and not (...)` không kích hoạt khi `published_at=None`) — đã xác nhận qua `curl` trực tiếp sitemap rằng 500 URL có thật, các bài tin theo ngày thật nằm ở vị trí sau trong sitemap (ngoài phạm vi 4 bài đã lấy). Phần đã verify chắc chắn: code nhận diện đúng sitemap phẳng (không index) và không trả về 0 bài như code cũ trước Slice 2. Dedup giữ nguyên cơ chế cũ (SHA256(url))

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
- [ ] Error handling đầy đủ theo [10 · Error Handling](.claude/rules/10-error-handling.md) (retry, timeout, JS-render fallback Playwright) — **đã làm trước 1 phần:** AI timeout chỉ skip 1 bài (không fail cả job), crawler lỗi (article + sub-sitemap) hiện `status="error"` trên UI; **còn thiếu:** JS-render fallback Playwright chưa làm
- **Verify:** giả lập timeout/JSON lỗi/nguồn bị block → job xử lý đúng theo bảng error-handling, không crash toàn job

### Slice 6 — Admin UI quản lý nguồn
- [ ] CRUD metadata nguồn (name/URL/active toggle) — không tự thêm parsing rule mới qua UI
- **Verify:** thêm/sửa/xoá nguồn qua UI; nguồn mới active hiển thị đúng ở sidebar chọn nguồn (Slice 2)

**Timeline (không đổi so với breakdown cũ):**
- Best case: ~7 tuần
- Realistic: 9–10 tuần (khuyến nghị dùng để plan)
- Worst case: 11–12 tuần
