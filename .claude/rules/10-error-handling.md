---
description: Xử lý ngoại lệ — crawler, AI, dedup, job timeout
alwaysApply: true
---

# Ngoại lệ & Cách xử lý

| Tình huống | Xử lý |
|---|---|
| Crawler timeout / bị block (1 bài viết cụ thể) | Retry 3 lần (exponential backoff); hết retry hoặc không parse được title/content → insert row `Article` với `status="error"` (hiện trên bảng crawl trực tiếp ở FE, URL thay tên vì không có title) + log cảnh báo phía server, tiếp tục bài kế tiếp |
| Sub-sitemap lỗi (1 khối ngày của sitemap VTV không tải được) | Retry 3 lần; hết retry → log cảnh báo phía server, bỏ qua khối đó, tiếp tục các sub-sitemap khác — **chưa hiện được trên UI** (không có URL cụ thể để gắn row lỗi — xem CLAUDE.md "Vấn đề cần làm rõ") |
| Website không có sitemap | Tự động fallback sang listing page crawler (chưa code — Slice 2) |
| Dữ liệu trùng lặp | Check SHA256(url) trước khi insert — bỏ qua nếu đã tồn tại |
| AI confidence < 0.6 | Flag `needs_review=true`, vẫn lưu và đưa vào báo cáo |
| AI trả về JSON không hợp lệ | Parse với try/except, retry 1 lần, nếu vẫn lỗi thì skip bài đó (`status="error"`) |
| AI timeout (gọi Ollama quá `AI_TIMEOUT_SECONDS`, đã xảy ra thật — `qwen3:8b` CPU-only có lúc >120s) | Bắt `httpx.HTTPError` (không chỉ `ValueError`) trong `_analyze_articles` → skip đúng 1 bài (`status="error"`), tiếp tục các bài còn lại, job vẫn sinh được báo cáo. **Lưu ý lịch sử:** ban đầu code chỉ bắt `ValueError`, khiến timeout làm fail cả job — đã sửa (Slice 1 mở rộng) |
| Người dùng hủy job (Cancel) | `POST /api/reports/{job_id}/cancel` → Celery `revoke(task_id, terminate=True)` nếu `celery_task_id` có giá trị, set `status="cancelled"`. Task bị kill bằng SIGTERM (không phải Python exception) nên tự nó không cập nhật được status — endpoint tự set. Dữ liệu `articles`/`article_analysis` đã insert dở trước khi hủy vẫn giữ lại (chấp nhận được, là dữ liệu thật) |
| Job chạy quá lâu | Chạy nền qua Celery, FE polling mỗi 3 giây; người dùng có thể Cancel chủ động (xem trên); FE tự khôi phục theo dõi job qua `sessionStorage` nếu reload trang giữa lúc job đang chạy |
| Website dùng JavaScript render | Playwright thay thế httpx cho nguồn đó (chưa code — Slice 5) |
