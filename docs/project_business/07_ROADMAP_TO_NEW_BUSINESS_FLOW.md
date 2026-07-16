# Roadmap: NGS Monitor MVP (on-demand) → Continuous Monitoring

> **Mục đích:** lộ trình theo thứ tự để đưa dự án hiện tại (mô hình on-demand: 1 Job = 1 lần chạy trọn vẹn) tiến tới mô hình **continuous monitoring** (Campaign sống liên tục → Scheduler tự crawl → AI → Alert → Case → Report), dựa trên đặc tả ở file `01`–`05` trong cùng thư mục.
>
> ✅ **Cập nhật (2026-07-16): toàn bộ `06_OPEN_DECISIONS.md` đã chốt xong** — roadmap dưới đây đã phản ánh đúng các quyết định mới nhất (gộp Job vào Campaign, Keyword bắt buộc lọc hậu-crawl, Report không phụ thuộc Alert/Case, dedup toàn cục + `crawl_queue`, PDF/Excel/CSV, AI runtime chuyển thủ công). Vẫn là roadmap đề xuất, chưa có ước tính thời gian cụ thể — nhưng không còn quyết định nghiệp vụ nào chặn việc bắt đầu Phase 1.
>
> **Nguyên tắc xuyên suốt roadmap:** giữ nguyên các quyết định MVP đã chốt mà rủi ro cao nếu đổi — **không** thêm social media connector, **không** tách microservices (giữ 1 backend FastAPI + Celery). **AI runtime:** mặc định MVP vẫn Ollama local (`qwen3:8b`), thiết kế qua lớp `AIProvider` interface (xem `03_SYSTEM_ARCHITECTURE.md` mục 5) — chuyển sang server AI riêng hoặc API trả phí khi dự án scale là **thao tác thủ công** do người vận hành tự quyết định (đã chốt, `06_OPEN_DECISIONS.md` mục 8), không có cơ chế tự động.

---

## Tổng quan các Phase

| Phase | Tên | Vì sao đứng ở vị trí này |
|---|---|---|
| 0 | Chốt phạm vi & rule mới | Không thể code nếu chưa quyết định rõ áp dụng bao nhiêu phần của đặc tả mới |
| 1 | Auth & RBAC | Mọi phase sau đều phụ thuộc (Campaign có `owner_id`, Case có `assigned_to`, Alert có `acknowledged_by`...) |
| 2 | Data model — Campaign & Master Data | Nền tảng cho Scheduler, Alert, Case; đổi từ "Job đơn lẻ" sang "Campaign sống" |
| 3 | Scheduler & Continuous Crawl | Phụ thuộc Campaign (chỉ Campaign ACTIVE mới được crawl định kỳ) |
| 4 | Content Repository & Review Workflow | Cần nội dung có trạng thái đánh giá nghiệp vụ trước khi Alert/Case có thể gắn vào |
| 5 | Alert Engine | Cần Content + AI đã chạy ổn định trước khi tính ngưỡng cảnh báo |
| 6 | Case Management | Cần Alert tồn tại trước (Case thường sinh từ Alert) |
| 7 | Report mở rộng | Không phụ thuộc gì mới về kiến trúc — có thể làm bất kỳ lúc nào sau Phase 2 |
| 8 | Monitoring Feed (UI real-time) | Cần toàn bộ pipeline Phase 3–5 chạy ổn định mới có gì để hiển thị real-time |
| 9 | Audit Log & System Settings | Có thể làm song song từ Phase 1, đặt cuối vì không chặn nghiệp vụ chính |

---

## Phase 0 — Chốt phạm vi & viết rule mới (không code)

**Thêm:**
- File rule mới `.claude/rules/15-campaign-lifecycle.md` (hoặc số kế tiếp) mô tả vòng đời Campaign đã chốt — chuyển từ nội dung file `01`–`05` sau khi các mục ở `06_OPEN_DECISIONS.md` đã được xác nhận.
- Cập nhật `CLAUDE.md` mục "Quyết định quan trọng" — ghi rõ quyết định "chuyển từ on-demand sang continuous monitoring" kèm ngày và lý do.

