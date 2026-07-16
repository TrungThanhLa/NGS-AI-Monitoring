# NGS Monitor — Kiến trúc kỹ thuật đề xuất cho mô hình mở rộng

> Nguyên tắc: **giữ nguyên nền tảng kỹ thuật hiện tại** (FastAPI monolith + Celery/Redis + PostgreSQL + Ollama local + Vite/React/AntD), chỉ bổ sung những gì thực sự cần thiết để hỗ trợ continuous monitoring. Không tách microservice, không thêm hạ tầng mới trừ khi bắt buộc. **AI runtime là ngoại lệ có kế hoạch mở rộng:** Ollama local là mặc định MVP, nhưng thiết kế phải để ngỏ khả năng chuyển sang server AI riêng hoặc API LLM trả phí khi dự án scale — xem mục 5.

---

## 1. Kiến trúc tổng thể — không đổi mô hình gốc

Giữ nguyên **modular monolith**: 1 backend FastAPI, Celery worker xử lý job nền, PostgreSQL là database duy nhất, Redis làm broker cho Celery. Bổ sung:

```
FastAPI (API + Scheduler trigger)
   │
   ├── Celery Worker (crawl + AI — như hiện tại)
   ├── Celery Beat (MỚI — lên lịch crawl định kỳ theo campaign_sources.crawl_frequency)
   └── WebSocket endpoint (MỚI — đẩy cập nhật real-time cho Monitoring Feed, nếu triển khai Phase 8 của roadmap)
```

**Không thêm:** service riêng cho AI/Crawler ở giai đoạn MVP, message broker khác ngoài Redis, search engine riêng (PostgreSQL full-text/GIN index đủ dùng ở quy mô hiện tại).

---

## 2. Tech stack — phần bổ sung

| Layer | Bổ sung mới | Lý do |
|---|---|---|
| Backend | `Celery Beat` (đã có sẵn trong hệ sinh thái Celery, không cần cài thêm dependency mới) | Lên lịch crawl định kỳ, thay cho việc trigger crawl thủ công qua `POST /api/reports/create` |
| Backend | JWT (`python-jose`) + `passlib[bcrypt]` | Auth — hiện chưa có |
| Backend | WebSocket (FastAPI có sẵn hỗ trợ, không cần lib ngoài) | Đẩy cập nhật real-time cho Monitoring Feed (chỉ cần nếu làm Phase 8 của roadmap) |
| Database | Không đổi — vẫn PostgreSQL, dùng thêm GIN index cho full-text search nếu cần tìm kiếm nội dung | Tận dụng hạ tầng đã có, tránh thêm Qdrant/OpenSearch không cần thiết ở quy mô dữ liệu hiện tại (hàng chục nghìn bài, không phải hàng triệu) |
| AI | Mặc định MVP: Ollama local (`qwen3:8b`), đặt sau 1 lớp `AIProvider` interface ngay từ đầu | Cho phép scale sau này (server AI riêng hoặc API trả phí) mà không phải viết lại pipeline — xem mục 5 |

**Không đưa vào phạm vi ở giai đoạn MVP hiện tại:** vector database riêng, kiến trúc microservices tách rời từng module, connector cho social media. Đa nhà cung cấp LLM (Claude/ChatGPT/Gemini) **không bị loại khỏi phạm vi vĩnh viễn** — đây là hướng mở rộng hợp lệ khi dự án scale, xem mục 5.

---

## 3. Data ownership & giao tiếp nội bộ

- Giữ nguyên nguyên tắc hiện có: `backend/workers/report_job.py` (hoặc worker tương đương cho continuous mode) là nơi duy nhất ghi vào `articles`/`article_analysis` — không có service khác cần gọi API nội bộ để lưu hộ dữ liệu.
- Module mới (Campaign/Alert/Case) nằm trong cùng 1 codebase FastAPI, dùng chung 1 kết nối DB, 1 Alembic migration history — không tách schema riêng.

