# NGS Monitor — CLAUDE.md

Web application thu thập và phân tích nội dung truyền thông phòng chống tin giả
tại Việt Nam. AI chạy local, output là file báo cáo Word (.docx).

## Rules

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

### Đã hoàn thành
- Scope MVP, tech stack, business flow 8 bước, DB schema 5 bảng, API contract, rule crawler/AI/DOCX/FE (rules 01–09) đã chốt
- Pilot test thật: khảo sát 40 kênh, crawl được 11/40 (làm nền cho quyết định "không build social media")
- Slice 0 + Slice 1 (walking skeleton VTV + mở rộng: crawl trực tiếp/benchmark, Cancel, giới hạn job, khôi phục F5, fix timeout/error-handling) — đã merge `main`, verify thật với VTV
- Crawl4AI (engine fetch thay thế httpx) — bật theo nguồn qua `parsing_rules.engine`, không đổi hành vi nguồn không khai engine (VTV)
- bocongan.gov.vn: sitemap xác nhận đóng băng (2026-07-07) → chuyển sang crawl 7 trang "chuyên mục" qua `parsing_rules.listing_pages` (lý do đầy đủ + selector thật xem bảng quyết định). Code + migration `0005` đã xong, đã commit và push `main` (`4756e21`), nhưng **chưa verify được bằng job thật** vì hiện bị chặn WAF — xem "Vấn đề cần làm rõ"
- tingia.gov.vn: chuyển từ listing-page 1 trang sang sitemap curated `parsing_rules.sitemap_pages` (2026-07-08, lý do xem bảng quyết định), migration `0006`. **Đã verify job thật thành công** — xem "Verify Slice 2" bên dưới
- Thêm nguồn thứ 7 vietnam.vn (2026-07-08, lý do dùng `_SITEMAP_DATE_PATTERNS` xem bảng quyết định), migration `0007`. **Đã verify job thật thành công**
- **Slice 3 (AI pipeline đầy đủ) — hoàn thành (2026-07-09):** thêm cột `article_analysis.ai_model` (migration `0008`, track model AI đã dùng, chuẩn bị đổi model khi chuyển server GPU) + chuyển `analyze_article()` sang async + thêm `analyze_articles_batch()` (asyncio.Semaphore giới hạn song song qua `AI_CONCURRENCY`, mặc định `1` = đúng hành vi tuần tự cũ) + nối vào `report_job.py` (thay 2 stopgap tạm thời) + script `export_analysis_csv.py` để đọc lướt kết quả. **Đã verify job thật 2 giai đoạn thành công** — xem "Trạng thái hiện tại"
- **Bug thật phát hiện + đã sửa (2026-07-09):** khi user tự đọc CSV kết quả verify Slice 3, phát hiện 1 bài VTV bị `status="error"` dù URL vẫn hợp lệ khi truy cập tay — nguyên nhân: VTV trả `301 redirect` sang subdomain khác (`worldcup.vtv.vn`), httpx mặc định không tự theo redirect. Đã thêm `follow_redirects=True` cho `httpx.Client()` ở cả 3 nơi crawl (`article.py`/`listing.py`/`sitemap.py`, cùng nguyên nhân gốc), 3 test mới, verify bằng dữ liệu thật (crawl lại đúng URL đã lỗi, thành công). Đã push `main`
- **Bỏ dedup toàn cục theo `url_hash` (2026-07-09) — giải quyết dứt điểm vấn đề "job mồ côi" + "report rỗng âm thầm":** qua thảo luận sâu với user (đọc kết quả verify Slice 3), phát hiện 2 vấn đề cùng gốc rễ (`articles.url_hash` UNIQUE toàn cục): (1) job fail/cancel giữa chừng để lại dữ liệu "mồ côi" không gắn được vào job mới, (2) job mới trùng khoảng ngày với job cũ (dù job cũ **thành công**) bị skip hết, báo `status="completed"` nhưng report **rỗng hoàn toàn**, không cảnh báo. Cân nhắc 5 phương án (retry đúng `job_id` / minh bạch số liệu / content-hash so sánh nội dung / chặn tạo job trùng / bỏ dedup hoàn toàn) — user chọn phương án triệt để nhất: **bỏ hẳn dedup xuyên job**, mỗi job luôn crawl + phân tích AI lại từ đầu. **Cập nhật sau code review:** thay vì bỏ hẳn UNIQUE, đổi sang **UNIQUE composite `(job_id, url_hash)`** (migration `0009`) — vẫn đạt đúng mục tiêu (URL trùng được phép ở job khác) nhưng giữ lưới an toàn DB chống trùng trong 1 job, không phụ thuộc hoàn toàn vào `set()` Python. `downgrade()` tự dedupe trước khi tạo lại UNIQUE đơn để tránh crash khi rollback. Thêm log warning ở `POST /api/reports/create` khi job mới trùng phạm vi ngày/nguồn với job `completed`/`running`/`pending` trước đó, để có dấu vết chi phí AI phải chạy lại. Đánh đổi chấp nhận: tốn AI chạy lại khi job trùng phạm vi (kể cả bài không đổi nội dung), bảng `articles` phình to hơn theo thời gian, kết quả AI có thể khác nhau giữa các lần phân tích cùng 1 bài (non-determinism) — user ưu tiên đúng đắn dữ liệu hơn tiết kiệm tài nguyên. Tác dụng phụ có lợi: tự động mở khả năng bắt được nội dung bài viết đã thay đổi (đính chính/cập nhật) mà không cần cơ chế riêng
- **Bỏ dedup xuyên job — implement + verify thật hoàn tất (2026-07-09):** 7 task (migration composite UNIQUE, `_crawl_sources()` dedup nội bộ job, log warning overlap, 5 rule doc, CLAUDE.md, verify thật, regression) đều đã qua đủ 2 vòng review (spec compliance + code quality) trước khi merge, cộng thêm 1 lượt **final review toàn bộ diff** sau khi xong cả 7 task — bắt được 2 việc bị bỏ sót mà review từng task riêng lẻ không thấy: (1) log message/tên biến `overlapping_completed_jobs` chưa cập nhật theo đúng scope đã mở rộng (`completed`/`running`/`pending`) — code review Task 3 đã sửa logic nhưng quên sửa chữ; (2) file plan (`docs/superpowers/plans/2026-07-09-remove-cross-job-dedup.md`) đã viết lại theo đúng kiến trúc mới nhưng chưa từng commit dù đã dùng để implement. Cả 2 đã sửa (commit `d9b09fc`, `1cb7ec8`). **Kết quả cuối:** 101/101 test pass, verify thật thành công trên DB dev (job mới `9438b4b0...` crawl lại đúng 5/5 URL của job cũ `2324df79...` thay vì bị skip, composite constraint `articles_job_id_url_hash_key` chặn đúng insert trùng trong cùng job trên dữ liệu thật, report không rỗng), đã push `main` (14 commit, `c25b26c..1cb7ec8`)
- **Slice 4 (Report đầy đủ) — hoàn thành (2026-07-10):** mở rộng `aggregate_basic()` thêm `source_counts`/`topic_counts`/`keyword_counts`/`monthly_counts`/`summary_stats`, dựng lại `generate_docx()` theo đúng cấu trúc bảng của `sample_report_form.docx` (chỉ bảng khớp dữ liệu thật — bỏ hẳn bảng cần hashtag/engagement/nền tảng social/chính sách cụ thể, không có trong DB; không vẽ chart — chỉ bảng số liệu, xem lý do ở plan `docs/superpowers/plans/2026-07-10-slice4-full-report.md`). Đồng thời sửa bug đã biết từ Slice 3: validate `emotion` AI trả về đúng 6 nhóm enum chuẩn ngay ở `ollama_client.py`, giá trị ngoài enum (VD `"Neutral"`) → `emotion=None` + `needs_review=true` + log warning, không còn lọt thẳng vào DB/report. **Đã verify job thật** (job `14a4c918-9f1e-4192-a815-0ef3b6c8a384`, nguồn VTV, `date_from=2026-06-01`/`date_to=2026-07-08`, 15/15 bài crawl + phân tích thành công, `status=completed`): đối chiếu tay Bảng 3.1 (`VTV=15`)/Bảng 3.13 (`negative=2, neutral=7, positive=6`)/Bảng 3.15 (`Fear=5, Trust=9, Không xác định=1`) với query DB trực tiếp (`GROUP BY` thật trên `articles`/`article_analysis`/`sources`) — khớp chính xác 100%. **Xác nhận thật ngoài dự kiến:** bug `emotion="Neutral"` (phát hiện lần đầu ở Slice 3, 1 lần duy nhất trong mẫu 5 bài) đã **tái xuất hiện thật** trong lần verify Slice 4 này (1/15 bài, bài "Bắt nóng đối tượng cướp tiệm vàng ở Hà Nội sau gần 4 giờ gây án") — cơ chế validate mới đã bắt đúng: log warning, set `emotion=None`, `needs_review=true`, thể hiện đúng trong bảng "Không xác định" (Bảng 3.15) và `summary_stats` (`"Số bài cần review (needs_review)": 1`). Xác nhận đây không phải lỗi hiếm gặp 1 lần mà là hành vi lặp lại thật của `qwen3:8b` — cơ chế validate cần giữ nguyên lâu dài, không tắt/bỏ.

