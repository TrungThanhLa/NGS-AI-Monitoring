# NGS Monitor — CLAUDE.md

Nền tảng giám sát liên tục, thu thập và phân tích nội dung truyền thông phòng chống tin giả tại Việt Nam, AI chạy local. Tự động crawl định kỳ theo Campaign, tự phân tích AI, tự cảnh báo bất thường, hỗ trợ lập hồ sơ điều tra; lập báo cáo

## Rules

> Mỗi rule mô tả **nghiệp vụ đúng duy nhất** của dự án, không phải "rule cho giai đoạn MVP" + "rule cho giai đoạn sau" — nội dung nào chưa hiện thực được đánh dấu `[CHƯA CODE]` ngay trong file, không tách file riêng theo giai đoạn. Xem [01 · Project Overview](.claude/rules/01-project-overview.md) mục "Về trạng thái implement hiện tại" để hiểu rõ khác biệt này trước khi đọc các rule khác.

<!-- Core — luôn áp dụng -->
- [01 · Project Overview](.claude/rules/01-project-overview.md)
- [02 · Tech Stack](.claude/rules/02-tech-stack.md)
- [03 · Database Schema](.claude/rules/03-database-schema.md)
- [04 · Business Flow](.claude/rules/04-business-flow.md)
- [10 · Error Handling](.claude/rules/10-error-handling.md)
- [11 · Core Principles](.claude/rules/11-core-principles.md)
- [12 · Response Format](.claude/rules/12-response-format.md)
- [13 · Workflow](.claude/rules/13-workflow.md)
- [14 · Coding Behavior](.claude/rules/14-coding-behavior.md)

<!-- Feature-specific — đọc khi làm task liên quan -->
- [05 · API Contracts](.claude/rules/05-api-contracts.md)
- [06 · Crawler Strategy](.claude/rules/06-crawler-strategy.md)
- [07 · AI Pipeline](.claude/rules/07-ai-pipeline.md)
- [08 · DOCX Report](.claude/rules/08-docx-report.md)
- [09 · Frontend UI](.claude/rules/09-frontend-ui.md)

<!-- Module chưa code — đọc khi bắt đầu code phần tương ứng trong roadmap
     (xem docs/ROADMAP_CONTINUOUS_MONITORING.md). Business rules riêng của từng domain;
     schema/API/UI dùng chung đã gộp vào rule 03/05/09 ở trên -->
- [15 · Auth & RBAC](.claude/rules/15-auth-rbac.md)
- [16 · Campaign Management](.claude/rules/16-campaign-management.md)
- [17 · Continuous Crawler & Scheduler](.claude/rules/17-continuous-crawler-scheduler.md)
- [18 · Alert & Case Management](.claude/rules/18-alert-case-management.md)

## Quick Reference

| Thứ cần nhớ | Giá trị |
|---|---|
| AI model | `qwen3:8b` via Ollama |
| DB | PostgreSQL — 5 bảng chính |
| Confidence threshold | `0.6` — dưới này → `needs_review=true` |
| Crawler strategy | Sitemap XML → fallback listing page |
| Delay giữa request | 1–2 giây |
| Job queue | Celery + Redis |
| Sinh báo cáo | python-docx + template |

## Trạng thái dự án & Quyết định quan trọng

> Cập nhật mục này khi có tiến độ hoặc quyết định mới — đây là log tổng hợp, không thay thế checklist chi tiết ở Roadmap dưới.
> **Lịch sử chi tiết đầy đủ** (số liệu job thật, log, quá trình quyết định) đã chuyển sang [docs/CHANGELOG.md](docs/CHANGELOG.md) — mục dưới đây chỉ giữ bản tóm tắt 1 dòng/mục.

### Nghiệp vụ đúng duy nhất — và vì sao code hiện tại chưa khớp

> **Lưu ý quan trọng (chốt lại 2026-07-16, sau khi phát hiện hiểu nhầm ở lần cập nhật trước):** dự án **không có 2 giai đoạn sản phẩm nối tiếp nhau** ("MVP on-demand đã xong" rồi "Continuous Monitoring là bước phát triển tiếp theo"). Chỉ có **một nghiệp vụ đúng duy nhất** — nền tảng giám sát liên tục, Campaign sống → Scheduler → AI → Alert → Case → Report (xem [01 · Project Overview](.claude/rules/01-project-overview.md)). Cách hiện thực ban đầu (mô hình "1 Job = 1 lần crawl theo yêu cầu", không Auth, không giám sát liên tục) là một cách hiểu nghiệp vụ **chưa đúng/chưa đủ** so với nhu cầu thật, không phải một giai đoạn sản phẩm hoàn chỉnh và đúng đắn. `docs/project_business/` là hồ sơ quá trình phát hiện ra sai lệch này và chốt lại nghiệp vụ đúng; [docs/ROADMAP_CONTINUOUS_MONITORING.md](docs/ROADMAP_CONTINUOUS_MONITORING.md) là lộ trình **sửa/bổ sung code hiện tại** cho khớp với nghiệp vụ đúng — không phải lộ trình "xây thêm tính năng mới trên nền đã đúng".

