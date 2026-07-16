# NGS Monitor — Crawler liên tục, AI Pipeline & API Contract đề xuất

> Giữ nguyên toàn bộ cơ chế crawl (sitemap/listing/Crawl4AI/Playwright) và pipeline AI hiện có (prompt versioning, 8 nhóm chủ đề, 6 nhóm cảm xúc) — xem `.claude/rules/06-crawler-strategy.md` và `.claude/rules/07-ai-pipeline.md`. File này mô tả phần **mở rộng** để hỗ trợ crawl định kỳ liên tục thay vì on-demand, và cách AI runtime chuyển đổi được sang server riêng/cloud LLM khi cần scale (xem `03_SYSTEM_ARCHITECTURE.md` mục 5).

---

## 1. Crawl liên tục — thay đổi so với hiện tại

**Hiện tại:** `POST /api/reports/create` → tạo Job → crawl 1 lần trong khoảng ngày chỉ định → kết thúc.

**Đề xuất mở rộng:** khi 1 Campaign chuyển `ACTIVE`, hệ thống tự động crawl định kỳ cho từng Source thuộc Campaign đó, theo `source.crawl_frequency` (đề xuất mặc định **1800 giây = 30 phút** cho báo điện tử — khác hẳn tần suất 5-15 phút thường thấy ở crawler mạng xã hội, vì báo điện tử VN không cập nhật nhanh bằng social feed).

```
Celery Beat (mỗi 1 phút) → kiểm tra Source nào đến hạn crawl
  → enqueue crawl_task(source_id, campaign_id)
  → crawl xong → dedup → lưu articles (dùng lại toàn bộ logic parser hiện có)
  → enqueue AI task cho các bài mới
  → AI xong → cập nhật article_analysis
  → kiểm tra AlertRule → sinh Alert nếu vượt ngưỡng
```

**Chống trùng (dedup) khi crawl liên tục:** khác với chế độ on-demand hiện tại (dedup trong phạm vi 1 job), khi crawl liên tục cần dedup theo `SHA256(url)` **toàn cục theo Source** (không giới hạn theo lần chạy) — nếu không, mỗi lần Beat trigger sẽ crawl lại toàn bộ bài cũ. Đây là thay đổi cần cân nhắc kỹ, xem `06_OPEN_DECISIONS.md`.

**Retry/timeout/delay:** giữ nguyên tham số hiện có (`CRAWLER_MAX_RETRIES=3`, `CRAWLER_TIMEOUT_SECONDS=30`, `CRAWLER_DELAY_SECONDS=1.5`).

---

## 2. AI Pipeline — không đổi logic, chỉ đổi cách trigger (và có thể đổi provider sau này)

Toàn bộ logic pipeline AI (prompt `backend/ai/prompts/v1.py`, 8 nhóm chủ đề, 6 nhóm cảm xúc, ngưỡng `confidence < 0.6 → needs_review`) giữ nguyên 100% bất kể chạy trên Ollama local hay provider khác. Thay đổi ở giai đoạn continuous crawl: thay vì AI chạy theo batch của 1 Job, AI chạy theo batch nhỏ mỗi khi có bài mới từ 1 lần crawl định kỳ.

**Công tắc `AI_AUTO_TRIGGER` — đã chốt (2026-07-16):** tách rời "crawl tự động theo lịch" khỏi "AI phân tích", điều khiển bằng 1 giá trị lưu ở bảng `system_settings` (không dùng `.env` — cần đổi được mà không phải redeploy/restart):
- `AI_AUTO_TRIGGER=false` (khuyến nghị khi tự build server AI riêng — tránh chạy phần cứng liên tục 24/7): crawl xong, bài viết giữ nguyên trạng thái `pending_analysis`, KHÔNG tự động chạy AI. Người dùng chủ động bấm nút để AI xử lý phần đang tồn đọng.
- `AI_AUTO_TRIGGER=true` (khuyến nghị khi dùng API LLM trả phí — Claude/ChatGPT/Gemini/DeepSeek): crawl xong tự động enqueue AI ngay, đúng pipeline liên tục end-to-end.
- Độc lập với `AI_PROVIDER` (mục 5, `03_SYSTEM_ARCHITECTURE.md`) — không suy luận giá trị này từ giá trị kia, cấu hình riêng từng biến.
- Có thể triển khai sớm cùng Phase 3 (Scheduler) — chỉ cần 1 dòng trong `system_settings` + 1 API đọc/ghi nhỏ, không cần đợi làm trọn Phase 9 (trang System Settings đầy đủ).
- **Quyền sửa (đã chốt 2026-07-16):** chỉ vai trò `ADMIN` được phép đổi giá trị công tắc này — dùng đúng permission `system.configure` đã có sẵn trong RBAC matrix (`04_SCREENS_UI_RBAC.md` mục 4, cột ADMIN = Y, các vai trò khác = N). Nếu triển khai công tắc này ở Phase 3 (trước khi Phase 1 Auth/RBAC hoàn thiện), tạm thời giới hạn sửa qua thao tác trực tiếp trên DB (không lộ ra API/UI công khai) cho tới khi RBAC sẵn sàng.
- **Đánh đổi cần biết:** khi tắt, Alert loại `HIGH_ATTENTION`/`NEGATIVE_TREND` (cần `sentiment`/`confidence` từ AI) sẽ không còn tính năng "báo ngay lúc phát sinh" — chỉ có sau khi người dùng bấm chạy AI. Riêng `KEYWORD_SPIKE` (đếm khớp từ khóa trên nội dung thô) vẫn tính được ngay lúc crawl xong, không phụ thuộc công tắc này.

