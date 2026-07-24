# Roadmap: sửa & hoàn thiện NGS Monitor theo đúng nghiệp vụ Continuous Monitoring

> **Trạng thái (cập nhật 2026-07-24): Phase 0–4 và Phase 7 đã CODE xong trên `main`, sẵn sàng bắt đầu Phase 5 (Alert Engine).** Ghi nhận ban đầu 2026-07-16 khi mới chốt thiết kế (chưa code) đã lỗi thời — xem CLAUDE.md mục "Trạng thái dự án & Quyết định quan trọng" để biết trạng thái mới nhất theo thời gian thực, file này chỉ giữ vai trò lộ trình theo Phase (thứ tự Thêm/Sửa/Xóa + rủi ro), không phải nguồn trạng thái authoritative. Đặc tả chi tiết đầy đủ (business rules, schema, API, screens) đã chuyển thành rule chính thức trong `.claude/rules/` — [01 · Project Overview](../.claude/rules/01-project-overview.md) (tầm nhìn), rule 03/04/05/06/07/08/09 (schema/flow/API/crawler/AI/report/UI, mỗi phần đánh dấu `[ĐÃ CODE]`/`[CHƯA CODE]`), và [15](../.claude/rules/15-auth-rbac.md)–[18](../.claude/rules/18-alert-case-management.md) (business rules riêng từng domain mới). Lịch sử quá trình ra quyết định đầy đủ (lý do từng lựa chọn) vẫn giữ ở `docs/project_business/06_OPEN_DECISIONS.md` để tham khảo.
>
> **Đây không phải roadmap cho "giai đoạn phát triển tiếp theo" tách biệt** — đây là lộ trình **sửa/bổ sung code on-demand hiện có** (lịch sử triển khai ở [ROADMAP_MVP.md](ROADMAP_MVP.md)) cho khớp với nghiệp vụ giám sát liên tục đã chốt là nghiệp vụ đúng duy nhất (xem [01 · Project Overview](../.claude/rules/01-project-overview.md)).
>
> **Nguyên tắc xuyên suốt roadmap:** giữ nguyên các quyết định đã chốt mà rủi ro cao nếu đổi — **không** thêm social media connector, **không** tách microservices (giữ 1 backend FastAPI + Celery). **AI runtime:** mặc định vẫn Ollama local (`qwen3:8b`), qua lớp `AIProvider` interface — chuyển sang server AI riêng hoặc API trả phí khi scale là **thao tác thủ công**, không có cơ chế tự động (xem [07 · AI Pipeline](../.claude/rules/07-ai-pipeline.md)).

---

## Tổng quan các Phase

| Phase | Tên | Vì sao đứng ở vị trí này |
|---|---|---|
| 0 | Chốt phạm vi & viết rule mới | ✅ Hoàn thành — rule [01](../.claude/rules/01-project-overview.md), 03–09, [15](../.claude/rules/15-auth-rbac.md)–[18](../.claude/rules/18-alert-case-management.md) đã cập nhật/tạo, `CLAUDE.md` đã cập nhật (2026-07-16) |
| 1 | Auth & RBAC | ✅ Hoàn thành — mọi phase sau đều phụ thuộc (Campaign có `owner_id`, Case có `assigned_to`, Alert có `acknowledged_by`...) |
| 2 | Data model — Campaign & Master Data | ✅ Hoàn thành — nền tảng cho Scheduler, Alert, Case; đổi từ "Job đơn lẻ" sang "Campaign sống" |
| 3 | Scheduler & Continuous Crawl | ✅ Hoàn thành — phụ thuộc Campaign (chỉ Campaign ACTIVE mới được crawl định kỳ) |
| 4 | Content Repository & Review Workflow | ✅ Hoàn thành — cần nội dung có trạng thái đánh giá nghiệp vụ trước khi Alert/Case có thể gắn vào |
| 5 | Alert Engine | **Đang chờ bắt đầu** — cần Content + AI đã chạy ổn định trước khi tính ngưỡng cảnh báo. **Không chặn Phase 7** |
| 6 | Case Management | Cần Alert tồn tại trước (Case thường sinh từ Alert). **Không chặn Phase 7** |
| 7 | Report mở rộng | ✅ Hoàn thành — không phụ thuộc Alert/Case, đã làm ngay sau Phase 2–3 |
| 8 | Monitoring Feed (UI real-time) | Cần toàn bộ pipeline Phase 3–5 chạy ổn định mới có gì để hiển thị real-time |
| 9 | Audit Log & System Settings | Có thể làm song song từ Phase 1, đặt cuối vì không chặn nghiệp vụ chính |
| 10 | Custom Role Management | Đề xuất 2026-07-17 — hoãn tới sau Phase 7 (Report), cần xử lý rủi ro thiết kế trước khi code (xem mục riêng cuối file) |