### Phần đã code — `[ĐÃ CODE]` (một phần hiện thực chưa đầy đủ, đang được sửa)

- Nền tảng (DB/Celery/Ollama), crawler đa nguồn/đa engine (7 nguồn thật, httpx/Crawl4AI/Playwright), AI pipeline đầy đủ 8 nhóm chủ đề, report DOCX khớp dữ liệu thật, frontend Vite đã merge `main` — chạy được đúng nhánh "crawl 1 lần theo yêu cầu" (`jobs`), chưa có Campaign/Scheduler/Alert/Case. Lịch sử triển khai từng Slice (checklist, verify, số liệu job thật): [docs/ROADMAP_MVP.md](docs/ROADMAP_MVP.md) — đây là **nhật ký lịch sử**, không phải mô tả 1 giai đoạn sản phẩm đã hoàn chỉnh.
- Admin UI quản lý nguồn qua giao diện riêng (Slice 6 cũ) đã loại khỏi scope thực thi trực tiếp (2026-07-16) — quản lý nguồn qua API `/api/sources` hiện có là đủ.
- Nguồn BoCongAn bị WAF chặn, chưa verify job thật — không phải lỗi code, chấp nhận rủi ro tạm thời.
- **Phase 1 — Auth & RBAC (2026-07-17), hoàn thành trên branch `phase1-auth-rbac`, chưa merge `main`:** scope đã chốt "Chỉ Auth core + seed ADMIN" (không làm `/api/users`/`/api/roles` CRUD ở phase này). Chi tiết đầy đủ ở rule [15 · Auth & RBAC](.claude/rules/15-auth-rbac.md) — phần dưới đây chỉ tóm tắt đã code gì:
  - Backend: bảng `users/roles/permissions/user_roles/role_permissions` (migration 0010), seed 5 vai trò + 25 permission đúng RBAC matrix + seed 1 tài khoản `admin` (migration 0011–0013, kể cả fix thiếu `case.close` cho MANAGER). JWT access (60 phút)/refresh (7 ngày) qua BCrypt + PyJWT, khóa tài khoản 5 lần sai/30 phút, rate limit `10/phút` cho `/api/auth/login` (slowapi). `POST /api/auth/login|refresh`, `GET /api/auth/me`. Middleware `require_permission(resource, action)` đã áp cho toàn bộ endpoint hiện có (`/api/sources`, `/api/reports/*`) — **chưa** áp `/api/users`/`/api/roles` vì các API đó chưa tồn tại.
  - Frontend: `AuthContext`/`useAuth()` (JWT lưu `localStorage`), `authFetch()` (tự gắn Bearer, tự refresh 1 lần khi 401), `ProtectedRoute` (redirect `/login` nếu chưa đăng nhập), `PermissionGuard` (đã tạo, **chưa gắn** vào nút nào — permission-gating hiện chỉ ở route/endpoint, không phải action-level). Trang `/sources`, `/reports`, `/reports/create` đã đổi sang `authFetch` (kể cả download DOCX qua blob vì thẻ `<a href>` không gắn được Bearer header). `MainLayout` hiện tên user thật + nút đăng xuất.
  - **Login page UI (2026-07-17):** giao diện đã đổi sang thiết kế port từ `ngs-monitor-ui/` (gradient `AuthLayout`, Card bo góc/shadow, logo NGS, `Alert` báo lỗi) — **logic đăng nhập giữ nguyên 100%** (`useAuth()`/`AuthContext` đã review ở trên), không dùng `@tanstack/react-query`/`zustand` của project tham khảo (rule 09 cấm). `ngs-monitor-ui/` chỉ là thư mục tham khảo, không commit vào git.
  - Verify: 163 test backend pass, `npm run type-check` sạch, đã review toàn nhánh (3 Important + 2 Minor tìm được → đã fix + re-verify), đã test bằng Playwright thật trên Docker stack thật (login, 403 khi chưa đăng nhập, download report, tạo report).
  - **Còn thiếu so với rule 15 (chưa làm ở phase này, để phase sau):** `/api/users`, `/api/roles`, `/api/audit-logs` (API + UI `/system/users`, `/system/roles`), bảng `audit_logs`/`system_settings` chưa tạo, `PermissionGuard` chưa gắn vào UI thật (ẩn/hiện nút theo quyền).

### Phần chưa code — `[CHƯA CODE]`

