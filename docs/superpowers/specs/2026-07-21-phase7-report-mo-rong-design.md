# Phase 7 — Report mở rộng — Design

> Trạng thái: đã thống nhất với user qua brainstorming 2026-07-21. Chưa code. Kế hoạch triển khai chi tiết sẽ viết ở `docs/superpowers/plans/2026-07-21-phase7-report-mo-rong-plan.md` (bước tiếp theo, viết bằng writing-plans skill).
>
> **Quyết định thứ tự Phase:** user chủ động chọn làm Phase 7 **trước** Phase 5 (Alert) và Phase 6 (Case) — đúng với ghi chú gốc trong roadmap ("Phase 7 không phụ thuộc Alert/Case — có thể làm ngay sau Phase 2–3"). Đây không phải đổi thứ tự nghiệp vụ, chỉ là chọn nhánh không phụ thuộc trước.

## Vì sao làm Phase 7 lúc này

Phase 0–4 (Auth, Campaign backend, Scheduler, Content Review) đã xong trên `main`. `jobs`/`/api/reports/*` vẫn chạy song song với `campaigns` từ Phase 2 — đây là nợ kỹ thuật tạm thời đã được chấp nhận có chủ đích ("giữ 2 hệ thống song song tạm thời", CLAUDE.md Phase 2). Phase 7 là lúc trả nợ: xóa hẳn `jobs`, để `campaigns` (`mode=ONE_SHOT`) thay thế hoàn toàn, đồng thời mở rộng thêm 3 định dạng xuất báo cáo (PDF/Excel/CSV).

Tham chiếu nghiệp vụ gốc: [16 · Campaign Management](../../.claude/rules/16-campaign-management.md) (BR-CAMP-07), [08 · DOCX Report](../../.claude/rules/08-docx-report.md), [03 · Database Schema](../../.claude/rules/03-database-schema.md), [05 · API Contracts](../../.claude/rules/05-api-contracts.md), `docs/ROADMAP_CONTINUOUS_MONITORING.md` mục "Phase 7".

## Phạm vi

**Trong phạm vi:**
- Xóa hẳn bảng `jobs`, router `backend/routers/reports.py`, `backend/workers/report_job.py`, cột `articles.job_id`/`article_analysis.job_id`/`report_history.job_id` — **hard-delete** toàn bộ dữ liệu cũ có `job_id != NULL` (articles/article_analysis/report_history) + file `.docx`/`.json` tương ứng trong `storage/` (đã xác nhận với user: đây là dữ liệu test, chấp nhận mất, không backup).
- Đổi `UNIQUE(job_id, url_hash)` → `UNIQUE(source_id, url_hash)` áp dụng toàn bảng `articles` (partial index của Phase 3 trở thành index thường).
- `report_history.campaign_id` (NOT NULL, FK → `campaigns`), cột `format` (`docx|json|pdf|xlsx|csv`) mới.
- Sửa `POST /api/campaigns/{id}/activate`: nếu `mode=ONE_SHOT`, dispatch Celery `chord` — crawl ngay lập tức toàn bộ Source (không đợi Beat), callback chỉ đánh dấu `status=COMPLETED` khi crawl xong — **không** tự chạy AI/report ở bước này.
- API mới `POST /api/campaigns/{id}/reports` — `{date_from, date_to, format}` → Celery task: batch AI-analyze bài `pending_analysis` trong `campaign_articles` của phạm vi đó → aggregate → sinh file theo `format` → ghi `report_history`. Dùng chung cho cả `ONE_SHOT` (sau khi `COMPLETED`) và `CONTINUOUS` (bất kỳ lúc nào).
- `backend/report/aggregator.py`: đổi `aggregate_basic(db, job_id)` → `aggregate_basic(db, campaign_id, date_from, date_to)`, join qua `campaign_articles` (không phải toàn bộ `articles` theo `source_id`).
- 3 module export mới: `pdf_generator.py` (WeasyPrint, từ HTML template), `excel_generator.py` (openpyxl), `csv_generator.py` (`csv` chuẩn) — dùng chung output của `aggregator.py`, song song `docx_generator.py` hiện có.
- Sửa `scheduler.py: check_due_sources()` — thêm điều kiện `Campaign.mode == 'CONTINUOUS'` để Beat không vô tình enqueue crawl cho Source chỉ thuộc Campaign `ONE_SHOT`.
- Sửa `continuous_crawl.py: crawl_task` — `maybe_analyze_article` chỉ chạy khi có ≥1 Campaign `CONTINUOUS ACTIVE` match bài đó (độc lập với việc có Campaign `ONE_SHOT` nào match hay không). `ONE_SHOT` không bao giờ tự trigger AI theo `AI_AUTO_TRIGGER`.
- BR-CAMP-03 (≥1 nguồn + ≥1 từ khóa để activate) áp dụng **đồng nhất mọi mode**, không có ngoại lệ cho `ONE_SHOT` — báo cáo luôn lấy dữ liệu qua `campaign_articles` (đã match từ khóa), không đọc thẳng `articles` theo `source_id`.
- FE: viết lại hoàn toàn `Campaigns/*` (List/Form/Detail) từ mock (`mockData.ts`) sang gọi API thật (`authFetch` tới `/api/campaigns/*`), tái dùng `SourceSidebar`/`SummaryCard` từ `Reports/` cho bước chọn nguồn. Thêm bước chọn từ khóa vào `CampaignForm`.
- FE: sửa `Reports/ReportCreate.tsx` — submit gọi `POST /api/campaigns` (`mode=ONE_SHOT`) rồi `POST /{id}/activate` thay vì `POST /api/reports/create`; polling đổi sang `GET /api/campaigns/{id}`.
- FE: sửa `Reports/index.tsx` — nguồn dữ liệu đổi từ `GET /api/reports/history` sang danh sách `report_history` join `campaigns` (endpoint mới hoặc mở rộng `GET /api/campaigns/{id}` trả kèm lịch sử report).
- FE: `CampaignDetail`/Reports thêm form "Tạo báo cáo" (chọn `date_from/date_to/format`) gọi `POST /api/campaigns/{id}/reports`, polling tương tự pattern job cũ.