### Trạng thái hiện tại
- Slice 0 + Slice 1 (gồm phần mở rộng): hoàn thành, đã merge `main`
- Crawl4AI engine: code xong, verify thật trên VTV/VOV qua lời gọi hàm trực tiếp — nay đã dùng thật cho 5/6 nguồn cấu hình ở Slice 2 (xem dưới)
- Slice 2: code xong + **đã verify job thật end-to-end với 2 nguồn mới (VOV, BoCongAn)** — xem kết quả chi tiết ở dòng Verify Slice 2 dưới
- BoCongAn sitemap thay thế: Giai đoạn A + B code xong, **đã commit và push lên `main`** (commit `4756e21`) — selector thật (`article.card-large`/`a[href^="/bai-viet/"]`/`span.text-bca-gray-700`), `urljoin` href tương đối, fallback `published_at`, migration `0005` đã chạy thật trên DB dev (`sitemap_url = NULL`, `parsing_rules` có đủ 7 `listing_pages` + selector). **Chưa verify bằng job thật với dữ liệu thật** — thử job thật (2026-07-07) cho kết quả `status=completed` nhưng 0 bài crawl được, do bocongan.gov.vn chặn WAF (Incapsula) toàn bộ request từ mạng hiện tại (xác nhận qua curl thường, curl với header trình duyệt đầy đủ, và gọi `httpx` trực tiếp từ container `celery-worker` — cả 3 đều bị chặn giống nhau, kể cả `sitemap.xml` vốn hoạt động được lúc sáng cùng ngày). Không phải lỗi code — 3 unit test suite của Task 1/2/3 đều pass, chỉ là chưa chạy được với dữ liệu thật do nghẽn mạng bên ngoài
- tingia.gov.vn: chuyển sang sitemap curated (`parsing_rules.sitemap_pages`), migration `0006` đã chạy thật trên DB dev, **đã verify job thật thành công** (2026-07-08, job `52298372...`): 4/4 bài crawl + AI phân tích xong (`status=completed`), toàn bộ URL thật thuộc đúng `tin-vua-check.xml` (1 trong 5 sub-sitemap đã khai), không có bài lỗi, `.docx`/`.json` hợp lệ. **Giới hạn thật của lần verify này:** do `MAX_ARTICLES_PER_JOB=4` và `tin-vua-check.xml` một mình đã đủ >4 bài trong khoảng ngày rộng (2025-04-01 → 2026-07-08), job dừng lại trước khi chạm tới 4 sub-sitemap còn lại — nghĩa là cơ chế dedup URL cross-sub-sitemap (đã unit test với dữ liệu giả) **chưa có cơ hội bắt được 1 trùng lặp thật** trong lần verify này (không xác nhận được có trùng lặp thật hay không, vì chưa quan sát đủ dữ liệu từ cả 5 sub-sitemap). Cũng phát hiện 1 vấn đề vận hành: `celery-worker` mount code qua volume nhưng KHÔNG tự nạp lại code Python đã sửa — phải `docker compose restart celery-worker` sau khi đổi `.py`, nếu không job sẽ chạy code cũ (gặp lỗi `TypeError` thật ở lần chạy job đầu tiên trước khi restart) — xem bảng quyết định
- vietnam.vn (nguồn thứ 7): migration `0007` đã chạy thật trên DB dev, **đã verify job thật thành công** (2026-07-08, job `911098e5...`, `date_from=2026-07-07`/`date_to=2026-07-08`): 4/4 bài crawl + AI phân tích xong (`status=completed`), toàn bộ URL thật thuộc `sitemap-post/2026-07-08.xml` (không lẫn `/tag/`, `/category/`, `/authors/`), không bài lỗi, `.docx`/`.json` hợp lệ. Nội dung nguồn đa dạng (thể thao/giải trí/sức khỏe...), không chuyên biệt tin giả — đã xác nhận với user đây đúng là nguồn mong muốn, không thêm lọc chủ đề ở bước crawl (để AI Slice 3 tự phân loại); ~1576 bài/ngày là khối lượng lớn, chưa xử lý giới hạn riêng ở task này (dùng chung `MAX_ARTICLES_PER_JOB`)
- **Bug thật phát hiện + đã sửa (2026-07-08):** ngay sau khi verify vietnam.vn xong, user tự chạy job qua FE và nhận `completed` với 0 bài — điều tra log `celery-worker` phát hiện `GET sitemap.xml` trả `403 Forbidden` (site chặn tạm thời, tự hết sau ~15 phút) nhưng `get_article_urls()` không check HTTP status trước khi parse, khiến trang lỗi bị hiểu nhầm thành "sitemap phẳng không có bài" → job báo `completed` thay vì lộ ra lỗi thật. Đã sửa: dùng lại `_fetch_with_retry` (vốn chỉ dùng cho sub-sitemap) cho cả fetch index, check `status_code >= 400`, trả về index URL như 1 `failed_loc` để `report_job.py` insert `Article(status="error")` (cơ chế đã có sẵn, không cần sửa `report_job.py`). Áp dụng cho **mọi nguồn dùng sitemap index** (VTV/VOV/VietnamPlus/CAND/vietnam.vn), không riêng vietnam.vn. 2 test mới (403 status + exception mạng), verify thêm bằng 1 URL 404 thật (không chỉ mock)
- **Slice 3: hoàn thành (2026-07-09).** `AI_CONCURRENCY`/`analyze_articles_batch()`/`ai_model` code xong + đã verify job thật 2 giai đoạn:
  - **Giai đoạn A (smoke test 5 bài, job `2324df79...`):** `source_ids=[VTV, VOV]`, `date_from=2026-06-01`/`date_to=2026-07-08` → `status=completed`, `crawled=5, analyzed=5`, không exception trong log, cả 5 dòng `article_analysis` có `ai_model='qwen3:8b'`/`prompt_version=1`, `.docx`/`.json` hợp lệ (magic bytes `PK\x03\x04`)
  - **Giai đoạn B (verify chính thức 15 bài, job `32c7bb38...`):** `source_ids=[VTV, VOV, VietnamPlus, CAND, TinGia]`, `date_from=2026-04-01`/`date_to=2026-07-08` → `status=completed`, `crawled=15, analyzed=14` (1 bài lỗi crawl VTV — đúng nhánh `status="error"` đã định nghĩa ở [10 · Error Handling](.claude/rules/10-error-handling.md), không phải bug mới: log ghi rõ "Crawl lỗi (hết retry hoặc không parse được)"), cả 14 dòng `ai_model='qwen3:8b'`, `.docx`/`.json` hợp lệ. Export CSV (`export_analysis_csv.py`) đọc lướt 14 bài: topic/sentiment đa dạng theo đúng nội dung (không lệch hệ thống, VD không phải lúc nào cũng cùng 1 topic), confidence toàn bộ 0.9–0.95 (chưa có bài nào kích hoạt `needs_review=true` trong mẫu này)
  - **Giới hạn thật của lần verify này (ghi nhận trung thực):** dù khai 5 `source_ids`, **toàn bộ 15 bài crawl được đều từ VTV** — vì `MAX_ARTICLES_PER_JOB` là giới hạn toàn job tính theo thứ tự `source_ids` (đã biết từ Slice 2), VTV một mình đã đủ 15 bài trong khoảng ngày rộng nên job dừng lại trước khi chạm tới VOV/VietnamPlus/CAND/TinGia. Không verify được tính đa dạng nguồn ở bước AI trong lần này
  - **Phát hiện thật cần theo dõi (chưa xử lý, không chặn Slice 3):** ở Giai đoạn A, 1/5 bài AI trả `emotion="Neutral"` — **không thuộc 6 nhóm cảm xúc chuẩn** đã định nghĩa (`Trust, Fear, Anger, Surprise, Sadness, Happy`, xem [07 · AI Pipeline](.claude/rules/07-ai-pipeline.md)). Tại thời điểm đó code chưa validate giá trị `emotion` trả về khớp enum trước khi lưu DB. Không xuất hiện lại ở mẫu 14 bài Giai đoạn B. **Cập nhật (Slice 4, 2026-07-10):** đã thêm validate ở `ollama_client.py` (giá trị ngoài enum → `emotion=None` + `needs_review=true` + log warning) và bug đã **tái xuất hiện thật** trong lần verify Slice 4 — cơ chế validate bắt đúng như thiết kế; xem bullet "Slice 4 (Report đầy đủ) — hoàn thành" ở mục Đã hoàn thành
