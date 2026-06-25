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
GET  /api/reports/{job_id}/download  # Download file DOCX
GET  /api/reports/history            # Lịch sử báo cáo

GET  /api/jobs/{job_id}              # Chi tiết job
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
  "created_at": "2026-06-22T10:00:00Z"
}
```