**Sửa:**
- `CLAUDE.md` Roadmap — thêm các Slice mới thay vì tiếp tục đánh số Slice theo mô hình on-demand cũ.

**Xóa:** không có.

**Trạng thái (2026-07-16):** toàn bộ `06_OPEN_DECISIONS.md` đã chốt — không còn việc cần làm rõ thêm trước khi bắt đầu Phase 1.

---

## Phase 1 — Auth & RBAC (nền tảng bắt buộc)

**Vì sao đầu tiên:** dự án hiện tại **chưa có Auth ở bất kỳ đâu**. Mọi entity mới ở phase sau (Campaign.owner_id, Case.assigned_to, Alert.acknowledged_by) đều cần `users` tồn tại trước.

**Thêm (theo `02_DOMAIN_MODEL_AND_DATABASE.md` mục 2.1, `04_SCREENS_UI_RBAC.md` mục 4):**
- Bảng `users, roles, permissions, user_roles, role_permissions` (migration mới).
- 5 role: `ADMIN, MANAGER, ANALYST, OPERATOR, VIEWER` với bộ permission rút gọn ở file `04` (chỉ permission cho module có trong roadmap gần).
- JWT access token (60 phút) + refresh token (7 ngày).
- Middleware `require_permission()` áp dụng cho mọi endpoint hiện có (`/api/sources`, `/api/reports/*`).
- Trang `/login` (FE) + `PermissionGuard` component.
- Rule: khóa tài khoản sau 5 lần đăng nhập sai (30 phút), password tối thiểu 8 ký tự hoa/thường/số.

**Sửa:**
- Toàn bộ API hiện có (`sources.py`, `reports.py`) — thêm `Depends(get_current_user)` + kiểm tra permission.
- FE: `MainLayout` — thêm Header hiển thị user, `PermissionGuard` bọc quanh nút Tạo/Sửa/Xóa hiện có.

**Xóa:** không có (đây là bổ sung thuần).

**Rủi ro:**
- 🔴 Đổi từ "không auth" sang "auth bắt buộc" là breaking change cho mọi API hiện có — cần xác định có cần backward-compat tạm thời hay chấp nhận đổi cứng.
- 🟡 Không tạo permission cho module chưa tồn tại — tránh nhầm lẫn giữa RBAC đã thiết kế và tính năng chưa build.

---

## Phase 2 — Data model: Campaign & Master Data

**Vì sao sau Auth:** `campaigns.owner_id` cần FK tới `users`.

**Thêm (theo `02_DOMAIN_MODEL_AND_DATABASE.md` mục 2.2):**
- Bảng `campaigns` với 5 trạng thái `DRAFT → ACTIVE → PAUSED/COMPLETED → ARCHIVED`.
- Bảng `keywords` + `campaign_keywords` (N:N) — **bắt buộc** (đã chốt 2026-07-16, `06_OPEN_DECISIONS.md` mục 2, Campaign cần ≥1 keyword mới `ACTIVE`).
- Bảng `campaign_sources` (N:N) — thay cho `jobs.source_ids UUID[]` hiện tại (mảng UUID không có ràng buộc FK, khó truy vấn ngược).
- Cột `sources.source_group` — hiện dự án chưa có khái niệm nhóm nguồn.
- API: `POST /api/campaigns`, `PUT/GET/DELETE /api/campaigns/{id}`, `POST /api/campaigns/{id}/activate`.

**Sửa:**
- `sources` — thêm cột `source_category_id`/`source_group`, giữ nguyên `parsing_rules` JSONB (đặc thù crawler hiện tại).
- `campaigns` thêm cột `mode` (`CONTINUOUS`/`ONE_SHOT`, đã chốt 2026-07-16, xem `06_OPEN_DECISIONS.md` mục 1) — thay hẳn ý tưởng `campaign_runs` từng cân nhắc.

