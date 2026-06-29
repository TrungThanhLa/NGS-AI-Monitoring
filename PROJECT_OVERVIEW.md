# PROJECT_OVERVIEW.md — Tài liệu tổng quan dự án NGS Monitor

> Tài liệu này dành cho người mới (Engineer, PO, PM, BA...) muốn hiểu nhanh dự án này
> đang làm gì, vận hành ra sao, và đang ở giai đoạn nào. Viết bằng tiếng Việt, ngôn ngữ
> đơn giản, có chú thích thuật ngữ kỹ thuật.
>
> **Thời điểm viết:** 2026-06-26, dựa trên code thật trong repo (branch `main`,
> nhánh đang phát triển `feature/live-crawl-cancel-benchmark`). Phần "đã code" trong
> tài liệu này được xác minh trực tiếp từ source code, không suy đoán từ tài liệu cũ.

---

## 1. 🏠 Tổng quan dự án (Project Overview)

**NGS Monitor** là một web app giúp các nhà nghiên cứu tại Việt Nam **tự động thu thập
bài viết từ báo điện tử/cổng thông tin chính thống**, sau đó dùng **AI chạy ngay trên
máy chủ riêng (local AI — không gửi dữ liệu ra ngoài)** để:

- Phân loại nội dung bài viết vào 8 nhóm chủ đề liên quan đến tin giả và phòng chống tin giả
  (VD: "Tin giả và thông tin sai lệch", "Cảnh báo lừa đảo trên không gian mạng"...)
  Lấy luôn cảm xúc (emotion, 6 nhóm: Trust, Fear, Anger, Surprise, Sadness, Happy) và
  sentiment (3 mức: positive/neutral/negative) — Bảng 3.15 cho báo cáo học thuật.
- Trích từ khóa (keyword) quan trọng của từng bài.

Cuối cùng, hệ thống **tự động đóng gói toàn bộ kết quả thành 1 file báo cáo Word
(`.docx`)** theo mẫu báo cáo học thuật (kèm 1 file `.json` chứa dữ liệu thô để người
dùng tự kiểm tra số liệu), giúp tiết kiệm rất nhiều thời gian so với việc đọc và phân
loại tay hàng trăm bài báo.

**Ai dùng sản phẩm này?**
Người dùng cuối là **nhà nghiên cứu / cán bộ làm báo cáo** về tình hình truyền thông
phòng chống tin giả tại Việt Nam (ví dụ: phục vụ luận văn, báo cáo định kỳ cho cơ
quan quản lý). Họ không cần biết code — chỉ cần chọn nguồn báo + khoảng ngày, bấm
nút, và chờ tải file kết quả.

**Vấn đề thực tế nào được giải quyết?**
Trước đây việc này phải làm tay: vào từng trang báo, đọc từng bài, tự phân loại chủ đề
và cảm xúc, rồi tự gõ vào file Word — rất chậm và dễ sai sót khi số lượng bài lớn
(hàng trăm bài/báo cáo). NGS Monitor tự động hóa toàn bộ quy trình này, từ thu thập dữ
liệu thật (không bịa) đến sinh báo cáo.

**Trạng thái hiện tại:** Đang **trong giai đoạn phát triển (development)**, chưa lên
production. Dự án đi theo chiến lược "vertical slice" (lát cắt đầu-cuối) — ưu tiên làm
ra một pipeline chạy thật từ đầu đến cuối với phạm vi hẹp trước, sau đó mở rộng dần.

- ✅ **Slice 0** (hạ tầng: Docker Compose, DB, Celery, Ollama) — hoàn thành.
- ✅ **Slice 1** (pipeline đầu-cuối cho 1 nguồn — VTV News, hardcode) — hoàn thành, đã
  test với dữ liệu thật (104 bài crawl thật từ VTV). Đã merge `main`.
- 🚧 Phần mở rộng của Slice 1 (bảng crawl trực tiếp, nút Cancel, benchmark thời gian,
  khôi phục job sau F5, fix bug AI timeout) — đã code và đã merge `main`. Có một số
  file đang ở trạng thái **đã sửa xong nhưng chưa commit** (`ollama_client.py`,
  `sitemap.py`, `report_job.py`, các test tương ứng, `.env.example`, `CLAUDE.md`, 2 file
  rule) — đây không phải việc đang làm dở, nội dung tài liệu này khớp với trạng thái
  sắp tới của `main`.
- ⏳ **Slice 2 – Slice 6** (nhiều nguồn, AI pipeline đầy đủ, báo cáo đầy đủ, UX hoàn
  chỉnh, Admin UI) — **chưa bắt đầu**.

---

## 2. 🧰 Tech Stack

