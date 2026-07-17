# Phase 1 Auth & RBAC — hoàn thiện phần còn thiếu

**Ngày:** 2026-07-17
**Trạng thái:** Đã duyệt design, chờ viết plan

## Bối cảnh

Phase 1 (Auth & RBAC) đã merge vào `main` với scope "Auth core + seed ADMIN": JWT login/refresh/change-password, khóa tài khoản, `require_permission()` áp cho `/api/sources` và `/api/reports/*`, FE có `AuthContext`/`authFetch`/`ProtectedRoute`/`PermissionGuard`.

Còn thiếu so với rule [15 · Auth & RBAC](../../../.claude/rules/15-auth-rbac.md) và [05 · API Contracts](../../../.claude/rules/05-api-contracts.md):
1. `/api/users` (CRUD) + UI `/system/users`
2. `/api/roles` (read-only) + UI `/system/roles`
3. `audit_logs` (bảng + API + UI `/system/audit-logs`)
4. `PermissionGuard` chưa gắn vào UI thật — chỉ có 1 tài khoản ADMIN nên RBAC matrix chưa test được với vai trò khác

Việc này chặn khả năng verify RBAC (không tạo được user vai trò khác để test).

**Phát hiện quan trọng trong lúc explore:** 3 trang mock UI hiện có (`System/Users`, `System/Roles`, `System/AuditLogs`) được thiết kế vượt xa schema/API thật đã chốt — role ảo (`EDITOR/AUDITOR/GUEST`), tab "phân quyền tùy chỉnh theo từng user" (không có bảng `user_permissions` override trong schema — quyền chỉ đến từ role qua `user_roles`+`role_permissions`), field không tồn tại (avatar, phòng ban, ngày hết hạn, gửi email), Excel import/export, và cho phép tạo/sửa/tạm ngưng role tùy ý (rule 05 chỉ định nghĩa `GET /api/roles`, BR-USER-01 nói rõ 5 role `is_system=true` không xóa/sửa qua UI). Ngoài ra `UserForm.tsx` + 2 route `/system/users/new`, `/system/users/:id/edit` là code trùng lặp với `UserModal.tsx` — không nơi nào trong UI trỏ tới 2 route này (UsersPage dùng thẳng modal).

**Quyết định:** viết lại 2 trang Users/Roles gọn theo đúng schema thật (giữ phong cách AntD hiện có), xóa `UserForm.tsx` + 2 route orphan.

## Phạm vi

Làm cả 4 mảng theo thứ tự: users → roles → audit_logs → gắn PermissionGuard.

**Ngoài phạm vi (không làm ở đợt này):**
- `system_settings` (dùng cho công tắc `AI_AUTO_TRIGGER` — thuộc Phase 3 Scheduler, chưa cần)
- Ghi audit log cho Source/Report CRUD (chỉ ghi cho hành động thuộc Auth/RBAC module đang làm)
- Đổi mật khẩu qua UI admin cho user khác (chỉ tự đổi mật khẩu của chính mình qua `/api/auth/change-password` đã có)

## Backend

### Migration

Bảng `audit_logs` đúng schema rule 03 — bất biến, không soft-delete:

```sql
CREATE TABLE audit_logs (
    audit_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID REFERENCES users(user_id),
    action       VARCHAR(100) NOT NULL,
    entity_type  VARCHAR(100),
    entity_id    UUID,
    old_value    JSONB,
    new_value    JSONB,
    ip_address   VARCHAR(100),
    user_agent   TEXT,
    created_at   TIMESTAMP DEFAULT NOW()
);
```

### `backend/audit/logger.py` (mới)

```python
def log_action(db, user, action, entity_type=None, entity_id=None,
               old_value=None, new_value=None, request=None): ...
```
Insert 1 row `audit_logs`, không commit riêng (dùng chung transaction với route gọi nó). Lấy `ip_address`/`user_agent` từ `request` nếu có.

**Điểm gọi (chỉ trong phạm vi Auth/RBAC):**
- `POST /api/auth/login` (thành công) — action `LOGIN`
- `POST /api/auth/change-password` — action `UPDATE`, entity_type `user`, entity_id chính user đó
- `POST /api/users` — action `CREATE`, entity_type `user`
- `PUT /api/users/{id}` — action `UPDATE`, entity_type `user`, kèm `old_value`/`new_value` (trước/sau các field đổi)

### `backend/routers/users.py` (mới)

```
GET  /api/users              — quyền user.manage. Filter tùy chọn: keyword, status, role_code
POST /api/users               — quyền user.manage
GET  /api/users/{id}          — quyền user.manage
PUT  /api/users/{id}          — quyền user.manage
```

**POST /api/users — request:**
```json
{"username": "...", "email": "...", "full_name": "...", "password": "...", "role_ids": ["uuid"]}
```
- `role_ids` bắt buộc ≥1 (BR-USER-03)
- Áp `is_password_strong()` có sẵn ở `backend/auth/security.py` (BR-USER-07)
- `username` unique — trùng → 409

