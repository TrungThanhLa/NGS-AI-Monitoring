# NGS Monitor — Màn hình mới, UI & RBAC Matrix đề xuất

> Kế thừa design system hiện có (Vite + React + AntD `^6.5.1`, xem `.claude/rules/09-frontend-ui.md`) — không đổi thư viện, không đổi phong cách. Chỉ mô tả màn hình/route **mới** cần thêm và RBAC matrix cho toàn bộ hệ thống (bao gồm cả phần hiện có).

---

## 1. Sidebar mở rộng

Sidebar hiện tại đã có cấu trúc 9 mục (Dashboard, Campaigns, Sources*, Contents, Alerts, Cases, Jobs, Reports*, System — dấu `*` là 2 trang thật hiện có). Khi triển khai các module mới, chuyển dần các trang đang mock (Dashboard) và mock hoàn toàn (Campaigns, Alerts, Cases) sang nối API thật theo đúng route đã có sẵn trong codebase FE — không cần tạo route mới, chỉ cần nối service.

**Trang "Jobs" (đã chốt 2026-07-16, hệ quả gộp Job vào Campaign — xem `06_OPEN_DECISIONS.md` mục 1):** không còn là module riêng — sáp nhập vào trang `/campaigns` (List Campaign lọc theo `mode=ONE_SHOT` để xem các báo cáo "chạy nhanh 1 lần", `mode=CONTINUOUS` để xem chiến dịch giám sát dài hạn). Route `/jobs` gỡ bỏ khỏi sidebar khi Module Campaign chuyển sang API thật.

## 2. Màn hình mới cần nối API thật (theo thứ tự ưu tiên gợi ý — xem roadmap file `07`)

### Module Auth (mới hoàn toàn)
| Màn hình | Route | Field/Action |
|---|---|---|
| Login | `/login` | Tên đăng nhập, Mật khẩu → JWT. Redirect Dashboard sau khi thành công |
| Profile | `/profile` | Xem/đổi mật khẩu, thông tin cá nhân |

### Module Campaign (hiện đang mock — chuyển thành thật)
| Màn hình | Route | Chi tiết |
|---|---|---|
| List | `/campaigns` | Filter: từ khóa, trạng thái, người phụ trách. Cột: Mã, Tên, Người phụ trách, Trạng thái, Số nguồn, Số nội dung, Hành động. Row actions: Xem/Sửa/Kích hoạt/Tạm dừng/Lưu trữ |
| Form | `/campaigns/new`, `/campaigns/:id/edit` | Section: Thông tin chung, Từ khóa (tùy chọn), Nguồn dữ liệu, Ngưỡng cảnh báo. Validate: tên bắt buộc, kích hoạt cần ≥1 nguồn |

### Module Content (mở rộng từ bảng "crawl trực tiếp" hiện có)
| Màn hình | Route | Chi tiết |
|---|---|---|
| List | `/contents` | Filter: chiến dịch, nguồn, chủ đề, sentiment, trạng thái đánh giá, khoảng thời gian |
| Detail | `/contents/:id` | Nội dung đầy đủ + kết quả AI (chủ đề/sentiment/emotion/confidence) + form đánh giá nghiệp vụ + cảnh báo/vụ việc liên quan |

### Module Alert (hiện đang mock — chuyển thành thật)
| Màn hình | Route | Chi tiết |
|---|---|---|
| List | `/alerts` | Filter: trạng thái, mức độ, loại cảnh báo, chiến dịch. Row actions: Xác nhận/Chuyển xử lý/Tạo vụ việc/Đóng |
| Detail | `/alerts/:id` | Thông tin cảnh báo, nội dung liên quan (nếu có), lịch sử xử lý |

### Module Case (hiện đang mock — chuyển thành thật)
| Màn hình | Route | Chi tiết |
|---|---|---|
| List | `/cases` | Filter: trạng thái, mức ưu tiên, người phụ trách. Row actions: Xem/Sửa/Đóng vụ việc |
| Form | `/cases/new`, `/cases/:id/edit` | Tên, Mô tả, Mức ưu tiên, Người phụ trách, Nội dung liên quan, Tệp đính kèm, Kết quả xử lý |

### Module System (mở rộng)
| Màn hình | Route | Chi tiết |
|---|---|---|
| User Management | `/system/users` | CRUD người dùng, gán vai trò |
| Role Management | `/system/roles` | Xem permission theo vai trò (không cho sửa 5 vai trò hệ thống) |
| Audit Log | `/system/audit-logs` | Chỉ xem, filter theo user/hành động/thời gian |

### Dashboard (hiện đang mock — chuyển thành thật)
- Widget: Tổng số nội dung, Nội dung hôm nay, Cảnh báo mới, Vụ việc đang xử lý.
- Chart: xu hướng theo thời gian, theo nguồn, theo sentiment.
- Bảng: nội dung mức độ chú ý cao, cảnh báo mới nhất.

### Monitoring Feed (chỉ triển khai ở giai đoạn sau — Phase 8 roadmap)
- Giao diện dạng Card thay Table, cập nhật real-time qua WebSocket, filter đa chiều — chi tiết thiết kế khi tới giai đoạn triển khai, không mô tả sâu ở đây vì phụ thuộc nhiều quyết định UX chưa chốt.

---

## 3. Quy ước UI (kế thừa, không đổi)

Không lặp lại toàn bộ design token đã có — dự án hiện tại dùng theme AntD mặc định (`^6.5.1`). Khi thêm màn hình mới:
- Dùng `StatusTag` cho các trạng thái (`ACTIVE`/`INACTIVE`/`DRAFT`... ) — tái sử dụng component `StatusTag` đã có trong `frontend/src/components/common/`.
- Cần thêm mới: `SeverityTag` (cho mức độ cảnh báo `LOW/MEDIUM/HIGH/CRITICAL`), `PermissionGuard` (ẩn nút theo quyền — chưa có vì chưa có Auth).
- Bulk action bar cho các bảng danh sách (Campaign/Alert/Case) — theo pattern bảng hiện có ở trang Sources/Reports.

---

## 4. RBAC Matrix đề xuất

> Rút gọn từ bộ đầy đủ, chỉ giữ permission cho module thực sự nằm trong roadmap gần (không tạo permission cho tính năng chưa có kế hoạch code — theo nguyên tắc ở file `01` mục 3).

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
| Hệ thống | `system.configure` | Cấu hình hệ thống | Y | N | N | N | N |

**Nguyên tắc:** Frontend chỉ ẩn/hiện theo permission qua `PermissionGuard` (UX) — Backend **luôn** kiểm tra lại permission thật ở middleware, không tin tưởng tuyệt đối vào việc ẩn nút ở FE.

**Seed mặc định:** 5 vai trò `ADMIN/MANAGER/ANALYST/OPERATOR/VIEWER` với `is_system=true`, không cho xóa qua UI.
