---
description: Auth, RBAC & System Admin — business rules, RBAC matrix, bảo mật
alwaysApply: false
---

# 15 · Auth, RBAC & System Admin

> **Trạng thái: `[CHƯA CODE]`** — nền tảng bắt buộc, mọi module khác phụ thuộc (Campaign có `owner_id`, Case có `assigned_to`, Alert có `acknowledged_by`...). Dự án hiện tại **chưa có Auth ở bất kỳ đâu**. Schema (`users, roles, permissions, user_roles, role_permissions, audit_logs, system_settings`): xem [03 · Database Schema](03-database-schema.md). API (`/api/auth/*`, `/api/users`, `/api/roles`, `/api/audit-logs`): xem [05 · API Contracts](05-api-contracts.md). Màn hình (Login/Profile/User/Role/Audit Log): xem [09 · Frontend UI](09-frontend-ui.md).

## Business Rules — Người dùng & Phân quyền (BR-USER)

- **BR-USER-01:** 5 vai trò mặc định `ADMIN, MANAGER, ANALYST, OPERATOR, VIEWER` (xem [01 · Project Overview](01-project-overview.md)). Vai trò hệ thống (`is_system=true`) không được xóa.
- **BR-USER-02:** Quyền hạn theo RBAC matrix ở mục dưới.
- **BR-USER-03:** Người dùng phải thuộc ít nhất 1 vai trò.
- **BR-USER-04:** Tài khoản bị vô hiệu hóa (disabled) không đăng nhập được.
- **BR-USER-05:** Không được xóa tài khoản ADMIN cuối cùng của hệ thống.
- **BR-USER-06:** Permission dạng `resource.action` (VD `campaign.create`). FE ẩn menu/nút khi thiếu quyền — chỉ là UX, không thay thế kiểm tra backend.
- **BR-USER-07:** Đăng nhập sai tối đa **5 lần** → khóa tài khoản **30 phút**. Access token hết hạn **60 phút**, refresh token **7 ngày**. Mật khẩu tối thiểu 8 ký tự, có hoa/thường/số. Băm bằng BCrypt.

## Bảo mật

- JWT Authentication + RBAC Authorization bắt buộc cho mọi API (`BR-SEC-01`).
- Không hardcode secret/credential trong code hay file cấu hình mẫu commit vào git (`BR-SEC-02`) — `SECRET_KEY` sinh qua `openssl rand -hex 32`, đọc từ `.env`, không có giá trị fallback mặc định trong code.
- Middleware `require_permission(resource, action)` áp dụng cho **mọi** router hiện có và mới (kể cả `/api/sources`, `/api/reports/*` đã code trước khi có Auth).
- Rate limiting cho endpoint `/auth/login` — cần thêm mới, dự án hiện tại chưa có bất kỳ rate limiting nào.
- Nếu sau này dùng cloud LLM provider (xem [07 · AI Pipeline](07-ai-pipeline.md) mục AI Runtime): không gửi kèm thông tin định danh người dùng/nội bộ trong prompt, chỉ gửi nội dung bài viết công khai đã crawl được.

## Hiệu năng

- API tra cứu/danh sách mục tiêu **< 3 giây** (`BR-PERF-01`) — không áp dụng cho API kích hoạt crawl/AI chạy nền.
- Số người dùng đồng thời mục tiêu **< 10** (phù hợp quy mô 1 cơ quan/đơn vị).

## RBAC Matrix

> Rút gọn — chỉ giữ permission cho module thực sự nằm trong roadmap gần, không tạo permission cho tính năng chưa có kế hoạch code.

| Module | Permission Code | Mô tả | ADMIN | MANAGER | ANALYST | OPERATOR | VIEWER |
|---|---|---|:---:|:---:|:---:|:---:|:---:|
| Dashboard | `dashboard.view` | Xem dashboard | Y | Y | Y | Y | Y |
| Chiến dịch | `campaign.view` | Xem danh sách/chi tiết | Y | Y | Y | Y | Y |
| Chiến dịch | `campaign.create` | Tạo chiến dịch | Y | Y | N | N | N |
| Chiến dịch | `campaign.update` | Cập nhật/kích hoạt/tạm dừng | Y | Y | N | N | N |
| Chiến dịch | `campaign.archive` | Lưu trữ chiến dịch | Y | Y | N | N | N |
| Nguồn dữ liệu | `source.view` | Xem nguồn | Y | Y | Y | Y | Y |
| Nguồn dữ liệu | `source.create` / `source.update` | Tạo/sửa nguồn | Y | N | N | Y | N |
| Nguồn dữ liệu | `source.delete` | Xóa mềm nguồn | Y | N | N | N | N |
| Nội dung | `content.view` | Xem kho nội dung | Y | Y | Y | Y | Y |
| Nội dung | `content.review` | Đánh giá trạng thái nội dung | Y | Y | Y | N | N |
| Cảnh báo | `alert.view` | Xem cảnh báo | Y | Y | Y | Y | Y |
| Cảnh báo | `alert.acknowledge` / `alert.update` | Xác nhận/cập nhật cảnh báo | Y | Y | Y | N | N |
| Cảnh báo | `alert.close` | Đóng cảnh báo | Y | Y | N | N | N |
| Vụ việc | `case.view` | Xem vụ việc | Y | Y | Y | N | Y |
| Vụ việc | `case.create` / `case.update` | Tạo/sửa vụ việc | Y | Y | Y | N | N |
| Vụ việc | `case.close` | Đóng vụ việc | Y | Y | N | N | N |
| Báo cáo | `report.view` | Xem báo cáo | Y | Y | Y | N | Y |
| Báo cáo | `report.create` | Tạo báo cáo | Y | Y | Y | N | N |
| Hệ thống | `user.manage` | Quản lý người dùng | Y | N | N | N | N |
| Hệ thống | `role.manage` | Quản lý vai trò | Y | N | N | N | N |
| Hệ thống | `audit_log.view` | Xem nhật ký hệ thống | Y | N | N | N | N |
| Hệ thống | `system.configure` | Cấu hình hệ thống (gồm công tắc `AI_AUTO_TRIGGER`) | Y | N | N | N | N |

**Nguyên tắc:** FE chỉ ẩn/hiện theo permission qua `PermissionGuard` (UX) — Backend **luôn** kiểm tra lại permission thật ở middleware.

**Seed mặc định:** 5 vai trò với `is_system=true`, không cho xóa qua UI.
