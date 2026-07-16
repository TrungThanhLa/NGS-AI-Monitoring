# Nhật ký triển khai — mô hình on-demand (Slice 0–6)

> **Đây là nhật ký lịch sử những gì đã hiện thực được tới nay (Slice 0–5, đang chạy thật trên `main`), không phải mô tả một giai đoạn sản phẩm ("MVP") đã hoàn chỉnh và đúng đắn.** Mô hình on-demand (1 Job = 1 lần chạy trọn vẹn, không giám sát liên tục, chưa có Auth/Alert/Case) là cách hiện thực **chưa đúng/chưa đủ** so với nghiệp vụ đúng duy nhất của dự án (xem [01 · Project Overview](../.claude/rules/01-project-overview.md)) — đang được sửa/bổ sung theo [ROADMAP_CONTINUOUS_MONITORING.md](ROADMAP_CONTINUOUS_MONITORING.md), không phải "phát triển tiếp lên trên nền đã đúng". Slice 6 (Admin UI quản lý nguồn) đã bỏ khỏi scope thực thi trực tiếp — xem lý do ở cuối file.
>
> Di dời từ `CLAUDE.md` (2026-07-16) để giảm dung lượng file gốc.
>
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
- **Mở rộng thêm sau khi verify** (đã merge `main` cùng đợt): bảng crawl trực tiếp + benchmark thời gian, hủy job (Cancel), giới hạn `MAX_ARTICLES_PER_JOB`, khôi phục job sau F5, fix AI timeout/crawler error-handling — xem "Quyết định quan trọng & lý do" ở `CLAUDE.md`

### Slice 2 — Nhiều nguồn + listing-page fallback
- [x] Listing page crawler (fallback khi nguồn không có sitemap) — `backend/crawler/listing.py`, phạm vi 1 trang không phân trang (YAGNI). **Cập nhật 2026-07-08:** tingia.gov.vn (nguồn từng dùng nhánh này) đã chuyển sang sitemap curated — cơ chế 1-trang trong `listing.py` giữ nguyên (fallback tổng quát cho nguồn tương lai không có sitemap) nhưng hiện không có nguồn thật nào đang dùng
- [x] Config & test 7 nguồn thực tế (VTV, VOV, VietnamPlus, CAND, BoCongAn, TinGia, Vietnam.vn — thêm sau khi Slice 2 "hoàn thành" ban đầu, vẫn ít hơn ước tính gốc 8–10, xem "Vấn đề cần làm rõ" ở `CLAUDE.md`) — toàn bộ 6 nguồn mới dùng engine Crawl4AI (`parsing_rules.engine = "crawl4ai"`), không viết CSS selector tay
- [x] FE: sidebar chọn nhiều nguồn (search, group theo nhóm kênh), tag nguồn đã chọn, summary card ước tính số bài/thời gian, preset ngày (7/30/90/150), warning khi ≥5 nguồn & ≥60 ngày
- **Verify:** crawl thành công 6 nguồn thực tế đã config (cả sitemap và fallback listing); test trùng URL bị dedup đúng (không insert lại) — **đã verify ở mức unit test + migration thật** (sitemap/listing parser, dispatch chiến lược, lọc ngày đăng thật sau fetch, seed 6 nguồn qua `alembic upgrade head`), và đã chạy job thật end-to-end thành công với VOV (2026-06-30, 4/4 bài crawl + AI phân tích xong, `.docx`/`.json` hợp lệ). Cách crawl BoCongAn dùng ở lần verify này (sitemap phẳng) đã lỗi thời — sitemap sau đó được xác nhận đóng băng hoàn toàn (2026-07-07) và đã thay bằng `listing_pages`, xem "Multi-listing-page cho bocongan.gov.vn" ở `CLAUDE.md`

### Slice 3 — AI pipeline đầy đủ
- [x] Prompt phân loại đầy đủ 8 nhóm chủ đề + keyword + sentiment + `emotion` (6 lớp) — thực ra đã xong từ Slice 1 (`backend/ai/prompts/v1.py`), Slice 3 chỉ xác nhận qua verify dữ liệu thật (xem dưới), không viết `v2.py` mới
- [x] Batch processing + tối ưu tốc độ — `AI_CONCURRENCY` (mặc định 1) + `analyze_articles_batch()` (asyncio.Semaphore + gather), track `ai_model` song song `prompt_version`
- [x] Đánh giá & tinh chỉnh prompt trên dữ liệu thật
- **Verify:** chạy AI trên **15 bài thực tế** (giảm từ ước tính ban đầu ≥50 bài — tránh chạy AI liên tục >1 tiếng hại phần cứng laptop CPU-only); `confidence < 0.6` → `needs_review=true` đúng ngưỡng; JSON lỗi → retry 1 lần → skip nếu vẫn lỗi (test case JSON không hợp lệ) — **đã verify job thật thành công 2 giai đoạn (2026-07-09)**

### Slice 4 — Report đầy đủ
- [x] Aggregate query đầy đủ: GROUP BY nguồn/chủ đề/tháng/sentiment/emotion
- [x] Build DOCX template đầy đủ theo `sample_report_form.docx` + placeholder map
- [x] Kiểm tra output với dữ liệu thật
- **Verify:** file `.docx` sinh ra khớp cấu trúc `sample_report_form.docx`; số liệu từng bảng khớp với query DB trực tiếp (so sánh tay ít nhất 2-3 bảng)

### Slice 5 — UX & vận hành hoàn chỉnh
- [x] Job status polling + progress UI chi tiết (`crawled/analyzed/total_estimated`) — đã làm ở Slice 1, mở rộng thêm bảng crawl trực tiếp + Cancel (xem Slice 1)
- [x] Trang lịch sử báo cáo (`GET /api/reports/history`)
- [x] Error handling đầy đủ theo [10 · Error Handling](../.claude/rules/10-error-handling.md) (retry, timeout, JS-render fallback Playwright) — hoàn thành
- **Verify:** giả lập timeout/JSON lỗi/nguồn bị block → job xử lý đúng theo bảng error-handling, không crash toàn job

### Slice 6 — Admin UI quản lý nguồn — ❌ ĐÃ BỎ KHỎI SCOPE MVP (2026-07-16)
- [ ] ~~CRUD metadata nguồn (name/URL/active toggle) — không tự thêm parsing rule mới qua UI~~
- **Quyết định:** loại khỏi phạm vi MVP — MVP coi như hoàn thành ở Slice 0–5. Quản lý nguồn tiếp tục qua migration/SQL trực tiếp như hiện tại (đủ dùng cho quy mô ~7 nguồn hiện có). Nếu cần Admin UI cho nguồn trong tương lai, cân nhắc gộp vào roadmap Continuous Monitoring (VD phần "Cấu hình hệ thống" ở [15 · Auth & RBAC](../.claude/rules/15-auth-rbac.md)) thay vì làm riêng lẻ.
- Ý tưởng "tab quản lý `parsing_rules` qua UI" (2026-07-08) — không còn liên quan vì Slice 6 đã bỏ.

**Timeline:** ước tính ban đầu (7–12 tuần, gồm cả Slice 6) không còn áp dụng — MVP hoàn thành ở Slice 5, không cần tính tiếp mốc thời gian cho Slice 6.
