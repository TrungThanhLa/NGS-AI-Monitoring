# Design: Bỏ dedup toàn cục theo `url_hash` — mỗi job crawl/phân tích độc lập

## Bối cảnh

Trong lúc đọc kết quả verify Slice 3, phát hiện qua thảo luận với user 2 vấn đề liên quan tới cơ chế dedup hiện tại (`articles.url_hash` UNIQUE toàn cục, không theo `job_id`):

1. **Job mồ côi khi fail/cancel giữa chừng:** bài đã crawl từ job cũ (fail) không bao giờ gắn được vào job mới cùng khoảng ngày, vì bị skip ở bước crawl (URL đã tồn tại) — report job mới thiếu vĩnh viễn những bài đó.
2. **Job mới trùng khoảng ngày với job cũ ĐÃ THÀNH CÔNG cũng bị ảnh hưởng y hệt** — không cần job cũ fail, chỉ cần trùng URL là bị skip. Job mới vẫn báo `status="completed"` nhưng report **rỗng hoàn toàn**, không có tín hiệu lỗi nào.
3. **Nhu cầu thật chưa từng được đáp ứng:** user muốn có khả năng crawl + phân tích lại 1 bài viết cũ nếu nội dung trang đã thay đổi (VD bài được đính chính/cập nhật sau khi đã crawl) — cơ chế dedup theo URL hiện tại (không xét nội dung) chặn hoàn toàn khả năng này.

Đã cân nhắc nhiều phương án (retry đúng `job_id` cũ, minh bạch số liệu `skipped_duplicate`, content-hash so sánh nội dung...) nhưng **user quyết định chọn hướng triệt để nhất**: bỏ hẳn dedup toàn cục, mỗi job luôn crawl + phân tích lại từ đầu, chấp nhận đánh đổi chi phí AI (CPU-only, ~90s/bài) để đổi lấy tính đúng đắn/đơn giản lâu dài cho production.

## Quyết định đã chốt qua trao đổi

- **Bỏ hoàn toàn check DB toàn cục** (`db.query(Article).filter_by(url_hash=url_hash).first() is not None`) trong `_crawl_sources()` — mỗi job không còn quan tâm URL đã từng được job khác crawl hay chưa.
- **Vẫn giữ 1 lớp chống trùng trong phạm vi 1 job** — dùng `set()` Python sống trong 1 lần gọi `_crawl_sources()`, không đụng DB. Lý do: một số nguồn (VTV/VOV/VietnamPlus/CAND/vietnam.vn) không có lớp bảo vệ riêng nào khác chống trùng URL trong cùng 1 lần crawl (khác TinGia đã có `seen` set riêng trong `_fetch_declared_sitemap_pages()`) — nếu bỏ hẳn, 1 job có thể vô tình insert 2 dòng `Article` giống hệt nhau nếu sitemap/listing trả về trùng URL, tốn AI phân tích 2 lần cho đúng 1 bài.
- **Bỏ UNIQUE constraint ở DB** (`articles_url_hash_key`) — bắt buộc phải bỏ, nếu không DB sẽ tự chặn insert (IntegrityError) dù code application đã bỏ check. Vẫn giữ cột `url_hash` (không xóa) + thêm index thường (không unique) để tra cứu nhanh.
- **Đơn giản hóa hash cho `failed_locs`** — hiện dùng `compute_url_hash(f"{job.job_id}:{loc}")` (mẹo né UNIQUE constraint cũ). Vì constraint không còn, đổi về `compute_url_hash(loc)` như mọi nơi khác, xóa comment cũ đã lỗi thời.
- **Không làm content-hash so sánh nội dung** — bị thay thế hoàn toàn bởi quyết định này (mỗi job luôn crawl+phân tích lại, tự động bắt được nội dung đổi mà không cần cơ chế so sánh riêng).
- **Không cần cơ chế "retry đúng `job_id` cũ"** — vấn đề "mồ côi" (Trường hợp 1) tự động biến mất, vì user giờ chỉ cần tạo job mới là crawl/phân tích lại được toàn bộ, không còn bị chặn bởi dữ liệu job cũ.
- **Đánh đổi chấp nhận:** mỗi lần job trùng khoảng ngày sẽ tốn AI chạy lại toàn bộ (kể cả bài không đổi nội dung) + bảng `articles` sẽ phình to hơn theo thời gian (nhiều dòng trùng URL, khác `job_id`) — user đã xác nhận chấp nhận, ưu tiên đúng đắn dữ liệu hơn tiết kiệm tài nguyên ở giai đoạn này.

## Phần 1 — Migration: bỏ UNIQUE constraint

**Schema — migration mới (revision tiếp theo sau `0008`):**
```python
def upgrade():
    op.drop_constraint("articles_url_hash_key", "articles", type_="unique")
    op.create_index("ix_articles_url_hash", "articles", ["url_hash"])

def downgrade():
    op.drop_index("ix_articles_url_hash", "articles")
    op.create_unique_constraint("articles_url_hash_key", "articles", ["url_hash"])
```
Tên constraint `articles_url_hash_key` đã xác nhận thật trong DB dev qua `\d articles`.

**Model — `backend/models/articles.py`:**
- `url_hash = Column(String(64), nullable=False, unique=True)` → bỏ `unique=True`, thêm `index=True`

## Phần 2 — `_crawl_sources()`: bỏ check toàn cục, thêm check nội bộ job

**`backend/workers/report_job.py`:**
- Khai báo `seen_urls: set[str] = set()` ở đầu `_crawl_sources()`, dùng chung cho toàn bộ vòng lặp `source_ids`
- Tìm:
  ```python
  url_hash = compute_url_hash(candidate["url"])
  if db.query(Article).filter_by(url_hash=url_hash).first() is not None:
      continue
  ```
  Thay bằng:
  ```python
  if candidate["url"] in seen_urls:
      continue
  seen_urls.add(candidate["url"])
  url_hash = compute_url_hash(candidate["url"])
  ```