- Slice 5–6: chưa bắt đầu
- **Bỏ dedup xuyên job: hoàn thành đầy đủ (2026-07-09)** — đã push `main`, xem chi tiết ở "Đã hoàn thành" phía trên. Không ảnh hưởng tiến độ Slice 5–6 (thay đổi ở tầng crawl/DB, không đụng report/FE)

### Bước tiếp theo
1. Chạy lại job thật cho bocongan.gov.vn khi mạng không còn bị Incapsula WAF chặn (thử lại sau vài giờ/vài ngày, hoặc từ mạng khác) — code + migration đã sẵn sàng, chỉ còn thiếu bước verify bằng dữ liệu thật
2. Bắt đầu Slice 5 (UX & vận hành hoàn chỉnh: trang lịch sử báo cáo `GET /api/reports/history`, error handling đầy đủ theo [10 · Error Handling](.claude/rules/10-error-handling.md) — còn thiếu JS-render fallback Playwright)

### Quyết định quan trọng & lý do
| Quyết định | Lý do |
|---|---|
| Không build social media (Facebook/YouTube/TikTok/Zalo) trong MVP | Cần API xác thực riêng, nội dung video không hợp pipeline text-crawl → AI-classify hiện tại; pilot test chỉ 11/40 kênh (toàn website) crawl được |
| Output báo cáo chỉ gồm `Report.docx` + `JSON raw data` | Tránh scope creep so với các file phụ liệt kê trong `sample_report_form.docx` (Dataset.csv, Chart.png...) |
| `emotion` (6 lớp) lấy cùng 1 lần gọi Ollama với `sentiment` | Báo cáo cần Bảng 3.15 tách biệt sentiment 3 lớp; gộp vào 1 lần gọi để tránh round-trip thứ 2 |
| Lọc lại theo `published_at` thật sau khi fetch bài, không chỉ tin sitemap `<lastmod>` | Một số nguồn (VD bocongan.gov.vn) ghi `<lastmod>` giống nhau cho mọi URL, không phải ngày đăng thật |
| Listing-page crawler chỉ hỗ trợ 1 trang, không phân trang | cơ chế này tạm không còn nguồn thật nào dùng — vẫn giữ lại làm fallback tổng quát |
| `_SITEMAP_DATE_PATTERNS`: dict domain → regex riêng (thay 2 regex chung `_DATE_RANGE_RE`/`_YEAR_MONTH_RE`) | Mỗi site có format URL khác nhau; thêm nguồn mới = thêm 1 entry, không ảnh hưởng site khác. Domain không khai pattern → skip |
| Một số site sẽ bỏ ưu tiên sitemap và sẽ được xử lý với cách riêng tương ứng theo từng site (ví dụ: theo chuyên mục, CSS Selector,...) |
| `_get_candidates()` ưu tiên `parsing_rules.listing_pages` cao nhất, kể cả khi `source.sitemap_url` vẫn còn giá trị trong DB |
| Crawl phân trang trong từng chuyên mục — CHƯA LÀM ở giai đoạn này |
| `parsing_rules.sitemap_pages` lưu ở DB (JSONB), không chuyển sang file JSON trong code hay hardcode dict trong `sitemap.py` | Cân nhắc 3 phương án cùng user (DB JSONB / code dict giống `_SITEMAP_DATE_PATTERNS` / 1 file JSON chung cho tất cả nguồn). Giữ DB JSONB để nhất quán với `listing_pages` (BoCongAn) — cùng 1 nguồn không nên tách config ra 2 nơi (DB cho CSS selector + file cho URL); sửa qua SQL/migration không cần rebuild code, trong khi 2 phương án kia đều cần sửa code + rebuild `celery-worker`. User đề xuất thêm tab quản lý `parsing_rules` qua Admin UI ở Slice 6 tương lai — xem note ở Slice 6 |