**Ngoài phạm vi (để dành phase khác, không tự làm thêm):**
- Nhánh "AI tự động phân tích khi có server AI riêng/cloud LLM → tự sinh report → tự trigger Vụ việc/Cảnh báo" cho `ONE_SHOT` — ghi `[CHƯA CODE]`, để dành khi Alert/Case (Phase 5/6) tồn tại. `AI_AUTO_TRIGGER` trong Phase 7 chỉ còn tác dụng cho `CONTINUOUS`, đúng nguyên bản thiết kế Phase 3.
- Loại báo cáo định kỳ `DAILY/WEEKLY/MONTHLY` (rule 08 nêu là tùy chọn) — không làm trong Phase 7 lần này trừ khi user yêu cầu bổ sung ở bước viết plan.
- Alert/Case (Phase 5/6), Monitoring Feed real-time (Phase 8), Custom Role (Phase 10) — không đụng tới.
- Cơ chế lock/chống race condition tổng quát cho việc bấm "Tạo báo cáo" trùng lặp — chấp nhận rủi ro nhỏ (xem Error Handling), không xây cơ chế khóa phân tán mới.

## Kiến trúc & luồng dữ liệu

### ONE_SHOT (thay thế hoàn toàn `/reports/create` cũ)

```
FE: chọn nguồn + từ khóa + khoảng ngày → POST /api/campaigns
    {mode=ONE_SHOT, source_ids, keyword_ids (bắt buộc ≥1), start_date, end_date}
    → Campaign status=DRAFT

FE: POST /api/campaigns/{id}/activate
    → validate ≥1 source AND ≥1 keyword (BR-CAMP-03, không ngoại lệ)
    → validate status hiện tại phải là DRAFT/PAUSED (không cho activate 2 lần khi đã ACTIVE/COMPLETED — 400)
    → status=ACTIVE
    → dispatch: chord(
          group(crawl_task.s(source_id) for source_id in campaign.sources)
        )(mark_crawl_done.s(campaign_id))

crawl_task(source_id)  [KHÔNG đổi so với Phase 3 — Discover/Fetch/matching như cũ]
    → match_campaigns_for_article ghi campaign_articles (bao gồm cả Campaign ONE_SHOT này)
    → maybe_analyze_article: CHỈ chạy nếu bài đó match ≥1 Campaign CONTINUOUS ACTIVE
       (bỏ qua nếu chỉ match Campaign ONE_SHOT, bất kể AI_AUTO_TRIGGER)

mark_crawl_done(campaign_id)  [Celery chord callback — task mới]
    → status=COMPLETED  (chỉ đánh dấu, KHÔNG chạm AI/report)

FE: polling GET /api/campaigns/{id} mỗi 3s → thấy COMPLETED → hiện nút "Tạo báo cáo"
```

### Tạo báo cáo (dùng chung ONE_SHOT sau COMPLETED và CONTINUOUS bất kỳ lúc nào)

