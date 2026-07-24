---
description: REST API endpoints — request/response schema đầy đủ (đã code + chưa code)
alwaysApply: false
---

# API Endpoints

> Toàn bộ endpoint đúng theo nghiệp vụ — `[ĐÃ CODE]` đang chạy thật, `[CHƯA CODE]` thuộc nghiệp vụ đúng nhưng chưa hiện thực (xem [docs/ROADMAP_CONTINUOUS_MONITORING.md](../../docs/ROADMAP_CONTINUOUS_MONITORING.md)).

## Sources — `[ĐÃ CODE một phần]`

```
GET  /api/sources                    # Lấy danh sách nguồn active — permission source.view
PUT  /api/sources/{id}                # Sửa source_group/crawl_frequency/status — permission source.update
```
`POST /api/sources` (thêm nguồn mới) và `DELETE /api/sources/{id}` — `[CHƯA CODE]`, xem CLAUDE.md mục "Phần chưa code" (tạo Nguồn mới cần cấu hình `parsing_rules` verify thủ công với site thật, không phải form tự phục vụ đơn giản — xem [06 · Crawler Strategy](06-crawler-strategy.md)).

`GET /api/sources` trả kèm `sitemap_url`, `parsing_rules`, `last_crawled_at`, `discover_backfilled_from` (readonly, hiển thị ở FE — 2026-07-24).

## Source Groups — `[ĐÃ CODE — 2026-07-24]`

```
GET  /api/source-groups?include_inactive=bool   # permission source.view — mặc định chỉ trả active
POST /api/source-groups                          {name}                    # permission source.create
PUT  /api/source-groups/{id}                      {name?, is_active?}       # permission source.update
```
Danh mục Nhóm nguồn chuẩn hóa (BR-SRC-01) — `sources.source_group` (PUT `/api/sources/{id}`) validate theo tên 1 dòng `is_active=true` trong bảng này.

## Topic Groups — `[ĐÃ CODE — 2026-07-24]`

```
GET /api/topic-groups   # permission campaign.view — CHỈ ĐỌC, không có POST/PUT/DELETE (cố ý)
```
Trả nguyên `TOPIC_GROUPS` từ `backend/ai/prompts/v1.py` — không phải danh mục CRUD được (gắn liền với prompt AI, xem [07 · AI Pipeline](07-ai-pipeline.md); cho phép sửa qua UI sẽ tạo rủi ro drift với prompt đang chạy + prompt injection nếu feed free text thẳng vào AI).

## Keywords — `[ĐÃ CODE]`

```
GET  /api/keywords?include_inactive=bool   # permission campaign.view — mặc định chỉ trả active
                                             # (dùng cho dropdown chọn Từ khóa ở Campaign/Report)
POST /api/keywords                          {keyword, topic_group?}              # permission campaign.create
PUT  /api/keywords/{id}                     {keyword?, topic_group?, is_active?} # permission campaign.update
```

## Report — `[ĐÃ CODE, đi qua Campaign]`

> Mô hình Job cũ (`POST /api/reports/create`, `GET /api/reports/{job_id}/*`, bảng `jobs`) **đã bị xóa hẳn** (Phase 7, migration `0021`) — không còn tồn tại trong code. Report giờ tạo qua Campaign (`mode=ONE_SHOT` cho báo cáo nhanh 1 lần, `mode=CONTINUOUS` cho giám sát dài hạn), xem [16 · Campaign Management](16-campaign-management.md).

```
POST /api/campaigns/{id}/reports                    {date_from, date_to, format}  # 202, permission report.create
GET  /api/campaigns/{id}/reports                    # danh sách báo cáo của 1 Campaign — permission report.view
GET  /api/campaigns/{id}/reports/{report_id}         # chi tiết 1 báo cáo — permission report.view
POST /api/campaigns/{id}/reports/{report_id}/cancel  # hủy báo cáo pending/running — permission report.create
GET  /api/campaigns/{id}/reports/{report_id}/download # 400 nếu status != completed — permission report.view

GET  /api/reports-history                           # lịch sử TOÀN BỘ báo cáo mọi Campaign, mới nhất trước
                                                       # — permission report.view
```
`format` một trong `docx|json|pdf|xlsx|csv`. Response 1 report:
```json
{
  "report_id": "uuid",
  "campaign_id": "uuid",
  "format": "docx",
  "status": "pending",
  "error_log": null,
  "file_path": "",
  "created_at": "2026-07-13T10:00:00Z"
}
```
`status` một trong `pending|running|completed|failed|cancelled`. Hủy báo cáo: revoke Celery task thật (`terminate=True`) nếu `celery_task_id` có giá trị, giống cơ chế Hủy Job cũ đã xóa (xem [10 · Error Handling](10-error-handling.md)).

---

## Auth & RBAC — `[ĐÃ CODE]`

