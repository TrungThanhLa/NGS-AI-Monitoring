# NGS-AI-Monitoring
NGS AI Monitoring Project

## Cách chạy project

---

### Yêu cầu
- Docker + Docker Compose
- ~6GB RAM trống cho container `ollama` (model `qwen3:8b` ~5.2GB, CPU-only mặc định)

---

### Chạy dev từng phần riêng (không qua Docker)

Chỉ cần khi sửa code và muốn hot-reload nhanh hơn rebuild Docker image — vẫn cần
`postgres`/`redis`/`ollama` chạy qua Docker Compose trước:

```bash
docker compose up -d postgres redis ollama
```

**Backend (FastAPI):**
```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn backend.main:app --reload --port 8000   # chạy từ thư mục gốc project, không phải trong backend/
```

**Celery worker (crawl → AI → sinh báo cáo):**
```bash
celery -A backend.workers.celery_app worker --loglevel=info   # chạy từ thư mục gốc project
```

**Frontend (Vite + React):**
```bash
cd frontend
npm install
npm run dev       # http://localhost:5173, gọi backend qua VITE_API_BASE_URL (mặc định http://localhost:8000)
```

---

### Chạy toàn bộ qua Docker Compose (khuyến nghị)

```bash
cp .env.example .env   # chỉnh lại nếu cần (mặc định đã chạy được ngay)
docker compose up -d
```

Lần đầu chạy sẽ mất vài phút vì container `ollama` tự động `ollama pull qwen3:8b` (~5.2GB) và
`backend` tự chạy `alembic upgrade head` trước khi start (xem `backend/entrypoint.sh`,
`ollama/entrypoint.sh`) — không cần chạy migration hay pull model thủ công.

Kiểm tra tất cả service đã healthy:
```bash
docker compose ps
```