---

## Phase 0 — Chốt phạm vi & viết rule mới ✅ Hoàn thành (2026-07-16)

- [x] Rule mới [01 · Project Overview](../.claude/rules/01-project-overview.md), [15 · Auth & RBAC](../.claude/rules/15-auth-rbac.md), [16 · Campaign Management](../.claude/rules/16-campaign-management.md), [17 · Continuous Crawler & Scheduler](../.claude/rules/17-continuous-crawler-scheduler.md), [18 · Alert & Case Management](../.claude/rules/18-alert-case-management.md).
- [x] `CLAUDE.md` mục "Quyết định quan trọng" — ghi quyết định "chuyển từ on-demand sang continuous monitoring" kèm ngày/lý do.
- [x] `CLAUDE.md` Roadmap — tách Slice cũ ra [ROADMAP_MVP.md](ROADMAP_MVP.md), thêm tham chiếu roadmap mới (file này).

---

## Phase 1 — Auth & RBAC (nền tảng bắt buộc) ✅ Hoàn thành

**Vì sao đầu tiên:** dự án hiện tại **chưa có Auth ở bất kỳ đâu**. Mọi entity mới ở phase sau (`campaigns.owner_id`, `cases.assigned_to`, `alerts.acknowledged_by`) đều cần `users` tồn tại trước.

**Thêm** (chi tiết đầy đủ ở [15 · Auth & RBAC](../.claude/rules/15-auth-rbac.md)):
- Bảng `users, roles, permissions, user_roles, role_permissions`.
- 5 role với RBAC matrix rút gọn (chỉ permission cho module có trong roadmap gần).
- JWT access token (60 phút) + refresh token (7 ngày).
- Middleware `require_permission()` áp dụng cho mọi endpoint hiện có (`/api/sources`, `/api/reports/*`).
- Trang `/login` (FE) + `PermissionGuard` component.

**Sửa:**
- Toàn bộ API hiện có (`sources.py`, `reports.py`) — thêm `Depends(get_current_user)` + kiểm tra permission.
- FE `MainLayout` — thêm Header hiển thị user, `PermissionGuard` bọc quanh nút Tạo/Sửa/Xóa hiện có.

**Xóa:** không có (bổ sung thuần).

**Rủi ro:**
- 🔴 Đổi từ "không auth" sang "auth bắt buộc" là breaking change cho mọi API hiện có — cần xác định có cần backward-compat tạm thời hay chấp nhận đổi cứng.
- 🟡 Không tạo permission cho module chưa tồn tại — tránh nhầm lẫn giữa RBAC đã thiết kế và tính năng chưa build.

---

## Phase 2 — Data model: Campaign & Master Data ✅ Hoàn thành

**Vì sao sau Auth:** `campaigns.owner_id` cần FK tới `users`.

**Thêm** (chi tiết đầy đủ ở [16 · Campaign Management](../.claude/rules/16-campaign-management.md)):
- Bảng `campaigns` (5 trạng thái, cột `mode=CONTINUOUS/ONE_SHOT` thay `jobs`).
- Bảng `keywords` + `campaign_keywords` — **bắt buộc** (Campaign cần ≥1 keyword mới `ACTIVE`).
- Bảng `campaign_sources` (N:N) — thay cho `jobs.source_ids UUID[]` hiện tại (mảng UUID không có ràng buộc FK, khó truy vấn ngược).
- Cột `sources.source_group`.
- API: `POST /api/campaigns`, `PUT/GET/DELETE /api/campaigns/{id}`, `POST /api/campaigns/{id}/activate`.

