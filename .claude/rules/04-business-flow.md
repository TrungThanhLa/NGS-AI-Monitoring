---
description: Business flow 8 bước — actor, luồng xử lý, Celery job lifecycle
alwaysApply: true
---

# Business Flow — 8 bước

```
Admin cấu hình nguồn (ngoài luồng chính — làm 1 lần)
         ↓
[Bước 1] User truy cập → FE gọi GET /api/sources → render sidebar
         ↓
[Bước 2] User chọn nguồn + ngày → POST /api/reports/create
         ↓
[Bước 3] System validate → tạo Job UUID → đẩy Celery queue qua Redis
         ↓
[Bước 4] Worker crawl:
         Sitemap XML (primary) → lọc URL theo ngày
         Listing page (fallback nếu không có sitemap)
         httpx tải HTML → BeautifulSoup parse
         Dedup SHA256(url) trong phạm vi 1 job (không xuyên job) → insert bảng articles
         ↓
[Bước 5] AI pipeline (per article):
         Ollama API → qwen3:8b
         → topics[], keywords[], sentiment, emotion, confidence
         → flag needs_review nếu confidence < 0.6
         → lưu article_analysis
         ↓
[Bước 6] Aggregate: GROUP BY nguồn/chủ đề/tháng/sentiment/emotion
         ↓
[Bước 7] python-docx điền template → lưu .docx + .json → status=completed
         ↓
[Bước 8] FE polling nhận completed → render Download → stream file về máy
```

**Actors:**
- **User**: Bước 1, 2, 8
- **System/AI**: Bước 3–7 (tự động, chạy nền)
- **Admin**: Cấu hình nguồn ngoài luồng chính

---

## Vòng đời job (Celery)

Trạng thái lưu ở cột `jobs.status`:

```
pending → running → completed
                  → failed
```

- `pending`: job vừa tạo, chưa được worker nhận
- `running`: worker đang crawl/phân tích (Bước 4–6)
- `completed`: đã sinh xong `.docx` + `.json` (Bước 7)
- `failed`: lỗi không khôi phục được, chi tiết lưu ở `jobs.error_log`