**PUT /api/users/{id} — request (mọi field optional, partial update):**
```json
{"full_name": "...", "email": "...", "status": "ACTIVE|INACTIVE|LOCKED", "role_ids": ["uuid"]}
```
- Không cho sửa `username`/`password` qua endpoint này (đổi mật khẩu người khác ngoài phạm vi — xem "Ngoài phạm vi")
- `status`: gửi `"ACTIVE"` khi tài khoản đang `LOCKED` → tự động clear `locked_until`+`failed_login_count` (dùng lại cho nút "Mở khóa" ở UI, không cần endpoint riêng)
- **BR-USER-05:** nếu user này là ADMIN active cuối cùng (đếm user có role ADMIN + `is_active=true`+`status=ACTIVE`) → chặn set `status != ACTIVE` HOẶC bỏ role ADMIN khỏi `role_ids` → 400
- **BR-USER-03:** `role_ids` (nếu gửi) không được rỗng → 400

**Response (dùng chung cho list/detail), tái dùng `UserResponse` schema đã có ở `backend/auth/schemas.py`** (đã có `roles`, `permissions`) — bổ sung thêm `status`, `is_active`, `created_at`, `last_login_at`.

### `backend/routers/roles.py` (mới)

```
GET /api/roles   — quyền role.manage
```
Trả về 5 role kèm danh sách permission (join `role_permissions`+`permissions`) + `user_count` (đếm qua `user_roles`).

### `backend/routers/audit_logs.py` (mới)

```
GET /api/audit-logs   — quyền audit_log.view
```
Filter: `user_id, action, entity_type, date_from, date_to`. Sort `created_at DESC`. Có phân trang (`page`/`page_size`, giống pattern list hiện có nếu có, nếu chưa có pattern nào thì dùng đơn giản `limit`/`offset` mặc định `limit=50`).

### Đăng ký router

Thêm `users.router`, `roles.router`, `audit_logs.router` vào `backend/main.py` (giống cách `sources.router`/`reports.router` đã đăng ký).

## Frontend

### `System/Users`

- Xóa `frontend/src/pages/System/Users/UserForm.tsx` và 2 route `/system/users/new`, `/system/users/:id/edit` ở `App.tsx` (orphan, trùng chức năng với modal).
- Viết lại `UserModal.tsx`: bỏ tab "Phân quyền" (permission tree tùy chỉnh theo user — không có backend), bỏ avatar upload, phòng ban, ngày hết hạn, gửi email, Excel import/export. Giữ lại: họ tên, username (disable khi edit), email, mật khẩu+xác nhận (chỉ khi tạo), trạng thái (Switch Kích hoạt/Vô hiệu hóa — map `ACTIVE`⇄`INACTIVE`), chọn role (multi-select, options lấy từ `GET /api/roles`, không hardcode `ROLE_PERMS`).
- Viết lại `index.tsx`: gọi `GET /api/users` thay `mockUsers`, nút khóa/mở khóa gọi `PUT /api/users/{id}` với `{status: 'ACTIVE'}` hoặc `{status: 'INACTIVE'}`, bỏ nút Import/Export Excel (không có backend), filter role lấy option thật từ API roles.

### `System/Roles`

Viết lại `index.tsx`: bảng liệt kê 5 role thật (nối `GET /api/roles` — mã, tên, số user, danh sách permission dạng tag/expand), bỏ nút Import/Export và bỏ toggle Tạm ngưng (không có API).

**Nút "Thêm mới" + `RoleFormModal` — giữ lại nhưng đóng băng ở mức giao diện tĩnh** (quyết định 2026-07-17, xem thêm ghi chú roadmap): thêm vào modal 1 phần chọn permission dạng checkbox (list phẳng 25 permission thật, group theo `resource`, KHÔNG phải cây lồng ảo như `PERM_TREE` cũ) — nhưng toàn bộ modal vẫn giữ hành vi mock hiện có (`message.info('Đây là giao diện minh hoạ...')`, không gọi API thật). Phủ 1 lớp overlay (nền mờ + icon khóa + text **"Đang phát triển"**) lên trên nội dung modal (hoặc lên nút "Thêm mới"/"Sửa" ở bảng danh sách — chọn 1 trong 2 vị trí, ưu tiên overlay ngay trong modal để vẫn xem được giao diện đầy đủ) — ngăn tương tác thật, chỉ để xem trước hình dạng UI. Đây là phần hiện thực **cho tính năng Custom Role** đã quyết định hoãn (xem "Ghi chú roadmap" cuối file) — không kết nối API `POST/PUT/DELETE /api/roles` nào vì các endpoint này chưa tồn tại và chưa được rule 05 định nghĩa.

### `System/AuditLogs`

Nối `GET /api/audit-logs`: bỏ option filter `LOGOUT/VIEW/EXPORT` (chưa ghi log các action này), map cột `resource`→`entity_type`, `resource_id`→`entity_id`. Filter theo `date_from`/`date_to` (RangePicker) gọi đúng query param.