**Sửa:**
- `sources` — thêm `source_group`, giữ nguyên `parsing_rules` JSONB (đặc thù crawler hiện tại).

**Xóa:**
- Bảng `jobs` — thay bằng `campaigns` với `mode='ONE_SHOT'`.
- API `POST /api/reports/create` — thay bằng `POST /api/campaigns` kèm `mode='ONE_SHOT'`.

**Rủi ro:**
- 🔴 Thay đổi schema lớn nhất — `jobs.source_ids UUID[]` hiện tại phải migrate dữ liệu cũ sang `campaign_sources` nếu muốn giữ lịch sử report cũ liên kết được.
- 🟢 (Đã giải quyết) Lọc theo keyword diễn ra ở tầng hậu-crawl (Phase 3, bảng `campaign_articles`), không đụng crawler thô.

---

## Phase 3 — Scheduler & Continuous Crawl ✅ Hoàn thành

**Vì sao sau Campaign:** chỉ Campaign `ACTIVE` mới được lên lịch crawl tự động.

**Thêm** (chi tiết đầy đủ ở [17 · Continuous Crawler & Scheduler](../.claude/rules/17-continuous-crawler-scheduler.md)):
- Celery Beat — duyệt theo **Nguồn** (không theo từng Campaign, tránh double-enqueue).
- Cột `sources.crawl_frequency` (mặc định 1800s = 30 phút), `sources.last_crawled_at`.
- Bảng `crawl_queue` (hàng đợi bền, 2 giai đoạn — chống mất dữ liệu khi crawl bị đứt giữa chừng).
- Bảng `campaign_articles` (matching từ khóa hậu-crawl).
- Công tắc `AI_AUTO_TRIGGER` trong `system_settings` (chỉ `ADMIN` được sửa).

**Sửa — thay đổi lớn nhất về nghiệp vụ (đã có giải pháp đầy đủ):**
- Đảo ngược quyết định "không dedup xuyên job" (2026-07-09) → dedup chuyển sang **toàn cục theo Source**.
- Rủi ro "crawl lỗi/gián đoạn giữa chừng" — giải quyết qua `crawl_queue` (2 giai đoạn, retry độc lập theo từng URL).

**Xóa:**
- Cơ chế `UNIQUE(job_id, url_hash)` (migration `0009`) — thay bằng `UNIQUE(source_id, url_hash)`.

**Rủi ro:**
- 🟡 Đảo ngược quyết định cũ — đã có thiết kế thay thế (`crawl_queue`), vẫn cần verify kỹ bằng dữ liệu thật khi code.
- 🔴 Crawl liên tục tăng tải lên trang nguồn — có thể vi phạm nguyên tắc "không spam request" nếu không kiểm soát `crawl_frequency` hợp lý.
- 🟡 Nếu vẫn Ollama local CPU-only — bật `AI_AUTO_TRIGGER=true` sẽ đẩy nhiều content vào AI queue hơn hẳn on-demand (đã ghi nhận timeout thật trước đây). Khuyến nghị bắt đầu với `AI_AUTO_TRIGGER=false`.

---

## Phase 4 — Content Repository & Review Workflow ✅ Hoàn thành

**Vì sao ở đây:** Alert (Phase 5) cần gắn vào Content đã có trạng thái đánh giá rõ ràng; hiện tại `articles` chỉ có trạng thái kỹ thuật.

**Thêm** (chi tiết ở [17 · Continuous Crawler & Scheduler](../.claude/rules/17-continuous-crawler-scheduler.md)):
- Cột `articles.review_status/reviewed_by/reviewed_at/reviewer_note` — tách riêng khỏi trạng thái kỹ thuật.
- API `POST /api/contents/{id}/review` — chỉ ANALYST/MANAGER được đổi trạng thái.
- Trang Content Detail (FE) — chưa có trang xem chi tiết 1 bài viết, chỉ có bảng "crawl trực tiếp".

**Sửa:**
- View "bảng crawl trực tiếp" (`GET /api/reports/{job_id}/articles`) — cần tư duy lại: không còn "1 job = 1 danh sách bài" mà là "1 Campaign = dòng nội dung liên tục".

**Xóa:** không có, đây là mở rộng.

