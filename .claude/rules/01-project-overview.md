---
description: NGS Monitor — tổng quan dự án, tầm nhìn, vai trò người dùng, phạm vi
alwaysApply: true
---

# Tổng quan dự án

**Tên:** NGS Monitor — Nền tảng Thu thập & Phân tích Nội dung Truyền thông Phòng, Chống Tin Giả tại Việt Nam

**Mục đích (tầm nhìn đúng duy nhất):** một **nền tảng giám sát liên tục** — người dùng định nghĩa 1 lần "cần theo dõi chủ đề gì, từ nguồn nào" (Campaign), hệ thống tự động crawl định kỳ, tự phân tích AI (8 nhóm chủ đề, sentiment, keyword), tự cảnh báo khi có dấu hiệu bất thường, và hỗ trợ chuyên viên lập hồ sơ điều tra khi cần. Báo cáo Word (`.docx`) chỉ là **một trong các đầu ra**, không phải đích đến duy nhất.

> **Về trạng thái implement hiện tại:** code trong `main` hiện chỉ hiện thực một mô hình con của tầm nhìn trên — "crawl 1 lần theo yêu cầu, không giám sát liên tục, chưa có Auth/Cảnh báo/Vụ việc". Đây **không phải một giai đoạn sản phẩm ("MVP") đã hoàn chỉnh và đúng** — là một phần hiện thực còn thiếu so với nghiệp vụ đúng ở trên, đang được bổ sung/sửa dần theo [docs/ROADMAP_CONTINUOUS_MONITORING.md](../../docs/ROADMAP_CONTINUOUS_MONITORING.md). Mỗi rule trong `.claude/rules/` đánh dấu rõ phần nào `[ĐÃ CODE]` / `[CHƯA CODE]` / `[SẼ SỬA]` để không nhầm lẫn giữa 2 điều này.

**Phạm vi (không đổi dù đã/chưa code):**
- Chỉ hỗ trợ website / báo điện tử tiếng Việt qua sitemap/listing/CSS-selector (20–50 nguồn)
- Mạng xã hội (Facebook, YouTube, TikTok, Zalo, Telegram) ngoài phạm vi — không mở rộng sang trừ khi có yêu cầu riêng
- Desktop-first UI
- AI chạy local (Ollama), không gọi API bên ngoài mặc định — chuyển sang server AI riêng/cloud LLM là thao tác thủ công khi cần scale, xem [07 · AI Pipeline](07-ai-pipeline.md)
- Đối tượng sử dụng: cơ quan nhà nước/tổ chức phòng chống tin giả tại Việt Nam

## Business flow

10 bước, từ tạo Campaign tới tạo báo cáo — xem [04 · Business Flow](04-business-flow.md).

## 5 vai trò người dùng — `[CHƯA CODE, chưa có Auth ở bất kỳ đâu]`

| Vai trò | Trách nhiệm chính |
|---|---|
| **ADMIN** | Toàn quyền — người dùng, cấu hình hệ thống, dữ liệu dùng chung, nguồn dữ liệu |
| **MANAGER** | Tạo/kích hoạt Campaign, xử lý cảnh báo, duyệt và tạo Case, duyệt báo cáo |
| **ANALYST** | Xem dữ liệu, đánh giá nội dung, xử lý cảnh báo, tạo Case — không xóa dữ liệu/cấu hình hệ thống |
| **OPERATOR** | Quản lý nguồn dữ liệu, vận hành crawler, xử lý lỗi crawl — không xử lý nội dung/duyệt báo cáo |
| **VIEWER** | Chỉ xem dashboard và báo cáo |

Chi tiết RBAC matrix đầy đủ theo permission: xem [15 · Auth & RBAC](15-auth-rbac.md).
