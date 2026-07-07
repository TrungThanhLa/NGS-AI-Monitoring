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

<!-- Feature-specific — đọc khi làm task liên quan -->
- [05 · API Contracts](.claude/rules/05-api-contracts.md)
- [06 · Crawler Strategy](.claude/rules/06-crawler-strategy.md)
- [07 · AI Pipeline](.claude/rules/07-ai-pipeline.md)
- [08 · DOCX Report](.claude/rules/08-docx-report.md)
- [09 · Frontend UI](.claude/rules/09-frontend-ui.md)

## Nguyên tắc hành vi khi code

> Bổ sung (không thay thế) cho [11 · Core Principles](.claude/rules/11-core-principles.md) (nguyên tắc nghiệp vụ/dữ liệu) và [13 · Workflow](.claude/rules/13-workflow.md) (quy trình EPCC).

### 1. Suy nghĩ trước khi code — không tự giả định
Khi yêu cầu chưa rõ (CSS selector cho nguồn mới, ngưỡng confidence đặc biệt, placeholder DOCX chưa định nghĩa...), dừng lại và hỏi thay vì đoán.
- Nêu rõ giả định trước khi code; nếu có điểm chưa chắc — hỏi lại user
- Nếu có nhiều cách hiểu yêu cầu, trình bày các cách hiểu — không tự chọn 1 cách rồi im lặng code
- Nếu có cách làm đơn giản hơn cách user đề xuất, nói rõ và đề xuất — không ngại phản biện
- Đây là phần mở rộng cho bước Explore của EPCC ([13 · Workflow](.claude/rules/13-workflow.md))

### 2. Tối giản — không thêm thứ ngoài yêu cầu
Theo đúng nguyên tắc MVP-first đã có ([11 · Core Principles](.claude/rules/11-core-principles.md)): mọi đoạn code mới phải là lượng code tối thiểu giải quyết đúng yêu cầu.
- Không thêm feature, config, hay "khả năng mở rộng" nếu không được yêu cầu rõ
- Không tạo abstraction (lớp trừu tượng/helper dùng chung) cho code chỉ dùng 1 lần
- Không viết error handling cho tình huống không thể xảy ra trong context hiện tại (xem case đã định nghĩa ở [10 · Error Handling](.claude/rules/10-error-handling.md))
- Ngoại lệ: thiết kế linh hoạt đã chốt trong schema (VD: `sources.parsing_rules` JSONB) là quyết định kiến trúc có chủ đích — không tính là "thêm ngoài yêu cầu"

### 3. Sửa đúng phạm vi — không "tiện tay" sửa thêm
Chỉ đụng vào phần code liên quan trực tiếp tới yêu cầu.
- Không "cải thiện" code/comment/format ở đoạn không liên quan
- Không refactor code đang chạy tốt nếu không được yêu cầu
- Giữ đúng style hiện có của file, kể cả quy ước comment tiếng Việt giải thích logic quan trọng ([13 · Workflow](.claude/rules/13-workflow.md))
- Phát hiện dead code không liên quan tới task → báo cho user biết, không tự xóa
- Chỉ dọn import/biến/function không dùng nữa nếu chính thay đổi của bạn gây ra — không dọn dead code có từ trước

### 4. Làm theo tiêu chí xác minh được — verify trước khi báo "xong"
Mọi task phải quy về tiêu chí kiểm tra được, không dừng ở "chạy được là xong".
- "Thêm validate nguồn" → viết test case cho input không hợp lệ, rồi làm nó pass
- "Sửa bug crawler/AI pipeline" → viết test reproduce lỗi trước, rồi mới fix
- "Refactor parser/aggregator" → đảm bảo test pass cả trước và sau khi sửa
- Với task nhiều bước, nêu ngắn gọn plan dạng: `1. [Bước] → verify: [cách kiểm tra]`
- Vẫn phải tuân thủ bước Commit của EPCC: lint + type check + test với ít nhất 1 nguồn dữ liệu thật trước khi commit ([13 · Workflow](.claude/rules/13-workflow.md))

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
- Điều tra sitemap bocongan.gov.vn đóng băng (2026-07-07): xác nhận thật qua curl trực tiếp — sitemap flat urlset, toàn bộ `<lastmod>` cố định 20/08/2025, site vẫn đăng bài mới nhưng không vào sitemap. Tìm được thay thế: 7 trang "chuyên mục" (`/chuyen-muc/...`) có ngày đăng thật, cập nhật liên tục, site SSR (Nuxt) nên không cần Playwright, `/rss` không phải feed thật (đã loại)
- Multi-listing-page cho bocongan.gov.vn — Giai đoạn A (code + test) đã xong: `parsing_rules.listing_pages`/`fetch_pages` trong `backend/crawler/listing.py` + routing ưu tiên trong `backend/workers/report_job.py` (`_get_candidates`), 9 test mới, 70/70 test pass. Giai đoạn B: CSS selector thật (`article.card-large` — không phải `card-small` như tưởng ban đầu, xem quyết định bên dưới) + `urljoin` cho href tương đối (`listing.py`) + fallback `published_at` về listing lastmod (`report_job.py`) + migration `0005` cập nhật `parsing_rules`/xoá `sitemap_url` — **code + migration đã xong, đã chạy migration thật trên DB dev, đã commit và push lên `main`** (commit `4756e21`), nhưng **chưa verify được bằng job thật** vì bocongan.gov.vn hiện bị chặn WAF (Incapsula) toàn bộ từ mạng hiện tại kể cả `sitemap.xml` — xem "Vấn đề cần làm rõ"

