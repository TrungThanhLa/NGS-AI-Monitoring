# NGS Monitor — CLAUDE.md

Nền tảng giám sát liên tục, thu thập và phân tích nội dung truyền thông phòng chống tin giả tại Việt Nam, AI chạy local. Tự động crawl định kỳ theo Campaign, tự phân tích AI, tự cảnh báo bất thường, hỗ trợ lập hồ sơ điều tra; lập báo cáo

> **Dự án dùng 2 AI phối hợp (Claude Code viết spec/plan/review, Gemini qua Antigravity thực thi)** — đọc [docs/AI_WORKFLOW.md](docs/AI_WORKFLOW.md) trước khi bắt đầu bất kỳ việc gì để nắm vai trò và quy ước bàn giao.

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

### Nghiệp vụ đúng duy nhất — và vì sao code hiện tại chưa khớp

> **Lưu ý quan trọng (chốt lại 2026-07-16, sau khi phát hiện hiểu nhầm ở lần cập nhật trước):** dự án **không có 2 giai đoạn sản phẩm nối tiếp nhau** ("MVP on-demand đã xong" rồi "Continuous Monitoring là bước phát triển tiếp theo"). Chỉ có **một nghiệp vụ đúng duy nhất** — nền tảng giám sát liên tục, Campaign sống → Scheduler → AI → Alert → Case → Report (xem [01 · Project Overview](.claude/rules/01-project-overview.md)). Cách hiện thực ban đầu (mô hình "1 Job = 1 lần crawl theo yêu cầu", không Auth, không giám sát liên tục) là một cách hiểu nghiệp vụ **chưa đúng/chưa đủ** so với nhu cầu thật, không phải một giai đoạn sản phẩm hoàn chỉnh và đúng đắn. `docs/project_business/` là hồ sơ quá trình phát hiện ra sai lệch này và chốt lại nghiệp vụ đúng; [docs/ROADMAP_CONTINUOUS_MONITORING.md](docs/ROADMAP_CONTINUOUS_MONITORING.md) là lộ trình **sửa/bổ sung code hiện tại** cho khớp với nghiệp vụ đúng — không phải lộ trình "xây thêm tính năng mới trên nền đã đúng".

### Phần đã code — `[ĐÃ CODE]` (một phần hiện thực chưa đầy đủ, đang được sửa)