---

## 4. Scheduler — thiết kế đề xuất

**Đã chốt (2026-07-16):** vòng lặp duyệt theo **Nguồn** (không duyệt theo từng Campaign) — tránh lỗi 1 Nguồn bị enqueue crawl trùng nhiều lần trong cùng 1 lượt kiểm tra khi có ≥2 Campaign `ACTIVE` cùng tham chiếu tới nó. Dữ liệu crawl được cũng chỉ gắn theo `source_id`, **không gắn `campaign_id`** ngay từ lúc crawl:

```
Celery Beat (chạy mỗi 1 phút, kiểm tra):
  for each Source đang được ≥1 Campaign ACTIVE tham chiếu (SELECT DISTINCT qua campaign_sources):
    if now - source.last_crawled_at >= source.crawl_frequency:
      enqueue crawl_task(source_id)   # KHÔNG kèm campaign_id

crawl_task(source_id) — TÁCH 2 GIAI ĐOẠN (đã chốt 2026-07-16, giải quyết rủi ro mất dữ liệu khi
  1 lượt crawl bị đứt giữa chừng — xem 06_OPEN_DECISIONS.md mục 4):

  Giai đoạn 1 — khám phá URL (rẻ, nhanh, ít khi lỗi):
    đọc sitemap/listing của source → lấy danh sách URL ứng viên
    → INSERT ... ON CONFLICT DO NOTHING vào bảng crawl_queue theo (source_id, url_hash)
      (status='pending') — không tải nội dung ở bước này, chỉ ghi nhận "đã biết URL này tồn tại"

  Giai đoạn 2 — tải nội dung (tốn thời gian, dễ bị đứt giữa chừng):
    lấy TẤT CẢ URL đang status='pending' trong crawl_queue của source này
    (bao gồm cả URL bị lỡ từ CÁC CHU KỲ TRƯỚC, không chỉ URL mới phát hiện ở Giai đoạn 1 lần này)
    → fetch từng URL, cập nhật status='fetched'/'failed' NGAY theo TỪNG bài (không đợi xong cả batch)
    → fetch thành công → lưu vào articles (gắn source_id, không đổi cơ chế hiện có)
    → nếu quy trình bị đứt giữa chừng (crash/timeout/mất mạng) → URL còn 'pending' TỰ ĐỘNG được
      thử lại ở chu kỳ kế tiếp — không phụ thuộc việc sitemap/listing có còn hiển thị URL đó không
    → URL fail quá `CRAWLER_MAX_RETRIES` lần liên tiếp → status='error' hẳn, ngừng thử lại
      (giống cơ chế `articles.status='error'` hiện có)

  → matching từ khóa (đã chốt, xem 06_OPEN_DECISIONS.md mục 2): với MỖI Campaign ACTIVE đang
    theo dõi source_id → so khớp bài mới lưu được với keyword của Campaign đó → ghi vào
    `campaign_articles` (xem 02_DOMAIN_MODEL_AND_DATABASE.md)
  → nếu công tắc AI_AUTO_TRIGGER = true (xem 05_CRAWLER_AI_API.md mục 2): enqueue AI analysis
    cho các bài mới; nếu false: bài giữ trạng thái pending_analysis, chờ người dùng bấm nút
  → AI xong (dù tự động hay thủ công) → với MỖI Campaign có bài này trong `campaign_articles`
    → kiểm tra alert_threshold RIÊNG cho từng Campaign
    → Campaign nào vượt ngưỡng → sinh 1 dòng Alert riêng (gắn đúng campaign_id của Campaign đó)
```

**Ví dụ dễ hình dung Giai đoạn 1/2:** giống ghi sẵn danh sách "cần mua: sữa, trứng, bánh mì" lên tờ giấy dán tủ lạnh (Giai đoạn 1 — ghi ngay, không sợ quên), rồi mới đi chợ mua từng món (Giai đoạn 2 — có thể bị gián đoạn giữa chừng). Nếu đi chợ dở dang phải về, tờ giấy vẫn còn "trứng, bánh mì" chưa gạch — hôm sau nhìn tờ giấy biết ngay cần mua tiếp gì, không cần nhớ lại từ đầu hay đi dò lại từng cửa hàng.

