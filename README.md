# NGS-AI-Monitoring
NGS AI Monitoring Project

## Port & Service Map

Toàn bộ service chạy qua `docker-compose.yml` (`docker compose up -d`). Bảng dưới liệt kê đầy đủ port có thể truy cập từ máy host.

| Service | Port | Mô tả | Chức năng / mục đích | Truy cập UI? |
|---|---|---|---|---|
| **Frontend** (Next.js) | `3000` | Web UI chính cho người dùng cuối | Form tạo báo cáo (chọn nguồn, khoảng ngày), theo dõi tiến trình job, tải file báo cáo `.docx` | **Có** — mở trực tiếp [http://localhost:3000](http://localhost:3000) |
| **Backend API** (FastAPI) | `8000` | REST API xử lý nghiệp vụ chính | Endpoint `/api/reports/create`, `/api/reports/{job_id}/status`, `/api/reports/{job_id}/download`, `/health` | **Có** — Swagger UI tự sinh tại [http://localhost:8000/docs](http://localhost:8000/docs) (test API trực tiếp, không cần Postman) |
| **Flower** (Celery monitor) | `5555` | Dashboard giám sát Celery | Xem task đang chạy/đã chạy, worker nào đang xử lý, retry/revoke task thủ công | **Có** — [http://localhost:5555](http://localhost:5555) |
| **PostgreSQL** | `5432` | Database chính | Lưu 5 bảng: `sources`, `jobs`, `articles`, `article_analysis`, `report_history` | Không có UI sẵn — cần `psql` hoặc tool ngoài (DBeaver, pgAdmin, TablePlus) kết nối `localhost:5432` (user/pass/db xem `.env`) |
| **Redis** | `6379` | Message broker + result backend cho Celery | Hàng đợi job giữa Backend API và Celery worker | Không có UI sẵn — cần `redis-cli` hoặc RedisInsight |
| **Ollama** | `11434` | AI inference server (local, model `qwen3:8b`) | Nhận request phân loại bài viết (topics/sentiment/emotion/confidence) từ `ai/ollama_client.py` | Không có UI — chỉ REST API, test bằng `curl http://localhost:11434/api/generate` |
| **celery-worker** | *(không expose port)* | Worker thực thi job nền | Chạy task `run_report_job` (crawl → AI → sinh DOCX/JSON) | Không có UI/port riêng — theo dõi qua Flower (`:5555`) hoặc `docker compose logs celery-worker` |

> Lưu ý: `celery-worker` và `flower` dùng cùng image với `backend` nhưng chạy command khác (`celery worker` / `celery flower`), không có route HTTP nghiệp vụ riêng ngoài cổng quản trị Flower.