### Vấn đề cần làm rõ (chưa chốt)
- **Kết quả AI không đảm bảo giống hệt nhau giữa các lần phân tích cùng 1 bài (phát hiện khi review plan bỏ dedup xuyên job, 2026-07-09):** `qwen3:8b` qua Ollama không set `temperature`/seed cố định — nếu 2 job trùng phạm vi ngày cùng phân tích 1 bài, `topics`/`sentiment`/`emotion`/`confidence` có thể khác nhau giữa 2 lần. Chưa xử lý (chưa set temperature/seed, chưa có cảnh báo trong report) — theo dõi thêm khi có dữ liệu thật từ nhiều job trùng phạm vi, cân nhắc set `temperature=0` nếu Ollama/`qwen3:8b` hỗ trợ. Xem [07 · AI Pipeline](.claude/rules/07-ai-pipeline.md)
- **Theo dõi kích thước bảng `articles` sau khi bỏ dedup xuyên job (2026-07-09):** mỗi job trùng phạm vi ngày với job trước sẽ thêm 1 bộ dòng mới (không tái sử dụng dòng cũ) — bảng phình to không giới hạn theo thời gian nếu user tạo report định kỳ trùng lịch. Chưa có ngưỡng cảnh báo hay kế hoạch dọn dẹp cụ thể — định kỳ kiểm tra `SELECT count(*) FROM articles`, nếu vượt mốc ước tính (VD >100,000 dòng) thì lên kế hoạch 1 slice archival/cleanup (ngoài phạm vi hiện tại)
- **Số nguồn Slice 2 hiện đạt 7 (không phải ước tính gốc 8–10; theo `content_survey.docx` con số thực tế nên là ~11–12, khớp pilot test 11/40 — chưa sửa số trong roadmap)** — đã xác nhận 7 nguồn crawl được thật (VTV+VOV+VietnamPlus+CAND+BoCongAn+TinGia+Vietnam.vn, thêm Vietnam.vn 2026-07-08 sau khi Slice 2 "hoàn thành" ban đầu ở mức 6); qdnd.vn bị loại do lỗi redirect-loop chưa rõ nguyên nhân (xem bảng quyết định); chinhphu.vn/mod.gov.vn/bvhttdl.gov.vn không có bài chuyên tin giả theo khảo sát thật — người dùng đã xác nhận 6 nguồn là đủ cho slice này trước đó, Vietnam.vn là bổ sung thêm theo yêu cầu mới, không ép đủ số 8–10