### Trạng thái hiện tại
- Slice 0 + Slice 1 (gồm phần mở rộng): hoàn thành, đã merge `main`
- Crawl4AI engine: code xong, verify thật trên VTV/VOV qua lời gọi hàm trực tiếp — nay đã dùng thật cho 5/6 nguồn cấu hình ở Slice 2 (xem dưới)
- Slice 2: code xong + **đã verify job thật end-to-end với 2 nguồn mới (VOV, BoCongAn)** — xem kết quả chi tiết ở dòng Verify Slice 2 dưới
- BoCongAn sitemap thay thế: Giai đoạn A + B code xong, **đã commit và push lên `main`** (commit `4756e21`) — selector thật (`article.card-large`/`a[href^="/bai-viet/"]`/`span.text-bca-gray-700`), `urljoin` href tương đối, fallback `published_at`, migration `0005` đã chạy thật trên DB dev (`sitemap_url = NULL`, `parsing_rules` có đủ 7 `listing_pages` + selector). **Chưa verify bằng job thật với dữ liệu thật** — thử job thật (2026-07-07) cho kết quả `status=completed` nhưng 0 bài crawl được, do bocongan.gov.vn chặn WAF (Incapsula) toàn bộ request từ mạng hiện tại (xác nhận qua curl thường, curl với header trình duyệt đầy đủ, và gọi `httpx` trực tiếp từ container `celery-worker` — cả 3 đều bị chặn giống nhau, kể cả `sitemap.xml` vốn hoạt động được lúc sáng cùng ngày). Không phải lỗi code — 3 unit test suite của Task 1/2/3 đều pass, chỉ là chưa chạy được với dữ liệu thật do nghẽn mạng bên ngoài
- Slice 3–6: chưa bắt đầu

### Bước tiếp theo
1. Chạy lại job thật cho bocongan.gov.vn khi mạng không còn bị Incapsula WAF chặn (thử lại sau vài giờ/vài ngày, hoặc từ mạng khác) — code + migration đã sẵn sàng, chỉ còn thiếu bước verify bằng dữ liệu thật
2. Bắt đầu Slice 3 (AI pipeline đầy đủ: prompt 8 nhóm + batch processing)

