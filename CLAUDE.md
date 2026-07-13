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
- [14 · Coding Behavior](.claude/rules/14-coding-behavior.md)

<!-- Feature-specific — đọc khi làm task liên quan -->
- [05 · API Contracts](.claude/rules/05-api-contracts.md)
- [06 · Crawler Strategy](.claude/rules/06-crawler-strategy.md)
- [07 · AI Pipeline](.claude/rules/07-ai-pipeline.md)
- [08 · DOCX Report](.claude/rules/08-docx-report.md)
- [09 · Frontend UI](.claude/rules/09-frontend-ui.md)

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
> **Lịch sử chi tiết đầy đủ** (số liệu job thật, log, quá trình quyết định) đã chuyển sang [docs/CHANGELOG.md](docs/CHANGELOG.md) — mục dưới đây chỉ giữ bản tóm tắt 1 dòng/mục.

### Đã hoàn thành
- Scope MVP, tech stack, business flow 8 bước, DB schema 5 bảng, API contract, rule crawler/AI/DOCX/FE (rules 01–09) đã chốt
- Pilot test thật: khảo sát 40 kênh, crawl được 11/40 (làm nền cho quyết định "không build social media")
- Slice 0 + Slice 1 (walking skeleton VTV + mở rộng: crawl trực tiếp/benchmark, Cancel, giới hạn job, khôi phục F5, fix timeout/error-handling) — đã merge `main`, verify thật với VTV
- Crawl4AI (engine fetch thay thế httpx) — bật theo nguồn qua `parsing_rules.engine`, không đổi hành vi nguồn không khai engine (VTV)
- 7 nguồn cấu hình xong: VTV, VOV, VietnamPlus, CAND, BoCongAn (listing_pages, sitemap đóng băng), TinGia (sitemap curated), vietnam.vn (sitemap curated) — chi tiết từng nguồn + verify job thật ở changelog
- **Slice 3 (AI pipeline đầy đủ) — hoàn thành (2026-07-09):** `AI_CONCURRENCY`/`analyze_articles_batch()`/track `ai_model` — đã verify job thật 2 giai đoạn (chi tiết ở changelog)
- **Bỏ dedup xuyên job (2026-07-09):** UNIQUE composite `(job_id, url_hash)` (migration `0009`) thay UNIQUE toàn cục — mỗi job crawl + phân tích AI lại từ đầu, không dedup xuyên job (giải quyết vấn đề "job mồ côi" + "report rỗng âm thầm"). Đánh đổi: AI chạy lại tốn tài nguyên khi job trùng phạm vi, `articles` phình to theo thời gian, kết quả AI không đảm bảo giống hệt giữa các lần (non-determinism) — xem "Vấn đề cần làm rõ"
- **Slice 4 (Report đầy đủ) — hoàn thành (2026-07-10):** aggregate đầy đủ (`source_counts`/`topic_counts`/`keyword_counts`/`monthly_counts`/`summary_stats`) + DOCX theo đúng `sample_report_form.docx` + validate `emotion` enum (giá trị lạ → `emotion=None`+`needs_review=true`). Verify job thật khớp 100% với query DB trực tiếp
- **EVEN_DISTRIBUTE_ACROSS_SOURCES — water-filling (2026-07-10):** chia đều + bù quota thiếu hụt giữa các nguồn đã chọn, tổng job tiến gần đúng `MAX_ARTICLES_PER_JOB` thay vì để nguồn đầu "ăn hết" ngân sách
- **Sửa 2 hạn chế sitemap index VOV/VTV + bỏ 1 request thừa (2026-07-10):** `_SITEMAP_URL_TEMPLATES` (VOV, tự sinh URL sub-sitemap không qua index) + `_SITEMAP_ALWAYS_INCLUDE` (VTV, fetch kèm catch-all khi `date_to >= today`) — cả 2 đã verify job thật

