---
description: Sinh báo cáo DOCX — template placeholder, aggregate queries, output format
alwaysApply: false
---

# Sinh báo cáo DOCX

**Quy trình (Bước 6–7 của business flow):**
1. Aggregate dữ liệu từ `articles` + `article_analysis`: `GROUP BY` nguồn / chủ đề / tháng / sentiment / emotion
2. `python-docx` điền dữ liệu đã aggregate vào template Word (`templates/report_template.docx`) qua engine `report/docx_generator.py`
3. Lưu file output `.docx` (đường dẫn ghi vào `jobs.output_docx`) và xuất song song file `.json` raw data (`jobs.output_json`)
4. Cập nhật `jobs.status = completed`, ghi 1 record vào `report_history`

**Slice liên quan:** Slice 1 (DOCX cơ bản, vài bảng) và Slice 4 (DOCX đầy đủ theo `sample_report_form.docx`) — xem [Roadmap](../../CLAUDE.md#roadmap--vertical-slices).

---

## Môi trường & Cấu hình

```env
STORAGE_PATH=./storage
DOCX_TEMPLATE_PATH=./templates/report_template.docx
```