## Roadmap — Vertical Slices

> Cập nhật trạng thái tại đây khi có tiến độ mới — tick `[x]` khi hoàn thành.
> Mỗi slice (trừ Slice 0) là 1 lát cắt **đầu-cuối** (DB → crawler → AI → report → FE) chạy được thật với dữ liệu thật, không chỉ 1 layer kỹ thuật. Mở rộng dần theo số nguồn/tính năng, không làm hết 1 layer rồi mới sang layer khác. Tổng scope và ước tính thời gian giữ nguyên so với breakdown cũ — chỉ đổi **thứ tự đóng gói** công việc.

### Slice 0 — Hạ tầng nền (prerequisite, không phải vertical slice)
- [x] Khởi tạo project, cấu trúc thư mục, Docker Compose
- [x] Thiết kế & migrate Database schema (5 bảng, gồm field `emotion` và `prompt_version`)
- [x] Setup Celery + Redis + Flower
- [x] Setup Ollama + pull model `qwen3:8b`
- **Verify:** `docker-compose up` chạy đủ service; DB có đủ 5 bảng; Celery worker nhận và chạy được 1 task test; `curl` Ollama trả response cho 1 prompt test — **đã chạy thật và pass cả 7 service (`docker compose ps` → healthy), bao gồm test healthcheck dependency khi Redis down (2026-06-25)**