| Tầng (Layer) | Công nghệ | Vai trò / Ghi chú |
|---|---|---|
| Frontend | **Next.js 14** + **React 18** + **TypeScript** + **Tailwind CSS** | Giao diện web người dùng thấy trực tiếp. Tailwind là thư viện giúp viết CSS nhanh bằng class có sẵn (VD: `bg-blue-500`) thay vì viết file CSS riêng. |
| Backend API | **FastAPI** (Python 3.12) | "Bộ não" xử lý nghiệp vụ — nhận request từ frontend, đọc/ghi database, đẩy việc nặng (crawl + AI) cho hàng đợi xử lý nền. Tự sinh giao diện test API (Swagger UI) tại `/docs`. |
| Job Queue (hàng đợi xử lý nền) | **Celery** + **Redis** | Việc crawl + phân tích AI rất chậm (có thể nhiều phút) nên không thể xử lý ngay trong lúc người dùng chờ trên web — phải đẩy vào "hàng đợi" để 1 worker (thợ) riêng xử lý ở chế độ nền. Redis đóng vai trò "hộp thư" trung gian giữa Backend API và Celery worker. |
| Giám sát hàng đợi | **Flower** | Dashboard (giao diện theo dõi) cho Celery — xem việc nào đang chạy, việc nào lỗi, ai đang xử lý. |
| Crawler (bộ thu thập dữ liệu) | **httpx** + **BeautifulSoup** (+ **Playwright** dự kiến) | httpx tải nội dung trang web về, BeautifulSoup "đọc hiểu" HTML để lấy ra tiêu đề/nội dung bài viết theo CSS selector cấu hình riêng từng nguồn. Playwright (giả lập trình duyệt thật) dành cho các trang web cần JavaScript chạy mới hiện nội dung — **chưa code, để Slice 5**. |
| AI Runtime | **Ollama** (chạy local, không gọi API ngoài) | Máy chủ chạy AI ngay trên hạ tầng của mình — không gửi dữ liệu bài báo ra ngoài Internet, tránh lo ngại bảo mật/chi phí API trả tiền. |
| AI Model | **`qwen3:8b`** | Model AI ngôn ngữ, hiểu tiếng Việt tốt, chạy được trên CPU (không cần GPU đắt tiền), nhưng khá chậm — có lúc mất hơn 1 phút/bài. |
| Database (cơ sở dữ liệu) | **PostgreSQL 16** + **SQLAlchemy** (ORM) + **Alembic** (migration) | Lưu toàn bộ dữ liệu: cấu hình nguồn, job, bài viết, kết quả AI, lịch sử báo cáo. ORM (Object-Relational Mapping) giúp viết code Python thao tác DB mà không cần viết câu lệnh SQL thủ công. Alembic theo dõi và áp các thay đổi cấu trúc bảng (migration) một cách có thứ tự, có thể tua lại. |
| Sinh báo cáo | **python-docx** | Thư viện Python điền dữ liệu vào file Word (`.docx`) — bảng số liệu, đoạn văn — không cần mở Microsoft Word. |
| Storage (lưu trữ file) | Local filesystem (ổ đĩa của máy chủ) | MVP (phiên bản tối thiểu) chưa cần hệ thống lưu trữ phức tạp như MinIO/S3 — file `.docx`/`.json` lưu thẳng vào thư mục `storage/` trên máy chạy backend. |
| Infrastructure / DevOps | **Docker Compose** | Đóng gói toàn bộ 7 service (Postgres, Redis, Ollama, Backend, Celery worker, Flower, Frontend) chạy cùng lúc bằng 1 lệnh `docker compose up`, không cần cài từng phần mềm riêng lẻ trên máy. |
| External Services | *Không có* | Dự án **không gọi bất kỳ API trả phí/bên ngoài nào** — kể cả AI cũng chạy local. Đây là quyết định kiến trúc có chủ đích (bảo mật + kiểm soát chi phí). |

> **Lưu ý quan trọng đã ghi trong CLAUDE.md:** gọi thẳng Ollama API bằng `httpx`, **không
> dùng LangChain** — giữ pipeline đơn giản, tránh thêm lớp trừu tượng không cần thiết.

---

## 3. 🗂️ Cấu trúc thư mục (Project Structure)

```
ngs-monitor/
├── frontend/                    # Next.js app — giao diện web
│   ├── app/
│   │   ├── page.tsx             # Toàn bộ UI hiện tại nằm ở đây (single-page app)
│   │   ├── layout.tsx           # Layout gốc (html/body, title, lang="vi")
│   │   └── globals.css          # Chỉ import Tailwind, không có style riêng
│   ├── components/               # (hiện đang RỖNG — chưa tách component nào)
│   ├── package.json / tsconfig.json / tailwind.config.js / next.config.js
│   └── Dockerfile
│
├── backend/                      # FastAPI app — toàn bộ logic nghiệp vụ
│   ├── main.py                  # Khởi tạo FastAPI, CORS, đăng ký router, /health
│   ├── db.py                    # Kết nối PostgreSQL qua SQLAlchemy
│   ├── routers/
│   │   └── reports.py           # Toàn bộ 5 endpoint /api/reports/* (chưa có sources.py)
│   ├── workers/
│   │   ├── celery_app.py        # Cấu hình Celery (broker=Redis, backend=Redis)
│   │   └── report_job.py        # Task chính: crawl → AI → sinh báo cáo (1 task tuần tự)
│   ├── crawler/
│   │   ├── sitemap.py           # Đọc sitemap.xml, lọc URL theo ngày, retry khi lỗi
│   │   └── article.py           # Tải + parse 1 bài viết theo CSS selector, dedup hash
│   ├── ai/
│   │   ├── ollama_client.py     # Gọi Ollama, parse JSON, retry, cắt nội dung dài
│   │   └── prompts/
│   │       └── v1.py            # PROMPT_VERSION=1 + prompt mẫu + 8 nhóm chủ đề + 6 cảm xúc
│   ├── report/
│   │   ├── aggregator.py        # Tổng hợp số liệu (đếm theo sentiment/emotion)
│   │   └── docx_generator.py    # Điền số liệu vào file .docx + xuất .json
│   ├── models/                  # 5 file model SQLAlchemy — 1 file/bảng
│   ├── alembic/versions/        # 3 migration (xem mục 6)
│   ├── tests/                   # 7 file test, ~28 test case (Pytest)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── entrypoint.sh             # alembic upgrade head → chạy uvicorn
│
├── ollama/entrypoint.sh          # ollama serve + tự pull model qwen3:8b lúc khởi động
├── docs/superpowers/             # Spec + plan kỹ thuật cho phần mở rộng Slice 1
├── storage/                      # File .docx/.json sinh ra (gitignored)
├── templates/                    # Template DOCX gốc (report_template.docx)
├── .claude/rules/                # 13 file rule — "luật chơi" chi tiết cho từng mảng
├── docker-compose.yml
├── .env.example / .env
└── CLAUDE.md                     # Tài liệu trung tâm: roadmap, quyết định, log tiến độ
```