### Trạng thái hiện tại
- Slice 0–4: hoàn thành, đã merge `main`, verify job thật cho từng slice (chi tiết ở [docs/CHANGELOG.md](docs/CHANGELOG.md))
- BoCongAn: code + migration `0005` đã push `main`, **chưa verify bằng job thật** — bị chặn WAF (Incapsula) từ mạng hiện tại, không phải lỗi code (3 unit test suite pass)
- Slice 5–6: chưa bắt đầu

### Bước tiếp theo
1. Chạy lại job thật cho bocongan.gov.vn khi mạng không còn bị Incapsula WAF chặn (thử lại sau vài giờ/vài ngày, hoặc từ mạng khác) — code + migration đã sẵn sàng, chỉ còn thiếu bước verify bằng dữ liệu thật
2. Bắt đầu Slice 5 (UX & vận hành hoàn chỉnh: trang lịch sử báo cáo `GET /api/reports/history`, error handling đầy đủ theo [10 · Error Handling](.claude/rules/10-error-handling.md) — còn thiếu JS-render fallback Playwright)

### Quyết định quan trọng & lý do
| Quyết định | Lý do |
|---|---|
| Không build social media (Facebook/YouTube/TikTok/Zalo) trong MVP | Cần API xác thực riêng, nội dung video không hợp pipeline text-crawl → AI-classify hiện tại; pilot test chỉ 11/40 kênh (toàn website) crawl được |
| Output báo cáo chỉ gồm `Report.docx` + `JSON raw data` | Tránh scope creep so với các file phụ liệt kê trong `sample_report_form.docx` (Dataset.csv, Chart.png...) |
| `emotion` (6 lớp) lấy cùng 1 lần gọi Ollama với `sentiment` | Báo cáo cần Bảng 3.15 tách biệt sentiment 3 lớp; gộp vào 1 lần gọi để tránh round-trip thứ 2 |
| Lọc lại theo `published_at` thật sau khi fetch bài, không chỉ tin sitemap `<lastmod>` | Một số nguồn (VD bocongan.gov.vn) ghi `<lastmod>` giống nhau cho mọi URL, không phải ngày đăng thật |
| Listing-page crawler chỉ hỗ trợ 1 trang, không phân trang | cơ chế này tạm không còn nguồn thật nào dùng — vẫn giữ lại làm fallback tổng quát |
| `_SITEMAP_DATE_PATTERNS`: dict domain → regex riêng (thay 2 regex chung `_DATE_RANGE_RE`/`_YEAR_MONTH_RE`) | Mỗi site có format URL khác nhau; thêm nguồn mới = thêm 1 entry, không ảnh hưởng site khác. Domain không khai pattern → skip |
| Một số site sẽ bỏ ưu tiên sitemap và sẽ được xử lý với cách riêng tương ứng theo từng site (ví dụ: theo chuyên mục, CSS Selector,...) |
| `_get_candidates()` ưu tiên `parsing_rules.listing_pages` cao nhất, kể cả khi `source.sitemap_url` vẫn còn giá trị trong DB |
| Crawl phân trang trong từng chuyên mục — CHƯA LÀM ở giai đoạn này |
| `parsing_rules.sitemap_pages` lưu ở DB (JSONB), không chuyển sang file JSON trong code hay hardcode dict trong `sitemap.py` | Cân nhắc 3 phương án cùng user (DB JSONB / code dict giống `_SITEMAP_DATE_PATTERNS` / 1 file JSON chung cho tất cả nguồn). Giữ DB JSONB để nhất quán với `listing_pages` (BoCongAn) — cùng 1 nguồn không nên tách config ra 2 nơi (DB cho CSS selector + file cho URL); sửa qua SQL/migration không cần rebuild code, trong khi 2 phương án kia đều cần sửa code + rebuild `celery-worker`. User đề xuất thêm tab quản lý `parsing_rules` qua Admin UI ở Slice 6 tương lai — xem note ở Slice 6 |