**Xóa (đã chốt 2026-07-16 — bỏ hẳn mô hình Job on-demand, xem `06_OPEN_DECISIONS.md` mục 1):**
- Bảng `jobs` — thay bằng `campaigns` với `mode='ONE_SHOT'`.
- API `POST /api/reports/create` — thay bằng `POST /api/campaigns` kèm `mode='ONE_SHOT'`.

**Rủi ro:**
- 🔴 Đây là thay đổi schema lớn nhất — `jobs.source_ids UUID[]` hiện tại phải migrate dữ liệu cũ sang `campaign_sources` nếu muốn giữ lịch sử report cũ liên kết được.
- 🟢 (Đã giải quyết 2026-07-16) Việc lọc theo keyword diễn ra ở tầng **hậu-crawl** (Phase 3, bảng `campaign_articles`), không đụng tới crawler thô — xem `06_OPEN_DECISIONS.md` mục 2.

---

## Phase 3 — Scheduler & Continuous Crawl

**Vì sao sau Campaign:** chỉ Campaign `ACTIVE` mới được lên lịch crawl tự động.

**Thêm (theo `03_SYSTEM_ARCHITECTURE.md` mục 4, `05_CRAWLER_AI_API.md` mục 1, mọi chi tiết đã chốt 2026-07-16):**
- Celery Beat — duyệt theo **Nguồn** (không theo từng Campaign, tránh double-enqueue) — khi ≥1 Campaign `ACTIVE` tham chiếu 1 Nguồn, tự đăng ký crawl định kỳ theo `source.crawl_frequency`.
- Cột `sources.crawl_frequency` (giây, đề xuất mặc định 1800s = 30 phút cho báo điện tử VN), `sources.last_crawled_at`.
- Bảng `crawl_queue` (hàng đợi bền, tách "khám phá URL" khỏi "tải nội dung" — chống mất dữ liệu khi 1 lượt crawl bị đứt giữa chừng).
- Bảng `campaign_articles` (kết quả matching từ khóa hậu-crawl, xác định bài nào thuộc phạm vi Campaign nào).
- Công tắc `AI_AUTO_TRIGGER` trong `system_settings` (bật/tắt AI tự động chạy sau khi crawl xong — chỉ `ADMIN` được sửa).

**Sửa — thay đổi lớn nhất về nghiệp vụ (đã chốt hướng giải quyết đầy đủ):**
- **Đảo ngược quyết định "không dedup xuyên job" (2026-07-09, ghi trong `CLAUDE.md`)** → dedup chuyển sang **toàn cục theo Source** (`SHA256(url)` không giới hạn theo lần chạy) — đã chốt, xem `06_OPEN_DECISIONS.md` mục 4.
- Rủi ro "crawl lỗi/gián đoạn giữa chừng" mà quyết định cũ từng né — đã có giải pháp cụ thể qua `crawl_queue` (2 giai đoạn: khám phá URL rẻ/bền, tải nội dung có thể retry độc lập theo từng URL) — không còn là thiết kế mở.

**Xóa:**
- Cơ chế `UNIQUE (job_id, url_hash)` composite hiện tại (migration `0009`) — thay bằng `UNIQUE(source_id, url_hash)` (đã chốt).

**Rủi ro:**
- 🟡 Đảo ngược 1 quyết định đã có lý do rõ ràng (tránh dữ liệu mồ côi) — đã có thiết kế thay thế (`crawl_queue`), nhưng vẫn cần verify kỹ bằng dữ liệu thật khi code, không chỉ revert migration đơn thuần.
- 🔴 Crawl liên tục tăng tải lên các trang nguồn — có thể vi phạm nguyên tắc "không spam request" nếu không kiểm soát `crawl_frequency` hợp lý.
- 🟡 Nếu vẫn dùng Ollama **local, CPU-only** ở giai đoạn này — bật `AI_AUTO_TRIGGER=true` sẽ đẩy nhiều content vào AI queue liên tục hơn hẳn mô hình on-demand hiện tại (đã ghi nhận AI timeout thật trước đây). Khuyến nghị bắt đầu với `AI_AUTO_TRIGGER=false` (phân tích thủ công) cho tới khi có server AI đủ mạnh hoặc chuyển sang cloud API (thao tác thủ công, đã chốt `06_OPEN_DECISIONS.md` mục 8).

