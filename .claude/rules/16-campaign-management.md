---
description: Campaign Management — business rules Campaign & Source, rationale gộp Job
alwaysApply: false
---

# 16 · Campaign Management

> **Trạng thái: `[CHƯA CODE]`.** Campaign thay thế hoàn toàn mô hình Job on-demand hiện tại (bảng `jobs`, xem [03 · Database Schema](03-database-schema.md)) — không giữ 2 hệ thống song song. Schema (`campaigns, keywords, campaign_keywords, campaign_sources, campaign_articles`): xem [03 · Database Schema](03-database-schema.md). API (`/api/campaigns/*`): xem [05 · API Contracts](05-api-contracts.md). Màn hình: xem [09 · Frontend UI](09-frontend-ui.md).

## Business Rules — Chiến dịch (BR-CAMP)

- **BR-CAMP-01:** Chiến dịch phải có Tên, Thời gian bắt đầu, Người phụ trách (`owner_id`).
- **BR-CAMP-02:** Trạng thái: `DRAFT → ACTIVE → PAUSED/COMPLETED → ARCHIVED`.
- **BR-CAMP-03:** Chỉ chuyển được sang `ACTIVE` khi có **≥1 nguồn dữ liệu VÀ ≥1 từ khóa**. Từ khóa dùng để **lọc phạm vi** (không chỉ gắn nhãn) — matching diễn ra ở bước **hậu-crawl** (không lọc ngay tại bước crawl thô, vì 1 Nguồn có thể dùng chung cho nhiều Campaign khác nhau) — xem [17 · Continuous Crawler & Scheduler](17-continuous-crawler-scheduler.md).
- **BR-CAMP-04:** Chiến dịch `ARCHIVED` chỉ được xem, không được sửa hoặc kích hoạt lại.
- **BR-CAMP-05:** Không xóa vật lý chiến dịch đã có dữ liệu — chỉ cho phép chuyển `ARCHIVED` (dừng crawl, giữ nguyên dữ liệu cũ).
- **BR-CAMP-06:** 1 Chiến dịch có thể theo dõi nhiều Nguồn; 1 Nguồn có thể được dùng ở nhiều Chiến dịch (N:N).
- **BR-CAMP-07:** Campaign có `mode = CONTINUOUS` (mặc định, giám sát liên tục) hoặc `ONE_SHOT` (crawl đúng 1 lần theo `start_date`/`end_date` rồi tự `COMPLETED`, không đăng ký Celery Beat — **thay thế hoàn toàn** Job cũ, không còn API `POST /api/reports/create` riêng, mọi report tạo qua `POST /api/campaigns`).

**Vì sao gộp Job vào Campaign (không tách 2 hệ thống):** với công tắc `AI_AUTO_TRIGGER` đã có ([17 · Continuous Crawler & Scheduler](17-continuous-crawler-scheduler.md)), khác biệt duy nhất còn lại giữa "Job" và "Campaign" chỉ là "crawl 1 lần" vs "crawl lặp lại theo lịch" — không đáng tách 2 schema/API riêng, gây trùng lặp logic không cần thiết. UI có thể vẫn gọi `mode=ONE_SHOT` là "Tạo báo cáo nhanh" để giữ trải nghiệm quen thuộc, nhưng lưu chung 1 bảng `campaigns`.

## Business Rules — Nguồn dữ liệu (BR-SRC, bổ sung cho `sources` hiện có)

- **BR-SRC-01:** Mỗi nguồn thuộc đúng 1 Nhóm nguồn (VD: Chính phủ, Bộ ngành, Báo chí) — quản trị qua Admin.
- **BR-SRC-02:** URL/domain của nguồn duy nhất trong toàn hệ thống (không đổi, đã áp dụng).
- **BR-SRC-03:** Trạng thái nguồn mở rộng: `ACTIVE` (đang crawl bình thường), `INACTIVE` (tắt thủ công), `ERROR` (tự động chuyển khi crawl lỗi liên tiếp quá **10 lần** — ngưỡng khởi điểm, sẽ điều chỉnh lại sau khi có dữ liệu vận hành thật).
- **BR-SRC-04:** Nguồn `INACTIVE`/`ERROR` không được đưa vào lịch crawl tự động.
- **BR-SRC-05:** Không được xóa nguồn đang được tham chiếu bởi ít nhất 1 Chiến dịch `ACTIVE`.

## Đường di chuyển từ mô hình Job hiện tại

1 bài viết không còn gắn cứng với 1 lần chạy cụ thể nào. Khi build Report (dù `mode=ONE_SHOT` hay `CONTINUOUS`), hệ thống xác định "bài nào thuộc báo cáo này" bằng cách lọc `source_id` (qua `campaign_sources`) kết hợp khoảng ngày (`published_at` trong `start_date`–`end_date`) — không dùng FK trực tiếp từ `articles` tới `campaigns`. Rủi ro migrate lớn nhất: `jobs.source_ids UUID[]` hiện tại (mảng, không FK) phải migrate sang `campaign_sources` (N:N có FK) nếu muốn giữ lịch sử report cũ liên kết được.