**Lý do không gắn `campaign_id` lúc crawl:** nếu nhiều Campaign cùng theo dõi 1 Nguồn (VD Campaign A và B cùng crawl VTV), dữ liệu chỉ nên lưu 1 bản gắn theo Nguồn — việc "Campaign nào cần biết bài này" xác định qua matching từ khóa (`campaign_articles`) ngay sau khi crawl, không cần biết ngay từ lúc crawl thô.

- Tần suất kiểm tra của Beat: 1 phút là đủ, không cần dày hơn vì `crawl_frequency` đề xuất tối thiểu 30 phút cho báo điện tử (khác hẳn social media cần 5-15 phút).

---

## 5. AI Runtime — lộ trình mở rộng (local → server riêng / cloud LLM trả phí)

**Đã chốt (2026-07-16, xem `06_OPEN_DECISIONS.md` mục 8): việc chuyển đổi là THỦ CÔNG hoàn toàn** — không xây cơ chế tự động phát hiện tải cao rồi tự chuyển provider. Người vận hành tự quan sát thực tế rồi tự đổi biến `AI_PROVIDER` trong `.env` (hoặc thêm 1 provider mới nếu cần) khi thấy phù hợp.

**Trạng thái MVP hiện tại:** Ollama local (`qwen3:8b`), gọi thẳng REST API `http://localhost:11434`, không qua abstraction layer nào (`backend/ai/ollama_client.py` gọi trực tiếp).

**Khi dự án scale, có 2 hướng mở rộng hợp lệ (không loại trừ nhau, có thể chọn 1 hoặc kết hợp theo loại tác vụ):**

1. **Server AI riêng do dự án tự dựng** — tách Ollama (hoặc model lớn hơn) ra 1 máy chủ GPU riêng, backend gọi sang qua network nội bộ/VPN thay vì `localhost`. Vẫn giữ được nguyên tắc "dữ liệu không rời khỏi hạ tầng do đơn vị tự quản lý" — chỉ đổi vị trí chạy model, không đổi nhà cung cấp.
2. **API LLM trả phí (Claude/ChatGPT/Gemini)** — gọi API bên ngoài qua internet, trả phí theo lượng dùng. Dữ liệu (tiêu đề/nội dung bài viết) sẽ được gửi ra ngoài hạ tầng nội bộ tới bên thứ ba.

**Thiết kế kỹ thuật cần chuẩn bị ngay từ giai đoạn MVP để 2 hướng trên khả thi mà không phải viết lại:**

```python
# backend/ai/providers/base.py — lớp trừu tượng, thêm ngay cả khi hiện tại chỉ có 1 implementation
class AIProvider(ABC):
    @abstractmethod
    async def analyze(self, title: str, content: str) -> dict: ...

# backend/ai/providers/ollama_provider.py   — implementation hiện tại (di chuyển nguyên code cũ vào đây)
# backend/ai/providers/remote_ollama_provider.py  — hướng (1), chỉ đổi base_url
# backend/ai/providers/cloud_llm_provider.py      — hướng (2), thêm khi thực sự cần
```