**Rủi ro:**
- 🟡 Trộn 2 khái niệm trạng thái (kỹ thuật vs nghiệp vụ) trong cùng 1 cột dễ gây nhầm — tách cột ngay từ đầu.

---

## Phase 5 — Alert Engine

**Không chặn Phase 7 (Report)** — Report có thể code ngay sau Phase 2–3, không cần đợi Alert/Case. Trong lúc chưa có backend thật, FE dùng UI tĩnh (mock) cho trang Alert/Case, đúng pattern đã áp dụng cho các trang mock hiện có.

**Vì sao sau Content:** Alert cần Content đã có `confidence`/`sentiment` ổn định và cần Campaign để biết ngưỡng cảnh báo theo từng chiến dịch.

**Thêm** (chi tiết ở [18 · Alert & Case Management](../.claude/rules/18-alert-case-management.md)):
- Bảng `alert_rules`, `alerts`.
- 3 loại cảnh báo khởi điểm: `HIGH_ATTENTION, NEGATIVE_TREND, KEYWORD_SPIKE`.
- API `GET /api/alerts`, `PUT /api/alerts/{id}/status`. Trang Alert List (FE).

**Sửa:**
- Làm rõ mối quan hệ `article_analysis.needs_review` (tín hiệu kỹ thuật) vs `Alert` (tín hiệu nghiệp vụ) — **không gộp 2 khái niệm này**.

**Xóa:** không có.

**Rủi ro:**
- 🔴 Không có công thức "đúng" nào để copy cho ngưỡng cảnh báo — bắt đầu bằng rule cứng (`confidence >= 0.8`), calibrate bằng dữ liệu thật.

---

## Phase 6 — Case Management

**Vì sao sau Alert:** Case thường sinh từ Alert. **Không chặn Phase 7** (giống Phase 5).

**Thêm** (chi tiết ở [18 · Alert & Case Management](../.claude/rules/18-alert-case-management.md)):
- Bảng `cases, case_articles, case_attachments`.
- API CRUD `/api/cases`. Trang Case List + Case Form (FE).

**Sửa:** không có thay đổi lớn tới phần đã có.

**Xóa:** không có.

**Rủi ro:**
- 🟡 Cần RBAC (Phase 1) đã ổn định trước — `assigned_to`/`assigned_org` vô nghĩa nếu chưa có user thật.
- 🟢 Rủi ro thấp nhất trong các phase nghiệp vụ mới — Case khá độc lập, không đụng pipeline crawl/AI.

---

## Phase 7 — Report mở rộng ✅ Hoàn thành (đã làm ngay sau Phase 2–3, không đợi Phase 5/6)

**Thêm:**
- `report_history.campaign_id` thay `job_id` — bắt buộc (bảng `jobs` đã xóa từ Phase 2).
- Định dạng xuất thêm **PDF**, **Excel (XLSX)**, **CSV** — dùng chung dữ liệu aggregate hiện có (`aggregator.py`), mỗi định dạng thêm 1 nhánh export song song `docx_generator.py`.

**Sửa:**
- Loại báo cáo — nếu áp dụng Campaign, có thể thêm `DAILY/WEEKLY/MONTHLY` (báo cáo định kỳ tự động) bên cạnh loại hiện tại (theo khoảng ngày tùy chọn).

**Xóa:** không có.

**Rủi ro:**
- 🟢 Thấp — module ít phụ thuộc kiến trúc.

---

## Phase 10 — Custom Role Management (đề xuất 2026-07-17, hoãn tới sau Phase 7)

> Đề xuất phát sinh khi hoàn thiện Phase 1: cho phép ADMIN **tạo role tùy chỉnh** qua UI (chọn permission có sẵn qua checkbox, không tự định nghĩa permission code mới). Schema `roles.is_system` đã có sẵn để chừa chỗ cho nhánh này (role `is_system=false`), nhưng API/UI/rule hiện tại (BR-USER-01, rule 05 `GET /api/roles` read-only) chưa hỗ trợ. Chi tiết đầy đủ: `docs/superpowers/specs/2026-07-17-phase1-auth-rbac-completion-design.md` mục "Ghi chú roadmap — Custom Role".