**Giải thích từng phần quan trọng:**

- **`frontend/app/page.tsx`** — Đây là toàn bộ giao diện người dùng hiện tại, viết
  trong 1 file (chưa tách component). Đây là nơi đầu tiên cần xem nếu muốn hiểu trải
  nghiệm người dùng thật.
- **`backend/routers/reports.py`** — "Cổng vào" duy nhất hiện có của backend. Tất cả
  request từ frontend (tạo báo cáo, xem trạng thái, hủy, tải file) đều đi qua đây.
- **`backend/workers/report_job.py`** — Đây là "trái tim" của hệ thống: 1 hàm Celery
  task chạy tuần tự crawl → gọi AI → sinh báo cáo. Vì là 1 task duy nhất (không tách
  riêng từng bước), debug khá dễ nhưng chưa chạy song song được (để dành Slice 3).
- **`backend/crawler/`** — Chỉ có chiến lược Sitemap XML (ưu tiên 1). Chiến lược
  fallback bằng listing page (ưu tiên 2, khi nguồn không có sitemap) **chưa được code**.
- **`backend/ai/prompts/`** — Thư mục này theo nguyên tắc **versioning** (đánh số
  phiên bản): mỗi lần tinh chỉnh prompt sẽ thêm file mới (`v2.py`, `v3.py`...), không
  sửa đè file cũ, để không lẫn kết quả cũ/mới khi so sánh.
- **`backend/models/`** — Định nghĩa cấu trúc 5 bảng DB bằng code Python (ORM), khớp
  với migration trong `alembic/versions/`.
- **`.claude/rules/`** — Đây thực chất là "sổ tay quy tắc" rất chi tiết, được AI
  assistant (Claude Code) đọc trước khi code mỗi lần. Tài liệu `PROJECT_OVERVIEW.md`
  này được viết dựa trên các rule đó + xác minh lại với code thật.

---

## 4. 🔄 Business Flow & Workflow chính

Hệ thống hiện có 2 luồng nghiệp vụ chính đã hoạt động thật: **Luồng tạo báo cáo** (chính)
và **Luồng theo dõi/hủy job** (phụ, mở rộng thêm sau Slice 1).

### Luồng 1: Tạo báo cáo (đầu-cuối, đã chạy thật)

Người dùng mở web → chọn khoảng ngày (nguồn hiện hardcode là VTV News, vì chưa làm
sidebar chọn nhiều nguồn) → bấm "Tạo báo cáo". Hệ thống tạo 1 "Job" (công việc) và đẩy
vào hàng đợi Celery để xử lý nền — backend trả lại `job_id` ngay, không chờ. Phía sau,
worker (thợ) lần lượt: tải sitemap → tải từng bài viết → gọi AI phân loại từng bài →
tổng hợp số liệu → sinh file `.docx` + `.json`. Frontend tự động hỏi lại trạng thái mỗi
3 giây cho đến khi xong, lúc đó hiện nút tải file.

```mermaid
flowchart TD
    A[Người dùng mở trang web] --> B[Chọn khoảng ngày]
    B --> C[Bấm Tạo báo cáo]
    C --> D[Backend validate: ngày hợp lệ, nguồn tồn tại & active]
    D -->|Không hợp lệ| E[Trả lỗi 400, hiện trên FE]
    D -->|Hợp lệ| F[Tạo Job UUID, lưu DB status=pending]
    F --> G[Đẩy việc vào hàng đợi Celery qua Redis]
    G --> H[Trả job_id ngay cho FE, không chờ]
    H --> I[Worker nhận việc, set status=running]
    I --> J[Crawl: đọc sitemap, lọc URL theo ngày]
    J --> K[Tải từng bài viết, parse title/content]
    K --> L{Tải/parse lỗi?}
    L -->|Có| M[Lưu bài với status=error, tiếp tục bài kế]
    L -->|Không| N[Lưu bài thành công vào DB]
    N --> O[Gọi AI Ollama phân loại bài]
    O --> P{AI lỗi/timeout?}
    P -->|Có| Q[Đánh dấu bài status=error, tiếp tục bài kế]
    P -->|Không| R[Lưu kết quả AI: topics/sentiment/emotion/confidence]
    R --> S[Sau khi hết bài: tổng hợp số liệu]
    S --> T[Sinh file .docx + .json, lưu vào storage]
    T --> U[Set status=completed]
    U --> V[FE polling thấy completed, hiện nút Tải file]
    V --> W[Người dùng tải file .docx về máy]
```

### Luồng 2: Theo dõi job & Hủy job (Cancel) — mở rộng Slice 1

