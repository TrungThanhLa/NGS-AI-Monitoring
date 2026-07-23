---
description: Matching từ khóa hậu-crawl, Content review workflow, AI_AUTO_TRIGGER
alwaysApply: false
---

# 17 · Continuous Crawler & Scheduler

> **Trạng thái: `[ĐÃ CODE]` Celery Beat/`crawl_queue`/matching từ khóa/`AI_AUTO_TRIGGER` (Phase 3) — `[CHƯA CODE]` Content review (`articles.review_status`, `/api/contents/*`, Phase 4).** Cơ chế Celery Beat theo Nguồn, `crawl_queue` 2 giai đoạn, dedup toàn cục theo Source: xem [06 · Crawler Strategy](06-crawler-strategy.md). Schema (`crawl_queue`, `articles.review_status`): xem [03 · Database Schema](03-database-schema.md). API (`/api/contents/*`): xem [05 · API Contracts](05-api-contracts.md).

## Crawl ONE_SHOT — đường xử lý riêng, tách khỏi Celery Beat của CONTINUOUS `[ĐÃ CODE — 2026-07-23]`

Celery Beat (`scheduler.check_due_sources`, mỗi 60s) chỉ duyệt Nguồn thuộc Campaign `CONTINUOUS` — Campaign `ONE_SHOT` **không** đăng ký Beat (BR-CAMP-07, [16 · Campaign Management](16-campaign-management.md)), crawl ngay lúc `activate` qua `chord` các task `campaign_tasks.crawl_campaign_source_once(campaign_id, source_id, date_from, date_to)` (1 task/Nguồn, callback `mark_crawl_done` chuyển Campaign sang `COMPLETED` sau khi tất cả xong).

`crawl_campaign_source_once` **không** dùng chung `continuous_crawl.crawl_task` — Discover đúng phạm vi `date_from`/`date_to` của Campaign (gọi lại `_get_candidates` sẵn có, không đổi), tái sử dụng `Article` đã crawl trước đó theo `url_hash` thay vì fetch lại. Lý do tách riêng: dùng chung `crawl_task` (thiết kế cho CONTINUOUS, quét cửa sổ `_DISCOVER_LOOKBACK_DAYS=30` ngày + rút cạn toàn bộ backlog `crawl_queue` của Nguồn) từng khiến 1 Campaign ONE_SHOT nhỏ kéo theo crawl ~4300 URL backlog của Nguồn, chạy hàng giờ thay vì đúng vài phút theo phạm vi ngày đã chọn — phát hiện qua smoke test Docker thật.

Tiến độ ghi vào bảng `campaign_crawl_progress` (`total_urls`/`done_urls`/`status` theo từng cặp Campaign-Nguồn, xem [03 · Database Schema](03-database-schema.md)) — đọc qua `GET /api/campaigns/{id}/crawl-progress` ([05 · API Contracts](05-api-contracts.md)). Kích hoạt lại 1 Campaign ONE_SHOT sau khi đã Pause giữa chừng: dòng tiến độ cũ bị xóa và tạo lại (không cộng dồn với lượt trước).

## CONTINUOUS tự chuyển `COMPLETED` khi tới `end_date` `[ĐÃ CODE — 2026-07-23]`

`complete_expired_continuous_campaigns()` (`backend/workers/scheduler.py`) chạy ở đầu mỗi chu kỳ `check_due_sources` (Beat, 60s) — độc lập với công tắc `SCHEDULER_ENABLED` (vòng đời Campaign không phụ thuộc việc crawl có đang bật hay không). Campaign `CONTINUOUS` đang `ACTIVE` mà `end_date` đã qua → tự chuyển `COMPLETED`, không đụng Campaign còn hạn/`PAUSED`/`ONE_SHOT`.

## Matching từ khóa (hậu-crawl, không lọc tại bước crawl)

Ngay sau khi crawl xong, với **mỗi Campaign `ACTIVE`** đang theo dõi `source_id` đó: so khớp bài mới (text matching đơn giản trên tiêu đề/nội dung, không cần AI) với từ khóa của Campaign đó → ghi vào `campaign_articles`. Xem lý do thiết kế và bảng schema ở [16 · Campaign Management](16-campaign-management.md).

## Nội dung (Content) — trạng thái đánh giá nghiệp vụ

- **BR-CONTENT-01:** Một nội dung tối thiểu phải có URL và (Tiêu đề hoặc Nội dung văn bản).
- **BR-CONTENT-02:** Trạng thái đánh giá nghiệp vụ `NEW → REVIEWED → NEED_VERIFY → VERIFIED / NOT_RELEVANT → CASE_CREATED` — **tách biệt** với trạng thái kỹ thuật hiện có (`pending_analysis/analyzed/error`), không gộp chung 1 cột.
- **BR-CONTENT-03:** Chỉ `ANALYST` và `MANAGER` được thay đổi trạng thái đánh giá nghiệp vụ.
- **BR-CONTENT-04:** Nội dung chỉ được xóa mềm, không xóa vật lý.

**Screens:** `/contents` (List), `/contents/:id` (Detail — nội dung đầy đủ + kết quả AI + form đánh giá + cảnh báo/vụ việc liên quan) — xem [09 · Frontend UI](09-frontend-ui.md).

## AI trigger — công tắc `AI_AUTO_TRIGGER`

Tách rời "crawl tự động theo lịch" khỏi "AI phân tích" — điều khiển bằng 1 giá trị lưu ở bảng `system_settings` ([15 · Auth & RBAC](15-auth-rbac.md), không dùng `.env` vì cần đổi được mà không redeploy/restart):

- `AI_AUTO_TRIGGER=false` (khuyến nghị khi tự build server AI riêng — tránh chạy phần cứng liên tục 24/7): crawl xong, bài viết giữ `pending_analysis`, KHÔNG tự động chạy AI. Người dùng chủ động bấm nút xử lý phần tồn đọng.
- `AI_AUTO_TRIGGER=true` (khuyến nghị khi dùng API LLM trả phí): crawl xong tự động enqueue AI ngay.
- Độc lập với `AI_PROVIDER` ([07 · AI Pipeline](07-ai-pipeline.md)) — cấu hình riêng từng biến, không suy luận cái này từ cái kia.
- **Chỉ `ADMIN` được sửa** (permission `system.configure`). Nếu triển khai trước khi Auth/RBAC hoàn thiện, tạm giới hạn sửa qua DB trực tiếp, không lộ ra API/UI công khai.
- **Đánh đổi:** khi tắt, Alert `HIGH_ATTENTION`/`NEGATIVE_TREND` (cần `sentiment`/`confidence` từ AI) mất tính năng "báo ngay lúc phát sinh" — chỉ có sau khi bấm chạy AI. Riêng `KEYWORD_SPIKE` (đếm khớp từ khóa trên nội dung thô) vẫn tính ngay lúc crawl xong.

**Tải hệ thống khi vẫn dùng Ollama local (CPU-only):** giữ `AI_CONCURRENCY` thấp (1–2), cân nhắc giới hạn số Campaign `ACTIVE` đồng thời (VD 3-5) ở giai đoạn đầu để tránh nghẽn AI queue. Khuyến nghị mặc định `AI_AUTO_TRIGGER=false` cho tới khi hạ tầng AI đủ mạnh.