### Vấn đề cần làm rõ (chưa chốt)
- **Kết quả AI không đảm bảo giống hệt nhau giữa các lần phân tích cùng 1 bài (phát hiện khi review plan bỏ dedup xuyên job, 2026-07-09):** `qwen3:8b` qua Ollama không set `temperature`/seed cố định — nếu 2 job trùng phạm vi ngày cùng phân tích 1 bài, `topics`/`sentiment`/`emotion`/`confidence` có thể khác nhau giữa 2 lần. Chưa xử lý (chưa set temperature/seed, chưa có cảnh báo trong report) — theo dõi thêm khi có dữ liệu thật từ nhiều job trùng phạm vi, cân nhắc set `temperature=0` nếu Ollama/`qwen3:8b` hỗ trợ. Xem [07 · AI Pipeline](.claude/rules/07-ai-pipeline.md)
- **Theo dõi kích thước bảng `articles` sau khi bỏ dedup xuyên job (2026-07-09):** mỗi job trùng phạm vi ngày với job trước sẽ thêm 1 bộ dòng mới (không tái sử dụng dòng cũ) — bảng phình to không giới hạn theo thời gian nếu user tạo report định kỳ trùng lịch. Chưa có ngưỡng cảnh báo hay kế hoạch dọn dẹp cụ thể — định kỳ kiểm tra `SELECT count(*) FROM articles`, nếu vượt mốc ước tính (VD >100,000 dòng) thì lên kế hoạch 1 slice archival/cleanup (ngoài phạm vi hiện tại)
- **Số nguồn Slice 2 hiện đạt 7 (không phải ước tính gốc 8–10; theo `content_survey.docx` con số thực tế nên là ~11–12, khớp pilot test 11/40 — chưa sửa số trong roadmap)** — đã xác nhận 7 nguồn crawl được thật (VTV+VOV+VietnamPlus+CAND+BoCongAn+TinGia+Vietnam.vn, thêm Vietnam.vn 2026-07-08 sau khi Slice 2 "hoàn thành" ban đầu ở mức 6); qdnd.vn bị loại do lỗi redirect-loop chưa rõ nguyên nhân (xem bảng quyết định); chinhphu.vn/mod.gov.vn/bvhttdl.gov.vn không có bài chuyên tin giả theo khảo sát thật — người dùng đã xác nhận 6 nguồn là đủ cho slice này trước đó, Vietnam.vn là bổ sung thêm theo yêu cầu mới, không ép đủ số 8–10

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
- [x] Listing page crawler (fallback khi nguồn không có sitemap) — `backend/crawler/listing.py`, phạm vi 1 trang không phân trang (YAGNI). **Cập nhật 2026-07-08:** tingia.gov.vn (nguồn từng dùng nhánh này) đã chuyển sang sitemap curated — cơ chế 1-trang trong `listing.py` giữ nguyên (fallback tổng quát cho nguồn tương lai không có sitemap) nhưng hiện không có nguồn thật nào đang dùng
- [x] Config & test 7 nguồn thực tế (VTV, VOV, VietnamPlus, CAND, BoCongAn, TinGia, Vietnam.vn — thêm sau khi Slice 2 "hoàn thành" ban đầu, vẫn ít hơn ước tính gốc 8–10, xem "Vấn đề cần làm rõ" dưới) — toàn bộ 6 nguồn mới dùng engine Crawl4AI (`parsing_rules.engine = "crawl4ai"`), không viết CSS selector tay
- [x] FE: sidebar chọn nhiều nguồn (search, group theo nhóm kênh), tag nguồn đã chọn, summary card ước tính số bài/thời gian, preset ngày (7/30/90/150), warning khi ≥5 nguồn & ≥60 ngày
- **Verify:** crawl thành công 6 nguồn thực tế đã config (cả sitemap và fallback listing); test trùng URL bị dedup đúng (không insert lại) — **đã verify ở mức unit test + migration thật** (sitemap/listing parser, dispatch chiến lược, lọc ngày đăng thật sau fetch, seed 6 nguồn qua `alembic upgrade head`), và đã chạy job thật end-to-end thành công với VOV (2026-06-30, 4/4 bài crawl + AI phân tích xong, `.docx`/`.json` hợp lệ). Cách crawl BoCongAn dùng ở lần verify này (sitemap phẳng) đã lỗi thời — sitemap sau đó được xác nhận đóng băng hoàn toàn (2026-07-07) và đã thay bằng `listing_pages`, xem "Multi-listing-page cho bocongan.gov.vn" ở "Đã hoàn thành"