Trong khi job đang chạy nền, frontend liên tục hỏi trạng thái (poll mỗi 3 giây) và hiển
thị 1 bảng "crawl trực tiếp" — danh sách từng bài đã crawl, link mở bài thật để người
dùng tự kiểm chứng, kèm thời gian crawl/phân tích từng bài. Người dùng có thể bấm
"Cancel" để hủy job đang chạy. Nếu người dùng lỡ tay F5 (tải lại trang), `job_id` được
lưu tạm ở `sessionStorage` của trình duyệt nên trang tự khôi phục lại đúng trạng thái
(không bị mất khả năng theo dõi/hủy job dù job thật vẫn chạy nền độc lập với frontend).

```mermaid
flowchart TD
    A[Job đang chạy nền] --> B[FE poll mỗi 3s: GET /status + GET /articles]
    B --> C[Hiện progress: đã crawl X / đã phân tích Y]
    C --> D[Hiện bảng crawl trực tiếp kèm benchmark thời gian]
    D --> E{Người dùng có hành động?}
    E -->|Bấm Cancel| F[POST /cancel]
    F --> G[Backend: Celery revoke task SIGTERM + set status=cancelled]
    G --> H[FE dừng polling, hiện thông báo đã hủy]
    E -->|Lỡ F5 reload trang| I[FE đọc job_id từ sessionStorage lúc mount]
    I --> J[Gọi lại GET /status + GET /articles để khôi phục UI]
    J -->|Job không còn tồn tại| K[Xóa sessionStorage, coi như chưa có job]
    J -->|Job vẫn tồn tại| C
    E -->|Không làm gì| L{status đã completed/failed/cancelled?}
    L -->|Chưa| B
    L -->|Rồi| M[Dừng polling, xóa sessionStorage]
```

> **Lưu ý nghiệp vụ quan trọng:** Khi Cancel, Celery `revoke(..., terminate=True)` giết
> task bằng tín hiệu SIGTERM — task **không tự cập nhật được status** vì bị giết giữa
> đường (không phải lỗi Python catch được), nên chính API endpoint `/cancel` phải tự
> set `status=cancelled` trong DB. Dữ liệu bài viết đã crawl/phân tích trước khi hủy
> **vẫn được giữ lại** (không xóa) — vì đây là dữ liệu thật, không phải rác.

---

## 5. 🔌 Kiến trúc hệ thống (System Architecture)

```mermaid
graph LR
    U["Người dùng<br/>(browser)"] -->|HTTP| FE["Frontend<br/>Next.js :3000"]
    FE -->|fetch JSON<br/>NEXT_PUBLIC_API_BASE_URL| BE["Backend API<br/>FastAPI :8000"]
    BE -->|đọc/ghi| DB[("PostgreSQL :5432<br/>5 bảng")]
    BE -->|đẩy việc + đọc trạng thái| Q[("Redis :6379<br/>broker + backend Celery")]
    Q -->|nhận việc| CW["Celery Worker<br/>(không expose port)"]
    CW -->|đọc/ghi| DB
    CW -->|crawl HTML| WEB["Báo điện tử<br/>(VD: vtv.vn)"]
    CW -->|gọi REST API| OL["Ollama :11434<br/>model qwen3:8b"]
    CW -->|ghi file| ST["storage/<br/>.docx + .json"]
    FE -->|GET download| BE
    BE -->|đọc file| ST
    FL["Flower :5555<br/>(dashboard giám sát)"] -.->|theo dõi| Q
```

**Luồng request đi từ đâu → qua đâu → đến đâu:**

1. Người dùng mở trình duyệt vào `http://localhost:3000` (Frontend).
2. Frontend gọi thẳng tới Backend API (`http://localhost:8000`) qua `fetch()` thuần
   (không qua proxy/BFF nào) — địa chỉ này cấu hình qua biến môi trường
   `NEXT_PUBLIC_API_BASE_URL`.
3. Backend API (FastAPI) là nơi duy nhất nói chuyện trực tiếp với PostgreSQL. Khi nhận
   request tạo báo cáo, nó **ghi DB trước** (tạo `Job` với `celery_task_id` tự sinh),
   sau đó mới đẩy việc cho Celery — để tránh race condition (lỡ Celery chạy xong trước
   khi DB commit, sẽ làm Cancel không tìm thấy `celery_task_id`).
4. Redis chỉ đóng vai trò "hộp thư" trung gian (message broker) — chuyển việc từ
   Backend sang Celery Worker, và lưu kết quả tạm (result backend).
5. Celery Worker là **thành phần duy nhất gọi ra ngoài Internet** (crawl các trang báo
   điện tử thật) và gọi Ollama (AI, chạy trên cùng hạ tầng, không phải Internet).
6. File kết quả (`.docx`/`.json`) được Celery Worker ghi trực tiếp vào ổ đĩa
   (`storage/`), và Backend API đọc lại file đó khi người dùng bấm "Tải báo cáo".
7. Flower chỉ là dashboard giám sát Redis/Celery — không tham gia vào luồng xử lý
   request thật, chỉ để dev/admin xem cho biết.

> Tất cả service trên chạy chung qua 1 file `docker-compose.yml` — bấm
> `docker compose up -d` là có đủ 7 service.

---

## 6. 🗄️ Mô hình dữ liệu (Data Model)

5 bảng chính, định nghĩa tại `backend/models/` (mỗi bảng 1 file) và đồng bộ qua
migration `backend/alembic/versions/` (`0001_initial.py` → tạo 5 bảng, `0002_seed_vtv_source.py`
→ seed sẵn 1 nguồn VTV để test, `0003_add_celery_task_id_and_duration_columns.py` →
thêm cột `celery_task_id` + 2 cột đo thời gian, phục vụ phần mở rộng Slice 1).