### Quyết định quan trọng & lý do
| Quyết định | Lý do |
|---|---|
| Không build social media (Facebook/YouTube/TikTok/Zalo) trong MVP | Cần API xác thực riêng, nội dung video không hợp pipeline text-crawl → AI-classify hiện tại; pilot test chỉ 11/40 kênh (toàn website) crawl được |
| Output báo cáo chỉ gồm `Report.docx` + `JSON raw data` | Tránh scope creep so với các file phụ liệt kê trong `sample_report_form.docx` (Dataset.csv, Chart.png...) |
| `emotion` (6 lớp) lấy cùng 1 lần gọi Ollama với `sentiment` | Báo cáo cần Bảng 3.15 tách biệt sentiment 3 lớp; gộp vào 1 lần gọi để tránh round-trip thứ 2 |
| Admin UI (Slice 6) chỉ CRUD metadata nguồn, không cho thêm parsing rule qua UI | Mỗi nguồn có cấu trúc HTML khác nhau, cần dev viết CSS selector tay — không tự động hóa ở MVP |
| Slice 1: 1 Celery task tuần tự (`workers/report_job.py`), không tách `crawl_worker`/`ai_worker` riêng | Đơn giản, dễ debug cho walking skeleton; tách task + batch parallelism để dành Slice 3 |
| `celery_task_id` tự sinh `uuid.uuid4()`, không suy từ `job_id` | Tránh race condition: Cancel đọc `None` nếu task chạy trước khi DB commit |
| `MAX_ARTICLES_PER_JOB` chỉ qua biến env, không đưa lên UI | Nhu cầu test/dev (AI local chậm), không phải nhu cầu người dùng — lộ lên UI có rủi ro báo cáo thiếu dữ liệu mà không ai biết |
| `AI_MAX_CONTENT_LENGTH`=5000, `AI_TIMEOUT_SECONDS`=360 (tạm thời) | Giảm tần suất AI timeout đã từng xảy ra thật ở mức 2000/120 — cần điều chỉnh lại khi có benchmark thật (Slice 3) |
| Crawl4AI bật theo nguồn qua `parsing_rules.engine == "crawl4ai"`, không thêm cột `crawler_engine` riêng | Tái dùng JSONB linh hoạt đã chốt sẵn — không cần migration; nguồn không khai `engine` (VTV) không bị ảnh hưởng |
| Hậu xử lý regex-trim content Crawl4AI tại marker `"Tin liên quan"`/`"Bình luận"` | `fit_markdown` mặc định dính nhiều rác (box bài liên quan/bình luận) — convention phổ biến báo điện tử VN, verify trên nhiều site |
| Hạ `lxml` xuống `~5.3` trong `requirements.txt` | `crawl4ai==0.9.0` yêu cầu `lxml~=5.3`, xung đột với `6.1.1` khi build Docker |
| `celery-worker`/`flower` phải rebuild riêng khi đổi `requirements.txt` | 3 service build image riêng dù chung Dockerfile — quên rebuild từng gây `ModuleNotFoundError` lúc worker start thật |
| Tổng quát hóa `sitemap.py` để nhận sitemap phẳng + nhiều pattern tên sub-sitemap | Mỗi nguồn có cấu trúc URL khác nhau (VOV/VietnamPlus/CAND dùng pattern khác VTV, BoCongAn không có index) — code cũ trả 0 bài cho các nguồn này |
| Lọc lại theo `published_at` thật sau khi fetch bài, không chỉ tin sitemap `<lastmod>` | Một số nguồn (VD bocongan.gov.vn) ghi `<lastmod>` giống nhau cho mọi URL, không phải ngày đăng thật |
| Listing-page crawler chỉ hỗ trợ 1 trang, không phân trang | YAGNI — nguồn duy nhất cần đến (tingia.gov.vn) không có phân trang thật; mở rộng khi có nguồn thật cần |
| `_SITEMAP_DATE_PATTERNS`: dict domain → regex riêng (thay 2 regex chung `_DATE_RANGE_RE`/`_YEAR_MONTH_RE`) | Mỗi site có format URL khác nhau, dễ false-positive nếu dùng chung; thêm nguồn mới = thêm 1 entry, không ảnh hưởng site khác. Domain không khai pattern → fetch-all an toàn |
| Sub-sitemap không khớp pattern của domain → bỏ qua hoàn toàn, KHÔNG fallback fetch-all | Bug thật: fallback fetch-all mặc định từng làm crawl nhầm trang danh mục (`categories.xml`...) của VietnamPlus như bài viết thật |
| bocongan.gov.vn: bỏ ưu tiên sitemap, chuyển sang crawl 7 trang "chuyên mục" (`/chuyen-muc/...`) qua `parsing_rules.listing_pages`/`fetch_pages` | Xác nhận thật (curl trực tiếp, 2026-07-07): sitemap.xml là flat urlset đóng băng ở `<lastmod>` cố định 20/08/2025, trả 0 bài cho mọi job trong phạm vi MVP 2026; 7 trang chuyên mục có ngày đăng thật, cập nhật liên tục, site SSR (Nuxt) nên `httpx` đọc được không cần Playwright |
| `listing_pages` (khai báo toàn bộ trang có thể dùng) tách riêng khỏi `fetch_pages` (tập con thực sự crawl), định danh bằng URL đầy đủ (không dùng "id" ngắn) | Cho phép bật/tắt nhanh 1 chuyên mục mà không mất khai báo gốc; URL vốn đã là khoá duy nhất nên không cần thêm tầng "id" — tránh abstraction thừa |
| `_get_candidates()` ưu tiên `parsing_rules.listing_pages` cao nhất, kể cả khi `source.sitemap_url` vẫn còn giá trị trong DB | Tránh phải đổi routing 2 lần — `sitemap_url` của bocongan.gov.vn sẽ bị xoá ở migration Giai đoạn B, nhưng routing không phụ thuộc việc đó đã xảy ra hay chưa |
| Rollout multi-listing-page cho bocongan.gov.vn tách 2 giai đoạn: A (code + test, không đụng dữ liệu thật) và B (CSS selector thật + migration DB + xoá `sitemap_url`) | Chưa có CSS selector thật cho 7 trang chuyên mục — nếu bật ngay lên production sẽ crash `KeyError` khi code đọc `rules["listing_item"]`; tách giai đoạn để code sẵn sàng mà không phá nguồn đang chạy |
| Phân trang `?page=N` trong từng chuyên mục — KHÔNG làm ở lần cải tiến bocongan.gov.vn này | **Sửa lại (2026-07-07):** dòng gốc ghi "đã verify hoạt động thật" là SAI — thực tế đã thử 3 kiểu URL phân trang phổ biến và cả 3 đều bị Incapsula (WAF) chặn, chưa từng verify hoạt động. Phạm vi lần này chỉ chọn giữa 7 URL chuyên mục khác nhau, mỗi URL lấy 10 bài mới nhất (`card-large`, không phải "~37-40 bài" như ước tính cũ dựa trên `card-small` — xem "Vấn đề cần làm rõ"); đào sâu lịch sử qua phân trang để lại làm sau nếu tìm được API thật |