```
FE: chọn date_from/date_to (mặc định = campaign.start_date/end_date với ONE_SHOT)/format
    → POST /api/campaigns/{id}/reports {date_from, date_to, format}
    → dispatch Celery task generate_campaign_report(campaign_id, date_from, date_to, format)

generate_campaign_report(campaign_id, date_from, date_to, format)
    1. article_ids = SELECT article_id FROM campaign_articles
                     WHERE campaign_id=X AND matched_at trong [date_from, date_to]
                     (hoặc lọc theo articles.published_at — xem "Cần làm rõ" bên dưới)
    2. pending = các article_id trong (1) có articles.status='pending_analysis'
       với mỗi bài trong pending: analyze_article(title, content_raw) [hàm có sẵn, không viết mới]
                                    → INSERT article_analysis (không còn job_id)
    3. aggregates = aggregate_basic(db, campaign_id, date_from, date_to)
                     (GROUP BY nguồn/chủ đề/tháng/sentiment/emotion, join qua campaign_articles)
    4. theo `format`:
         docx → generate_docx(campaign, aggregates, path)
         json → export_json(aggregates, path)
         pdf  → generate_pdf(campaign, aggregates, path)   [WeasyPrint, module mới]
         xlsx → generate_excel(campaign, aggregates, path) [openpyxl, module mới]
         csv  → generate_csv(aggregates, path)             [csv chuẩn, module mới]
    5. INSERT report_history(campaign_id=X, format=..., file_path=path)

FE: polling trạng thái task (endpoint mới, tương tự GET /{job_id}/status cũ nhưng theo report task_id)
    → xong → Download qua report_history mới nhất
```

### Scheduler — sửa 1 điều kiện (Phase 3 → Phase 7)

```
check_due_sources()  [Celery Beat, mỗi 60s]
    SELECT DISTINCT source_id FROM sources
      JOIN campaign_sources JOIN campaigns
      WHERE campaigns.status='ACTIVE' AND campaigns.mode='CONTINUOUS'   -- THÊM điều kiện mode
      AND sources.status='ACTIVE'
    → như cũ (so crawl_frequency, enqueue crawl_task)
```

## Data Model — thay đổi schema (migration mới, số tiếp theo sau `0019`)

- **DROP** bảng `jobs`.
- **DROP** cột `articles.job_id`, `article_analysis.job_id`.
- **DROP** constraint `UNIQUE(job_id, url_hash)` trên `articles`; đổi partial index `articles_source_id_url_hash_continuous_key` (`WHERE job_id IS NULL`) thành `UNIQUE(source_id, url_hash)` áp dụng toàn bảng.
- **ALTER** `report_history`: đổi `job_id` → `campaign_id UUID NOT NULL REFERENCES campaigns(campaign_id)`, thêm `format VARCHAR(20) NOT NULL DEFAULT 'docx'`.
- **Trước khi DROP:** script migration tự đếm `SELECT COUNT(*) FROM jobs` — nếu > 5, dừng lại in cảnh báo yêu cầu xác nhận thủ công (an toàn dữ liệu, xem Error Handling). Nếu ≤ 5 (đúng kỳ vọng hiện tại — dữ liệu test), tự động xóa `jobs` + `articles`/`article_analysis`/`report_history` có `job_id` cũ + file `.docx`/`.json` liên quan trong `storage/`.
- **Không đổi:** `campaigns`, `campaign_sources`, `campaign_keywords`, `campaign_articles`, `campaign_article_keywords`, `crawl_queue`, `system_settings` — schema Phase 2/3 giữ nguyên.

## Error Handling

| Tình huống | Xử lý |
|---|---|
| 1 `crawl_task` con trong chord lỗi hoàn toàn (crash, không phải lỗi từng URL — lỗi từng URL đã tự bắt như Phase 3/rule 10) | Chord vẫn chạy callback `mark_crawl_done` (dùng `chord(...).apply_async(link_error=...)` hoặc bọc try/except trong từng `crawl_task` để không propagate exception ra ngoài group) — Campaign vẫn `COMPLETED`, log cảnh báo Source nào lỗi, báo cáo tổng hợp trên phần dữ liệu crawl được, không chặn toàn bộ |
| `generate_campaign_report` task crash giữa chừng (AI timeout hàng loạt, DB lỗi) | Theo đúng pattern lỗi AI có sẵn (rule 10): 1 bài AI timeout → skip (`status='error'`), tiếp tục các bài còn lại. Nếu cả task crash hoàn toàn → không ghi `report_history`, FE polling thấy `failed`, người dùng bấm lại "Tạo báo cáo" |
| Bấm "Tạo báo cáo" 2 lần liên tiếp cho cùng Campaign+khoảng ngày trước khi lần 1 xong | Cho phép chạy trùng, không lock — giống hành vi cũ (`reports.py` cũ chỉ *warn*, không chặn). Tác động thực tế nhỏ vì bước AI chỉ xử lý bài `pending_analysis` (bài đã `analyzed` không phân tích lại) |
| Migration xóa `jobs` chạy trên DB có nhiều dữ liệu thật hơn kỳ vọng | Tự đếm trước khi xóa (xem Data Model) — dừng + cảnh báo nếu vượt ngưỡng nhỏ, không xóa mù quáng |
| `POST /{id}/activate` gọi 2 lần (double-click) | Chặn ở API: `status` đã `ACTIVE`/`COMPLETED`/`ARCHIVED` → trả 400, không dispatch chord lần 2 |
| Source vừa thuộc Campaign `ONE_SHOT` đang activate, vừa thuộc Campaign `CONTINUOUS` khác đang crawl nền (Beat) | Không cần xử lý đặc biệt — dedup toàn cục `UNIQUE(source_id, url_hash)` (đã đổi ở Phase 7) đảm bảo an toàn, 2 lượt trùng chỉ tốn tải, không sinh lỗi/dữ liệu trùng |

