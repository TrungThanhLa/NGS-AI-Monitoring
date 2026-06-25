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
