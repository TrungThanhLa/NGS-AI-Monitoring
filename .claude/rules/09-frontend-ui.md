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

## Trạng thái thật đã code (Slice 1 + mở rộng) — khác mockup trên

Mockup trên là thiết kế đích cho Slice 2 (nhiều nguồn, sidebar đầy đủ). Slice 1 hiện tại (`frontend/app/page.tsx`) chỉ là **form tối giản** theo đúng phạm vi roadmap Slice 1 (1 nguồn VTV hardcode), nhưng đã code thêm các phần sau (branch `feature/live-crawl-cancel-benchmark`, chưa merge `main`):

- **Bảng crawl trực tiếp**: cập nhật theo cùng nhịp polling 3s, hiển thị danh sách bài đã crawl (link mở bài thật để tự kiểm chứng) kèm 3 cột benchmark thời gian (`crawl_duration_seconds`/`analysis_duration_seconds`/`total_duration_seconds`, gọi `GET /api/reports/{job_id}/articles`). Bài lỗi (`status="error"`) hiện URL thay tên vì không có title.
- **Nút "Cancel"**: hiện khi `status` là `pending`/`running`, gọi `POST /api/reports/{job_id}/cancel`.
- **Khôi phục sau reload (F5)**: `job_id` lưu vào `sessionStorage` lúc tạo job, tự đọc lại lúc mount để dựng lại đúng UI (bảng, nút Cancel, link download) — vì job chạy nền độc lập FE, reload trước đây làm mất hết khả năng theo dõi/hủy job dù job thật vẫn đang chạy.