**Vì sao hoãn tới sau Phase 7:** không chặn nghiệp vụ chính (Campaign/Scheduler/Alert/Case đều dùng role cố định là đủ), và cần thời gian xử lý rủi ro thiết kế trước khi code — làm vội sẽ lặp lại đúng sai lầm "code trước khi rule chốt" mà dự án từng gặp.

**Rủi ro cần xử lý trước khi bắt đầu code (không phải chỉ liệt kê, mà phải có quyết định rõ cho từng mục):**
1. Cập nhật chính thức BR-USER-01 (rule 15) + rule 05 (thêm `POST/PUT/DELETE /api/roles`) — role không còn "5 cố định" mà là "5 mặc định `is_system=true` không xóa được + custom role `is_system=false` tạo được qua UI".
2. Thêm `GET /api/permissions` — API liệt kê permission khả dụng để UI hiển thị checkbox (hiện chưa tồn tại).
3. **Không có ràng buộc phụ thuộc giữa permission** ở bất kỳ đâu trong hệ thống hiện tại (mỗi `require_permission()` kiểm tra độc lập) — cần tự thêm 1 bảng ánh xạ nhỏ hardcode (VD `PERMISSION_IMPLIES = {"case.close": ["case.view"]}`), theo đúng triết lý "rule cứng, không xây engine tổng quát" đã áp dụng ở Alert Rule Engine (rule 18) — không có sẵn hạ tầng nào hỗ trợ việc này.
4. Rủi ro "shadow-admin": role tùy chỉnh gộp đủ permission nhóm Hệ thống (`user.manage/role.manage/audit_log.view/system.configure`) sẽ tương đương ADMIN nhưng khó nhận diện qua tên — cần cảnh báo UI rõ ràng + bắt buộc ghi `audit_logs` khi tạo/sửa role loại này.
5. Business rule mới cho xóa role đang có user gắn — DB đã có `ON DELETE RESTRICT` (`role_permissions`/`user_roles`) chặn ở tầng DB, nhưng API cần bắt lỗi này và trả message rõ ràng thay vì để lộ lỗi DB thô.

**Đã chuẩn bị sẵn ở Phase 1 (đợt hoàn thiện Auth/RBAC, 2026-07-17):** UI `RoleFormModal` (tạo/sửa role + checkbox chọn permission thật) đã dựng tĩnh, phủ overlay "Đang phát triển", chưa nối API — khi tới lượt Phase 10, chỉ cần xử lý 5 rủi ro trên rồi bỏ overlay + nối API thật.

**Rủi ro:**
- 🟡 Trung bình — không đụng pipeline crawl/AI, nhưng đụng trực tiếp rule bảo mật/phân quyền đã chốt (BR-USER-01) — cần review kỹ trước khi đổi.

---

## Phase 8 — Monitoring Feed (UI Real-time)

**Vì sao cuối cùng:** phụ thuộc trọn vẹn Phase 3–5 chạy ổn định mới có gì để hiển thị real-time.

**Thêm:**
- WebSocket đẩy content mới về FE real-time (hiện chỉ polling 3s cho trạng thái Job).
- Giao diện Card-based thay "bảng crawl trực tiếp" hiện tại.
- Bộ lọc theo Campaign/Nguồn/Chủ đề/Sentiment/Trạng thái đánh giá.

**Sửa:**
- Trang `/reports` hiện tại — làm rõ quan hệ với Monitoring Feed mới: thay thế hoàn toàn luồng "tạo báo cáo", hay chạy song song?

**Xóa:**
- Nếu Monitoring Feed thay thế hoàn toàn — có thể bỏ bảng "crawl trực tiếp" dạng Table trong `ReportCreate.tsx`.

**Rủi ro:**
- 🔴 Rework FE lớn nhất — đổi cả pattern polling→WebSocket lẫn Table→Card, làm sau cùng khi các phase dữ liệu đã ổn định.
- 🟡 Đánh giá lại mục tiêu hiệu năng (feed <5s) có phù hợp quy mô dữ liệu thật hay không trước khi cam kết.

---

## Phase 9 — Audit Log & System Settings (có thể làm song song từ Phase 1)