### Slice 1 — "1 nguồn, đầu-cuối" (walking skeleton)
Mục tiêu: chứng minh toàn bộ pipeline chạy thông từ FE đến file kết quả, với phạm vi hẹp nhất (1 nguồn, vài bài).
- [x] API `POST /api/reports/create` (1 source_id, date range) → tạo Job, đẩy Celery queue
- [x] Crawler: sitemap parser cho 1 nguồn thật (VD VTV) + article parser (httpx + BeautifulSoup) + dedup SHA256 + lưu `articles`
- [x] AI: gọi Ollama, parse JSON, lưu `article_analysis` (đủ field kể cả `emotion`, chưa cần tối ưu prompt 8 nhóm)
- [x] Report: DOCX cơ bản (vài bảng chính) + export JSON raw data
- [x] FE tối giản: 1 form chọn nguồn (hardcode) + date range → submit → polling status → download
- **Verify:** chạy thử với 1 nguồn thực tế, ra được ≥1 file `.docx` + `.json` hợp lệ; `jobs.status` chuyển đúng `pending → running → completed` — **đã chạy thật, 104 bài crawl thật từ VTV, AI phân tích thật qua `qwen3:8b`, DOCX/JSON hợp lệ, 32 unit test pass**
- **Mở rộng thêm sau khi verify** (đã merge `main` cùng đợt): bảng crawl trực tiếp + benchmark thời gian, hủy job (Cancel), giới hạn `MAX_ARTICLES_PER_JOB`, khôi phục job sau F5, fix AI timeout/crawler error-handling — xem "Quyết định quan trọng & lý do" ở trên