---

## Phase 4 — Content Repository & Review Workflow

**Vì sao ở đây:** Alert (Phase 5) cần gắn vào Content đã có trạng thái đánh giá rõ ràng; hiện tại `articles` chỉ có trạng thái kỹ thuật (`pending_analysis/analyzed/error`), không có trạng thái nghiệp vụ.

**Thêm (theo `02_DOMAIN_MODEL_AND_DATABASE.md` mục 2.6):**
- Cột `articles.review_status` (`NEW, REVIEWED, NEED_VERIFY, VERIFIED, NOT_RELEVANT, CASE_CREATED`) — tách riêng khỏi trạng thái kỹ thuật hiện có.
- Cột `reviewed_by, reviewed_at, reviewer_note`.
- API `POST /api/contents/{id}/review` — chỉ ANALYST/MANAGER được đổi trạng thái.
- Trang Content Detail (FE) — hiện dự án chưa có trang xem chi tiết 1 bài viết, chỉ có bảng danh sách "crawl trực tiếp".

**Sửa:**
- View "bảng crawl trực tiếp" hiện tại (`GET /api/reports/{job_id}/articles`) — cần tư duy lại vì với continuous crawl, không còn "1 job = 1 danh sách bài" mà là "1 Campaign = dòng nội dung liên tục".

**Xóa:** không có, đây là mở rộng.

**Rủi ro:**
- 🟡 Trộn 2 khái niệm trạng thái (kỹ thuật vs nghiệp vụ) trong cùng 1 cột dễ gây nhầm — tách cột ngay từ đầu như đã thiết kế ở file `02`.

---

## Phase 5 — Alert Engine

**Đã chốt (2026-07-16):** Report (Phase 7) **không phụ thuộc** Phase 5/6 — có thể code Report ngay sau Phase 2–3, không cần đợi Alert/Case xong. Phase 5/6 vẫn giữ trong roadmap (không bỏ), chỉ lùi độ ưu tiên code xuống sau Report. Trong lúc chưa có backend thật, FE dùng UI tĩnh (mock data) cho trang Alert/Case — đúng pattern đã áp dụng cho Dashboard/Contents/Jobs/System hiện tại (`.claude/rules/09-frontend-ui.md`), không chặn việc demo giao diện tổng thể.

**Vì sao sau Content:** Alert cần Content đã có `confidence`/`sentiment` ổn định từ AI pipeline (đã có sẵn từ Slice 3 hiện tại) và cần Campaign để biết ngưỡng cảnh báo theo từng chiến dịch.

**Thêm (theo `01_PRODUCT_VISION_AND_BUSINESS_RULES.md` mục 2.8, `02_DOMAIN_MODEL_AND_DATABASE.md` mục 2.3):**
- Bảng `alert_rules`, `alerts`.
- 3 loại cảnh báo khởi điểm: `HIGH_ATTENTION, NEGATIVE_TREND, KEYWORD_SPIKE` — tận dụng dữ liệu AI đã có sẵn, không cần thêm field mới.
- API `GET /api/alerts`, `PUT /api/alerts/{id}/status`.
- Trang Alert List (FE).

**Sửa:**
- Cần làm rõ mối quan hệ giữa `article_analysis.needs_review` (tín hiệu kỹ thuật — AI không chắc chắn) và `Alert` (tín hiệu nghiệp vụ — cần con người chú ý) — **không nên coi 2 khái niệm này là một**.

**Xóa:** không có.

**Rủi ro:**
- 🔴 Không có công thức "đúng" nào để copy cho ngưỡng cảnh báo — phải tự thiết kế rule đơn giản (threshold tĩnh) trước, calibrate bằng dữ liệu thật (xem `06_OPEN_DECISIONS.md` mục 6).

---

## Phase 6 — Case Management

