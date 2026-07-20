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
- **Phase 1 — Auth & RBAC** - Chi tiết đầy đủ ở rule [15 · Auth & RBAC](.claude/rules/15-auth-rbac.md) — phần dưới đây tóm tắt đã code gì:
  - **Auth core (2026-07-17):** bảng `users/roles/permissions/user_roles/role_permissions` + seed 5 vai trò/25 permission/1 admin (migration 0010–0014); JWT access/refresh (BCrypt + PyJWT) với khóa tài khoản, rate limit; `/api/auth/login|refresh|change-password|me`; `require_permission()` áp cho **toàn bộ endpoint hiện có** (`/api/sources`, `/api/reports/*`).
  - **User/Role/Audit Log management (2026-07-17):** đã tạo `users/roles/audit_logs` + API/FE quản lý (`/api/users`, `/api/roles`, `/api/audit-logs`, `/system/users`, `/system/roles`, `/system/audit-logs`) — **chưa triển khai cấu hình permission tùy chỉnh cho từng role** (custom role qua UI, dời sang Phase 10).
  - **Còn thiếu so với rule 15:** `system_settings` (bảng + API cấu hình `AI_AUTO_TRIGGER` qua UI) — để dành cho Phase liên quan tới Scheduler ([17 · Continuous Crawler & Scheduler](.claude/rules/17-continuous-crawler-scheduler.md)).
- **Phase 2 — Campaign & Master Data, backend** -  Chi tiết đầy đủ ở plan [docs/superpowers/plans/2026-07-20-phase2-campaign-master-data.md](docs/superpowers/plans/2026-07-20-phase2-campaign-master-data.md) và rule [16 · Campaign Management](.claude/rules/16-campaign-management.md) — phần dưới đây tóm tắt đã code gì:
  - **Schema (migration 0017):** bảng `keywords`, `campaigns`, `campaign_keywords`, `campaign_sources` + cột `sources.source_group` — verify reversible (downgrade/upgrade).
  - **API:** `GET`/`POST /api/keywords` (permission tái dùng `campaign.view`/`campaign.create`, không tạo permission `keyword.*` riêng); `POST`/`GET`/`GET {id}`/`PUT`/`DELETE` (soft-delete → `ARCHIVED`)/`POST {id}/activate`/`POST {id}/pause` cho `/api/campaigns` — đủ BR-CAMP-01 → 07.
  - **Verify:** 226/226 test pass (bao gồm regression test cho lỗi 400 sai khi payload có ID trùng lặp), smoke test HTTP thật qua Docker với tài khoản admin thật, xác nhận không đụng tới flow `jobs`/`/api/reports/*` cũ.
  - **Chưa làm trong Phase 2 (theo đúng quyết định phạm vi ban đầu):** FE vẫn mock (`/campaigns` chưa nối API thật), không migrate dữ liệu `jobs` cũ sang `campaigns`, chưa xóa `jobs`/`/api/reports/*` — để dành Phase sau.

### Phần chưa code — `[CHƯA CODE]`

Campaign FE nối API thật + migrate dữ liệu `jobs` cũ, xóa hẳn `jobs`/`/api/reports/*` (thay bằng `campaigns` mode=ONE_SHOT), Scheduler crawl liên tục, Content review, Alert, Case, `system_settings` (công tắc `AI_AUTO_TRIGGER` qua UI), Custom Role Management (Phase 10) — toàn bộ business rule/schema/API/screens đã chốt, viết thành rule chính thức [15](.claude/rules/15-auth-rbac.md)–[18](.claude/rules/18-alert-case-management.md) và gộp vào rule 03/04/05/06/07/08/09 ở trên. Thứ tự triển khai theo Phase: [docs/ROADMAP_CONTINUOUS_MONITORING.md](docs/ROADMAP_CONTINUOUS_MONITORING.md). Lịch sử đầy đủ quá trình ra quyết định: `docs/project_business/`.

### Bước tiếp theo
1. Phase 2 (Campaign & Master Data — backend) đã hoàn thành trên `main`, sẵn sàng bắt đầu **Phase 3 (Scheduler & Continuous Crawl)**, xem [docs/ROADMAP_CONTINUOUS_MONITORING.md](docs/ROADMAP_CONTINUOUS_MONITORING.md).