- `failed_locs` insert: đổi `url_hash=compute_url_hash(f"{job.job_id}:{loc}")` → `url_hash=compute_url_hash(loc)`, xóa comment cũ giải thích mẹo né UNIQUE constraint (không còn đúng)

## Phần 3 — Cập nhật tài liệu (đã rà soát toàn bộ, liệt kê đủ chỗ cần sửa)

**`.claude/rules/03-database-schema.md`** (dòng 54): sửa comment `url_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA256(url) — dùng để dedup` → bỏ `UNIQUE`, sửa comment phản ánh đúng: dùng để tra cứu, KHÔNG còn dùng để chặn trùng giữa các job.

**`.claude/rules/04-business-flow.md`** (dòng 21): sửa `Dedup SHA256(url) → insert bảng articles` → mô tả lại đúng: dedup chỉ trong phạm vi 1 job, không còn chặn giữa các job.

**`.claude/rules/06-crawler-strategy.md`** (dòng 33 + phần "Quy tắc"): sửa `Dedup bằng SHA256(url) trước khi insert vào bảng articles (cột url_hash có UNIQUE constraint)` → mô tả đúng cơ chế mới (dedup nội bộ 1 job qua `set()`, không còn UNIQUE constraint).

**`.claude/rules/10-error-handling.md`**:
- Dòng 11 (sub-sitemap lỗi): bỏ đoạn `"để tránh đụng UNIQUE constraint khi job khác sau này gặp lại đúng sub-sitemap lỗi"` (không còn đúng)
- Dòng 13 ("Dữ liệu trùng lặp"): sửa lại mô tả — dedup giờ chỉ trong phạm vi 1 job, không còn "bỏ qua nếu đã tồn tại" ở cấp toàn hệ thống
- Dòng 20 ("Job fail/cancel giữa lúc phân tích AI..."): **xóa toàn bộ dòng này** — vấn đề mô tả (job mồ côi, cần cơ chế retry `job_id`) không còn tồn tại sau khi bỏ dedup toàn cục. Thay bằng 1 dòng mới ngắn gọn ghi nhận đã giải quyết bằng cách khác (xem quyết định quan trọng).

**`CLAUDE.md`**:
- Dòng 139 (quyết định "Slice 3 Task 4: không chia chunk"): thêm ghi chú — lý do gốc trích dẫn ("report thiếu bài vì url_hash unique toàn cục") đã hết hiệu lực sau thay đổi kiến trúc này, nhưng quyết định "không chia chunk" vẫn giữ nguyên vì lý do độc lập khác (chunk không giải quyết vấn đề durability triệt để, xem lại nếu cần)
- Dòng 143 (mục "Vấn đề cần làm rõ" về job mồ côi): **xóa bullet này**, thay bằng 1 dòng mới trong "Đã hoàn thành"/"Quyết định quan trọng" ghi nhận đã giải quyết bằng cách bỏ dedup toàn cục (ngày thật, lý do, đánh đổi đã chấp nhận)
- Dòng 167 (Slice 1 checklist): giữ nguyên (lịch sử, không sửa — đúng lúc đó dedup toàn cục là hành vi đúng)
- Dòng 178 (Slice 2 Verify): giữ nguyên (lịch sử, không sửa)

## Phần 4 — Test

**Rà soát toàn bộ test suite hiện có (đã xác nhận không có test nào cần XÓA):**
- Grep toàn bộ `backend/tests/` xác nhận **không có test nào hiện tại assert hành vi "job mới skip URL đã tồn tại từ job khác"** — nghĩa là không có test cũ bị phá bởi thay đổi này, chỉ cần THÊM test mới cho hành vi mới.
- Các test khác có nhắc `url_hash` (`test_article.py`, `test_crawl4ai_client.py`, `test_export_analysis_csv.py`, `test_reports_router.py`) chỉ dùng để: (a) assert `compute_url_hash()` tính đúng SHA256 (không đổi, hàm này không bị sửa), hoặc (b) tạo giá trị ngẫu nhiên `f"hash-{uuid.uuid4()}"` làm fixture (không phụ thuộc UNIQUE constraint, vẫn chạy đúng dù bỏ constraint) — **không cần sửa**.

**Test mới trong `backend/tests/test_report_job.py`:**
1. `test_crawl_sources_recrawls_url_already_belonging_to_another_job` — tạo job A với 1 `Article` đã tồn tại (khác `job_id`), chạy `_crawl_sources` cho job B với candidate trùng URL đó → assert job B **insert được** 1 `Article` mới mang `job_id=B` (khác hẳn hành vi cũ là bị skip)
2. `test_crawl_sources_dedups_within_same_job_when_candidates_repeat_url` — candidate list có URL lặp lại 2 lần (mô phỏng sitemap/listing trả trùng) → assert chỉ insert **đúng 1** `Article` cho job đó

## Verify cuối (dữ liệu thật)

1. Chạy migration thật (`alembic upgrade head`), xác nhận `\d articles` không còn `articles_url_hash_key` UNIQUE, có `ix_articles_url_hash` index thường
2. Toàn bộ test suite pass (bao gồm 2 test mới)
3. Tạo job thật với 1 nguồn + khoảng ngày đã từng crawl thành công trước đó (VD VTV, cùng ngày đã verify ở Slice 3) → xác nhận job mới **crawl lại được** đúng những bài đó (không bị skip), AI phân tích lại từ đầu, report có đầy đủ dữ liệu (không rỗng)