Campaign (thay thế hoàn toàn `jobs`), Scheduler crawl liên tục, Content review, Alert, Case, User/Role management + Audit Log (phần còn lại của Auth/RBAC ngoài Auth core) — toàn bộ business rule/schema/API/screens đã chốt, viết thành rule chính thức [15](.claude/rules/15-auth-rbac.md)–[18](.claude/rules/18-alert-case-management.md) và gộp vào rule 03/04/05/06/07/08/09 ở trên. Thứ tự triển khai theo Phase: [docs/ROADMAP_CONTINUOUS_MONITORING.md](docs/ROADMAP_CONTINUOUS_MONITORING.md). Lịch sử đầy đủ quá trình ra quyết định: `docs/project_business/`.

### Bước tiếp theo
1. Quyết định cách xử lý branch `phase1-auth-rbac` (merge vào `main` / mở PR / giữ nguyên chờ thêm việc) — **đang chờ quyết định của user**, chưa chốt.
2. Sau khi Auth core lên `main`: bắt đầu Phase 2 (Campaign & Master Data) hoặc làm nốt phần User/Role management + Audit Log còn thiếu của Phase 1 — xem [docs/ROADMAP_CONTINUOUS_MONITORING.md](docs/ROADMAP_CONTINUOUS_MONITORING.md).

### Quyết định quan trọng & lý do
| Quyết định | Lý do |
|---|---|
| Không build social media (Facebook/YouTube/TikTok/Zalo) trong MVP | Cần API xác thực riêng, nội dung video không hợp pipeline text-crawl → AI-classify hiện tại|
| Crawl xử lý linh hoạt theo từng nguồn thay vì 1 cơ chế chung: lọc lại `published_at` thật sau fetch (không tin tuyệt đối sitemap `<lastmod>`), `_SITEMAP_DATE_PATTERNS` theo domain, `_get_candidates()` ưu tiên `parsing_rules.listing_pages` nếu có dù vẫn còn `sitemap_url`, 1 số site xử lý riêng ngoài sitemap (chuyên mục/CSS selector) | Mỗi nguồn báo có đặc thù khác nhau (format ngày, độ tin cậy sitemap, cấu trúc URL) — VD bocongan.gov.vn ghi `<lastmod>` giống nhau cho mọi URL, không phải ngày đăng thật; thêm nguồn mới = thêm 1 entry cấu hình, không ảnh hưởng nguồn khác |
| Listing-page crawler chỉ hỗ trợ 1 trang, không phân trang | Hiện không còn nguồn thật nào dùng — giữ lại làm fallback tổng quát (YAGNI) |
| Chỉ giữ `/sources` và `/reports` (2 trang) nối API thật; mọi trang khác (Dashboard, Campaigns, Contents, Alerts, Cases, Jobs, System/*) là mock UI-only |
| Phase 1 Auth & RBAC thu hẹp scope còn "Auth core + seed 1 ADMIN" | Tránh làm luôn CRUD user/role (vốn cần UI riêng, ít khẩn cấp hơn) trước khi có Campaign — mở khóa được toàn bộ middleware `require_permission` cho các module sau mà không cần chờ UI quản trị user hoàn chỉnh |
| `SEED_ADMIN_PASSWORD`/`SECRET_KEY` bắt buộc qua biến môi trường, không có fallback hardcode trong code | Đúng BR-SEC-02 — tránh lộ secret mặc định vào git dù chỉ là placeholder |
| Login page: chỉ port UI (Card/gradient/logo) từ `ngs-monitor-ui/`, không port state management (`@tanstack/react-query`/`zustand`) | Rule 09 cấm 2 thư viện này cho project — giữ nguyên `AuthContext` đã review, tránh trộn 2 kiến trúc quản lý state khác nhau trong cùng 1 app |

### Vấn đề cần làm rõ (chưa chốt)


## Roadmap

Chi tiết đầy đủ đã chuyển ra file riêng — mục này chỉ giữ bản tóm tắt trạng thái. **Đây là MỘT lộ trình sửa/bổ sung code hiện tại về đúng nghiệp vụ, không phải 2 lộ trình của 2 giai đoạn sản phẩm khác nhau:**

- [docs/ROADMAP_MVP.md](docs/ROADMAP_MVP.md) — **nhật ký lịch sử** những gì đã hiện thực được tới nay (Slice 0–5, chạy thật trên `main`; Slice 6 đã bỏ khỏi scope 2026-07-16). Dùng để biết code hiện có tới đâu, không phải mô tả một sản phẩm hoàn chỉnh.
- [docs/ROADMAP_CONTINUOUS_MONITORING.md](docs/ROADMAP_CONTINUOUS_MONITORING.md) — lộ trình Phase 0–9 để sửa/bổ sung code hiện tại cho khớp nghiệp vụ đúng, đặc tả đầy đủ ở rule [15](.claude/rules/15-auth-rbac.md)–[18](.claude/rules/18-alert-case-management.md). Phase 0 (chốt phạm vi) đã hoàn thành 2026-07-16 — sẵn sàng bắt đầu Phase 1 (Auth & RBAC) khi có quyết định triển khai.
