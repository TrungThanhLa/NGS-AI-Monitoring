---
description: REST API endpoints — request/response schema đầy đủ (đã code + chưa code)
alwaysApply: false
---

# API Endpoints

> Toàn bộ endpoint đúng theo nghiệp vụ — `[ĐÃ CODE]` đang chạy thật, `[CHƯA CODE]` thuộc nghiệp vụ đúng nhưng chưa hiện thực (xem [docs/ROADMAP_CONTINUOUS_MONITORING.md](../../docs/ROADMAP_CONTINUOUS_MONITORING.md)).

## Sources — `[ĐÃ CODE]`

```
GET  /api/sources                    # Lấy danh sách nguồn active
POST /api/sources                    # Admin: thêm nguồn mới
PUT  /api/sources/{id}               # Admin: cập nhật nguồn
DELETE /api/sources/{id}             # Admin: xóa nguồn
```

## Reports (mô hình Job cũ) — `[ĐÃ CODE, SẼ XÓA khi migrate sang Campaign]`

> `jobs`/`POST /api/reports/create` là cách hiện thực nghiệp vụ "on-demand" ban đầu — bị xóa khi Campaign thay thế, không giữ song song. Xem [16 · Campaign Management](16-campaign-management.md) mục "API Contract".

```
POST /api/reports/create             # Tạo job báo cáo mới — [SẼ XÓA], thay bằng
                                      # POST /api/campaigns kèm mode=ONE_SHOT
GET  /api/reports/{job_id}/status    # Polling trạng thái job
GET  /api/reports/{job_id}/articles  # Bảng crawl trực tiếp: danh sách bài đã crawl
                                      # kèm benchmark thời gian
POST /api/reports/{job_id}/cancel    # Hủy job đang chạy (pending/running)
GET  /api/reports/{job_id}/download  # Download file DOCX
GET  /api/reports/history            # Lịch sử báo cáo, sắp xếp mới nhất trước
```

### POST /api/reports/create — Request body
```json
{
  "source_ids": ["uuid1", "uuid2"],
  "date_from": "2026-01-01",
  "date_to": "2026-05-30"
}
```

### GET /api/reports/{job_id}/status — Response
```json
{
  "job_id": "uuid",
  "status": "running",
  "progress": {
    "crawled": 120,
    "analyzed": 80,
    "total_estimated": 200
  },
  "error_log": null,
  "created_at": "2026-06-22T10:00:00Z"
}
```
`status` có thể là `pending|running|completed|failed|cancelled`.

### GET /api/reports/{job_id}/articles — Response
```json
{
  "articles": [
    {
      "title": "Tiêu đề bài viết",
      "url": "https://vtv.vn/...",
      "status": "analyzed",
      "source_name": "VTV News",
      "crawl_duration_seconds": 0.24,
      "analysis_duration_seconds": 67.0,
      "total_duration_seconds": 67.24
    }
  ]
}
```
- `title` là `null` nếu `status="error"` (crawl lỗi, không lấy được title)
- `source_name` là `null` nếu bài không gắn được nguồn (hiếm gặp, `source_id` không NOT NULL ở tầng DB) — FE hiện `"-"` khi `null`
- `analysis_duration_seconds`/`total_duration_seconds` là `null` nếu bài chưa được AI phân tích xong
- `total_duration_seconds` tính ngay trong response (`crawl + analysis`), không lưu DB

### POST /api/reports/{job_id}/cancel — Response
```json
{
  "job_id": "uuid",
  "status": "cancelled"
}
```
- 400 nếu `status` hiện tại không thuộc `pending`/`running` (đã `completed`/`failed`/`cancelled`)
- Revoke Celery task thật (`terminate=True`) nếu `celery_task_id` có giá trị

### GET /api/reports/history — Response
```json
{
  "history": [
    {
      "report_id": "uuid",
      "job_id": "uuid",
      "file_path": "/storage/....docx",
      "created_at": "2026-07-13T10:00:00Z",
      "date_from": "2026-01-01",
      "date_to": "2026-05-30",
      "job_status": "completed",
      "source_names": ["VTV News", "VOV"]
    }
  ]
}
```
- Sắp xếp theo `created_at` giảm dần (mới nhất trước)
- Không phân trang — `report_history` chỉ có 1 dòng/job hoàn thành thành công, không phình to như `articles`
- `source_names` rỗng nếu job không còn nguồn nào khớp (hiếm, `jobs.source_ids` không có FK cứng tới `sources`)

---

## Auth & RBAC — `[CHƯA CODE]`

```
POST /api/auth/login          {username, password} → {access_token, refresh_token, user}
POST /api/auth/refresh        {refresh_token} → {access_token}
GET  /api/auth/me             → {user_id, username, roles[], permissions[]}

GET/POST     /api/users
GET/PUT      /api/users/{id}
GET          /api/roles
GET          /api/audit-logs  (filter: user_id, action, entity_type, date_from, date_to)
```

Toàn bộ endpoint mới đều yêu cầu JWT + kiểm tra permission tương ứng theo RBAC matrix — xem [15 · Auth & RBAC](15-auth-rbac.md). Middleware `require_permission(resource, action)` áp dụng cho **mọi** router hiện có và mới (kể cả `/api/sources`, `/api/reports/*` đã code).

## Campaign — `[CHƯA CODE]`

```
GET    /api/campaigns                      (filter: status, keyword)
POST   /api/campaigns                      {name, description?, owner_id, start_date, end_date?,
                                             mode, source_ids[], keyword_ids[], alert_threshold?}
GET    /api/campaigns/{id}
PUT    /api/campaigns/{id}
DELETE /api/campaigns/{id}                 (xóa mềm → chuyển ARCHIVED)
POST   /api/campaigns/{id}/activate
POST   /api/campaigns/{id}/pause
```

`POST /api/reports/create` bị **xóa**, thay bằng `POST /api/campaigns` kèm `mode=ONE_SHOT`. Chi tiết: xem [16 · Campaign Management](16-campaign-management.md).

## Content (Nội dung) — `[CHƯA CODE]`

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
