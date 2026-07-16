---
description: Frontend UI — toàn bộ màn hình theo trạng thái thật/mock/chưa code
alwaysApply: false
---

# Frontend — layout & trạng thái từng màn hình

Frontend dùng **Vite + React + AntD**, sidebar 9 mục (menu 2 cấp cho "Cấu hình hệ thống"). Không dùng `@tanstack/react-query`/`zustand`/`msw` — chỉ `fetch` thuần + `useState`. Mỗi route dưới đây được đánh dấu đúng trạng thái implement — **không có khái niệm "route MVP" vs "route giai đoạn sau"**, chỉ có "đã nối API thật" / "mock tạm" / "chưa có route".

## Đã nối API thật — `[ĐÃ CODE]`

- **`/sources`** (`frontend/src/pages/Sources/index.tsx`) — gọi `GET /api/sources`
- **`/reports`** (`frontend/src/pages/Reports/index.tsx`) — danh sách báo cáo (`GET /api/reports/history`)
- **`/reports/create`** (`frontend/src/pages/Reports/ReportCreate.tsx`) — trang tạo báo cáo, tách riêng khỏi trang list

### Layout `/reports/create`

```
┌─────────────────────┬──────────────────────────────────────┐
│  Nguồn dữ liệu      │  Cấu hình báo cáo                   │
│  [🔍 Tìm nguồn...]  │                                      │
│                     │  Nguồn đã chọn:                      │
│  Chính phủ (VPCP)   │  [VTV News ×] [VOV ×] [QĐND ×]      │
│  ☐ Cổng TTĐT CP     │                                      │
│  ☐ Facebook TTCP    │  Khoảng thời gian:                   │
│                     │  Từ [01/01/2026]  →  Đến [30/05/2026]│
│  Bộ Công an         │  [7 ngày] [30 ngày] [3 tháng] [5T]  │
│  ☑ Cổng BCA         │                                      │
│  ☑ Báo CAND         │  ┌──────────────────────────────┐   │
│                     │  │ 3 nguồn · 150 ngày           │   │
│  VTV                │  │ ~900 bài · ~45 phút           │   │
│  ☑ VTV News         │  └──────────────────────────────┘   │
│  ☐ VTV Tin giả      │                                      │
│                     │  ⚠️ Job sẽ chạy nền, thông báo khi  │
│  VOV                │  xong (≥5 nguồn + ≥60 ngày)         │
│  ☑ VOV.vn           │                                      │
│                     │  [Đặt lại]      [Tạo báo cáo →]     │
│  0/40 đã chọn       │                                      │
└─────────────────────┴──────────────────────────────────────┘
```

**Logic UI:**
- Sidebar chọn nguồn (`SourceSidebar.tsx`): search realtime, group theo nhóm kênh, checkbox từng nguồn
- Tags: nguồn đã chọn hiển thị dạng tag, xóa được từng cái
- Summary card (`SummaryCard.tsx`): ước tính `số_nguồn × số_ngày × 2 bài/ngày`
- Warning: tự hiện khi `≥5 nguồn AND ≥60 ngày`
- Nút submit: disabled khi `source_ids.length === 0 OR date_from >= date_to`
- Preset buttons: 7 / 30 / 90 / 150 ngày tính từ hôm nay
- Tạo job qua `POST /api/reports/create`, polling status mỗi 3 giây qua `GET /api/reports/{job_id}/status`, bảng crawl trực tiếp, nút Cancel, khôi phục sau F5 qua `sessionStorage`

Không còn trang Login/Profile trong lần migrate Vite này — sẽ thêm lại cùng Auth (xem dưới).

## Mock UI-only, chưa nối API thật — `[ĐÃ CODE giao diện, CHƯA nối API]`

Dashboard, Campaigns, Contents, Alerts, Cases, Jobs, System/* — dữ liệu lấy từ `frontend/src/data/mockData.ts`, không gọi API thật. Route đã có sẵn trong codebase, không cần tạo route mới khi nối API thật sau này. Trang **"Jobs"** sẽ sáp nhập vào `/campaigns` (lọc `mode=ONE_SHOT` cho "chạy nhanh 1 lần", `mode=CONTINUOUS` cho chiến dịch giám sát dài hạn) khi Campaign nối API thật — route `/jobs` gỡ bỏ tại thời điểm đó.

## Chưa có route — `[CHƯA CODE]`

Màn hình mới cần thêm route khi các module tương ứng được code — chi tiết từng màn hình:

| Màn hình | Route | Chi tiết |
|---|---|---|
| Login | `/login` | Tên đăng nhập, Mật khẩu → JWT. Redirect Dashboard sau khi thành công |
| Profile | `/profile` | Xem/đổi mật khẩu, thông tin cá nhân |
| User Management | `/system/users` | CRUD người dùng, gán vai trò |
| Role Management | `/system/roles` | Xem permission theo vai trò (không cho sửa 5 vai trò hệ thống) |
| Audit Log | `/system/audit-logs` | Chỉ xem, filter theo user/hành động/thời gian |

→ chi tiết [15 · Auth & RBAC](15-auth-rbac.md)

| Campaign List | `/campaigns` | Filter: từ khóa, trạng thái, người phụ trách. Cột: Mã, Tên, Người phụ trách, Trạng thái, Số nguồn, Số nội dung. Row actions: Xem/Sửa/Kích hoạt/Tạm dừng/Lưu trữ |
| Campaign Form | `/campaigns/new`, `/campaigns/:id/edit` | Section: Thông tin chung, Từ khóa (bắt buộc ≥1), Nguồn dữ liệu (bắt buộc ≥1), Ngưỡng cảnh báo, Chế độ (`ONE_SHOT`/`CONTINUOUS`) |

→ chi tiết [16 · Campaign Management](16-campaign-management.md)

| Content Detail | `/contents/:id` | Nội dung đầy đủ + kết quả AI + form đánh giá + cảnh báo/vụ việc liên quan |

→ chi tiết [17 · Continuous Crawler & Scheduler](17-continuous-crawler-scheduler.md)

| Alert List | `/alerts` (nối API thật) | Filter: trạng thái, mức độ, loại cảnh báo, chiến dịch. Row actions: Xác nhận/Chuyển xử lý/Tạo vụ việc/Đóng |
| Alert Detail | `/alerts/:id` | Thông tin cảnh báo, nội dung liên quan (nếu có), lịch sử xử lý |
| Case List | `/cases` (nối API thật) | Filter: trạng thái, mức ưu tiên, người phụ trách. Row actions: Xem/Sửa/Đóng vụ việc |
| Case Form | `/cases/new`, `/cases/:id/edit` | Tên, Mô tả, Mức ưu tiên, Người phụ trách, Nội dung liên quan, Tệp đính kèm, Kết quả xử lý |

→ chi tiết [18 · Alert & Case Management](18-alert-case-management.md). **Thứ tự code:** Report ([08 · DOCX Report](08-docx-report.md)) không phụ thuộc Alert/Case — Alert/Case tiếp tục dùng mock UI-only cho tới khi tới lượt trong roadmap, không chặn các module khác.

Component mới cần thêm: `PermissionGuard` (ẩn nút theo quyền), `Header` hiển thị user hiện tại (`MainLayout`), `SeverityTag` (mức độ cảnh báo), bulk action bar cho bảng Alert/Case (theo pattern bảng hiện có ở Sources/Reports).