### Slice 2 — Nhiều nguồn + listing-page fallback
- [x] Listing page crawler (fallback khi nguồn không có sitemap) — `backend/crawler/listing.py`, phạm vi 1 trang không phân trang (YAGNI). **Cập nhật 2026-07-08:** tingia.gov.vn (nguồn từng dùng nhánh này) đã chuyển sang sitemap curated — cơ chế 1-trang trong `listing.py` giữ nguyên (fallback tổng quát cho nguồn tương lai không có sitemap) nhưng hiện không có nguồn thật nào đang dùng
- [x] Config & test 7 nguồn thực tế (VTV, VOV, VietnamPlus, CAND, BoCongAn, TinGia, Vietnam.vn — thêm sau khi Slice 2 "hoàn thành" ban đầu, vẫn ít hơn ước tính gốc 8–10, xem "Vấn đề cần làm rõ" dưới) — toàn bộ 6 nguồn mới dùng engine Crawl4AI (`parsing_rules.engine = "crawl4ai"`), không viết CSS selector tay
- [x] FE: sidebar chọn nhiều nguồn (search, group theo nhóm kênh), tag nguồn đã chọn, summary card ước tính số bài/thời gian, preset ngày (7/30/90/150), warning khi ≥5 nguồn & ≥60 ngày
- **Verify:** crawl thành công 6 nguồn thực tế đã config (cả sitemap và fallback listing); test trùng URL bị dedup đúng (không insert lại) — **đã verify ở mức unit test + migration thật** (sitemap/listing parser, dispatch chiến lược, lọc ngày đăng thật sau fetch, seed 6 nguồn qua `alembic upgrade head`), và đã chạy job thật end-to-end thành công với VOV (2026-06-30, 4/4 bài crawl + AI phân tích xong, `.docx`/`.json` hợp lệ). Cách crawl BoCongAn dùng ở lần verify này (sitemap phẳng) đã lỗi thời — sitemap sau đó được xác nhận đóng băng hoàn toàn (2026-07-07) và đã thay bằng `listing_pages`, xem "Multi-listing-page cho bocongan.gov.vn" ở "Đã hoàn thành"

