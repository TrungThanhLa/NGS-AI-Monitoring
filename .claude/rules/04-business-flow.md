---
description: Business flow đúng duy nhất (10 bước) — actor, luồng xử lý, trạng thái implement
alwaysApply: true
---

# Business Flow — 10 bước (nghiệp vụ đúng duy nhất)

> **Đây là business flow đúng duy nhất của dự án** — không phải "flow MVP" + "flow giai đoạn sau". Code hiện tại (`main`) mới chỉ hiện thực một **mô hình con tạm thời** của flow này: crawl 1 lần theo yêu cầu (tương đương bước 1–3 + 5–7, bỏ qua "Chiến dịch sống", Cảnh báo, Vụ việc). Đây không phải một giai đoạn sản phẩm hoàn chỉnh riêng — là bước hiện thực chưa đầy đủ, đang được sửa dần theo [docs/ROADMAP_CONTINUOUS_MONITORING.md](../../docs/ROADMAP_CONTINUOUS_MONITORING.md).

```
Tạo Campaign → Chọn từ khóa (bắt buộc ≥1) → Chọn nguồn dữ liệu (bắt buộc ≥1)
→ Kích hoạt Campaign → Scheduler tự động crawl định kỳ theo từng Nguồn
→ Chuẩn hóa & loại trùng dữ liệu → AI phân tích (tóm tắt/chủ đề/cảm xúc/độ tin cậy)
→ Hệ thống tự sinh Cảnh báo khi vượt ngưỡng → Chuyên viên xem & đánh giá nội dung
→ (tùy chọn) Tạo Vụ việc để điều tra sâu → Tạo Báo cáo tổng hợp theo Campaign
```

**Actors:**
- **ADMIN/OPERATOR**: cấu hình nguồn dữ liệu (ngoài luồng chính, làm 1 lần)
- **MANAGER/ANALYST**: tạo/kích hoạt Campaign, chọn từ khóa + nguồn, xem & đánh giá nội dung, xử lý cảnh báo, tạo vụ việc, tạo báo cáo
- **System/AI**: crawl định kỳ, chuẩn hóa/loại trùng, phân tích AI, sinh cảnh báo tự động

Chi tiết từng module: [15 · Auth & RBAC](15-auth-rbac.md), [16 · Campaign Management](16-campaign-management.md), [17 · Continuous Crawler & Scheduler](17-continuous-crawler-scheduler.md), [18 · Alert & Case Management](18-alert-case-management.md), [08 · DOCX Report](08-docx-report.md).

---

## Trạng thái implement hiện tại — `[ĐÃ CODE]` (mô hình con tạm thời, chưa đúng đầy đủ flow trên)

Code hiện tại trong `main` chưa có Campaign/Scheduler/Alert/Case/Auth — chỉ chạy được nhánh "crawl 1 lần theo yêu cầu, không giám sát liên tục":

```
Admin cấu hình nguồn (ngoài luồng chính — làm 1 lần)
         ↓
User truy cập → FE gọi GET /api/sources → render sidebar
         ↓
User chọn nguồn + ngày → POST /api/reports/create
         ↓
System validate → tạo Job UUID → đẩy Celery queue qua Redis
         ↓
Worker crawl:
         Sitemap XML (primary) → lọc URL theo ngày
         Listing page (fallback nếu không có sitemap)
         httpx tải HTML → BeautifulSoup parse
         Dedup SHA256(url) trong phạm vi 1 job (không xuyên job) → insert bảng articles
         ↓
AI pipeline (per article):
         Ollama API → qwen3:8b
         → topics[], keywords[], sentiment, emotion, confidence
         → flag needs_review nếu confidence < 0.6
         → lưu article_analysis
         ↓
Aggregate: GROUP BY nguồn/chủ đề/tháng/sentiment/emotion
         ↓
python-docx điền template → lưu .docx + .json → status=completed
         ↓
FE polling nhận completed → render Download → stream file về máy
```

Đây tương đương `campaigns.mode='ONE_SHOT'` sau khi migrate (xem [16 · Campaign Management](16-campaign-management.md)) — không có Kích hoạt/Scheduler/Cảnh báo/Vụ việc, không có vai trò người dùng (chưa có Auth).

### Vòng đời job (Celery) — `[ĐÃ CODE, SẼ XÓA cùng bảng jobs]`

Trạng thái lưu ở cột `jobs.status`:

```
pending → running → completed
                  → failed
                  → cancelled
```

- `pending`: job vừa tạo, chưa được worker nhận
- `running`: worker đang crawl/phân tích
- `completed`: đã sinh xong `.docx` + `.json`
- `failed`: lỗi không khôi phục được, chi tiết lưu ở `jobs.error_log`
- `cancelled`: người dùng chủ động hủy (xem [10 · Error Handling](10-error-handling.md))