| Bảng | Mục đích | Trường quan trọng |
|---|---|---|
| `sources` | Cấu hình từng nguồn báo (tên, domain, sitemap URL, CSS selector riêng) | `domain` (UNIQUE), `parsing_rules` (JSONB — selector title/content/date/author), `is_active` |
| `jobs` | 1 lần "tạo báo cáo" = 1 job | `status` (pending/running/completed/failed/cancelled), `source_ids` (mảng UUID), `date_from`/`date_to`, `celery_task_id` (để hủy job), `output_docx`/`output_json` |
| `articles` | 1 bài viết crawl được | `url_hash` (SHA256, UNIQUE — chống trùng), `status` (pending_analysis/analyzed/error), `crawl_duration_seconds` |
| `article_analysis` | Kết quả AI phân tích 1 bài | `topics` (mảng text, 8 nhóm), `sentiment`, `emotion`, `confidence`, `needs_review` (true nếu confidence<0.6), `prompt_version`, `analysis_duration_seconds` |
| `report_history` | Lịch sử file báo cáo đã sinh | `job_id`, `file_path` |

**Quan hệ giữa các bảng (nói theo ngôn ngữ đời thường):**

- 1 `source` (nguồn báo) có thể được dùng trong **nhiều** `job` khác nhau — nhưng mỗi
  job lưu danh sách nguồn dưới dạng mảng `source_ids`, không có bảng nối trung gian.
- 1 `job` có **nhiều** `articles` (mỗi bài crawl được trong khoảng ngày job đó yêu cầu).
- 1 `article` có **tối đa 1** `article_analysis` (1 bài chỉ phân tích AI 1 lần — nếu
  lỗi thì đánh dấu `status=error` trên chính bài đó, không tạo bản ghi phân tích).
- 1 `job` có **tối đa 1** `report_history` được tạo lúc job hoàn thành (sinh xong
  `.docx`).
- `articles.source_id` trỏ về đúng nguồn báo đã sinh ra bài đó (1 nguồn → nhiều bài).

```mermaid
erDiagram
    SOURCES ||--o{ ARTICLES : "cung cấp bài cho"
    JOBS ||--o{ ARTICLES : "crawl ra"
    JOBS ||--o{ ARTICLE_ANALYSIS : "phân tích trong"
    ARTICLES ||--o| ARTICLE_ANALYSIS : "được phân tích thành"
    JOBS ||--o| REPORT_HISTORY : "sinh ra"

    SOURCES {
        uuid source_id PK
        string domain
        jsonb parsing_rules
        bool is_active
    }
    JOBS {
        uuid job_id PK
        uuid_array source_ids
        string status
        string celery_task_id
        text output_docx
    }
    ARTICLES {
        uuid article_id PK
        uuid job_id FK
        uuid source_id FK
        string url_hash
        string status
        float crawl_duration_seconds
    }
    ARTICLE_ANALYSIS {
        uuid analysis_id PK
        uuid article_id FK
        uuid job_id FK
        string sentiment
        string emotion
        float confidence
        bool needs_review
        int prompt_version
    }
    REPORT_HISTORY {
        uuid report_id PK
        uuid job_id FK
        text file_path
    }
```

**Lưu ý quan trọng về dữ liệu lỗi:** Khi crawl 1 bài lỗi (hết retry) hoặc 1 sub-sitemap
lỗi, hệ thống **vẫn insert 1 row vào `articles`** với `status="error"` (thay vì bỏ qua
âm thầm) — để người dùng nhìn thấy lỗi đó trên bảng crawl trực tiếp ở frontend, không
bị "mất tích" không rõ lý do. Với sub-sitemap lỗi, `url_hash` được tính theo
`job_id + url` (khác cách tính `SHA256(url)` thông thường) để tránh đụng `UNIQUE
constraint` nếu job khác sau này gặp lại đúng sub-sitemap lỗi đó.

---

## 7. 🚀 Môi trường & Cách chạy dự án (Setup & Run)

### 7.1. Yêu cầu máy tính (prerequisites)

- **Docker** + **Docker Compose** (cách chạy được khuyến nghị — không cần cài Python/Node
  riêng trên máy, mọi service chạy trong container).
- Nếu muốn chạy backend/frontend KHÔNG qua Docker (chạy trực tiếp để debug nhanh):
  Python 3.12, Node.js 20.

### 7.2. Clone repo + cấu hình môi trường

```bash
git clone <repo-url>
cd NGS-AI-Monitoring
cp .env.example .env
```

File `.env` chứa các biến quan trọng (đã có giá trị mẫu hợp lý trong `.env.example`,
xem thêm mục 9):

```env
POSTGRES_DB=ngs_monitor
POSTGRES_USER=ngs
POSTGRES_PASSWORD=ngs
DATABASE_URL=postgresql://ngs:ngs@postgres:5432/ngs_monitor
REDIS_URL=redis://redis:6379/0
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen3:8b
AI_CONFIDENCE_THRESHOLD=0.6
AI_MAX_CONTENT_LENGTH=5000
AI_TIMEOUT_SECONDS=360
CRAWLER_DELAY_SECONDS=1.5
CRAWLER_MAX_RETRIES=3
CRAWLER_TIMEOUT_SECONDS=30
STORAGE_PATH=./storage
DOCX_TEMPLATE_PATH=./templates/report_template.docx
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
MAX_ARTICLES_PER_JOB=    # để trống = không giới hạn (chỉ set khi test/dev)
```

