# Tài liệu nghiệp vụ mở rộng — NGS Monitor — Mục lục

> ✅ **Đã chuyển hóa thành rule chính thức (2026-07-16).** Toàn bộ `06_OPEN_DECISIONS.md` đã chốt — nội dung ở `01`–`05` đã được phân phối vào `.claude/rules/` (tầm nhìn/flow/schema/API/crawler/AI/report/UI gộp vào rule 01/03–09, business rules riêng từng domain mới ở rule 15–18), và `07_ROADMAP_TO_NEW_BUSINESS_FLOW.md` đã promote thành `docs/ROADMAP_CONTINUOUS_MONITORING.md`. **Dùng `.claude/rules/` và roadmap mới làm nguồn chân lý khi code** — thư mục này giữ lại làm hồ sơ lưu trữ quá trình ra quyết định (lý do "vì sao" phía sau từng lựa chọn), không cập nhật tiếp.
>
> **Lưu ý khi đọc các file `01`–`07` bên dưới:** dùng cách gọi "hướng phát triển tiếp theo" (di sản từ lúc còn là bản nháp) — cách gọi này **không còn đúng** sau khi đã xác nhận rằng mô hình on-demand hiện tại là cách hiện thực **chưa đúng/chưa đủ**, không phải một giai đoạn sản phẩm đã hoàn chỉnh song song với "continuous monitoring". Xem khung đúng ở [01 · Project Overview](../../.claude/rules/01-project-overview.md).

## Danh sách file

| File | Nội dung |
|---|---|
| [01_PRODUCT_VISION_AND_BUSINESS_RULES.md](01_PRODUCT_VISION_AND_BUSINESS_RULES.md) | Tầm nhìn mở rộng, 5 vai trò người dùng, business flow 10 bước, toàn bộ business rule theo domain (đã hợp nhất thành 1 bộ mã rule duy nhất, không còn trùng/mâu thuẫn) |
| [02_DOMAIN_MODEL_AND_DATABASE.md](02_DOMAIN_MODEL_AND_DATABASE.md) | Domain model, schema database đề xuất (bảng, cột, FK, enum) cho các entity mới: Campaign, Alert, Case, RBAC, Audit Log |
| [03_SYSTEM_ARCHITECTURE.md](03_SYSTEM_ARCHITECTURE.md) | Kiến trúc kỹ thuật đề xuất — giữ nguyên nền tảng hiện tại (FastAPI monolith + Celery + PostgreSQL + Ollama), chỉ mở rộng thêm phần cần thiết (Scheduler, WebSocket, RBAC middleware) |
| [04_SCREENS_UI_RBAC.md](04_SCREENS_UI_RBAC.md) | Danh sách màn hình/route mới theo module, design system (kế thừa AntD hiện có), RBAC matrix đầy đủ theo permission |
| [05_CRAWLER_AI_API.md](05_CRAWLER_AI_API.md) | Chiến lược crawl mở rộng (continuous), pipeline AI (mặc định Ollama local, có lớp adapter để mở rộng sang server AI riêng/API trả phí khi cần scale), API contract đề xuất cho các module mới |
| [06_OPEN_DECISIONS.md](06_OPEN_DECISIONS.md) | **Danh sách quyết định còn mở** — những điểm cần bạn chốt trước khi các file trên trở thành rule chính thức |
| [07_ROADMAP_TO_NEW_BUSINESS_FLOW.md](07_ROADMAP_TO_NEW_BUSINESS_FLOW.md) | Roadmap theo Phase 0→9: thứ tự Thêm/Sửa/Xóa để triển khai hướng mở rộng này, kèm rủi ro từng phase |

## Nguyên tắc xuyên suốt bộ tài liệu này

1. **AI runtime — local là mặc định MVP, không phải giới hạn vĩnh viễn:** giai đoạn hiện tại giữ Ollama local (chi phí thấp, dữ liệu không rời khỏi hạ tầng nội bộ). Khi dự án scale lên, được phép chuyển sang (a) server AI riêng do dự án tự dựng và gọi sang, hoặc (b) API trả phí (Claude/ChatGPT/Gemini) — xem điều kiện chuyển đổi và rủi ro ở `06_OPEN_DECISIONS.md`. Thiết kế pipeline AI nên trừu tượng hóa qua 1 lớp adapter ngay từ đầu để không phải viết lại khi chuyển.
2. **Không đổi các quyết định MVP khác có rủi ro cao khi đổi:** không crawl social media, không tách kiến trúc thành nhiều microservice riêng — các quyết định này vẫn giữ nguyên trong mọi file dưới đây.
2. **Một rule = một mã, một nguồn chân lý** — không dùng 2 hệ đánh số song song cho cùng 1 domain.
3. **Chỗ nào là đề xuất mặc định (có thể đổi) sẽ được đánh dấu rõ**, không âm thầm coi là đã chốt.
4. Khi các file này được duyệt, nội dung sẽ được chuyển hóa thành rule chính thức trong `.claude/rules/` (đánh số tiếp theo `15+`) và cập nhật `CLAUDE.md` — bản thân các file trong `project_business/` chỉ là bản nháp làm việc.
