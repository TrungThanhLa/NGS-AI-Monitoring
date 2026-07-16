---
description: Sinh báo cáo — DOCX (đã code) + PDF/Excel/CSV (chưa code), aggregate queries
alwaysApply: false
---

# Sinh báo cáo

## DOCX + JSON — `[ĐÃ CODE]`

**Quy trình:**
1. Aggregate dữ liệu từ `articles` + `article_analysis`: `GROUP BY` nguồn / chủ đề / tháng / sentiment / emotion
2. `python-docx` điền dữ liệu đã aggregate vào template Word (`templates/report_template.docx`) qua engine `report/docx_generator.py`
3. Lưu file output `.docx` (đường dẫn ghi vào `jobs.output_docx`) và xuất song song file `.json` raw data (`jobs.output_json`)
4. Cập nhật `jobs.status = completed`, ghi 1 record vào `report_history`

Chi tiết Slice đã hoàn thành: [docs/ROADMAP_MVP.md](../../docs/ROADMAP_MVP.md).

```env
STORAGE_PATH=./storage
DOCX_TEMPLATE_PATH=./templates/report_template.docx
```

---

## PDF, Excel (XLSX), CSV — `[CHƯA CODE]`

Đầu ra sẽ mở rộng thêm **PDF**, **Excel (XLSX)** và **CSV** bên cạnh `.docx`/`.json` — mỗi định dạng thêm 1 nhánh export mới song song `docx_generator.py`, dùng chung dữ liệu aggregate hiện có (`report/aggregator.py`), không đổi query.

## Đổi theo Campaign — `[CHƯA CODE]`

`jobs.output_docx`/`report_history.job_id` đổi thành `report_history.campaign_id` (bắt buộc NOT NULL, không còn là "nếu" — bảng `jobs` bị xóa hẳn khi Campaign thay thế hoàn toàn mô hình Job, xem [03 · Database Schema](03-database-schema.md) và [16 · Campaign Management](16-campaign-management.md)). Report **không phụ thuộc** Alert/Case ([18 · Alert & Case Management](18-alert-case-management.md)) — có thể code Report ngay sau Campaign + Scheduler, không cần đợi Alert/Case xong.

**Không tự động xuất báo cáo khi đóng Case** — Report vẫn tạo thủ công theo Campaign/khoảng ngày như bình thường.