```
POST /api/auth/login          {username, password} → {access_token, refresh_token, user}
POST /api/auth/refresh        {refresh_token} → {access_token}
GET  /api/auth/me             → {user_id, username, roles[], permissions[]}
PUT  /api/auth/me                                    # cập nhật thông tin cá nhân
POST /api/auth/change-password
POST /api/auth/me/avatar                             # multipart upload
GET  /api/auth/me/avatar

GET/POST     /api/users                              # permission user.manage
GET/PUT      /api/users/{id}
POST         /api/users/{id}/avatar
GET          /api/users/{id}/avatar
GET          /api/roles                              # permission role.manage — read-only, chưa hỗ trợ tạo role tùy chỉnh (Phase 10)
GET          /api/audit-logs                          # permission audit_log.view (filter: user_id, action, entity_type, date_from, date_to)
GET/PUT      /api/system-settings                     # permission system.configure (VD SCHEDULER_ENABLED, AI_AUTO_TRIGGER)
```

Toàn bộ endpoint yêu cầu JWT + kiểm tra permission tương ứng theo RBAC matrix — xem [15 · Auth & RBAC](15-auth-rbac.md). Middleware `require_permission(resource, action)` áp dụng cho **mọi** router (kể cả `/api/sources`, `/api/reports-history`).

## Campaign — `[ĐÃ CODE]`

```
GET    /api/campaigns                      (filter: status, keyword)         # permission campaign.view
POST   /api/campaigns                      {name, description?, owner_id, start_date, end_date?,
                                             mode, source_ids[], keyword_ids[], alert_threshold?}  # permission campaign.create
GET    /api/campaigns/{id}                                                    # permission campaign.view
PUT    /api/campaigns/{id}                                                    # permission campaign.update
DELETE /api/campaigns/{id}                 (xóa mềm → chuyển ARCHIVED)        # permission campaign.archive
POST   /api/campaigns/{id}/activate                                          # permission campaign.update
POST   /api/campaigns/{id}/pause                                             # permission campaign.update
GET    /api/campaigns/{id}/crawl-progress  # permission campaign.view
```

Report của Campaign: xem mục "Report" ở trên.

### GET /api/campaigns/{id}/crawl-progress — Response

Nội dung khác nhau theo `mode` của Campaign — xem [17 · Continuous Crawler & Scheduler](17-continuous-crawler-scheduler.md).

**`mode=ONE_SHOT`** — đọc từ bảng `campaign_crawl_progress`:
```json
{
  "mode": "ONE_SHOT",
  "sources": [
    {
      "source_id": "uuid",
      "source_name": "VTV News",
      "total_urls": 42,
      "done_urls": 17,
      "status": "fetching"
    }
  ],
  "overall_percent": 40.5
}
```
- `total_urls` là `null` cho tới khi Discover xong (chưa biết tổng số URL)
- `status` một trong `pending|discovering|fetching|done|error`
- `overall_percent = round(100 * sum(done_urls) / sum(total_urls), 1)`, trả `0.0` nếu `total_urls` toàn `null`/tổng bằng 0

**`mode=CONTINUOUS`** — tính trực tiếp từ `sources`/`crawl_queue`/`campaign_articles`, không qua `campaign_crawl_progress`:
```json
{
  "mode": "CONTINUOUS",
  "sources": [
    {
      "source_id": "uuid",
      "source_name": "VTV News",
      "last_crawled_at": "2026-07-23T08:00:00Z",
      "source_status": "ACTIVE",
      "pending_count": 3,
      "matched_last_24h": 5
    }
  ]
}
```
- `pending_count`: số URL của Nguồn còn `status='pending'` trong `crawl_queue`
- `matched_last_24h`: số `campaign_articles` của Campaign này khớp trong 24 giờ gần nhất (`matched_at >= now() - 24h`)

## Content (Nội dung) — `[ĐÃ CODE]`

```
GET  /api/contents           (filter: campaign_id, source_id, sentiment, review_status, date_from, date_to)
GET  /api/contents/{id}
POST /api/contents/{id}/review   {review_status, note?}
```

Chi tiết: xem [17 · Continuous Crawler & Scheduler](17-continuous-crawler-scheduler.md).

## Alert & Case — `[CHƯA CODE]`

```
GET /api/alerts                            (filter: status, severity, campaign_id)
GET /api/alerts/{id}
PUT /api/alerts/{id}/status                {status, note?}

GET    /api/cases                          (filter: status, priority, assigned_to)
POST   /api/cases                          {title, description?, priority, alert_id?,
                                             article_ids[]?, assigned_to?, assigned_org?}
GET    /api/cases/{id}
PUT    /api/cases/{id}
POST   /api/cases/{id}/attachments         (multipart upload)
```

Chi tiết: xem [18 · Alert & Case Management](18-alert-case-management.md).
