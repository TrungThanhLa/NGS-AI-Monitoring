---
description: Xử lý ngoại lệ — crawler, AI, dedup, job timeout
alwaysApply: true
---

# Ngoại lệ & Cách xử lý

| Tình huống | Xử lý |
|---|---|
| Crawler timeout / bị block (1 bài viết cụ thể) | Retry 3 lần (exponential backoff); hết retry hoặc không parse được title/content → insert row `Article` với `status="error"` (hiện trên bảng crawl trực tiếp ở FE, URL thay tên vì không có title) + log cảnh báo phía server, tiếp tục bài kế tiếp. **Riêng nguồn dùng engine Crawl4AI** (`parsing_rules.engine="crawl4ai"`): không tự retry — lỗi/thiếu title/content trả `None` ngay, vẫn rơi vào đúng nhánh insert `status="error"` này (2026-06-29) |
| Sub-sitemap lỗi (1 khối ngày của sitemap VTV không tải được) | Retry 3 lần; hết retry → log cảnh báo phía server **và** insert row `Article` với `status="error"` (`url` = URL sub-sitemap lỗi, `title=null`, hash `SHA256(url)` như mọi trường hợp khác — không còn cần mẹo né UNIQUE đơn, đã đổi sang composite `(job_id, url_hash)` từ 2026-07-09) → hiện trên bảng crawl trực tiếp ở FE, bỏ qua khối đó, tiếp tục các sub-sitemap khác (2026-06-26) |
| Website không có sitemap | Tự động fallback sang listing page crawler (chưa code — Slice 2) |
| Dữ liệu trùng lặp | Check SHA256(url) **trong phạm vi 1 job** (`set()` cục bộ + `UNIQUE` composite `(job_id, url_hash)` ở DB) — không dedup xuyên job (2026-07-09, xem "Quyết định quan trọng") |
| Bài viết crawl được nhưng ngày đăng thật nằm ngoài `date_from`/`date_to` yêu cầu | Bỏ qua âm thầm, không insert (không phải lỗi) — cần thiết vì 1 số nguồn có sitemap không lọc được chính xác theo ngày trước khi fetch (VD `bocongan.gov.vn` ghi `<lastmod>` giống nhau cho mọi URL, không phải ngày đăng thật) (2026-06-29) |
| AI confidence < 0.6 | Flag `needs_review=true`, vẫn lưu và đưa vào báo cáo |
| AI trả về JSON không hợp lệ | Parse với try/except, retry 1 lần, nếu vẫn lỗi thì skip bài đó (`status="error"`) |
| Nội dung bài viết dài hơn `AI_MAX_CONTENT_LENGTH` | Cắt tại ranh giới câu gần nhất (`.`, `!`, `?`, xuống dòng) trước khi gửi AI, không cắt cứng giữa câu/từ — xem [07 · AI Pipeline](.claude/rules/07-ai-pipeline.md) |
| AI timeout (gọi Ollama quá `AI_TIMEOUT_SECONDS`, đã xảy ra thật — `qwen3:8b` CPU-only có lúc >120s) | Bắt `httpx.HTTPError` (không chỉ `ValueError`) trong `_analyze_articles` → skip đúng 1 bài (`status="error"`), tiếp tục các bài còn lại, job vẫn sinh được báo cáo. **Lưu ý lịch sử:** ban đầu code chỉ bắt `ValueError`, khiến timeout làm fail cả job — đã sửa (Slice 1 mở rộng) |
| Người dùng hủy job (Cancel) | `POST /api/reports/{job_id}/cancel` → Celery `revoke(task_id, terminate=True)` nếu `celery_task_id` có giá trị, set `status="cancelled"`. Task bị kill bằng SIGTERM (không phải Python exception) nên tự nó không cập nhật được status — endpoint tự set. Dữ liệu `articles` (giai đoạn crawl) đã insert dở trước khi hủy vẫn giữ lại — commit ngay từng bài. **Cập nhật (Slice 3, 2026-07-08):** `article_analysis` (giai đoạn phân tích AI) KHÔNG còn đảm bảo giữ được durability theo từng bài — `_analyze_articles` gửi cả batch `pending` vào 1 lệnh `analyze_articles_batch()` duy nhất, chỉ ghi DB sau khi *toàn bộ* batch trả về kết quả; nếu job chết giữa lúc batch đang chạy (khả năng cao nhất khi bị Cancel/crash, vì đây là bước chiếm gần hết thời gian chạy), **mất trắng kết quả AI của cả batch đó**, kể cả bài đã phân tích xong trong bộ nhớ nhưng chưa kịp ghi DB |
| Job chạy quá lâu | Chạy nền qua Celery, FE polling mỗi 3 giây; người dùng có thể Cancel chủ động (xem trên); FE tự khôi phục theo dõi job qua `sessionStorage` nếu reload trang giữa lúc job đang chạy |
| Website dùng JavaScript render | Playwright thay thế httpx cho nguồn đó qua `parsing_rules.engine="playwright"` — retry 3 lần exponential backoff như httpx (không phải ngoại lệ như Crawl4AI) |