Sau khi lên: mở [http://localhost:3000](http://localhost:3000) (Frontend) — xem bảng port đầy đủ bên dưới.

Dừng toàn bộ:
```bash
docker compose down
```

> **GPU cho Ollama (tùy chọn):** mặc định CPU-only. Muốn bật GPU NVIDIA/AMD, set biến
> `COMPOSE_FILE` trong `.env` theo hướng dẫn có sẵn trong file `.env.example` (đã comment sẵn),
> rồi chạy lại `docker compose up -d` như cũ — không cần đổi lệnh. Xem thêm
> [02 · Tech Stack](.claude/rules/02-tech-stack.md).

---

## Port & Service Map

Toàn bộ service chạy qua `docker-compose.yml` (`docker compose up -d`). Bảng dưới liệt kê đầy đủ port có thể truy cập từ máy host.

| Service | Port | Mô tả | Chức năng / mục đích | Truy cập UI? |
|---|---|---|---|---|
| **Frontend** (Vite + React, build tĩnh serve qua nginx) | `3000` | Web UI chính cho người dùng cuối | Form tạo báo cáo (chọn nguồn, khoảng ngày), theo dõi tiến trình job, tải file báo cáo `.docx` | **Có** — mở trực tiếp [http://localhost:3000](http://localhost:3000) |
| **Backend API** (FastAPI) | `8000` | REST API xử lý nghiệp vụ chính | Endpoint `/api/reports/create`, `/api/reports/{job_id}/status`, `/api/reports/{job_id}/articles` (danh sách bài đã crawl kèm benchmark thời gian), `/api/reports/{job_id}/cancel` (hủy job đang chạy), `/api/reports/{job_id}/download`, `/health` | **Có** — Swagger UI tự sinh tại [http://localhost:8000/docs](http://localhost:8000/docs) (test API trực tiếp, không cần Postman) |
| **Flower** (Celery monitor) | `5555` | Dashboard giám sát Celery | Xem task đang chạy/đã chạy, worker nào đang xử lý, retry/revoke task thủ công | **Có** — [http://localhost:5555](http://localhost:5555) |
| **PostgreSQL** | `5432` | Database chính | Lưu 5 bảng: `sources`, `jobs`, `articles`, `article_analysis`, `report_history` | Không có UI sẵn — cần `psql` hoặc tool ngoài (DBeaver, pgAdmin, TablePlus) kết nối `localhost:5432` (user/pass/db xem `.env`) |
| **Redis** | `6379` | Message broker + result backend cho Celery | Hàng đợi job giữa Backend API và Celery worker | Không có UI sẵn — cần `redis-cli` hoặc RedisInsight |
| **Ollama** | `11434` | AI inference server (local, model `qwen3:8b`) | Nhận request phân loại bài viết (topics/sentiment/emotion/confidence) từ `ai/ollama_client.py` | Không có UI — chỉ REST API, test bằng `curl http://localhost:11434/api/generate` |
| **celery-worker** | *(không expose port)* | Worker thực thi job nền | Chạy task `run_report_job` (crawl → AI → sinh DOCX/JSON) | Không có UI/port riêng — theo dõi qua Flower (`:5555`) hoặc `docker compose logs celery-worker` |

> Lưu ý: `celery-worker` và `flower` dùng cùng image với `backend` nhưng chạy command khác (`celery worker` / `celery flower`), không có route HTTP nghiệp vụ riêng ngoài cổng quản trị Flower.

> `MAX_ARTICLES_PER_JOB` (trong `.env`): giới hạn số bài crawl/job — chỉ dùng khi test (AI local chạy CPU rất chậm, ~60-120s/bài). Để trống = không giới hạn (mặc định, dùng cho production).

---

## Bảng so sánh 2 cách chạy Frontend

| Khía cạnh | Vite Dev Server (Local) | Build Test (Local) | Nginx (Docker Container) |
|---|---|---|---|
| **Lệnh chạy** | `npm run dev` (từ thư mục `frontend/`) | `npm run build` + `npx serve dist` | `docker compose up -d` (toàn bộ project) |
| **Cách hoạt động** | Node.js dev server + Hot Module Replacement (HMR) | Vite build tĩnh → serve qua Node.js `serve` tool | Vite build tĩnh → Nginx serve file từ `dist/` |
| **URL truy cập** | http://localhost:5173 | http://localhost:3000 | http://localhost:3000 |
| **Ghi chú** | Tự động hot reload khi sửa code (giữ state, <1s refresh) | Build output giống production; serve tool chỉ cho test, không production | Giống build test nhưng dùng Nginx thay Node.js serve |
| **Mục đích** | Development — sửa code nhanh, debug dễ | Testing — verify production build trước commit, phát hiện lỗi minify/tree-shake | Production — serve 1000+ users, tối ưu tốc độ + resource |
| **Server HTTP** | Node.js (`vite` dev server) | Node.js (`serve` package — dev tool) | Nginx (compiled C, production-grade) |
| **Tốc độ load** | Nhanh (unminified, có source map) | Rất nhanh (minified, optimized) | Rất nhanh (minified, optimized) |
| **RAM** | ~150-200 MB (Node.js + source) | ~50-100 MB (Node.js serve + dist files) | ~30-50 MB (Nginx + dist files) |
| **Concurrent users** | ~10-20 users (dev tool) | ~50-100 users (test tool) | 1000+ users (production) |
| **API endpoint** | `http://localhost:8000` (local dev) | `http://localhost:8000` (local dev) | `http://backend:8000` (Docker network) |
| **Khi nào dùng** | ✅ Mỗi ngày dev, sửa code frontend | ✅ Trước commit, verify build ổn | ✅ Production, khi deploy thực tế |
| **Khuyến nghị** | **Default** — mỗi ngày dev đều dùng cách này | **Bắt buộc trước commit** — chạy lần này phát hiện lỗi sớm | **Final** — dùng cho production / deployment |

---

### Quy trình dev → production

```
[DEV] npm run dev (Vite)              [TEST] npm run build + npx serve dist     [PROD] docker compose up (Nginx)
         ↓                                            ↓                                    ↓
Sửa code & test logic          Verify build tĩnh + performance          Deploy final build
HMR <1s refresh                Production-like environment               Serve 1000+ users
Debug console, DevTools        Minified, tree-shake, optimize           Nginx tối ưu
         ↓                                            ↓                                    ↓
       PASS  ────────────→      PASS  ─────────────→      PASS  ──→  Commit & Push
```

---

## Deployment — Chạy lên Server Production

Có 2 trường hợp deploy:

### TH1: Server trắng tinh (không có nginx/service nào chạy)

```bash
cp .env.example .env
docker compose up -d --build
```

Frontend container nginx sẽ tự động lắng nghe port `3000`. Truy cập [http://server-ip:3000](http://server-ip:3000).

---

### TH2: Server đã có nginx sẵn → Dùng Reverse Proxy

**Lý do:** Server có dự án khác chạy, hoặc muốn nginx xử lý SSL/TLS, caching, rate-limiting tập trung.

#### **Bước 1: Kiểm tra port 3000 có đang dùng không**

```bash
sudo lsof -i :3000
# Nếu có output → port bị chiếm; nếu không → port trống

# Nếu 3000 bị chiếm, tìm port trống
sudo lsof -i :3001
sudo lsof -i :3002
sudo lsof -i :3003
# → Chọn port đầu tiên không có output (VD: 3001, 3002...)
```

#### **Bước 2: Cập nhật docker-compose.yml — Thay port (nếu cần)**

Nếu port 3000 trống, bỏ qua bước này. Nếu bị chiếm, mở `docker-compose.yml`:

```yaml
services:
  # ... các service khác (postgres, redis, ollama, backend, celery-worker, flower) ...
  
  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
      args:
        VITE_API_BASE_URL: "http://backend:8000"
    ports:
      - "3001:80"        # ← Thay 3000 → 3001 (hoặc port trống khác tìm được)
    depends_on:
      backend:
        condition: service_healthy
```

#### **Bước 3: Config nginx reverse proxy**

Tạo file `/etc/nginx/sites-available/ngs-monitor`:

```nginx
upstream ngs_monitor_frontend {
    # Phải khớp port trong docker-compose.yml
    # Nếu 3000 trống → localhost:3000
    # Nếu 3000 bị chiếm → localhost:3001 (hoặc port đã chọn)
    server localhost:3001;
}

server {
    listen 80;
    server_name ngs-monitor.example.com;   # ← Thay domain thực tế

    location / {
        proxy_pass http://ngs_monitor_frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Frontend là SPA (React Router): serve index.html nếu file không tồn tại
        error_page 404 =200 /index.html;
    }

    # Tùy chọn: cache static files (JS, CSS, images)
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        proxy_pass http://ngs_monitor_frontend;
        proxy_cache_valid 200 30d;
        expires 30d;
    }
}
```

#### **Bước 4: Enable nginx config**

```bash
# Symlink vào sites-enabled
sudo ln -s /etc/nginx/sites-available/ngs-monitor /etc/nginx/sites-enabled/

# Test nginx syntax
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

#### **Bước 5: Chạy docker compose**

```bash
# Quay lại thư mục gốc project
cd /path/to/ngs-monitor

# Chuẩn bị .env
cp .env.example .env

# Build + start
docker compose up -d --build

# Kiểm tra tất cả service healthy
docker compose ps

# Xem logs frontend
docker compose logs -f frontend
```

#### **Bước 6 (Tùy chọn): Thêm HTTPS — Dùng Certbot**

```bash
# Cài Certbot (nếu chưa có)
sudo apt install certbot python3-certbot-nginx

# Lấy certificate (tự động update nginx config)
sudo certbot --nginx -d ngs-monitor.example.com

# Bật auto-renew (mặc định đã set)
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

Certbot sẽ tự động update nginx config thành `listen 443 ssl` + redirect `80 → 443`.

---

## Bảng tổng hợp — Quy trình Deployment

| Bước | Lệnh / Hành động | Điều kiện / Ghi chú |
|---|---|---|
| **Kiểm tra port** | `sudo lsof -i :3000` | Nếu port bị chiếm → tìm port trống tiếp (`3001`, `3002`...) |
| **Cập nhật docker-compose.yml** | `ports: - "3001:80"` | Chỉ cần nếu port 3000 bị chiếm; nếu trống bỏ qua |
| **Config nginx upstream** | `server localhost:3001;` | Phải khớp port trong docker-compose.yml |
| **Enable nginx config** | `sudo ln -s sites-available/ngs-monitor sites-enabled/` | Symlink để nginx load config |
| **Test nginx syntax** | `sudo nginx -t` | Kiểm tra trước khi reload |
| **Reload nginx** | `sudo systemctl reload nginx` | Áp dụng config mới |
| **Build + start Docker** | `docker compose up -d --build` | Lần đầu chạy sẽ pull model `qwen3:8b` (~vài phút) |
| **Kiểm tra health** | `docker compose ps` | Tất cả service phải `running` (hoặc `health: healthy`) |
| **Truy cập** | `http://ngs-monitor.example.com` | Nginx proxy tới container frontend |
| **Thêm HTTPS (tùy chọn)** | `sudo certbot --nginx -d ngs-monitor.example.com` | Tự động update nginx config + auto-renew |

---

## Troubleshoot — Debug khi có vấn đề

```bash
# 1. Kiểm tra port 3001 có container chạy không
sudo lsof -i :3001

# 2. Kiểm tra container đang chạy
docker compose ps
docker compose logs -f frontend

# 3. Test kết nối từ host tới container
curl -v http://localhost:3001

# 4. Kiểm tra nginx error log
sudo tail -f /var/log/nginx/error.log

# 5. Kiểm tra nginx access log
sudo tail -f /var/log/nginx/access.log

# 6. Test nginx config
sudo nginx -t

# 7. Reload nginx nếu config lỗi
sudo systemctl reload nginx

# 8. Restart docker compose nếu container dead
docker compose restart
```

---

## Các lưu ý quan trọng

- **Backend API:** Container backend vẫn chạy port `8000` trong Docker network, frontend container gọi tới `http://backend:8000` (Docker DNS resolution). Server's nginx **không cần proxy** backend — chỉ proxy frontend.
- **Database & Redis:** Chạy trong Docker, không expose ra ngoài server (chỉ backend/celery worker dùng trong network).
- **Ollama:** Chạy trong Docker, cấp ~5.2GB RAM cho model `qwen3:8b`. CPU-only mặc định (nhanh chập tùy máy).
- **Celery Worker & Flower:** Chạy nền trong Docker. Monitor qua Flower UI (port `5555` nếu muốn expose, hiện tại chỉ internal network).
- **Storage folder:** File `.docx` + `.json` lưu ở `./storage` trên server (đã gitignored). Sau khi tạo báo cáo, user tải về từ frontend qua endpoint `/api/reports/{job_id}/download`.


