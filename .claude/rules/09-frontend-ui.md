---
description: Frontend UI — layout màn hình tạo báo cáo, sidebar, date picker, job polling
alwaysApply: false
---

# UI — Màn hình "Tạo báo cáo"

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
- Sidebar: search realtime, group theo nhóm kênh, checkbox từng nguồn
- Tags: nguồn đã chọn hiển thị dạng tag, xóa được từng cái
- Summary card: ước tính `số_nguồn × số_ngày × 2 bài/ngày`
- Warning: tự hiện khi `≥5 nguồn AND ≥60 ngày`
- Nút submit: disabled khi `source_ids.length === 0 OR date_from >= date_to`
- Preset buttons: 7 / 30 / 90 / 150 ngày tính từ hôm nay
- Job status polling mỗi 3 giây qua `GET /api/reports/{job_id}/status`

---

## Trạng thái thật đã code (sau migration Vite, `feature/vite-ui-migration`, 2026-07-15) — khác mockup trên

Frontend đã chuyển toàn bộ từ Next.js sang **Vite + React + AntD**, port nguyên giao diện từ
project tham khảo `ngs-monitoring-ui` (xem CLAUDE.md "Quyết định quan trọng"). Layout thật hiện
là sidebar 9 mục (menu 2 cấp cho "Cấu hình hệ thống") thay vì single-page như mockup ASCII trên
— chỉ 2 trang có logic thật, còn lại là mock UI-only:

- **`/sources`** (`frontend/src/pages/Sources/index.tsx`) — THẬT, gọi `GET /api/sources`
- **`/reports`** (`frontend/src/pages/Reports/index.tsx`) — THẬT, danh sách báo cáo (`GET /api/reports/history`)
- **`/reports/create`** (`frontend/src/pages/Reports/ReportCreate.tsx`) — THẬT, tách riêng khỏi trang list (không còn modal). Vẫn giữ đúng logic sidebar chọn nguồn (`SourceSidebar.tsx`) + summary card ước tính (`SummaryCard.tsx`) khớp mockup ASCII trên — tạo job qua `POST /api/reports/create`, polling status, bảng crawl trực tiếp, nút Cancel, khôi phục sau F5 qua `sessionStorage` như trước
- **Mọi trang khác** (Dashboard, Campaigns, Contents, Alerts, Cases, Jobs, System/*) — mock UI-only, dữ liệu lấy từ `frontend/src/data/mockData.ts`, không gọi API thật. Không dùng `@tanstack/react-query`/`zustand`/`msw` — chỉ `fetch` thuần + `useState`
- Không còn trang Login/Profile — bỏ toàn bộ Auth theo quyết định phạm vi migration