### 7.3. Chạy toàn bộ hệ thống bằng Docker Compose

```bash
docker compose up -d
```

Lệnh này tự động:
1. Khởi động PostgreSQL, Redis.
2. Khởi động Ollama, tự `ollama pull qwen3:8b` (lần đầu sẽ mất vài phút tải model).
3. Build & khởi động Backend (tự chạy `alembic upgrade head` để tạo bảng trước khi
   chạy `uvicorn`).
4. Khởi động Celery worker + Flower.
5. Build & khởi động Frontend (chạy ở dev mode `next dev`, port 3000).

### 7.4. Kiểm tra đã chạy thành công chưa

```bash
docker compose ps          # tất cả service phải ở trạng thái "healthy"
curl http://localhost:8000/health    # kỳ vọng: {"status": "ok"}
```

Sau đó mở trình duyệt:

| Việc cần kiểm tra | URL |
|---|---|
| Giao diện web chính | http://localhost:3000 |
| Swagger UI (test API trực tiếp, không cần Postman) | http://localhost:8000/docs |
| Flower (dashboard Celery) | http://localhost:5555 |

### 7.5. Chạy test (Pytest) cho backend

```bash
# Đảm bảo DATABASE_URL trong môi trường đang trỏ đúng DB test/dev
cd backend
pytest
```

> Có 7 file test (~28 test case) cho crawler, AI client, aggregator, docx generator,
> router, sitemap, report job — xem chi tiết mục 8 (Gotchas) và mục 4 (Business Flow).

---

## 8. ⚠️ Những điều cần LƯU Ý (Gotchas & Important Notes)

- ⚠️ **Nguồn dữ liệu hiện đang hardcode (cố định cứng)** — Frontend chỉ có 1 nguồn
  VTV News (`VTV_SOURCE_ID` hardcode trong `page.tsx`), không có sidebar chọn nhiều
  nguồn như mockup trong `.claude/rules/09-frontend-ui.md`. Mockup đó là thiết kế đích
  cho **Slice 2**, chưa code. Đừng nhầm "thiết kế đích" với "hiện trạng".
- ⚠️ **`/api/sources` (CRUD nguồn) chưa tồn tại** — dù được liệt kê trong API contract
  (`.claude/rules/05-api-contracts.md`), đây là việc của **Slice 6** (Admin UI), chưa
  code. Hiện tại nguồn duy nhất (VTV) được tạo sẵn qua migration `0002_seed_vtv_source.py`.
- ⚠️ **Listing-page fallback crawler chưa code** — nếu 1 nguồn không có sitemap, hệ
  thống **chưa có cách crawl** nguồn đó (việc của Slice 2). Hiện chỉ hỗ trợ crawl qua
  sitemap XML.
- ⚠️ **Playwright (crawl trang JS-render) chưa code** — dành cho Slice 5. Nguồn nào
  cần JavaScript chạy để hiện nội dung sẽ **không crawl được** ở giai đoạn hiện tại.
- ⚠️ **`AI_TIMEOUT_SECONDS=360` và `AI_MAX_CONTENT_LENGTH=5000` là giải pháp tạm thời**
  (ghi rõ trong CLAUDE.md, 2026-06-26) — vì model `qwen3:8b` chạy CPU-only có lúc mất
  >120s/bài thật. Đừng tự ý hạ giá trị này xuống thấp nếu chưa rõ lý do, vì sẽ làm
  tăng tỷ lệ bài bị skip do timeout.
- ⚠️ **AI timeout chỉ skip 1 bài, KHÔNG fail cả job** — đây là 1 bug đã fix
  (commit `5602bf8`): code cũ chỉ bắt `ValueError`, không bắt `httpx.HTTPError`
  (timeout), khiến cả job fail mất hết báo cáo dù phần lớn bài đã phân tích xong. Khi
  sửa code liên quan đến `_analyze_articles` trong `report_job.py`, **luôn giữ việc
  bắt cả 2 loại exception này**.
- ⚠️ **Cancel job dùng SIGTERM, không phải Python exception** — task Celery bị giết
  giữa đường khi Cancel, nên **chính nó không tự cập nhật được `status` trong DB**.
  Logic set `status=cancelled` nằm ở endpoint `/cancel`, không nằm trong
  `report_job.py`. Dữ liệu đã insert dở (articles/article_analysis) trước khi hủy
  **vẫn giữ lại**, không bị xóa — đây là quyết định có chủ đích (chấp nhận dữ liệu
  thật một phần thay vì dọn sạch).
- ⚠️ **`celery_task_id` luôn tự sinh bằng `uuid.uuid4()` và **commit DB trước** khi gọi
  `apply_async()`** — không bao giờ suy ra từ `job_id`. Đây là để tránh race condition:
  nếu Celery task chạy/xong trước khi DB commit xong, request Cancel đến sớm sẽ đọc
  `celery_task_id=None` và không revoke được task thật.
- ⚠️ **`MAX_ARTICLES_PER_JOB` chỉ là biến môi trường, không có trên UI** — cố ý không
  đưa lên giao diện vì đây là nhu cầu test/dev (AI local rất chậm), đưa lên UI thật có
  rủi ro tạo báo cáo thiếu dữ liệu mà người dùng không biết.