## Testing

- **Backend (Pytest, TDD theo rule 13):**
  - `aggregator.py`: `aggregate_basic(db, campaign_id, date_from, date_to)` trả đúng dữ liệu qua `campaign_articles`, loại đúng bài ngoài khoảng ngày/không match từ khóa.
  - `campaigns.py`: `activate` với `mode=ONE_SHOT` dispatch đúng chord (mock Celery), `activate` 2 lần → 400, thiếu keyword/source → 400 (mọi mode).
  - `mark_crawl_done`: test set đúng `COMPLETED`, không tự chạy AI/report.
  - `POST /api/campaigns/{id}/reports`: test sinh đúng cả 4 định dạng, batch AI chỉ chạy trên bài `pending_analysis`, không phân tích lại bài `analyzed`.
  - `scheduler.py`: test filter `mode=CONTINUOUS` — Source chỉ thuộc Campaign `ONE_SHOT` không bị Beat enqueue.
  - `continuous_crawl.py`: test `maybe_analyze_article` chỉ chạy khi có ≥1 Campaign `CONTINUOUS ACTIVE` match; không chạy nếu chỉ match Campaign `ONE_SHOT`.
  - Migration: round-trip `alembic downgrade -1 && upgrade head` sạch; test riêng logic đếm-trước-khi-xóa `jobs`.
- **Generator PDF/Excel/CSV:** mỗi định dạng sinh file hợp lệ (đọc lại bằng `openpyxl`/`csv.reader`/kiểm tra PDF header), đối chiếu số liệu khớp bản DOCX cùng input — đảm bảo 4 định dạng không lệch số liệu.
- **Smoke test thật (Docker, bắt buộc theo rule 13):** tạo 1 Campaign `ONE_SHOT` với ≥1 nguồn thật + ≥1 từ khóa thật → activate → xác nhận crawl ngay (không đợi Beat) → COMPLETED → bấm "Tạo báo cáo" → xác nhận AI chạy + sinh đúng cả 4 định dạng, số liệu khớp nhau.
- **FE:** kiểm tra thủ công `/campaigns`, `/campaigns/new`, `/campaigns/:id`, `/reports/create` (đã đổi sang gọi Campaign API), `/reports` (danh sách lịch sử mới) — golden path + thiếu source/keyword.

## Cần làm rõ khi viết plan (chưa chốt hoàn toàn, không chặn thiết kế tổng thể)

1. **`generate_campaign_report` lọc theo `campaign_articles.matched_at` hay `articles.published_at`?** — `matched_at` là lúc hệ thống ghi nhận match (gần với `crawled_at`), `published_at` là ngày đăng bài thật. Với `ONE_SHOT`, `start_date`/`end_date` mang ý nghĩa "khoảng ngày đăng bài cần báo cáo" (giống `date_from`/`date_to` cũ của Job) — nên nhiều khả năng phải lọc theo `articles.published_at`, cần join thêm `articles` thay vì chỉ dùng `matched_at`. Sẽ chốt cụ thể khi viết plan, tham chiếu cách `report_job.py` cũ đã lọc (`published_at` trong `date_from`–`date_to`, rule 10).
2. **Endpoint polling trạng thái `generate_campaign_report`** — dùng cơ chế nào để FE biết task đang chạy/xong (trả về `task_id` lúc `POST /reports` rồi có endpoint `GET .../reports/{task_id}` riêng, hay lưu trạng thái ngay trên dòng `report_history` với cột `status`)? Sẽ quyết định cụ thể khi viết plan, dựa trên pattern polling cũ (`jobs.status`) để tái dùng tối đa.
3. **`GET /api/campaigns/{id}` có cần trả kèm danh sách `report_history` của Campaign đó luôn, hay tách endpoint riêng `GET /api/campaigns/{id}/reports`?** — ảnh hưởng thiết kế FE `Reports/index.tsx` và `CampaignDetail`. Sẽ chốt khi viết plan.