- Nền tảng (DB/Celery/Ollama), crawler đa nguồn/đa engine (httpx/Crawl4AI/Playwright), AI pipeline 8 nhóm chủ đề, report DOCX, frontend Vite — nhánh gốc "crawl 1 lần theo yêu cầu" (`jobs`). Lịch sử Slice: [docs/ROADMAP_MVP.md](docs/ROADMAP_MVP.md). Nguồn BoCongAn bị WAF chặn — chấp nhận rủi ro tạm thời.
- **Phase 1 — Auth & RBAC** ([15](.claude/rules/15-auth-rbac.md)): JWT (BCrypt+PyJWT) + 5 vai trò/25 permission, `require_permission()` áp mọi router; User/Role/Audit Log quản lý qua `/system/*`. Còn thiếu: custom role qua UI (Phase 10).
- **Phase 2 — Campaign & Master Data** ([16](.claude/rules/16-campaign-management.md)): `keywords/campaigns/campaign_keywords/campaign_sources` + API CRUD đủ BR-CAMP-01→07. FE `/campaigns` đã nối API thật (không còn mock).
- **Phase 3 — Scheduler & Continuous Crawl** ([17](.claude/rules/17-continuous-crawler-scheduler.md)): Celery Beat 60s → Discover → Fetch → Matching từ khóa hậu-crawl → AI trigger (`AI_AUTO_TRIGGER`). Dedup toàn cục theo Source (partial unique index, song song không đụng `jobs`). Giới hạn còn mở: `maybe_analyze_article` chạy đồng bộ trong `crawl_task` (chưa tách task Celery riêng — chỉ rủi ro khi `AI_AUTO_TRIGGER=true`, hiện mặc định tắt); `match_campaigns_for_article` không back-match bài cũ khi Campaign kích hoạt muộn.
- **Phase 4 — Content Repository & Review Workflow**: `articles.review_status` + `/api/contents/*`, FE `/contents` nối API thật, sentiment luôn lấy bản `article_analysis` mới nhất/bài (chống lệch khi AI phân tích lại). Chưa có endpoint xóa (cột `deleted_at` mới dự phòng), chưa phân trang.
- **Phase 7 — Report mở rộng, xóa hẳn `jobs`** (làm trước Phase 5/6 vì không phụ thuộc Alert/Case, đúng roadmap): migration `0021` xóa bảng `jobs` + router `reports.py` cũ, thay bằng `POST/GET /api/campaigns/{id}/reports` (+ `cancel`/`download`) — Report giờ đi qua Campaign (`mode=ONE_SHOT` cho báo cáo nhanh). **Còn sót:** route `/jobs` (FE) chưa gỡ, vẫn là trang mock độc lập dù đáng lẽ đã sáp nhập vào `/campaigns`.
- **Campaign ONE_SHOT — giới hạn phạm vi & tiến độ crawl (2026-07-23)**: task Celery riêng `crawl_campaign_source_once` (Discover đúng `date_from`/`date_to` Campaign, không dùng chung cửa sổ CONTINUOUS — tránh 1 Campaign nhỏ kéo theo toàn bộ backlog Nguồn), bảng `campaign_crawl_progress`, `end_date<=hôm nay` bắt buộc, CONTINUOUS tự `COMPLETED` khi hết `end_date`.
- **CONTINUOUS — Discover theo phạm vi Campaign (2026-07-24, thực thi bởi Gemini Pro — Claude Code mới spot-check, CHƯA re-verify đầy đủ)**: thay cửa sổ 30 ngày cố định bằng `_compute_required_floor()` (hợp `start_date` các Campaign CONTINUOUS ACTIVE, cap 180 ngày) + `sources.discover_backfilled_from` (mốc backfill sâu nhất, chỉ tiến không lùi). `start_date` CONTINUOUS chặn cứng ≤180 ngày lúc tạo/kích hoạt. Đã xóa sạch dữ liệu crawl/campaign cũ trên DB dev (chỉ giữ `sources`) trước khi triển khai vì không tương thích ngược.
- **Vận hành CONTINUOUS ổn định (2026-07-24, Claude Code tự thiết kế/code/test TDD)**: Pause giờ `revoke(terminate=True)` task Celery đang chạy thật thay vì chỉ đổi `status` DB (trước đó task cứ chạy tiếp hết batch dù đã Pause); sửa cờ "Đang quét" (`sources.crawl_started_at`) kẹt vĩnh viễn do `SIGTERM` giết tiến trình trước khi `finally` kịp xóa cờ; sửa root cause Beat dispatch chồng chất `crawl_task` cho cùng 1 Nguồn có backlog lớn (từng thấy 22 task chồng chất/15 phút, chiếm hết worker pool) — tái dùng `crawl_started_at` làm khóa, claim nguyên tử trong `check_due_sources` trước khi dispatch, không cần cột/lock mới; `--concurrency=8` cho `celery-worker` (trước đó ăn theo core máy, không chủ đích). UI đi kèm: cột "Trạng thái" quét, ring loader theo `LAST_BEAT_TICK_AT` (tự cảnh báo nếu Beat im lặng >90s), tắt `SCHEDULER_ENABLED` tự Pause mọi Campaign CONTINUOUS Active (cảnh báo xác nhận trước).

### Phần chưa code — `[CHƯA CODE]`

Alert, Case, `POST`/`DELETE /api/sources`, `DELETE /api/contents/{id}` (soft-delete thật, cột `deleted_at` đã có sẵn từ Phase 4), Custom Role Management (Phase 10), gỡ route `/jobs` (FE, đã hết tác dụng từ khi Campaign nối API thật) — toàn bộ business rule/schema/API/screens đã chốt, viết thành rule chính thức [15](.claude/rules/15-auth-rbac.md)–[18](.claude/rules/18-alert-case-management.md) và gộp vào rule 03/04/05/06/07/08/09 ở trên. Thứ tự triển khai theo Phase: [docs/ROADMAP_CONTINUOUS_MONITORING.md](docs/ROADMAP_CONTINUOUS_MONITORING.md). Lịch sử đầy đủ quá trình ra quyết định: `docs/project_business/`.

### Bước tiếp theo
1. Phase 1–4 và Phase 7 (Report mở rộng, xóa `jobs`) đã hoàn thành, sẵn sàng bắt đầu **Phase 5 (Alert Engine)** — xem [18 · Alert & Case Management](.claude/rules/18-alert-case-management.md) mục BR-ALERT, [docs/ROADMAP_CONTINUOUS_MONITORING.md](docs/ROADMAP_CONTINUOUS_MONITORING.md). Lý do làm Alert sau Content review: Alert/Case cần trỏ vào 1 Content đã có `review_status` + API xem chi tiết rõ ràng để chuyên viên xử lý — Content Repository là nền dữ liệu Alert/Case build lên trên, không phải ngược lại.
2. Dọn dẹp nhỏ còn sót (không chặn Phase 5): gỡ route `/jobs` (FE) — đã dư thừa từ khi `/campaigns` nối API thật.

