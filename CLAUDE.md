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
- **Phase 3 — Scheduler & Continuous Crawl** - Chi tiết đầy đủ ở plan [docs/superpowers/plans/2026-07-20-phase3-scheduler-continuous-crawl-plan.md](docs/superpowers/plans/2026-07-20-phase3-scheduler-continuous-crawl-plan.md) và rule [17 · Continuous Crawler & Scheduler](.claude/rules/17-continuous-crawler-scheduler.md) — phần dưới đây tóm tắt đã code gì:
  - **Schema (migration 0018):** bảng `crawl_queue`, `system_settings` (seed `SCHEDULER_ENABLED`/`AI_AUTO_TRIGGER` mặc định `'false'`), `campaign_articles`, `campaign_article_keywords` (bảng phụ tự thêm ngoài rule 03 gốc — lưu ĐẦY ĐỦ mọi từ khóa trúng, không chỉ 1); cột `sources.crawl_frequency/last_crawled_at/status/consecutive_error_count`; partial unique index `articles_source_id_url_hash_continuous_key` trên `(source_id, url_hash) WHERE job_id IS NULL` — dedup toàn cục cho continuous crawl, KHÔNG đụng `UNIQUE(job_id, url_hash)` của jobs cũ.
  - **Pipeline (`backend/workers/continuous_crawl.py`, `backend/workers/scheduler.py`):** Celery Beat quét mỗi 60s (`list_due_sources`) → `crawl_task(source_id)` = Discover (`discover_source_urls`, tái dùng `_get_candidates` của `report_job.py`) → Fetch (`fetch_pending_urls`, tái dùng `fetch_article_dispatch`, tự chuyển `sources.status=ERROR` sau >10 chu kỳ lỗi liên tiếp theo BR-SRC-03) → Matching từ khóa hậu-crawl (`match_campaigns_for_article`) → AI trigger theo bài (`maybe_analyze_article`, đọc `AI_AUTO_TRIGGER`).
  - **API:** `PUT /api/sources/{id}` (mới — tài liệu cũ ghi nhầm đã code, thực tế trước Phase 3 chỉ có `GET`), `GET`/`PUT /api/system-settings`.
  - **FE tối thiểu:** modal sửa nguồn (`source_group`/`crawl_frequency`/`status`) trên `/sources`; Card "Giám sát liên tục" (2 công tắc) trên `/system/settings`.
  - **2 bug thật phát hiện lúc smoke test Docker thật (2026-07-21), đã sửa:**
    1. Discover ban đầu quét `date_from=2000-01-01` mỗi chu kỳ — với nguồn dùng `_SITEMAP_URL_TEMPLATES` sinh 1 URL sub-sitemap/tháng (VD `vtv.vn`), việc này tạo ~300+ request HTTP/chu kỳ, vi phạm nguyên tắc "không spam request" (rule 11) và có nguy cơ bị chặn IP. **Sửa:** đổi sang cửa sổ trượt `_DISCOVER_LOOKBACK_DAYS = 30` ngày tính từ `today`, không quét vô hạn về quá khứ.
    2. `crawl_frequency` ngắn hơn thời gian 1 chu kỳ Fetch xử lý hết backlog (nguồn có nhiều bài) → Beat enqueue chồng nhiều `crawl_task` cho CÙNG 1 source_id → 2 tiến trình cùng fetch trùng URL, tiến trình sau bị `IntegrityError` (đúng thiết kế partial unique index) nhưng crash cả task, mất tiến độ batch. **Sửa:** bắt `IntegrityError` quanh insert `Article`, rollback + đánh dấu `crawl_queue` `'fetched'` + tiếp tục xử lý URL còn lại thay vì crash — có unit test tái hiện race điều kiện (`test_fetch_pending_urls_skips_gracefully_on_concurrent_duplicate_insert`).
  - **2 bug bổ sung phát hiện ở final whole-branch review (2026-07-21), đã sửa:**
    3. `PUT /api/sources/{id}` không có ngưỡng dưới cho `crawl_frequency` — Admin/Operator gọi API trực tiếp (bỏ qua FE) có thể đặt giá trị quá nhỏ, tái diễn bug #1 ở quy mô rộng hơn. **Sửa:** thêm `_MIN_CRAWL_FREQUENCY_SECONDS = 300`, trả 400 nếu thấp hơn — khớp đúng `min={5}` phút FE đã có sẵn.
    4. `fetch_pending_urls` dùng `fetched_articles` (chỉ bài MỚI) để quyết định reset/tăng `consecutive_error_count` — nếu 1 chu kỳ TOÀN bài bị `IntegrityError` (race #2 ở trên, không phải site lỗi thật), `fetched_articles` rỗng → tính nhầm là lỗi, có thể oan chuyển `status=ERROR` sau nhiều chu kỳ race liên tiếp. **Sửa:** thêm biến đếm riêng `handled_count` (gồm cả bài IntegrityError) làm căn cứ BR-SRC-03.
  - **Verify:** 263/263 test pass, smoke test Docker thật (crawl thật VTV News qua sitemap thật, AI phân tích không bật `AI_AUTO_TRIGGER`), xác nhận song song `jobs`/`campaigns` không xung đột (7 bài `job_id` khác NULL + 143 bài `job_id=NULL` cùng 1 nguồn, dedup đúng cả 2 phía), final whole-branch review (Opus) kết luận "Ready to merge — With fixes", 4 Important tìm thấy (2 đã sửa như trên, 2 còn lại ghi nhận là giới hạn thiết kế bên dưới, chưa cần quyết định gấp vì `AI_AUTO_TRIGGER` mặc định tắt).
  - **Chưa làm trong Phase 3 (đúng phạm vi đã chốt):** `POST`/`DELETE /api/sources` (nợ tài liệu cũ, không thuộc Phase 3), Content review/Alert/Case (Phase 4-6), xóa `jobs` (Phase 7).
  - **Giới hạn thiết kế đã biết, chưa giải quyết (ghi nhận để theo dõi, cần quyết định của user trước khi bật `AI_AUTO_TRIGGER`/mở rộng Scheduler cho nhiều nguồn bận rộn):**
    - Chưa có cơ chế khóa phân tán (distributed lock) ngăn hẳn việc 2 `crawl_task` cùng `source_id` chạy chồng lấn — bản sửa hiện tại chỉ *chống crash*, không *chống lãng phí* (2 tiến trình vẫn cùng tải trùng nội dung, dù không ghi trùng DB). Chấp nhận được vì `crawl_frequency` tối thiểu giờ đã 300s và mặc định 1800s, đủ dài cho hầu hết nguồn sau chu kỳ "bắt kịp" (catch-up) đầu tiên.
    - `maybe_analyze_article` gọi AI **đồng bộ, tuần tự trong chính `crawl_task`** (không enqueue thành task Celery riêng như rule 17 mô tả "enqueue AI ngay") — với Ollama CPU-only có lúc >100s/bài (rule 07/10), 1 `crawl_task` có backlog vừa phải có thể chạy hàng chục phút, làm tăng đúng nguy cơ chồng lấn (race #2/#4 ở trên). Chưa ảnh hưởng vì `AI_AUTO_TRIGGER` mặc định `false` — cần quyết định (tách AI thành task Celery riêng, hay chấp nhận rủi ro) trước khi bật thật.
    - `match_campaigns_for_article` chỉ chạy trên bài MỚI fetch trong chu kỳ hiện tại — Campaign kích hoạt SAU khi 1 nguồn đã crawl lâu (hoặc thêm từ khóa mới vào Campaign đang chạy) sẽ KHÔNG tự động match ngược lại các bài cũ đã có sẵn trong `articles` (dedup toàn cục theo Source khiến URL cũ không bao giờ được fetch lại để chạy qua matching lần nữa). Cần quyết định: chấp nhận "theo dõi chỉ tính từ lúc kích hoạt" (giới hạn hiện tại), hay xây thêm bước back-match khi kích hoạt Campaign (việc lớn hơn, chưa có trong phạm vi Phase 3).
- **Phase 4 — Content Repository & Review Workflow (hoàn thành 2026-07-21)** — Chi tiết đầy đủ ở plan [~/.claude/plans/h-y-d-a-v-o-ti-n-cuddly-cocke.md] và rule [17 · Continuous Crawler & Scheduler](.claude/rules/17-continuous-crawler-scheduler.md) mục "Nội dung (Content)" — phần dưới đây tóm tắt đã code gì:
  - **Schema (migration 0019):** thêm 5 cột vào `articles` — `review_status` (mặc định `'NEW'`, NOT NULL), `reviewed_by` (FK `users.user_id`, `ondelete="RESTRICT"`), `reviewed_at`, `reviewer_note`, `deleted_at` (cột dự phòng cho BR-CONTENT-04, **chưa có nơi nào ghi giá trị** — chờ endpoint xóa ở phase sau). Verify round-trip `alembic downgrade -1 && upgrade head` sạch. Không cần migration permission mới — `content.view`/`content.review` đã seed sẵn từ migration 0011.
  - **API (`backend/routers/contents.py`, mới):** `GET /api/contents` (filter `campaign_id`/`source_id`/`sentiment`/`review_status`/`date_from`/`date_to`, loại `deleted_at IS NOT NULL`), `GET /api/contents/{id}` (404 nếu không tồn tại/đã xóa mềm/UUID sai định dạng), `POST /api/contents/{id}/review` (validate `review_status` theo `VALID_REVIEW_STATUSES`, ghi `audit_logs` action=`content.review`, permission `content.review` tự động enforce BR-CONTENT-03 — không cần role check riêng).
  - **Điểm kỹ thuật quan trọng:** lọc/hiển thị sentiment luôn dùng bản `article_analysis` **MỚI NHẤT/bài** (subquery `max(analyzed_at)` group by `article_id`) — tránh List/Detail hiển thị lệch nhau khi 1 bài bị AI phân tích lại nhiều lần (rule 07: `qwen3:8b` không cố định output). Lọc bằng `article_id IN (subquery)` thay vì join thẳng `ArticleAnalysis` vào query chính — tránh lỗi Postgres khi kết hợp `.distinct()`+`.order_by()` sau join. `campaign_ids`/analysis/`source_name` đều batch 1 query theo `article_id.in_([...])`, không N+1.
  - **FE (`/contents`, `/contents/:id`):** nối API thật, bỏ hẳn `attention_score/level` và persons/organizations/locations (không có dữ liệu AI thật tương ứng — tránh hiển thị số liệu giả), thay bằng `confidence`/`needs_review`/`topics[]`/`keywords[]` (dữ liệu thật từ `article_analysis`). Select đổi `review_status` bọc trong `<PermissionGuard permission="content.review">`.
  - **Verify:** 23 test mới (TDD, viết trước router) + toàn bộ 286/286 test pass, `alembic` round-trip sạch, `npm run build` không lỗi type. Smoke test thật qua Docker với đăng nhập `admin` thật và dữ liệu crawl thật (CAND): list/filter (sentiment/source/review_status) đúng, detail đầy đủ `analysis`, review cập nhật đúng + có audit log (`old_value`→`new_value` đúng), 400 cho `review_status` sai/UUID sai, 404 cho content không tồn tại. Riêng 403 cho OPERATOR/VIEWER: không verify trực tiếp bằng curl (không có tài khoản OPERATOR thật, không có mật khẩu `viewer-test`) — user chủ động chọn tin tưởng 2 automated test đã cover đúng path permission thật (`test_review_content_forbidden_for_operator_role`, `test_review_content_allowed_for_analyst_role`).
  - **Chưa làm trong Phase 4 (đúng phạm vi đã chốt):** không có endpoint `DELETE` (cột `deleted_at` chỉ dự phòng), không phân trang (giữ đúng contract rule 05 dạng mảng thuần túy — rủi ro hiệu năng dài hạn ghi nhận, chưa cần xử lý ngay).

### Phần chưa code — `[CHƯA CODE]`

Campaign FE nối API thật + migrate dữ liệu `jobs` cũ, xóa hẳn `jobs`/`/api/reports/*` (thay bằng `campaigns` mode=ONE_SHOT), Alert, Case, `POST`/`DELETE /api/sources`, `DELETE /api/contents/{id}` (soft-delete thật, cột `deleted_at` đã có sẵn từ Phase 4), Custom Role Management (Phase 10) — toàn bộ business rule/schema/API/screens đã chốt, viết thành rule chính thức [15](.claude/rules/15-auth-rbac.md)–[18](.claude/rules/18-alert-case-management.md) và gộp vào rule 03/04/05/06/07/08/09 ở trên. Thứ tự triển khai theo Phase: [docs/ROADMAP_CONTINUOUS_MONITORING.md](docs/ROADMAP_CONTINUOUS_MONITORING.md). Lịch sử đầy đủ quá trình ra quyết định: `docs/project_business/`.

### Bước tiếp theo
1. Phase 4 (Content Repository & Review Workflow) đã hoàn thành, sẵn sàng bắt đầu **Phase 5 (Alert Engine)** — xem [18 · Alert & Case Management](.claude/rules/18-alert-case-management.md) mục BR-ALERT, [docs/ROADMAP_CONTINUOUS_MONITORING.md](docs/ROADMAP_CONTINUOUS_MONITORING.md). Lý do làm Alert sau Content review: Alert/Case cần trỏ vào 1 Content đã có `review_status` + API xem chi tiết rõ ràng để chuyên viên xử lý — Content Repository là nền dữ liệu Alert/Case build lên trên, không phải ngược lại.

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
| Phase 3: dedup continuous crawl dùng **partial unique index** `(source_id, url_hash) WHERE job_id IS NULL`, KHÔNG đổi thẳng `UNIQUE(source_id, url_hash)` áp dụng toàn bảng `articles` | Đổi thẳng đòi hỏi xóa hẳn `jobs` ngay (mọi FK phụ thuộc: `article_analysis.job_id`, `report_history.job_id`) — tắt tính năng "Tạo báo cáo" on-demand cho tới khi Phase 7 xây lại trên `campaigns mode=ONE_SHOT`. User từ chối đánh đổi này, giữ nguyên jobs chạy song song tới Phase 7 |
| Phase 3: AI phân tích theo bài (`article_id`), không theo Campaign — `article_analysis` không có cột `campaign_id` | Kết quả AI là thuộc tính của nội dung, không đổi theo Campaign nào đang xem; phân tích theo Campaign sẽ tốn gấp nhiều lần tài nguyên AI cho cùng 1 bài và có thể ra kết quả mâu thuẫn giữa các Campaign (do `qwen3:8b` không cố định seed/temperature, xem rule 07) |
| Phase 3: `campaign_articles.matched_keyword_id` = keyword_id NHỎ NHẤT trong số từ khóa trúng (không phải "từ khóa đầu tiên khai báo"); thêm bảng phụ `campaign_article_keywords` lưu ĐẦY ĐỦ mọi từ khóa trúng | `campaign_keywords` không có cột thứ tự khai báo nên "từ khóa đầu tiên" không có nghĩa thật — chọn `keyword_id` làm tiêu chí sắp xếp xác định (deterministic). User yêu cầu FE phải hiện được đủ mọi từ khóa trúng (Phase 4), không chỉ 1 — nên thêm bảng phụ thay vì đổi PK bảng chính |
| Phase 3: tách cột `sources.status` (ACTIVE/INACTIVE/ERROR, riêng cho Scheduler) khỏi `sources.is_active` (có sẵn, riêng cho luồng Job) | 2 khái niệm lệch nhau trong thực tế (VD ẩn nguồn khỏi sidebar Job nhưng vẫn để Scheduler crawl nền) — `status=ERROR` còn là trạng thái **tự động** hệ thống set (BR-SRC-03), không thể dùng chung 1 cột boolean |
| Phase 3: Discover dùng cửa sổ trượt 30 ngày (`_DISCOVER_LOOKBACK_DAYS`), không quét "từ năm 2000" như thiết kế ban đầu | Phát hiện bug thật lúc smoke test Docker: quét vô hạn về quá khứ khiến nguồn dùng `_SITEMAP_URL_TEMPLATES` (VD vtv.vn) tạo ~300+ request/chu kỳ — vi phạm nguyên tắc không spam request, nguy cơ bị chặn IP |
| Phase 3: bắt `IntegrityError` quanh insert Article trong `fetch_pending_urls`, rollback + đánh dấu `crawl_queue` xong thay vì để crash cả task | Phát hiện race điều kiện thật: `crawl_frequency` ngắn hơn 1 chu kỳ Fetch (nguồn có backlog lớn) khiến Beat enqueue chồng nhiều `crawl_task` cùng nguồn, 2 tiến trình cùng fetch trùng URL — partial unique index chặn đúng nhưng không được để crash mất tiến độ batch |
| Phase 3: worktree thực thi plan (`.claude/worktrees/`) bị hủy bỏ giữa chừng, chuyển toàn bộ sang thực thi trực tiếp trên `main` | User yêu cầu rõ ràng không dùng worktree cho việc thực thi plan của dự án này (đã lặp lại yêu cầu này trước đó) |
| Phase 4: thêm cột `articles.deleted_at` ngay trong migration 0019, nhưng KHÔNG làm endpoint `DELETE` | Chuẩn bị sẵn cho BR-CONTENT-04 (rẻ, additive), nhưng làm endpoint xóa vượt phạm vi 3 API đã chốt ở rule 05 — dời sang phase có nhu cầu thật |
| Phase 4: không thêm phân trang cho `GET /api/contents`, giữ đúng contract rule 05 (mảng thuần túy) | Giữ đúng contract đã chốt, tránh phá vỡ FE đang code theo response shape hiện tại — rủi ro hiệu năng dài hạn (bảng `articles` tăng liên tục) ghi nhận riêng, không phải việc của Phase 4 |
| Phase 4: lọc/hiển thị sentiment luôn qua bản `article_analysis` MỚI NHẤT/bài (subquery `max(analyzed_at)`), không join thẳng bảng `article_analysis` vào query chính | Tự phát hiện lúc tự review lại plan (không phải bug thật đã xảy ra): join thẳng có nguy cơ (1) List/Detail hiển thị sentiment khác nhau cho cùng 1 bài nếu AI đã phân tích lại nhiều lần (rule 07 — `qwen3:8b` không cố định output), (2) lỗi Postgres khi kết hợp `.distinct()` với `.order_by()` sau join |
| Phase 4: bỏ hẳn `attention_score/attention_level` và trường persons/organizations/locations khỏi FE Content (2 trang), thay bằng `confidence`/`needs_review`/`topics[]`/`keywords[]` | Mock cũ có các trường này nhưng AI pipeline thật (rule 07) không sinh ra — giữ lại sẽ hiển thị số liệu giả, vi phạm nguyên tắc "mọi kết luận trong báo cáo phải có nguồn dữ liệu thực tế" (rule 11) |
| Phase 4: không verify trực tiếp 403 cho OPERATOR/VIEWER bằng curl, dùng lại 2 automated test đã có | Không có tài khoản OPERATOR thật và không có mật khẩu tài khoản `viewer-test` — user chủ động chọn tin tưởng test tự động (cùng code path `require_permission("content","review")` mà server thật đang chạy) thay vì tạo tài khoản tạm |

### Vấn đề cần làm rõ (chưa chốt)


## Roadmap

Chi tiết đầy đủ đã chuyển ra file riêng — mục này chỉ giữ bản tóm tắt trạng thái. **Đây là MỘT lộ trình sửa/bổ sung code hiện tại về đúng nghiệp vụ, không phải 2 lộ trình của 2 giai đoạn sản phẩm khác nhau:**

- [docs/ROADMAP_MVP.md](docs/ROADMAP_MVP.md) — **nhật ký lịch sử** những gì đã hiện thực được tới nay (Slice 0–5. Dùng để biết code hiện có tới đâu, không phải mô tả một sản phẩm hoàn chỉnh.
- [docs/ROADMAP_CONTINUOUS_MONITORING.md](docs/ROADMAP_CONTINUOUS_MONITORING.md) — lộ trình Phase 0–9 để sửa/bổ sung code hiện tại cho khớp nghiệp vụ đúng, đặc tả đầy đủ ở rule [15](.claude/rules/15-auth-rbac.md)–[18](.claude/rules/18-alert-case-management.md). Phase 0–4 (chốt phạm vi, Auth & RBAC, Campaign & Master Data, Scheduler & Continuous Crawl, Content Repository & Review Workflow) đã hoàn thành trên `main` — sẵn sàng bắt đầu Phase 5 (Alert Engine).