**Cân nhắc tải hệ thống khi vẫn dùng Ollama local (CPU-only):** crawl liên tục tạo ra nhiều lượt gọi AI hơn hẳn on-demand, cần:
- Giữ `AI_CONCURRENCY` ở mức thấp (1–2) như khuyến nghị hiện tại.
- Cân nhắc giới hạn số Campaign `ACTIVE` đồng thời ở giai đoạn đầu (VD tối đa 3-5 campaign) để tránh nghẽn AI queue.
- Đây chính là 1 trong các tín hiệu cho thấy đã đến lúc cân nhắc chuyển sang server AI riêng hoặc API trả phí (xem `03_SYSTEM_ARCHITECTURE.md` mục 5) thay vì tiếp tục giới hạn số Campaign chạy song song.

---

## 3. Alert Rule Engine — thiết kế tối giản (không phải rule engine phức tạp)

Không cần xây dựng 1 "rule engine" tổng quát cấu hình được qua UI ngay từ đầu — bắt đầu bằng **rule cứng trong code**, dễ mở rộng sau:

```python
def check_alerts(article, analysis, campaign):
    alerts = []
    if analysis.confidence >= 0.8 and analysis.sentiment == "negative":
        alerts.append(("HIGH_ATTENTION", "HIGH"))
    # NEGATIVE_TREND, KEYWORD_SPIKE: chạy theo batch định kỳ (VD mỗi giờ),
    # so sánh số lượng bài negative/từ khóa trúng trong N giờ gần nhất
    # với trung bình các ngày trước đó cho cùng Campaign
    return alerts
```

Ngưỡng cụ thể (`0.8`, số giờ so sánh...) là **giá trị khởi điểm cần tinh chỉnh bằng dữ liệu thật**, không có công thức "đúng" nào để copy sẵn — đây luôn là bước cần calibrate riêng theo dữ liệu thực tế của hệ thống.

---

## 4. API Contract — endpoint mới cần thêm

### Auth
```
POST /api/auth/login          {username, password} → {access_token, refresh_token, user}
POST /api/auth/refresh        {refresh_token} → {access_token}
GET  /api/auth/me             → {user_id, username, roles[], permissions[]}
```

### Campaigns
```
GET    /api/campaigns                      (filter: status, keyword)
POST   /api/campaigns                      {name, description?, owner_id, start_date, end_date?,
                                             source_ids[], keyword_ids[]?, alert_threshold?}
GET    /api/campaigns/{id}
PUT    /api/campaigns/{id}
DELETE /api/campaigns/{id}                 (xóa mềm → chuyển ARCHIVED)
POST   /api/campaigns/{id}/activate
POST   /api/campaigns/{id}/pause
```

### Contents (mở rộng từ `GET /api/reports/{job_id}/articles` hiện có)
```
GET  /api/contents                         (filter: campaign_id, source_id, sentiment,
                                             review_status, date_from, date_to)
GET  /api/contents/{id}
POST /api/contents/{id}/review             {review_status, note?}
```

### Alerts
```
GET /api/alerts                            (filter: status, severity, campaign_id)
GET /api/alerts/{id}
PUT /api/alerts/{id}/status                {status, note?}
```

### Cases
```
GET    /api/cases                          (filter: status, priority, assigned_to)
POST   /api/cases                          {title, description?, priority, alert_id?,
                                             article_ids[]?, assigned_to?, assigned_org?}
GET    /api/cases/{id}
PUT    /api/cases/{id}
POST   /api/cases/{id}/attachments         (multipart upload)
```

### Users / Roles (Admin)
```
GET/POST     /api/users
GET/PUT      /api/users/{id}
GET          /api/roles
GET          /api/audit-logs               (filter: user_id, action, entity_type, date_from, date_to)
```

Toàn bộ endpoint mới đều yêu cầu JWT + kiểm tra permission tương ứng theo bảng RBAC ở file `04`.

---

## 5. Điều gì KHÔNG đổi

- `backend/crawler/sitemap.py`, `listing.py`, `article.py`, `crawl4ai_client.py`, `playwright_client.py` — không sửa logic parse, chỉ đổi nơi gọi.
- `backend/ai/ollama_client.py`, `backend/ai/prompts/v1.py` — không đổi.
- `backend/report/aggregator.py`, `docx_generator.py` — không đổi, chỉ thêm tham số lọc theo `campaign_id` nếu cần.
- API hiện có (`/api/sources`, `/api/reports/*`) — giữ nguyên để không phá vỡ luồng on-demand hiện tại, trừ khi Phase 0 của roadmap quyết định thay thế hoàn toàn bằng Campaign.