**Vì sao sau Alert:** Case thường sinh từ Alert.

**Thêm:**
- Bảng `cases, case_articles, case_attachments`.
- Trạng thái: 5 bước `NEW → VERIFYING → PROCESSING → RESOLVED → CLOSED`.
- API CRUD `/api/cases`, action gán người xử lý (permission `case.assign`, chỉ MANAGER/ADMIN).
- Trang Case List + Case Form (FE).

**Sửa:** không có thay đổi lớn tới phần đã có.

**Xóa:** không có.

**Rủi ro:**
- 🟡 Cần RBAC (Phase 1) đã ổn định trước — `assigned_to`/`assigned_org` vô nghĩa nếu chưa có user thật.
- 🟢 Rủi ro thấp nhất trong các phase nghiệp vụ mới — Case là module khá độc lập, không đụng vào pipeline crawl/AI hiện có.

---

## Phase 7 — Report mở rộng (có thể làm song song, không phụ thuộc cứng vào phase khác)

**Thêm:**
- `report_history.campaign_id` thay cho `job_id` — **bắt buộc**, không còn là "nếu" (bảng `jobs` đã bị xóa hẳn từ Phase 2, đã chốt 2026-07-16, xem `06_OPEN_DECISIONS.md` mục 1).
- Định dạng xuất thêm **PDF**, **Excel (XLSX)** và **CSV** (đã chốt 2026-07-16) — dùng chung dữ liệu aggregate hiện có (`aggregator.py`), mỗi định dạng thêm 1 nhánh export mới song song `docx_generator.py`.

**Sửa:**
- Loại báo cáo — nếu áp dụng Campaign, có thể thêm loại `DAILY/WEEKLY/MONTHLY` (báo cáo định kỳ tự động) bên cạnh loại hiện tại (theo khoảng ngày tùy chọn).

**Xóa:** không có.

**Rủi ro:**
- 🟢 Thấp — module ít phụ thuộc kiến trúc, nhưng mở rộng định dạng cần xác nhận riêng vì đảo ngược 1 quyết định MVP đã chốt có chủ đích.

---

## Phase 8 — Monitoring Feed (UI Real-time)

**Vì sao cuối cùng:** phụ thuộc trọn vẹn Phase 3–5 chạy ổn định mới có gì để hiển thị real-time.

**Thêm:**
- WebSocket để đẩy content mới về FE real-time (hiện chỉ có polling 3s cho trạng thái Job).
- Giao diện Card-based thay cho "bảng crawl trực tiếp" hiện tại.
- Bộ lọc theo Campaign/Nguồn/Chủ đề/Sentiment/Trạng thái đánh giá.

**Sửa:**
- Trang `/reports` (FE hiện tại) — mối quan hệ với Monitoring Feed mới cần làm rõ: Feed có thay thế hoàn toàn luồng "tạo báo cáo" hiện tại, hay chạy song song?

**Xóa:**
- Nếu Monitoring Feed thay thế hoàn toàn — có thể bỏ bảng "crawl trực tiếp" dạng Table hiện có trong `ReportCreate.tsx`.

**Rủi ro:**
- 🔴 Đây là rework FE lớn nhất — đổi cả pattern polling→WebSocket lẫn Table→Card, nên làm sau cùng khi các phase dữ liệu đã ổn định.
- 🟡 Cần đánh giá lại mục tiêu hiệu năng (feed <5s...) có phù hợp quy mô dữ liệu thật của dự án hiện tại hay không trước khi cam kết.

---

## Phase 9 — Audit Log & System Settings (có thể làm song song từ Phase 1)

**Thêm:**
- Bảng `audit_logs` (immutable, không soft-delete) — ghi mọi hành động CREATE/UPDATE/DELETE/LOGIN/LOGOUT/EXPORT.
- Trang `/system/audit-logs` (FE) — chỉ xem, không sửa/xóa.
- `system_settings` — đưa các hằng số hiện đang hardcode trong `.env` lên UI cấu hình được, nếu cần.