### Vấn đề cần làm rõ (chưa chốt)
- **Số nguồn ước tính ở Slice 2** ghi "8–10 nguồn thực tế" nhưng theo `content_survey.docx` thực tế là ~11–12 nguồn, khớp pilot test 11/40 — chưa sửa số trong roadmap
- **Số nguồn Slice 2 chỉ đạt 6 (không phải 8–10)** — đã xác nhận 6 nguồn crawl được thật (VTV+VOV+VietnamPlus+CAND+BoCongAn+TinGia); qdnd.vn bị loại do lỗi redirect-loop chưa rõ nguyên nhân (xem bảng quyết định); chinhphu.vn/mod.gov.vn/bvhttdl.gov.vn không có bài chuyên tin giả theo khảo sát thật — người dùng xác nhận 6 nguồn là đủ cho slice này, không ép đủ số
- **Hằng số `ESTIMATED_SECONDS_PER_ARTICLE = 90` ở `SummaryCard.tsx`** là ước lượng thô, chưa có benchmark thật trên nhiều nguồn — cần điều chỉnh lại khi Slice 3 có dữ liệu benchmark thật trên ≥50 bài
- **Nhánh lọc `published_at` thật sau fetch cho BoCongAn (Task 3) — đã rõ nguyên nhân, không còn là vấn đề "chưa verify" đơn thuần**: lần verify job thật (2026-06-30) chỉ lấy được 4 URL đầu (trang tĩnh, `published_at=NULL`) vì sitemap.xml của bocongan.gov.vn **đã xác nhận đóng băng hoàn toàn** ở mốc 20/08/2025 (curl trực tiếp 2026-07-07) — sitemap không phải nguồn dữ liệu dùng được cho phạm vi MVP 2026 nữa, không phải vấn đề "chưa lấy đủ URL". Đã quyết định chuyển sang `listing_pages` (7 trang chuyên mục) thay thế — xem bảng quyết định. Nhánh lọc `published_at` vẫn giữ nguyên vì sẽ hữu ích thật khi dùng listing_pages (ngày lấy từ chuyên mục đáng tin hơn)
- **bocongan.gov.vn hiện bị chặn WAF (Incapsula) toàn bộ từ mạng hiện tại (phát hiện 2026-07-07)** — mọi request tới cả 7 URL `listing_pages` VÀ `sitemap.xml` (endpoint từng hoạt động được qua curl sáng cùng ngày) đều trả về trang challenge JS thay vì nội dung thật, xác nhận qua 3 cách độc lập (curl thường, curl với header trình duyệt đầy đủ, `httpx` trực tiếp từ container `celery-worker`). Chưa rõ đây là block tạm thời (VD do tích luỹ nhiều request tự động trong lúc nghiên cứu/test cùng ngày) hay chính sách WAF cố định — cần thử lại sau (mạng khác hoặc chờ một thời gian) để biết chắc. Đây là điều kiện tiên quyết để hoàn thành verify job thật cho Giai đoạn B (xem "Bước tiếp theo")
- **Đã sửa nhầm lẫn trong nghiên cứu Giai đoạn B ban đầu:** lúc đầu tưởng `card-small` (38 item/trang) là danh sách bài của chuyên mục — SAI, đã verify lại bằng vị trí DOM thật: `card-small`/`card-medium` nằm trong 2 sidebar widget site-wide ("Tin tức mới cập nhật"/"Tin đọc nhiều trong tuần"), không liên quan chuyên mục đang xem. `card-large` (10 item/trang, nằm trong cột chính có `<h3 class="category-title">`) mới là đúng — đã sửa selector theo đúng `card-large` trước khi code
- **Không làm phân trang (`?page=N`) lẫn form lọc "Từ ngày"/"Đến ngày" của bocongan.gov.vn trong Giai đoạn B lần này** — cả 2 đều là tính năng JS phía client (Vue Headless UI listbox + `vue-datepicker`, nút "Tìm kiếm" là thẻ `<a>` không có `action=`/`method=` tĩnh), không phải URL/form gọi được trực tiếp bằng `httpx`. Đã thử 3 kiểu URL phân trang phổ biến (`?page=2`, `/page/2`, `?p=2`, kể cả thử lại cẩn thận với delay dài + header `Referer`) — cả 3 đều bị Incapsula chặn ngay từ lúc nghiên cứu (trước cả khi phát hiện toàn site bị chặn ở Task 4). Mỗi chuyên mục hiện chỉ lấy 10 bài mới nhất/job (không phân trang) — **hướng mở rộng tương lai:** cần người dùng tự inspect tab Network trên trình duyệt thật khi bấm "Tìm kiếm"/chuyển trang để lấy API thật (endpoint/param/header), từ đó mới biết có gọi được bằng `httpx` hay bắt buộc cần Playwright

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
- [x] Listing page crawler (fallback khi nguồn không có sitemap) — `backend/crawler/listing.py`, phạm vi 1 trang không phân trang (YAGNI, chỉ tingia.gov.vn cần đến hiện tại)
- [x] Config & test 6 nguồn thực tế (VTV, VOV, VietnamPlus, CAND, BoCongAn, TinGia — ít hơn ước tính gốc 8–10, xem "Vấn đề cần làm rõ" dưới) — toàn bộ 5 nguồn mới dùng engine Crawl4AI (`parsing_rules.engine = "crawl4ai"`), không viết CSS selector tay
- [x] FE: sidebar chọn nhiều nguồn (search, group theo nhóm kênh), tag nguồn đã chọn, summary card ước tính số bài/thời gian, preset ngày (7/30/90/150), warning khi ≥5 nguồn & ≥60 ngày
- **Verify:** crawl thành công 6 nguồn thực tế đã config (cả sitemap và fallback listing); test trùng URL bị dedup đúng (không insert lại) — **đã verify ở mức unit test + migration thật** (sitemap/listing parser, dispatch chiến lược, lọc ngày đăng thật sau fetch, seed 6 nguồn qua `alembic upgrade head`) **và đã chạy job thật end-to-end với 2 nguồn mới (2026-06-30):** gọi `POST /api/reports/create` với cả 2 `source_ids` (VOV + BoCongAn) trong 1 request (`MAX_ARTICLES_PER_JOB=4` để giới hạn thời gian chạy AI CPU-only) — job này (`32f0bcaa...`) tự "đói" hết quota ở VOV trước (do `MAX_ARTICLES_PER_JOB` là giới hạn toàn job, tính theo thứ tự `source_ids`, xem `_crawl_sources` trong `report_job.py`): 4 bài sitemap-index lastmod-đáng-tin của VOV crawl thành công + AI phân tích xong cả 4 (`status=completed`), BoCongAn chưa được chạm tới trong job này (log worker xác nhận sitemap BoCongAn chưa từng được fetch ở job `32f0bcaa`). Để có dữ liệu thật từ BoCongAn, tạo thêm 1 job riêng chỉ với `source_ids=[BoCongAn]` (`job e4a6b316...`): 4 bài sitemap phẳng (không có index, đúng nhánh code mới — xem Task 1) crawl thành công + AI phân tích xong cả 4 (`status=completed`). Cả 2 job sinh `.docx` hợp lệ (`file` xác nhận `Microsoft Word 2007+`, không rỗng) + `.json` hợp lệ. Không có article nào lỗi (`status="error"`), không có exception trong log worker. **Giới hạn thật của lần verify này (ghi nhận trung thực):** do `MAX_ARTICLES_PER_JOB=4`, 4 URL đầu crawl được từ sitemap phẳng của BoCongAn đều là trang tĩnh (trang chủ, trang lãnh đạo, infographic — không phải bài tin theo ngày) nên `published_at` rút ra được là `NULL` cho cả 4 bài; nhánh lọc lại theo `published_at` thật sau fetch (an toàn hơn tin `<lastmod>` giả — xem Task 3) có chạy nhưng **không có cơ hội thật sự loại bỏ bài nào** trong lần verify này (vì điều kiện `if published_at and not (...)` không kích hoạt khi `published_at=None`) — đã xác nhận qua `curl` trực tiếp sitemap rằng 500 URL có thật, các bài tin theo ngày thật nằm ở vị trí sau trong sitemap (ngoài phạm vi 4 bài đã lấy). Phần đã verify chắc chắn: code nhận diện đúng sitemap phẳng (không index) và không trả về 0 bài như code cũ trước Slice 2. Dedup giữ nguyên cơ chế cũ (SHA256(url)). **(Lịch sử — nay đã thay bằng `listing_pages`, xem "Đã hoàn thành"/"Trạng thái hiện tại" ở trên):** sitemap của BoCongAn sau đó được xác nhận đóng băng hoàn toàn (2026-07-07) và không còn được dùng — đoạn verify này chỉ còn giá trị lịch sử, không phản ánh cách BoCongAn crawl hiện tại