### PermissionGuard wiring

- **`ProtectedRoute.tsx`**: thêm prop optional `permission?: string`; nếu có và `user.permissions` không chứa → render trang "Không có quyền truy cập" (403 đơn giản) thay vì `<Outlet/>`.
- Áp `permission` cho route: `/system/users` → `user.manage`, `/system/roles` → `role.manage`, `/system/audit-logs` → `audit_log.view`, `/system/master-data`, `/system/settings`, `/system/connectors` → `system.configure`.
- Bọc `PermissionGuard` quanh nút: Sources page (Thêm/Sửa/Xóa nguồn → `source.create`/`source.update`/`source.delete`), `ReportCreate` (nút "Tạo báo cáo" → `report.create`).
- `MainLayout.tsx`: lọc menu item con theo permission tương ứng trước khi render Sider (dùng `user.permissions` từ `useAuth()`).

## Testing

- Backend: Pytest cho `users.py` (tạo user thiếu role_ids → 400, xóa role ADMIN cuối cùng → 400, khóa/mở tài khoản qua status, permission check 403 khi thiếu quyền), `roles.py` (chỉ ADMIN xem được), `audit_logs.py` (filter đúng, ghi log đúng lúc login/tạo user).
- Test thật tối thiểu theo Workflow (rule 13): tạo 1 user role `VIEWER` qua API thật, login bằng user đó, xác nhận bị chặn 403 ở endpoint cần quyền cao hơn (VD `POST /api/sources`).

## Rủi ro / điểm chưa chắc

- Enum `status` (`ACTIVE|LOCKED|INACTIVE`) và cột `is_active` (bool) trên `users` có phần chồng chéo — thiết kế này chỉ dùng `status` làm nguồn sự thật cho UI admin thao tác, `is_active` giữ nguyên logic cũ (login check) và tự động đồng bộ theo `status` (set `is_active=False` khi `status != ACTIVE`) để không phá vỡ `_is_user_usable()` hiện có.

## Ghi chú roadmap — Custom Role (hoãn, không thuộc đợt này)

Trong lúc bàn bạc (2026-07-17), có đề xuất cho phép ADMIN **tạo role tùy chỉnh** qua UI (chọn permission có sẵn qua checkbox, không tự định nghĩa permission mới). Quyết định: **hoãn**, làm sau khi Phase 1 (đợt này) và Report mở rộng (Phase 7 roadmap) hoàn thành — lý do và rủi ro chi tiết đã ghi lại, cần xử lý trước khi triển khai thật:

1. Đụng BR-USER-01 (5 role cố định) + rule 05 (`GET /api/roles` read-only) — cần cập nhật rule 05/15 chính thức trước, không code trước khi sửa rule.
2. Thiếu `GET /api/permissions` (API liệt kê permission khả dụng cho checkbox) — chưa được định nghĩa ở rule 05.
3. **Chưa có ràng buộc phụ thuộc giữa các permission** (VD tick `case.close` không tự kéo theo `case.view`) — hệ thống hiện tại (và toàn bộ roadmap đã viết) không có khái niệm này ở bất kỳ đâu, mỗi permission được `require_permission()` kiểm tra độc lập; RBAC matrix hợp lý hiện tại chỉ nhờ người viết rule tự tay đảm bảo. Nếu làm custom role, cần tự thêm 1 bảng ánh xạ phụ thuộc nhỏ hardcode trong code (theo đúng triết lý "rule cứng, không xây engine tổng quát" ở rule 18 Alert Rule Engine), không có sẵn hạ tầng nào hỗ trợ.
4. Rủi ro "shadow-admin" — role tùy chỉnh gộp đủ permission nhóm Hệ thống (`user.manage/role.manage/audit_log.view/system.configure`) sẽ tương đương ADMIN nhưng khó nhận diện qua tên role — cần cảnh báo UI + ghi audit log khi tạo/sửa role loại này.
5. Cần business rule mới cho xóa role đang có user gắn (DB đã có `ON DELETE RESTRICT` ở `role_permissions`/`user_roles`, nhưng API cần bắt lỗi và trả message rõ ràng thay vì lỗi DB thô).

**Việc đã làm trước ở đợt này:** UI `RoleFormModal` (tạo/sửa role + checkbox permission) đã dựng sẵn dạng tĩnh, phủ overlay "Đang phát triển", không nối API — xem mục `System/Roles` ở trên. Khi tới lượt làm Custom Role thật, chỉ cần: viết migration/rule/API theo 5 điểm trên, bỏ overlay, nối modal vào API thật.

**Cần thêm vào [docs/ROADMAP_CONTINUOUS_MONITORING.md](../../ROADMAP_CONTINUOUS_MONITORING.md):** thêm 1 mục ngay sau Phase 7 (Report mở rộng) ghi nhận "Custom Role Management" là công việc dự kiến kế tiếp, kèm ngày quyết định và tham chiếu 5 rủi ro trên.