**Thêm** (chi tiết ở [15 · Auth & RBAC](../.claude/rules/15-auth-rbac.md)):
- Bảng `audit_logs` (immutable, không soft-delete).
- Trang `/system/audit-logs` (FE) — chỉ xem.
- `system_settings` — đưa hằng số hardcode trong `.env` lên UI cấu hình được (VD `AI_AUTO_TRIGGER`, có thể triển khai sớm hơn ở Phase 3 chỉ với 1 dòng setting).

**Sửa:** không đụng gì lớn tới phần đã có.

**Xóa:** không có.

**Rủi ro:** 🟢 Thấp — module độc lập, có thể làm bất cứ lúc nào sau khi có Auth (Phase 1).

---

## Bảng tổng hợp Thêm / Sửa / Xóa theo toàn bộ roadmap

| Loại | Nội dung | Phase |
|---|---|---|
| **Thêm** | `users, roles, permissions, user_roles, role_permissions` | 1 |
| **Thêm** | `campaigns` (`mode=CONTINUOUS/ONE_SHOT`, thay `jobs`), `keywords, campaign_keywords, campaign_sources` | 2 |
| **Thêm** | Celery Beat, `sources.crawl_frequency/last_crawled_at/source_group`, `crawl_queue`, `campaign_articles`, công tắc `AI_AUTO_TRIGGER` (`system_settings`) | 3 |
| **Thêm** | `articles.review_status/reviewed_by/at/note`, trang Content Detail | 4 |
| **Thêm** | `alert_rules, alerts`, trang Alert List (UI tĩnh trước, backend thật sau Report) | 5 |
| **Thêm** | `cases, case_articles, case_attachments`, trang Case List/Form (UI tĩnh trước, backend thật sau Report) | 6 |
| **Thêm** | Report format PDF/Excel/CSV, `report_history.campaign_id` (bắt buộc, thay `job_id`) | 7 (ngay sau Phase 3) |
| **Thêm** | WebSocket, Monitoring Feed Card UI | 8 |
| **Thêm** | `audit_logs, system_settings`, trang Audit Log | 9 |
| **Sửa** | Toàn bộ API hiện có → thêm auth + permission check | 1 |
| **Sửa** | Dedup: `UNIQUE(job_id, url_hash)` → `UNIQUE(source_id, url_hash)` toàn cục | 3 |
| **Sửa** | `AI_CONCURRENCY`/`AI_TIMEOUT_SECONDS` — đánh giá lại cho tải liên tục; mặc định `AI_AUTO_TRIGGER=false` cho tới khi hạ tầng AI đủ mạnh | 3 |
| **Sửa** | `articles.status` — tách trạng thái kỹ thuật khỏi trạng thái nghiệp vụ | 4 |
| **Sửa** | Quan hệ `needs_review` (AI) vs `Alert` (business) — làm rõ, không gộp | 5 |
| **Xóa** | `jobs`, API `POST /api/reports/create`, cột `articles.job_id`, trang "Jobs" trên UI (sáp nhập vào `/campaigns`) | 2 |
| **Xóa** | Cơ chế "không dedup xuyên job" (migration `0009`) — quay lại dedup toàn cục theo Source | 3 |
| **Xóa** | (tuỳ chọn) Bảng "crawl trực tiếp" dạng Table nếu Monitoring Feed thay thế hoàn toàn | 8 |
| **Không đổi** | Không social media, không tách microservices, `AI_CONFIDENCE_THRESHOLD=0.6`, toàn bộ crawler parser hiện có, format output AI (JSON topics/keywords/sentiment/emotion/confidence) | — |
| **Có thể đổi khi scale (không phải MVP, chuyển THỦ CÔNG)** | AI runtime: Ollama local → server AI riêng hoặc API trả phí, qua `AIProvider` interface + biến `AI_PROVIDER` trong `.env` | 3, 5+ |

---

## Trước khi bắt đầu Phase 1

Không còn quyết định nghiệp vụ nào chặn việc bắt đầu code. Việc còn lại duy nhất: **ước tính thời gian cụ thể** (best/realistic/worst case theo tuần) cho từng Phase — chưa có, sẽ bổ sung khi bắt đầu lập kế hoạch thực thi.
