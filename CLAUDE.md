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
- **Tích hợp Crawl4AI làm engine fetch thay thế** (chuẩn bị cho Slice 2, chưa phải checklist item của Slice 2) — thêm `backend/crawler/crawl4ai_client.py` (`fetch_article_crawl4ai` + `fetch_article_dispatch`), bật theo từng nguồn qua key `parsing_rules.engine` (không thêm cột/migration), giữ nguyên 100% hành vi cũ cho nguồn không khai `engine` (VTV). Verify thật trên VTV + VOV, 48 unit test pass (12 test riêng cho crawl4ai). Đã qua code review (8 góc nhìn) trước khi commit, phát hiện & fix 1 bug thật (exception từ crawl4ai làm fail nguyên job — xem bảng "Quyết định quan trọng" dưới)

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
| Lỗi sub-sitemap (hết retry) cũng insert row `Article` với `status="error"` (`url` = URL sub-sitemap lỗi, `title=null`) | Tái dùng đúng cơ chế hiển thị lỗi đã có cho article-level crawl error — không cần migration/đổi FE. Hash `url_hash` theo `job_id + url` (không phải `SHA256(url)` như bài viết) để tránh đụng `UNIQUE` constraint khi job khác sau này crawl lại đúng nguồn gặp lại sub-sitemap lỗi (2026-06-26) |
| `AI_MAX_CONTENT_LENGTH` 2000→5000, `AI_TIMEOUT_SECONDS` 120→360 (tạm thời) + cắt nội dung tại ranh giới câu thay vì cắt cứng giữa câu/từ | Giảm rủi ro mất ngữ nghĩa bài dài và giảm tần suất AI timeout (đã từng xảy ra thật ở mức 2000/120). Đây là giải pháp tạm — tăng theo khoảng người dùng đề xuất (5-6 phút, chọn mức cao 360s), sẽ nâng/hạ lại theo tần suất lỗi thật gặp phải khi có thêm dữ liệu (Slice 3) (2026-06-26) |
| Crawl4AI bật theo nguồn qua key `parsing_rules.engine == "crawl4ai"` (JSONB có sẵn), không thêm cột `crawler_engine` riêng | Tái dùng đúng thiết kế linh hoạt đã chốt sẵn (`sources.parsing_rules` JSONB) — không cần migration, ít thay đổi nhất; nguồn không khai `engine` (VTV) chạy y nguyên httpx cũ, không regression (2026-06-29) |
| Logic rẽ nhánh httpx/Crawl4AI viết dạng hàm thuần `fetch_article_dispatch()` trong `crawl4ai_client.py`, không dùng class `ArticleFetcher` | Chỉ là dispatch theo 1 flag, không có state cần giữ giữa các lần fetch — đúng style function-based đang dùng toàn bộ `crawler/`; tránh đặt câu hỏi thừa về lifecycle instance khi không cần (2026-06-29) |
| Hạ `lxml` từ `6.1.1` xuống `~5.3` trong `requirements.txt` | Xung đột dependency thật khi build Docker: `crawl4ai==0.9.0` yêu cầu `lxml~=5.3`, không tương thích `6.1.1`. Đã dry-run xác nhận resolve sạch với `beautifulsoup4`/`python-docx` hiện có trước khi đổi (2026-06-29) |
| Thêm bước hậu xử lý regex-trim cắt content Crawl4AI tại marker `"Tin liên quan"`/`"Bình luận"` | Verify thật cho thấy `fit_markdown` mặc định của Crawl4AI không sạch — dính thêm ~66% rác (VTV: 2887→1737 ký tự) tới ~72% rác (VOV: 13909→8097 ký tự) là box "bài liên quan"/bình luận, làm dài context không cần thiết khi feed AI. 2 marker này là convention phổ biến báo điện tử VN (verify trên 2 site khác nhau), không phải đặc thù 1 site (2026-06-29) |
| `celery-worker`/`flower` phải rebuild riêng khi đổi `requirements.txt`, không chỉ `backend` | 3 service dùng chung `backend/Dockerfile` nhưng Compose build 3 image riêng — quên rebuild `celery-worker`/`flower` từng gây `ModuleNotFoundError: crawl4ai` lúc worker start thật (2026-06-29) |
| Xóa `ping_task` khỏi `celery_app.py` | Dead code sót lại từ verify Celery ở Slice 0 (xem Slice 0 dưới), không còn được gọi ở đâu — đã xác nhận không có tham chiếu nào trước khi xóa, test + container `celery-worker` vẫn chạy `healthy` sau khi xóa (2026-06-29) |
| Chấp nhận phần rác còn dư khi crawl VOV qua Crawl4AI (không thêm `excluded_selector`) | Phần dư (~600-700 ký tự, box "bài liên quan" nhúng trong content) không lớn, CSS selector thủ công cũng gặp đúng vấn đề này (không phải nhược điểm riêng của Crawl4AI) — chưa đáng đánh đổi thêm độ phức tạp ở giai đoạn này; có thể quay lại nếu Slice 2 phát hiện vấn đề rõ hơn (2026-06-29) |
| Bọc `try/except Exception` quanh `fetch_article_dispatch()` trong `_crawl_sources()` | Bug thật phát hiện qua code review trước khi commit: lỗi từ `fetch_article_crawl4ai()` (network exception trong `asyncio.run`, `ValueError` từ `datetime.fromisoformat` nếu meta tag ngày không chuẩn ISO-8601) bay thẳng lên `run_report_job`, làm fail nguyên cả job thay vì chỉ 1 bài — sai đúng nguyên tắc đã ghi ở `10-error-handling.md`. Chưa kích hoạt trong production (chưa nguồn nào dùng `engine=crawl4ai` thật) nhưng sửa trước khi nguồn đầu tiên dùng tới (2026-06-29) |
| Tổng quát hóa `sitemap.py` để nhận sitemap phẳng + nhiều pattern tên sub-sitemap (thay vì chỉ đúng pattern VTV) | Verify thật cho thấy VOV/VietnamPlus/CAND dùng pattern khác VTV (`news-YYYY-M.xml`/`/YYYY/M/...`), bocongan.gov.vn dùng sitemap phẳng không có index — code cũ sẽ trả về 0 bài cho cả 4 nguồn này nếu không sửa (2026-06-29) |
| Lọc lại theo `published_at` thật sau khi fetch bài (không chỉ tin sitemap `<lastmod>`) | bocongan.gov.vn ghi `<lastmod>` giống nhau y hệt cho toàn bộ 500 URL trong sitemap (timestamp build lại sitemap, không phải ngày đăng thật, đã verify thật bằng curl) — lọc theo lastmod sẽ làm rớt nhầm toàn bộ bài hợp lệ hoặc giữ nhầm toàn bộ bài không hợp lệ tùy khoảng ngày yêu cầu (2026-06-29) |
| Listing-page crawler chỉ hỗ trợ 1 trang, không phân trang | Nguồn duy nhất cần đến (tingia.gov.vn) không có phân trang thật trên trang danh sách (đã verify) — không xây cơ chế phân trang khi chưa có nguồn thật nào cần (YAGNI), mở rộng khi Slice sau có nguồn cần thật (2026-06-29) |
| Cả 5 nguồn mới (VOV, VietnamPlus, CAND, BoCongAn, TinGia) dùng engine Crawl4AI, không viết CSS selector tay | Tránh 6x công reverse-engineer CSS selector cho 6 template HTML khác nhau; Crawl4AI đã verify hoạt động thật trên VTV+VOV trước đó, đúng định hướng đã ghi sẵn trong roadmap Slice 2 (2026-06-29) |
| Tạm loại qdnd.vn khỏi Slice 2 | `curl`/WebFetch tới `sitemap.xml` và cả trang chủ qdnd.vn đều bị redirect-loop vô hạn (302) từ network môi trường test — chưa rõ do chặn bot hay do IP/network môi trường test, cần verify lại từ server production trước khi thêm (2026-06-29) |
| Thay 2 regex chung `_DATE_RANGE_RE`/`_YEAR_MONTH_RE` bằng `_SITEMAP_DATE_PATTERNS` (dict domain → regex riêng với named groups) | 2 regex chung dễ false-positive và ẩn đi việc mỗi site thực ra có format URL khác nhau; khi thêm nguồn mới phải đoán xem nó khớp regex nào. Dict per-domain tường minh hơn: thêm nguồn = thêm 1 entry, đổi format = sửa 1 dòng, không ảnh hưởng site khác. Named groups `year+month+day_start+day_end` → khoảng ngày; `year+month` (không có day_*) → toàn tháng — không cần type string trung gian. Domain không khai → fetch-all an toàn. Không cần migration — `source.domain` đã có sẵn (2026-07-01) |

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