### Slice 3 — AI pipeline đầy đủ
- [x] Prompt phân loại đầy đủ 8 nhóm chủ đề + keyword + sentiment + `emotion` (6 lớp) — thực ra đã xong từ Slice 1 (`backend/ai/prompts/v1.py`), Slice 3 chỉ xác nhận qua verify dữ liệu thật (xem dưới), không viết `v2.py` mới
- [x] Batch processing + tối ưu tốc độ — `AI_CONCURRENCY` (mặc định 1) + `analyze_articles_batch()` (asyncio.Semaphore + gather), track `ai_model` song song `prompt_version`
- [x] Đánh giá & tinh chỉnh prompt trên dữ liệu thật
- **Verify:** chạy AI trên **15 bài thực tế** (giảm từ ước tính ban đầu ≥50 bài — tránh chạy AI liên tục >1 tiếng hại phần cứng laptop CPU-only, xem bảng quyết định); `confidence < 0.6` → `needs_review=true` đúng ngưỡng; JSON lỗi → retry 1 lần → skip nếu vẫn lỗi (test case JSON không hợp lệ) — **đã verify job thật thành công 2 giai đoạn (2026-07-09)**, xem "Trạng thái hiện tại"

### Slice 4 — Report đầy đủ
- [x] Aggregate query đầy đủ: GROUP BY nguồn/chủ đề/tháng/sentiment/emotion
- [x] Build DOCX template đầy đủ theo `sample_report_form.docx` + placeholder map
- [x] Kiểm tra output với dữ liệu thật
- **Verify:** file `.docx` sinh ra khớp cấu trúc `sample_report_form.docx`; số liệu từng bảng khớp với query DB trực tiếp (so sánh tay ít nhất 2-3 bảng)

### Slice 5 — UX & vận hành hoàn chỉnh
- [x] Job status polling + progress UI chi tiết (`crawled/analyzed/total_estimated`) — đã làm ở Slice 1, mở rộng thêm bảng crawl trực tiếp + Cancel (xem Slice 1)
- [ ] Trang lịch sử báo cáo (`GET /api/reports/history`)
- [ ] Error handling đầy đủ theo [10 · Error Handling](.claude/rules/10-error-handling.md) (retry, timeout, JS-render fallback Playwright) — **đã làm trước 1 phần:** AI timeout chỉ skip 1 bài (không fail cả job), crawler lỗi (article + sub-sitemap) hiện `status="error"` trên UI; **còn thiếu:** JS-render fallback Playwright chưa làm
- **Verify:** giả lập timeout/JSON lỗi/nguồn bị block → job xử lý đúng theo bảng error-handling, không crash toàn job

### Slice 6 — Admin UI quản lý nguồn
- [ ] CRUD metadata nguồn (name/URL/active toggle) — không tự thêm parsing rule mới qua UI
- **Verify:** thêm/sửa/xoá nguồn qua UI; nguồn mới active hiển thị đúng ở sidebar chọn nguồn (Slice 2)
- **Ý tưởng chưa chốt (2026-07-08, do user đề xuất khi bàn về nơi lưu `parsing_rules` cho TinGia):** thêm 1 tab riêng trong Admin UI cho phép xem/sửa `parsing_rules` (CSS selector, `listing_pages`, `sitemap_pages`...) trực tiếp qua UI thay vì phải migration/SQL. Hiện **trái với quyết định đã chốt** ở dòng "Admin UI (Slice 6) chỉ CRUD metadata nguồn, không cho thêm parsing rule qua UI" (xem bảng quyết định) — cần bàn riêng nếu muốn đổi scope Slice 6, vì mỗi loại nguồn (sitemap curated/listing-page nhiều trang/CSS selector tay) cần 1 dạng form khác nhau, không phải 1 form CRUD đơn giản

**Timeline (không đổi so với breakdown cũ):**
- Best case: ~7 tuần
- Realistic: 9–10 tuần (khuyến nghị dùng để plan)
- Worst case: 11–12 tuần