### Quyết định quan trọng & lý do
| Quyết định | Lý do |
|---|---|
| Không build social media (Facebook/YouTube/TikTok/Zalo) trong MVP | Cần API xác thực riêng, nội dung video không hợp pipeline text-crawl → AI-classify hiện tại |
| Crawl xử lý linh hoạt theo từng nguồn (CSS selector/pattern riêng trong `parsing_rules`) thay vì 1 cơ chế chung | Mỗi nguồn báo có đặc thù khác nhau (format ngày, độ tin cậy sitemap, cấu trúc URL) — thêm nguồn mới = thêm 1 entry cấu hình, không ảnh hưởng nguồn khác |
| `SEED_ADMIN_PASSWORD`/`SECRET_KEY` bắt buộc qua biến môi trường, không fallback hardcode | Đúng BR-SEC-02 — tránh lộ secret mặc định vào git |
| Không xây Custom Role (checkbox permission) ngay, dời Phase 10 | Chưa đủ dữ liệu vận hành để thiết kế đúng ràng buộc giữa các permission |
| Không dùng `.claude/worktrees/` khi thực thi plan, luôn code trực tiếp trên `main` | Yêu cầu rõ ràng, lặp lại nhiều lần của user cho dự án này |
| Không phân trang `GET /api/contents`, giữ contract mảng thuần túy (rule 05) | Giữ đúng contract đã chốt — rủi ro hiệu năng dài hạn ghi nhận riêng, chưa cần xử lý ngay |
| Campaign ONE_SHOT bắt buộc `end_date <= hôm nay` | ONE_SHOT là "chụp nhanh" dữ liệu quá khứ — cho phép tương lai sẽ tạo kỳ vọng sai là tự crawl tiếp như CONTINUOUS |
| CONTINUOUS Discover: cửa sổ = hợp (MIN) `start_date` mọi Campaign CONTINUOUS ACTIVE cùng theo dõi 1 Nguồn ("Option C"), không tách task riêng theo từng cặp Campaign-Nguồn ("Option B") | Option B bùng nổ số task + Discover trùng lặp giữa các Campaign chung Nguồn — Option C giữ nguyên kiến trúc "1 task/Nguồn", chỉ đổi cách tính `date_from` |
| `sources.discover_backfilled_from` chỉ tiến về quá khứ, không bao giờ co lại kể cả khi Campaign cần mốc sâu đó đã rời đi | Dữ liệu đã fetch không cần "un-fetch" — co lại chỉ khiến chu kỳ sau quét bù lại đúng phần vừa tốn công, lãng phí |
| CONTINUOUS `start_date` chặn cứng (400) trong 180 ngày trước hôm nay, không cap ngầm lúc backfill | Để người dùng biết ngay giới hạn thay vì tưởng nhầm hệ thống backfill đúng ngày họ chọn |

### Vấn đề cần làm rõ (chưa chốt)


## Roadmap

Chi tiết đầy đủ đã chuyển ra file riêng — mục này chỉ giữ bản tóm tắt trạng thái. **Đây là MỘT lộ trình sửa/bổ sung code hiện tại về đúng nghiệp vụ, không phải 2 lộ trình của 2 giai đoạn sản phẩm khác nhau:**

- [docs/ROADMAP_MVP.md](docs/ROADMAP_MVP.md) — **nhật ký lịch sử** những gì đã hiện thực được tới nay (Slice 0–5. Dùng để biết code hiện có tới đâu, không phải mô tả một sản phẩm hoàn chỉnh.
- [docs/ROADMAP_CONTINUOUS_MONITORING.md](docs/ROADMAP_CONTINUOUS_MONITORING.md) — lộ trình Phase 0–9 để sửa/bổ sung code hiện tại cho khớp nghiệp vụ đúng, đặc tả đầy đủ ở rule [15](.claude/rules/15-auth-rbac.md)–[18](.claude/rules/18-alert-case-management.md). Phase 0–4 và Phase 7 (chốt phạm vi, Auth & RBAC, Campaign & Master Data, Scheduler & Continuous Crawl, Content Repository & Review Workflow, Report mở rộng/xóa `jobs`) đã hoàn thành trên `main` — sẵn sàng bắt đầu Phase 5 (Alert Engine).
