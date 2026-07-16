---
description: Tech stack và lý do chọn từng công nghệ
alwaysApply: true
---

# Tech Stack

| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| Frontend | Vite + React + Ant Design (`antd@^6.5.1`) | Desktop-first, SPA build tĩnh |
| Backend API | Python + FastAPI | REST API, async |
| Job Queue | Celery + Redis | Background jobs, retry tự động |
| Crawler | httpx + BeautifulSoup + Playwright | Sitemap XML primary, listing page fallback |
| Crawler (engine tùy chọn) | Crawl4AI (HTTP-only mode) | Bật theo nguồn qua `parsing_rules.engine = "crawl4ai"` — tự nhận diện content, không cần CSS selector tay. Mặc định vẫn httpx (2026-06-29) |
| AI Runtime | Ollama | Local inference, REST API |
| AI Model | `qwen3:8b` | Tiếng Việt tốt, chạy CPU-only mặc định — GPU tùy chọn qua `COMPOSE_FILE` trong `.env` (xem dưới), chưa verify bằng GPU thật |
| NLP phụ trợ | underthesea | Keyword/NER extraction nhanh |
| Database | PostgreSQL + SQLAlchemy | ORM, migration với Alembic |
| Sinh DOCX | python-docx | Điền template Word |
| Storage | Local filesystem (MVP) | Chuyển MinIO khi scale |
| Monitoring | Flower | Celery dashboard |

> **Ghi chú quan trọng:** Gọi thẳng Ollama API — không dùng LangChain ở giai đoạn MVP. Ưu tiên đơn giản, không thêm abstraction layer nếu không cần thiết.

---

## Cấu trúc thư mục

```
ngs-monitor/
├── frontend/                  # Vite + React SPA (build tĩnh, serve qua nginx — xem docker-compose.yml)
│   ├── src/
│   │   ├── layouts/MainLayout.tsx   # Sider (menu 2 cấp) + Header + Outlet
│   │   ├── pages/
│   │   │   ├── Dashboard/           # Tổng quan (mock)
│   │   │   ├── Sources/             # Nguồn dữ liệu — THẬT, gọi GET /api/sources
│   │   │   ├── Reports/             # Báo cáo — THẬT, 2 trang (list + create), nối full flow backend
│   │   │   ├── Campaigns/ Contents/ Alerts/ Cases/ Jobs/  # mock, chỉ hiển thị UI
│   │   │   └── System/              # Users, Roles, MasterData, Settings, Connectors, AuditLogs — mock
│   │   ├── components/common/       # StatusTag, Logo... dùng chung
│   │   ├── data/mockData.ts         # Toàn bộ mock data cho các trang chưa nối backend thật
│   │   └── theme/                   # ConfigProvider theme AntD
│   ├── Dockerfile                   # multi-stage: node build → nginx serve
│   └── nginx.frontend.conf
│
├── backend/                   # FastAPI app
│   ├── main.py
│   ├── db.py                  # PostgreSQL connection
│   ├── routers/
│   │   ├── sources.py         # CRUD sources (Slice 6, chưa code)
│   │   └── reports.py         # Tạo job, status, articles (bảng crawl trực tiếp),
│   │                          # cancel, download — gộp chung 1 router (Slice 1+)
│   ├── workers/
│   │   ├── celery_app.py      # Celery config
│   │   └── report_job.py      # 1 task tuần tự: crawl → AI → report (Slice 1+;
│   │                          # quyết định không tách crawl_worker/ai_worker riêng
│   │                          # — xem CLAUDE.md "Quyết định quan trọng & lý do")
│   ├── crawler/
│   │   ├── sitemap.py         # Sitemap XML parser
│   │   ├── listing.py         # Listing page fallback
│   │   ├── article.py         # Article content parser (httpx + CSS selector, mặc định)
│   │   └── crawl4ai_client.py # Engine thay thế (engine="crawl4ai") + fetch_article_dispatch()
│   ├── ai/
│   │   ├── ollama_client.py   # Gọi Ollama API
│   │   ├── prompts/           # Prompt versioned theo file: v1.py, v2.py...
│   │   │   └── v1.py          # PROMPT_VERSION + CLASSIFICATION_PROMPT — không sửa đè, thêm file mới khi tinh chỉnh (Slice 3+)
│   │   └── nlp.py             # underthesea NER/keyword
│   ├── report/
│   │   ├── aggregator.py      # Tổng hợp thống kê
│   │   └── docx_generator.py  # python-docx engine
│   ├── models/                # SQLAlchemy models (1 file/bảng)
│   ├── alembic/                # migration, env.py đọc DATABASE_URL từ env
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── Dockerfile
│   └── entrypoint.sh           # alembic upgrade head → uvicorn
│
├── storage/                   # File output (.docx, .json) — gitignored
├── templates/                 # DOCX template base
├── ollama/
│   └── entrypoint.sh           # ollama serve + auto-pull OLLAMA_MODEL
├── docker-compose.yml
├── docker-compose.gpu-nvidia.yml # override: bật GPU NVIDIA cho ollama (tùy chọn, xem dưới)
├── docker-compose.gpu-amd.yml    # override: bật GPU AMD/ROCm cho ollama (tùy chọn, xem dưới)
├── .env.example
└── CLAUDE.md
```

---

## Môi trường & Cấu hình chung

```env
# .env
REDIS_URL=redis://localhost:6379/0
```

Các biến cấu hình riêng theo từng thành phần (database, crawler, AI, report) xem ở rule tương ứng.

### GPU cho Ollama (tùy chọn, mặc định tắt)

Mặc định `docker-compose.yml` chạy `ollama` CPU-only (không đổi hành vi cũ). Để bật GPU trên
máy có GPU tương thích, set biến đặc biệt `COMPOSE_FILE` trong `.env` (Docker Compose tự đọc
biến này từ `.env` để quyết định merge thêm file nào trước khi chạy `docker compose up` —
không cần đổi lệnh, không cần flag `-f`/`--profile`):

```env
# NVIDIA (CUDA) — cần cài nvidia-container-toolkit trên host trước
COMPOSE_FILE=docker-compose.yml:docker-compose.gpu-nvidia.yml

# AMD (ROCm) — cần cài driver ROCm trên host trước; hỗ trợ hạn chế trên Windows/WSL2
COMPOSE_FILE=docker-compose.yml:docker-compose.gpu-amd.yml
```

Không set `COMPOSE_FILE` (hoặc để trống) = giữ nguyên CPU-only như trước đây.
