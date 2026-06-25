---
description: EPCC development workflow — Explore, Plan, Code, Commit
alwaysApply: true
---

# Workflow chuẩn EPCC

Follow these 4 steps for every feature, in order.

### Explore
- Đọc kỹ yêu cầu; hỏi lại nếu mơ hồ — KHÔNG tự giả định
- Xem các file liên quan: models, schemas, existing routes

### Plan
- Liệt kê file sẽ tạo/chỉnh sửa
- Xác định API contract (endpoint, request/response shape) trước khi code
- Viết test cases cần pass trước khi implement (TDD)

### Code
- Backend trước, Frontend sau
- Viết unit test (Pytest) song song với implementation
- Mỗi function phải có comment giải thích logic quan trọng bằng tiếng Việt

### Commit
- Chạy lint + type check trước khi commit
- Không commit secret, `.env`, hoặc file build
- Test với dữ liệu thật — luôn chạy thử với ít nhất 1 nguồn thực tế trước khi commit