### Quyết định quan trọng & lý do
| Quyết định | Lý do |
|---|---|
| Không build social media (Facebook/YouTube/TikTok/Zalo) trong MVP | Cần API xác thực riêng, nội dung video không hợp pipeline text-crawl → AI-classify hiện tại|
| Crawl xử lý linh hoạt theo từng nguồn thay vì 1 cơ chế chung: lọc lại `published_at` thật sau fetch (không tin tuyệt đối sitemap `<lastmod>`), `_SITEMAP_DATE_PATTERNS` theo domain, `_get_candidates()` ưu tiên `parsing_rules.listing_pages` nếu có dù vẫn còn `sitemap_url`, 1 số site xử lý riêng ngoài sitemap (chuyên mục/CSS selector) | Mỗi nguồn báo có đặc thù khác nhau (format ngày, độ tin cậy sitemap, cấu trúc URL) — VD bocongan.gov.vn ghi `<lastmod>` giống nhau cho mọi URL, không phải ngày đăng thật; thêm nguồn mới = thêm 1 entry cấu hình, không ảnh hưởng nguồn khác |
| Listing-page crawler chỉ hỗ trợ 1 trang, không phân trang | Hiện không còn nguồn thật nào dùng — giữ lại làm fallback tổng quát (YAGNI) |
| Chỉ giữ `/sources` và `/reports` (2 trang) nối API thật; mọi trang khác (Dashboard, Campaigns, Contents, Alerts, Cases, Jobs, System/*) là mock UI-only |
| `SEED_ADMIN_PASSWORD`/`SECRET_KEY` bắt buộc qua biến môi trường, không có fallback hardcode trong code | Đúng BR-SEC-02 — tránh lộ secret mặc định vào git dù chỉ là placeholder |
| Không xây tính năng tạo Role tùy chỉnh (checkbox permission) ngay — giữ nguyên 5 vai trò cố định trong code, dời custom role sang Phase 10 riêng | Cần làm rõ ràng buộc giữa các permission trước (permission nào phụ thuộc/loại trừ permission nào) — chưa đủ dữ liệu vận hành để thiết kế đúng; UI tạo role vẫn giữ dạng tĩnh (checkbox picker) sau lớp overlay "Đang phát triển", không xóa hẳn, để tái dùng khi tới Phase 10 |
| Phase 2: chỉ thêm Campaign/Keyword mới, **không đụng** `jobs`/`/api/reports/*`/`report_job.py` hiện có, giữ 2 hệ thống song song tạm thời | Roadmap gốc có mâu thuẫn (nói "xóa `jobs`" nhưng cột FK phụ thuộc chưa gỡ tới Phase 3/7) — chọn phương án rủi ro thấp nhất, xác nhận trực tiếp với user thay vì tự suy đoán |
| Phase 2: không migrate dữ liệu `jobs` cũ sang `campaigns`, giữ nguyên dữ liệu cũ | User chọn phương án nhanh nhất, ít rủi ro nhất, chấp nhận đánh đổi không giữ liên kết lịch sử report cũ với Campaign |
| Phase 2: chỉ làm backend/API, FE giữ mock | Đúng phạm vi user chốt — tránh làm dở dang UI khi chưa quyết định thiết kế màn hình Campaign |
| Phase 2: `activate` và `pause` làm chung 1 lượt, không tách riêng | User chọn gộp để tránh phải quay lại sửa router 2 lần |
| Phase 2: `/api/keywords` chỉ có `GET`+`POST`, không có `PUT`/`DELETE`; tái dùng permission `campaign.view`/`campaign.create`, không tạo `keyword.*` riêng | User chọn phương án đơn giản nhất — keyword hiện chỉ cần tạo và liệt kê để gắn vào Campaign, chưa có nhu cầu sửa/xóa |

### Vấn đề cần làm rõ (chưa chốt)


## Roadmap

Chi tiết đầy đủ đã chuyển ra file riêng — mục này chỉ giữ bản tóm tắt trạng thái. **Đây là MỘT lộ trình sửa/bổ sung code hiện tại về đúng nghiệp vụ, không phải 2 lộ trình của 2 giai đoạn sản phẩm khác nhau:**

- [docs/ROADMAP_MVP.md](docs/ROADMAP_MVP.md) — **nhật ký lịch sử** những gì đã hiện thực được tới nay (Slice 0–5. Dùng để biết code hiện có tới đâu, không phải mô tả một sản phẩm hoàn chỉnh.
- [docs/ROADMAP_CONTINUOUS_MONITORING.md](docs/ROADMAP_CONTINUOUS_MONITORING.md) — lộ trình Phase 0–9 để sửa/bổ sung code hiện tại cho khớp nghiệp vụ đúng, đặc tả đầy đủ ở rule [15](.claude/rules/15-auth-rbac.md)–[18](.claude/rules/18-alert-case-management.md). Phase 0 (chốt phạm vi) đã hoàn thành 2026-07-16 — sẵn sàng bắt đầu Phase 1 (Auth & RBAC) khi có quyết định triển khai.
