---
description: Alert & Case Management — business rules, rule engine tối giản
alwaysApply: false
---

# 18 · Alert & Case Management

> **Trạng thái: `[CHƯA CODE]`.** Report ([08 · DOCX Report](08-docx-report.md)) **không phụ thuộc** 2 module này — có thể code Report ngay sau [16 · Campaign Management](16-campaign-management.md) + [17 · Continuous Crawler & Scheduler](17-continuous-crawler-scheduler.md), không cần đợi Alert/Case xong. Trong lúc chưa có backend thật, FE dùng UI tĩnh (mock) cho trang Alert/Case, đúng pattern đã áp dụng cho các trang mock hiện có ([09 · Frontend UI](09-frontend-ui.md)). Schema (`alert_rules, alerts, cases, case_articles, case_attachments`): xem [03 · Database Schema](03-database-schema.md). API: xem [05 · API Contracts](05-api-contracts.md).

## Business Rules — Cảnh báo (BR-ALERT)

- **BR-ALERT-01:** 3 loại cảnh báo khởi điểm, tận dụng dữ liệu AI đã có sẵn (không cần thêm field mới):
  - `HIGH_ATTENTION` — nội dung có `confidence` cao và `sentiment=negative`.
  - `NEGATIVE_TREND` — tỷ lệ nội dung `sentiment=negative` tăng bất thường trong khoảng thời gian ngắn cho cùng 1 Campaign.
  - `KEYWORD_SPIKE` — số lượng nội dung trúng 1 từ khóa cụ thể tăng đột biến so với trung bình các ngày trước (tính được ngay lúc crawl xong, không cần AI).
- **BR-ALERT-02:** Mức độ: `LOW, MEDIUM, HIGH, CRITICAL`.
- **BR-ALERT-03:** Sinh tự động khi điều kiện rule thỏa mãn — mỗi Campaign có thể có `alert_threshold` riêng.
- **BR-ALERT-04:** Trạng thái: `NEW → ACKNOWLEDGED → PROCESSING → RESOLVED → CLOSED`.
- **BR-ALERT-05:** Chỉ `MANAGER` và `ADMIN` được đóng (`CLOSED`) 1 cảnh báo.
- **BR-ALERT-06:** 1 cảnh báo có thể gắn 1 nội dung cụ thể, hoặc không gắn nội dung nào (cảnh báo tổng hợp theo xu hướng, VD `NEGATIVE_TREND`/`KEYWORD_SPIKE`).
- **Quan hệ với `needs_review` (AI):** `article_analysis.needs_review` là tín hiệu **kỹ thuật** (AI không chắc chắn, `confidence < 0.6`) — Alert là tín hiệu **nghiệp vụ** (cần con người chú ý). **Không coi 2 khái niệm này là một.**

## Alert Rule Engine — tối giản, không phải rule engine phức tạp

Không xây "rule engine" tổng quát cấu hình qua UI ngay từ đầu — bắt đầu bằng rule cứng trong code:

```python
def check_alerts(article, analysis, campaign):
    alerts = []
    if analysis.confidence >= 0.8 and analysis.sentiment == "negative":
        alerts.append(("HIGH_ATTENTION", "HIGH"))
    # NEGATIVE_TREND, KEYWORD_SPIKE: chạy theo batch định kỳ (VD mỗi giờ), so sánh số lượng
    # bài negative/từ khóa trúng trong N giờ gần nhất với trung bình các ngày trước cho cùng Campaign
    return alerts
```

Ngưỡng `confidence >= 0.8` là **giá trị khởi điểm**, chưa dựa trên dữ liệu thật — sẽ điều chỉnh lại sau khi có đủ dữ liệu từ vận hành, không coi là số liệu cuối cùng.

## Business Rules — Vụ việc (BR-CASE)

- **BR-CASE-01:** Vụ việc được tạo từ 1 Cảnh báo và/hoặc gắn với 1/nhiều Nội dung cụ thể — luôn ghi nhận người tạo (`created_by`).
- **BR-CASE-02:** Trạng thái: `NEW → VERIFYING → PROCESSING → RESOLVED → CLOSED` (5 trạng thái).
- **BR-CASE-03:** Vụ việc `CLOSED` không được sửa.
- **BR-CASE-04:** Một Nội dung có thể thuộc nhiều Vụ việc khác nhau (N:N).
- **BR-CASE-05:** Vụ việc có file đính kèm (bằng chứng, tài liệu điều tra).
- **Không tự động xuất báo cáo khi đóng Case** — Report vẫn tạo thủ công theo Campaign/khoảng ngày như bình thường, không có luồng "Case đóng → tự sinh report kèm nội dung điều tra".

## AI Phân tích — nguyên tắc không thương lượng

- **BR-AI-03:** AI **không được phép** kết luận "đây là tin giả" — chỉ gắn cờ `needs_review=true` kèm lý do, quyết định cuối cùng luôn thuộc về con người. Nguyên tắc đã có sẵn (`AI_CONFIDENCE_THRESHOLD`), giữ nguyên khi mở rộng — xem [07 · AI Pipeline](07-ai-pipeline.md).