- ⚠️ **`sessionStorage` (không phải `localStorage`)** dùng để khôi phục job sau F5 —
  cố ý chọn `sessionStorage` để tự dọn khi đóng tab, tránh "job ma" tồn đọng nhiều
  ngày trong trình duyệt.
- ⚠️ **Frontend Dockerfile chạy `npm run dev` (dev mode), không phải `next build && next start`**
  — phù hợp cho môi trường phát triển hiện tại, nhưng **không nên dùng để deploy
  production** mà không sửa lại Dockerfile.
- ⚠️ **CORS hiện hardcode chỉ cho phép `http://localhost:3000`** trong `backend/main.py`
  — nếu đổi port frontend hoặc deploy domain khác, phải sửa danh sách `allow_origins`.
- 💡 **Quy ước comment tiếng Việt giải thích logic quan trọng** — team có quy ước viết
  comment tiếng Việt cho phần logic nghiệp vụ không hiển nhiên (xem `13-workflow.md`).
  Khi đọc code, đừng ngạc nhiên khi thấy comment tiếng Việt xen giữa code tiếng Anh.
- 💡 **Prompt AI được versioned (đánh số phiên bản) trong `backend/ai/prompts/`** — khi
  tinh chỉnh prompt, **không sửa đè file cũ** (`v1.py`), luôn thêm file mới
  (`v2.py`...) với `PROMPT_VERSION` tăng dần, để mỗi bản ghi `article_analysis` biết
  chính xác nó được sinh ra từ prompt phiên bản nào.
- 💡 **Có 1 nhánh git đang phát triển song song** — `feature/live-crawl-cancel-benchmark`
  (theo các commit gần nhất và 9 file đang sửa chưa commit: `ollama_client.py`,
  `sitemap.py`, `report_job.py` và các test liên quan). Nếu thấy hành vi code khác mô
  tả ở đây, kiểm tra lại `git status`/`git diff` trước khi báo bug.
- 💡 **Mọi quyết định kiến trúc quan trọng + lý do đã được ghi log đầy đủ** trong bảng
  "Quyết định quan trọng & lý do" của `CLAUDE.md` — nên đọc bảng đó trước khi đề xuất
  thay đổi lớn, để tránh lặp lại tranh luận đã có câu trả lời.

---

## 9. 🔗 Tích hợp bên ngoài (External Integrations)

