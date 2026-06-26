---
description: REST API endpoints — request/response schema đầy đủ
alwaysApply: false
---

# API Endpoints

```
GET  /api/sources                    # Lấy danh sách nguồn active
POST /api/sources                    # Admin: thêm nguồn mới
PUT  /api/sources/{id}               # Admin: cập nhật nguồn
DELETE /api/sources/{id}             # Admin: xóa nguồn

POST /api/reports/create             # Tạo job báo cáo mới
GET  /api/reports/{job_id}/status    # Polling trạng thái job
GET  /api/reports/{job_id}/articles  # Bảng crawl trực tiếp: danh sách bài đã crawl
                                      # kèm benchmark thời gian (Slice 1 mở rộng)
POST /api/reports/{job_id}/cancel    # Hủy job đang chạy (pending/running) (Slice 1 mở rộng)
GET  /api/reports/{job_id}/download  # Download file DOCX
GET  /api/reports/history            # Lịch sử báo cáo (chưa code — Slice 5)

GET  /api/jobs/{job_id}              # Chi tiết job (chưa code)
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
      "crawl_duration_seconds": 0.24,
      "analysis_duration_seconds": 67.0,
      "total_duration_seconds": 67.24
    }
  ]
}
```
- `title` là `null` nếu `status="error"` (crawl lỗi, không lấy được title)
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