### Slice 3 — AI pipeline đầy đủ
- [ ] Prompt phân loại đầy đủ 8 nhóm chủ đề + keyword + sentiment + `emotion` (6 lớp)
- [ ] Batch processing + tối ưu tốc độ
- [ ] Đánh giá & tinh chỉnh prompt trên dữ liệu thật
- **Verify:** chạy AI trên ≥50 bài thực tế; `confidence < 0.6` → `needs_review=true` đúng ngưỡng; JSON lỗi → retry 1 lần → skip nếu vẫn lỗi (test case JSON không hợp lệ)

### Slice 4 — Report đầy đủ
- [ ] Aggregate query đầy đủ: GROUP BY nguồn/chủ đề/tháng/sentiment/emotion
- [ ] Build DOCX template đầy đủ theo `sample_report_form.docx` + placeholder map
- [ ] Kiểm tra output với dữ liệu thật
- **Verify:** file `.docx` sinh ra khớp cấu trúc `sample_report_form.docx`; số liệu từng bảng khớp với query DB trực tiếp (so sánh tay ít nhất 2-3 bảng)

### Slice 5 — UX & vận hành hoàn chỉnh
- [x] Job status polling + progress UI chi tiết (`crawled/analyzed/total_estimated`) — đã làm ở Slice 1, mở rộng thêm bảng crawl trực tiếp + Cancel (xem Slice 1)
- [ ] Trang lịch sử báo cáo (`GET /api/reports/history`)
- [ ] Error handling đầy đủ theo [10 · Error Handling](.claude/rules/10-error-handling.md) (retry, timeout, JS-render fallback Playwright) — **đã làm trước 1 phần:** AI timeout chỉ skip 1 bài (không fail cả job), crawler lỗi (article + sub-sitemap) hiện `status="error"` trên UI; **còn thiếu:** JS-render fallback Playwright chưa làm
- **Verify:** giả lập timeout/JSON lỗi/nguồn bị block → job xử lý đúng theo bảng error-handling, không crash toàn job

### Slice 6 — Admin UI quản lý nguồn
- [ ] CRUD metadata nguồn (name/URL/active toggle) — không tự thêm parsing rule mới qua UI
- **Verify:** thêm/sửa/xoá nguồn qua UI; nguồn mới active hiển thị đúng ở sidebar chọn nguồn (Slice 2)

**Timeline (không đổi so với breakdown cũ):**
- Best case: ~7 tuần
- Realistic: 9–10 tuần (khuyến nghị dùng để plan)
- Worst case: 11–12 tuần