- Chọn provider qua biến môi trường (`AI_PROVIDER=ollama_local|ollama_remote|cloud_llm`), không hardcode.
- Giữ nguyên format output (JSON: `topics/keywords/sentiment/emotion/confidence/summary`) bất kể provider nào — để không phải sửa `article_analysis` hay `docx_generator.py`.
- **Không cần code cả 3 provider ngay bây giờ** — chỉ cần tách `AIProvider` interface ra khỏi `ollama_client.py` hiện có (refactor tối thiểu), để khi thật sự cần chuyển thì chỉ thêm 1 class mới, không sửa phần còn lại của hệ thống.
- **Ví dụ cụ thể khi chuyển sang ChatGPT (cloud API):** (1) thêm 1 file mới `backend/ai/providers/openai_provider.py` implement `AIProvider`, gọi OpenAI Chat Completions API thay vì Ollama REST API, nhưng vẫn phải trả về đúng format JSON hiện có (`topics/keywords/sentiment/emotion/confidence/summary`); (2) thêm 1 nhánh nhỏ (vài dòng) ở nơi khởi tạo provider (factory theo `AI_PROVIDER`) để ánh xạ sang class mới này; (3) thêm biến `.env` (`AI_PROVIDER=cloud_llm`, `OPENAI_API_KEY=...`). **Không đổi:** nội dung prompt/danh mục 8 chủ đề/6 cảm xúc (`prompts/v1.py`), schema `article_analysis`, `aggregator.py`, `docx_generator.py`/PDF/Excel, crawler, Alert/Case — toàn bộ phần còn lại của hệ thống không biết và không cần biết provider nào đang chạy phía sau.

**Điều kiện nên cân nhắc chuyển đổi (không phải quy tắc cứng, xem thêm rủi ro ở `06_OPEN_DECISIONS.md`):**
- Server local không đủ tài nguyên xử lý khi số Campaign `ACTIVE` tăng (CPU-only Ollama đã ghi nhận timeout thật ở quy mô hiện tại).
- Cần chất lượng phân tích cao hơn `qwen3:8b` có thể đáp ứng cho một số tác vụ khó.
- Có ngân sách vận hành cho GPU riêng hoặc API trả phí.

---

## 6. Bảo mật — bổ sung cho Auth mới

- JWT access token 60 phút + refresh token 7 ngày.
- Middleware `require_permission(resource, action)` áp dụng cho mọi router hiện có và mới.
- Rate limiting cho endpoint `/auth/login` — **cần thêm mới**, dự án hiện tại chưa có bất kỳ rate limiting nào.
- Không hardcode secret — `SECRET_KEY` sinh qua `openssl rand -hex 32`, đọc từ `.env`, không có giá trị fallback mặc định trong code.
- Nếu sau này dùng cloud LLM (mục 5, hướng 2): không gửi kèm thông tin định danh người dùng/nội bộ trong prompt, chỉ gửi nội dung bài viết công khai đã crawl được.

---

## 7. Hiệu năng — mục tiêu đề xuất

Giữ mục tiêu khiêm tốn, phù hợp quy mô thật của dự án:

| Chỉ tiêu | Giá trị đề xuất |
|---|---|
| Số người dùng đồng thời | < 10 (phù hợp quy mô 1 cơ quan/đơn vị) |
| Số nội dung lưu trữ mục tiêu (Phase đầu) | 10.000–50.000 bài |
| Thời gian phản hồi API tra cứu/danh sách | < 3 giây |
| Tần suất Celery Beat kiểm tra lịch crawl | 1 phút |
| Cập nhật Monitoring Feed (nếu làm Phase 8) | < 5 giây sau khi crawl xong |

---

## 8. Điều gì KHÔNG thay đổi so với kiến trúc hiện tại

- `backend/crawler/*` (sitemap, listing, article parser, Crawl4AI, Playwright dispatch) — giữ nguyên toàn bộ, chỉ đổi **nơi gọi** (từ trigger thủ công sang trigger bởi Celery Beat).
- `backend/ai/*` — giữ nguyên logic prompt/parse JSON hiện có; chỉ tách thành `AIProvider` interface (mục 5), không đổi hành vi khi vẫn dùng Ollama local.
- `backend/report/*` (aggregator, docx_generator) — giữ nguyên, chỉ mở rộng thêm filter theo `campaign_id` nếu cần.
- Docker Compose, cấu trúc thư mục, GPU tùy chọn cho Ollama — không đổi.
