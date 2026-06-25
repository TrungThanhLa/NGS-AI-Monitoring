---
description: Tech stack và lý do chọn từng công nghệ
alwaysApply: true
---

# Tech Stack

| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| Frontend | Next.js + Tailwind CSS | Desktop-first, React |
| Backend API | Python + FastAPI | REST API, async |
| Job Queue | Celery + Redis | Background jobs, retry tự động |
| Crawler | httpx + BeautifulSoup + Playwright | Sitemap XML primary, listing page fallback |
| AI Runtime | Ollama | Local inference, REST API |
| AI Model | `qwen3:8b` | Tiếng Việt tốt, chạy CPU-only |
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
├── frontend/                  # Next.js app
│   ├── app/
│   │   ├── page.tsx           # Màn hình tạo báo cáo (main)
│   │   ├── history/page.tsx   # Lịch sử báo cáo
│   │   └── admin/page.tsx     # Admin quản lý nguồn
│   └── components/
│       ├── SourceSidebar.tsx  # Sidebar chọn nguồn
│       ├── DatePicker.tsx     # Date range + presets
│       ├── SummaryCard.tsx    # Ước tính số bài & thời gian
│       └── JobStatus.tsx      # Polling + progress
│
├── backend/                   # FastAPI app
│   ├── main.py
│   ├── routers/
│   │   ├── sources.py         # CRUD sources
│   │   ├── reports.py         # Tạo job, download
│   │   └── jobs.py            # Job status
│   ├── workers/
│   │   ├── celery_app.py      # Celery config
│   │   ├── crawl_worker.py    # Task crawl
│   │   └── ai_worker.py       # Task AI analysis
│   ├── crawler/
│   │   ├── sitemap.py         # Sitemap XML parser
│   │   ├── listing.py         # Listing page fallback
│   │   └── article.py         # Article content parser
│   ├── ai/
│   │   ├── ollama_client.py   # Gọi Ollama API
│   │   ├── prompt.py          # Prompt templates
│   │   └── nlp.py             # underthesea NER/keyword
│   ├── report/
│   │   ├── aggregator.py      # Tổng hợp thống kê
│   │   └── docx_generator.py  # python-docx engine
│   ├── models/                # SQLAlchemy models
│   └── db.py                  # PostgreSQL connection
│
├── storage/                   # File output (.docx, .json)
├── templates/                 # DOCX template base
├── docker-compose.yml
└── CLAUDE.md
```

---

## Môi trường & Cấu hình chung

```env
# .env
REDIS_URL=redis://localhost:6379/0
```

Các biến cấu hình riêng theo từng thành phần (database, crawler, AI, report) xem ở rule tương ứng.