**Sửa:** không đụng gì lớn tới phần đã có.

**Xóa:** không có.

**Rủi ro:** 🟢 Thấp — module độc lập, có thể làm bất cứ lúc nào sau khi có Auth (Phase 1) và middleware ghi log.

---

## Bảng tổng hợp Thêm / Sửa / Xóa theo toàn bộ roadmap

| Loại | Nội dung | Phase |
|---|---|---|
| **Thêm** | `users, roles, permissions, user_roles, role_permissions` | 1 |
| **Thêm** | `campaigns` (có cột `mode=CONTINUOUS/ONE_SHOT`, thay `jobs`), `keywords, campaign_keywords, campaign_sources` | 2 |
| **Thêm** | Celery Beat, `sources.crawl_frequency/last_crawled_at/source_group`, `crawl_queue`, `campaign_articles`, công tắc `AI_AUTO_TRIGGER` (`system_settings`) | 3 |
| **Thêm** | `articles.review_status/reviewed_by/at/note`, trang Content Detail | 4 |
| **Thêm** | `alert_rules, alerts`, trang Alert List (UI tĩnh trước, backend thật sau Report) | 5 |
| **Thêm** | `cases, case_articles, case_attachments`, trang Case List/Form (UI tĩnh trước, backend thật sau Report) | 6 |
| **Thêm** | Report format: PDF/Excel/CSV (đã chốt), `report_history.campaign_id` (bắt buộc, thay `job_id`) | 7 (có thể làm ngay sau Phase 3, không cần đợi Phase 5/6) |
| **Thêm** | WebSocket, Monitoring Feed Card UI | 8 |
| **Thêm** | `audit_logs, system_settings`, trang Audit Log | 9 |
| **Sửa** | Toàn bộ API hiện có → thêm auth + permission check | 1 |
| **Sửa** | Dedup: từ `UNIQUE(job_id, url_hash)` → `UNIQUE(source_id, url_hash)` toàn cục | 3 |
| **Sửa** | `AI_CONCURRENCY`/`AI_TIMEOUT_SECONDS` — đánh giá lại cho tải liên tục; mặc định `AI_AUTO_TRIGGER=false` cho tới khi hạ tầng AI đủ mạnh | 3 |
| **Sửa** | `articles.status` — tách trạng thái kỹ thuật khỏi trạng thái nghiệp vụ | 4 |
| **Sửa** | Quan hệ `needs_review` (AI) vs `Alert` (business) — làm rõ, không gộp | 5 |
| **Xóa** | `jobs`, API `POST /api/reports/create`, cột `articles.job_id`, trang "Jobs" trên UI (sáp nhập vào `/campaigns`) | 2 |
| **Xóa** | Cơ chế "không dedup xuyên job" (migration `0009`) — quay lại dedup toàn cục theo Source | 3 |
| **Xóa** | (tuỳ chọn) Bảng "crawl trực tiếp" dạng Table nếu Monitoring Feed thay thế hoàn toàn | 8 |
| **Không đổi** | Không social media, không tách microservices, `AI_CONFIDENCE_THRESHOLD=0.6`, toàn bộ crawler parser hiện có, format output AI (JSON topics/keywords/sentiment/emotion/confidence) | — |
| **Có thể đổi khi scale (không phải MVP, chuyển THỦ CÔNG)** | AI runtime: Ollama local → server AI riêng hoặc API trả phí (Claude/ChatGPT/Gemini/DeepSeek...), qua lớp `AIProvider` interface + biến `AI_PROVIDER` trong `.env` | 3, 5+ |

---

## Trước khi bắt đầu Phase 1

**Cập nhật (2026-07-16):** `06_OPEN_DECISIONS.md` đã chốt toàn bộ — không còn quyết định nghiệp vụ nào chặn việc bắt đầu code Phase 1. Roadmap này vẫn **chưa có ước tính thời gian cụ thể** (best/realistic/worst case theo tuần) — đây là việc còn lại duy nhất trước khi coi roadmap là kế hoạch thực thi đầy đủ.
