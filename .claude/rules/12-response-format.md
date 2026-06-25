---
description: Quy tắc định dạng response — ngôn ngữ, thuật ngữ, TL;DR
alwaysApply: true
---

# Response Format

Quy tắc định dạng chung cho mọi response — áp dụng đồng thời tất cả rules bên dưới.

---

## 1. Ngôn ngữ & Từ ngữ

- **Dùng từ ngữ đơn giản, dễ hiểu** — tránh từ học thuật, từ chuyên ngành nặng, cú pháp phức tạp không cần thiết.
- **Thuật ngữ tiếng Anh phải có chú thích tiếng Việt** — viết ngay sau từ đó trong dấu ngoặc đơn.
  - Ví dụ đúng: `idempotency (tính bất biến khi gọi lặp)`, `threshold (ngưỡng)`, `payload (dữ liệu gửi kèm)`
  - Ngoại lệ: tên riêng (Redis, Odoo, FastAPI, Qwen3...) và tên field/model trong code — không cần dịch.
- **Ngôn ngữ response** — dùng cùng ngôn ngữ với câu hỏi (tiếng Việt nếu hỏi tiếng Việt, English nếu hỏi English).

---

## 2. TL;DR

Cuối mỗi response giải thích, phân tích, tư vấn, gợi ý — luôn thêm phần TL;DR.

```
---
**TL;DR:** [1–3 câu tóm tắt điểm cốt lõi]
```

- **Always** append TL;DR — không bỏ qua dù câu trả lời ngắn
- **Ngắn gọn** — tối đa 3 câu, chỉ giữ điểm quan trọng nhất
- **Không áp dụng** cho: pure code output không có giải thích, one-word/one-line answers, danh sách lệnh đơn thuần