### Slice 3 — AI pipeline đầy đủ
- [x] Prompt phân loại đầy đủ 8 nhóm chủ đề + keyword + sentiment + `emotion` (6 lớp) — thực ra đã xong từ Slice 1 (`backend/ai/prompts/v1.py`), Slice 3 chỉ xác nhận qua verify dữ liệu thật (xem dưới), không viết `v2.py` mới
- [x] Batch processing + tối ưu tốc độ — `AI_CONCURRENCY` (mặc định 1) + `analyze_articles_batch()` (asyncio.Semaphore + gather), track `ai_model` song song `prompt_version`
- [x] Đánh giá & tinh chỉnh prompt trên dữ liệu thật
- **Verify:** chạy AI trên **15 bài thực tế** (giảm từ ước tính ban đầu ≥50 bài — tránh chạy AI liên tục >1 tiếng hại phần cứng laptop CPU-only, xem bảng quyết định); `confidence < 0.6` → `needs_review=true` đúng ngưỡng; JSON lỗi → retry 1 lần → skip nếu vẫn lỗi (test case JSON không hợp lệ) — **đã verify job thật thành công 2 giai đoạn (2026-07-09)**, xem "Trạng thái hiện tại"

### Slice 4 — Report đầy đủ
- [x] Aggregate query đầy đủ: GROUP BY nguồn/chủ đề/tháng/sentiment/emotion
- [x] Build DOCX template đầy đủ theo `sample_report_form.docx` + placeholder map
- [x] Kiểm tra output với dữ liệu thật
- **Verify:** file `.docx` sinh ra khớp cấu trúc `sample_report_form.docx`; số liệu từng bảng khớp với query DB trực tiếp (so sánh tay ít nhất 2-3 bảng)

### Slice 5 — UX & vận hành hoàn chỉnh
- [x] Job status polling + progress UI chi tiết (`crawled/analyzed/total_estimated`) — đã làm ở Slice 1, mở rộng thêm bảng crawl trực tiếp + Cancel (xem Slice 1)
- [ ] Trang lịch sử báo cáo (`GET /api/reports/history`)
- [ ] Error handling đầy đủ theo [10 · Error Handling](.claude/rules/10-error-handling.md) (retry, timeout, JS-render fallback Playwright) — **đã làm trước 1 phần:** AI timeout chỉ skip 1 bài (không fail cả job), crawler lỗi (article + sub-sitemap) hiện `status="error"` trên UI; **còn thiếu:** JS-render fallback Playwright chưa làm
- **Verify:** giả lập timeout/JSON lỗi/nguồn bị block → job xử lý đúng theo bảng error-handling, không crash toàn job

### Slice 6 — Admin UI quản lý nguồn
- [ ] CRUD metadata nguồn (name/URL/active toggle) — không tự thêm parsing rule mới qua UI
- **Verify:** thêm/sửa/xoá nguồn qua UI; nguồn mới active hiển thị đúng ở sidebar chọn nguồn (Slice 2)
- **Ý tưởng chưa chốt (2026-07-08, do user đề xuất khi bàn về nơi lưu `parsing_rules` cho TinGia):** thêm 1 tab riêng trong Admin UI cho phép xem/sửa `parsing_rules` (CSS selector, `listing_pages`, `sitemap_pages`...) trực tiếp qua UI thay vì phải migration/SQL. Hiện **trái với quyết định đã chốt** ở dòng "Admin UI (Slice 6) chỉ CRUD metadata nguồn, không cho thêm parsing rule qua UI" (xem bảng quyết định) — cần bàn riêng nếu muốn đổi scope Slice 6, vì mỗi loại nguồn (sitemap curated/listing-page nhiều trang/CSS selector tay) cần 1 dạng form khác nhau, không phải 1 form CRUD đơn giản

**Timeline (không đổi so với breakdown cũ):**
- Best case: ~7 tuần
- Realistic: 9–10 tuần (khuyến nghị dùng để plan)
- Worst case: 11–12 tuần