| Service | Mục đích | Luồng dữ liệu | Cấu hình (env) | Lưu ý |
|---|---|---|---|---|
| **Các trang báo điện tử Việt Nam** (VD: vtv.vn) | Nguồn dữ liệu bài viết để crawl | Celery worker → tải sitemap.xml/HTML qua `httpx` → parse bằng `BeautifulSoup` theo CSS selector lưu trong `sources.parsing_rules` | `CRAWLER_DELAY_SECONDS` (delay giữa request, mặc định 1.5s — tránh bị chặn IP), `CRAWLER_MAX_RETRIES=3`, `CRAWLER_TIMEOUT_SECONDS=30` | Đây không phải "API chính thức" — là crawl trang công khai. Phải tuân thủ delay giữa request để tránh bị site chặn IP. CSS selector khác nhau theo từng site, cấu hình tay trong `sources.parsing_rules` (JSONB), không tự động hóa. |
| **Ollama** (AI local) | Phân loại chủ đề/sentiment/emotion/keyword cho từng bài viết | Celery worker → POST `http://ollama:11434/api/generate` với `model=qwen3:8b` + prompt → nhận JSON kết quả | `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `AI_TIMEOUT_SECONDS=360`, `AI_MAX_CONTENT_LENGTH=5000`, `AI_CONFIDENCE_THRESHOLD=0.6` | **Không phải dịch vụ bên thứ 3** — chạy ngay trong Docker Compose, không có rate limit/billing. Nhưng chạy CPU-only nên rất chậm (~60–120s/bài thật), dễ timeout nếu set `AI_TIMEOUT_SECONDS` quá thấp. |

> Dự án **không tích hợp** với bất kỳ dịch vụ thanh toán, email, SMS, hay AI API trả
> phí bên ngoài nào — đây là quyết định kiến trúc có chủ đích (xem mục 2, Tech Stack).

---

## 10. 👥 Glossary — Bảng thuật ngữ dự án

| Thuật ngữ | Ý nghĩa |
|---|---|
| **Job** | 1 lần người dùng bấm "Tạo báo cáo" = 1 job, có `job_id` riêng, trạng thái chạy qua các bước pending → running → completed/failed/cancelled. |
| **Sitemap XML** | File XML chuẩn mà website công khai, liệt kê toàn bộ URL bài viết + ngày đăng — giúp crawler biết bài nào mới mà không cần dò từng trang. |
| **Listing page** | Trang danh sách bài viết (VD: trang chuyên mục) — dùng làm cách crawl dự phòng (fallback) khi site không có sitemap. **Chưa code.** |
| **Parsing rules** | Cấu hình CSS selector riêng từng nguồn (lưu ở `sources.parsing_rules`, dạng JSONB) để biết lấy tiêu đề/nội dung/ngày/tác giả từ đâu trong HTML. |
| **Dedup** | Viết tắt "deduplicate" — chống trùng lặp, dùng `SHA256(url)` để kiểm tra 1 bài đã crawl trước khi insert lại. |
| **Sentiment** | Phân loại cảm xúc bài viết ở mức đơn giản: tích cực (positive) / trung lập (neutral) / tiêu cực (negative). |
| **Emotion** | Phân loại cảm xúc chi tiết hơn sentiment, 6 nhóm: Trust (tin tưởng), Fear (sợ hãi), Anger (giận dữ), Surprise (bất ngờ), Sadness (buồn), Happy (vui) — phục vụ Bảng 3.15 trong báo cáo học thuật. |
| **Confidence** | Mức độ "tự tin" của AI vào kết quả phân loại, từ 0.0 đến 1.0. Dưới `0.6` thì bị đánh dấu `needs_review=true`. |
| **needs_review** | Cờ (flag) đánh dấu bài viết có confidence thấp — vẫn được lưu và đưa vào báo cáo, nhưng nên có người xem lại thủ công. |
| **Prompt version** | Số phiên bản của câu lệnh (prompt) gửi cho AI — lưu kèm mỗi kết quả phân tích để biết nó được sinh ra từ phiên bản prompt nào, tránh lẫn lộn khi tinh chỉnh prompt sau này. |
| **Celery worker** | Tiến trình (process) chạy nền, nhận việc từ hàng đợi (queue) và xử lý — ở đây là nơi thực thi `report_job.py` (crawl + AI + sinh báo cáo). |
| **Broker (message broker)** | "Hộp thư" trung gian giữa nơi tạo việc (Backend API) và nơi xử lý việc (Celery worker) — ở đây dùng Redis. |
| **Revoke (Celery)** | Lệnh hủy 1 task Celery đang chạy hoặc đang chờ trong hàng đợi — dùng khi người dùng bấm "Cancel". |
| **ORM** | Object-Relational Mapping — thư viện (ở đây là SQLAlchemy) giúp viết code Python để thao tác database mà không cần viết câu lệnh SQL thủ công. |
| **Migration (Alembic)** | Tệp ghi lại 1 thay đổi cấu trúc database (VD: thêm cột, tạo bảng) theo thứ tự, để có thể áp dụng lại hoặc tua lại một cách an toàn. |
| **MVP** | Minimum Viable Product — phiên bản tối thiểu có thể dùng được, chỉ đủ tính năng cốt lõi, chưa đầy đủ mọi tính năng mong muốn. |
| **Vertical slice (lát cắt đầu-cuối)** | Cách chia nhỏ công việc theo "1 luồng chạy được hết từ đầu đến cuối với phạm vi hẹp", thay vì làm xong hết 1 lớp kỹ thuật (toàn bộ DB) rồi mới sang lớp khác (toàn bộ crawler). |
| **Walking skeleton** | Tên gọi cho Slice 1 — bản pipeline "khung xương" chạy được thật từ đầu đến cuối với phạm vi hẹp nhất (1 nguồn, vài bài), trước khi mở rộng. |

---

## 11. ❓ Câu hỏi cần làm rõ

> Đã hỏi user và nhận câu trả lời (2026-06-26) — ghi lại để tránh hỏi lại lần sau.

- [x] **File chưa commit có phải việc đang làm dở?** → **Đã xong, chỉ chưa commit.**
  Nội dung tài liệu này (dựa trên working tree hiện tại) khớp với trạng thái sắp tới
  của `main`, không phải snapshot giữa đường.
- [x] **Số nguồn ước tính Slice 2 (8–10 hay 11–12)?** → **Giữ nguyên "8–10 nguồn"
  trong roadmap** — không sửa số ngay, để khi thực sự làm Slice 2 mới khảo sát và chốt
  số chính xác dựa trên kết quả crawl thật.
- [ ] **`AI_TIMEOUT_SECONDS=360` và `AI_MAX_CONTENT_LENGTH=5000` là giải pháp tạm** —
  CLAUDE.md ghi sẽ "nâng/hạ lại theo tần suất lỗi thật gặp phải" ở Slice 3, nhưng chưa
  có tiêu chí cụ thể (VD: tỷ lệ timeout bao nhiêu % thì cần điều chỉnh). Lý do cần hỏi:
  để biết khi nào nên chủ động đề xuất điều chỉnh giá trị này. *(Chưa hỏi — vẫn còn mở.)*
- [x] **Domain frontend production cho CORS?** → **Chưa biết / chưa lên kế hoạch
  deploy.** Dự án vẫn đang ở giai đoạn development; cấu hình `allow_origins=["http://localhost:3000"]`
  trong `backend/main.py` là tạm ổn cho hiện tại, cần quay lại sửa khi có kế hoạch
  deploy cụ thể.
- [x] **Frontend production build (`next build && next start`) ở slice nào?** →
  **Chưa lên kế hoạch**, chưa gắn vào slice cụ thể nào. Dockerfile hiện chạy
  `npm run dev` là tạm ổn cho giai đoạn development.

---
**TL;DR:** NGS Monitor là web app giúp nhà nghiên cứu tự động crawl báo điện tử Việt
Nam, dùng AI local (Ollama/qwen3:8b) phân loại chủ đề/sentiment/emotion, rồi xuất báo
cáo Word + JSON. Dự án đang ở **Slice 1 đã hoàn thành** (1 nguồn VTV, pipeline chạy
thật đầu-cuối) — Slice 2–6 (nhiều nguồn, AI đầy đủ, báo cáo đầy đủ, Admin UI) **chưa
bắt đầu**. Kiến trúc: Next.js ↔ FastAPI ↔ PostgreSQL, việc nặng (crawl+AI) xử lý nền
qua Celery+Redis, mọi thứ chạy qua Docker Compose, không gọi dịch vụ bên ngoài nào.
