# Chia đều số bài crawl theo nguồn — Design Spec

**Ngày:** 2026-07-10
**Trạng thái:** Đã duyệt với user, sẵn sàng chuyển sang implementation plan

## Cập nhật sau verify thật (2026-07-10, revision 2) — đổi quyết định #3 "không bù" → "có bù"

Sau khi implement + verify job thật với dữ liệu thật (3 nguồn VTV/Vietnam.vn/TinGia, cùng 1
ngày), phát hiện đánh đổi "không bù thiếu hụt" ở quyết định #3 gây khó chịu hơn dự tính: TinGia
không có bài nào trong ngày đó → quota 2 của TinGia bị bỏ phí hoàn toàn, dù VTV/Vietnam.vn thừa
khả năng crawl thêm (job 2 nguồn cùng ngày, không có TinGia, VTV lấy được 3 bài thật — chứng
minh VTV có đủ bài, chỉ là quota ban đầu giới hạn nó ở 1). User yêu cầu đổi sang **có bù**.

**Quyết định #3 mới:** dùng thuật toán **water-filling** — quota của từng nguồn được tính LẠI
ngay trước khi xử lý nguồn đó (không tính 1 lần cố định trước loop), dựa trên:
`quota_nguồn_này = _distribute_evenly(ngân_sách_còn_lại, số_nguồn_chưa_xử_lý)[0]`

Trong đó `ngân_sách_còn_lại = max_articles - số_bài_đã_crawl_thật_tính_đến_lúc_này` (đã tự động
trừ đúng phần các nguồn trước đã lấy được, kể cả khi ít hơn quota ban đầu của chúng). Nhờ vậy,
nguồn nào thiếu bài sẽ tự động "nhường" ngân sách chưa dùng cho các nguồn xử lý sau, tổng job
tiến gần tới đúng `MAX_ARTICLES_PER_JOB` hơn (miễn tổng candidate thật của các nguồn còn lại đủ).
Không cần hàm mới — tái dùng `_distribute_evenly()` đã có, chỉ đổi cách gọi (gọi lại mỗi vòng
nguồn thay vì gọi 1 lần trước loop). Quyết định #1, #2 giữ nguyên không đổi.

## Bối cảnh & vấn đề

`_crawl_sources()` (`backend/workers/report_job.py`) hiện duyệt tuần tự từng nguồn trong `job.source_ids`, chỉ dừng khi **tổng số bài toàn job** chạm `MAX_ARTICLES_PER_JOB`. Hệ quả: nếu nguồn đầu tiên (theo thứ tự chọn ở FE) có đủ bài trong khoảng ngày yêu cầu, các nguồn còn lại không bao giờ được crawl. Đã ghi nhận thật nhiều lần (Slice 2 verify tingia.gov.vn, Slice 3 verify VTV, Slice 4 verify VTV) — luôn chỉ 1 nguồn "ăn hết" ngân sách.

User muốn khi test với số bài nhỏ (5–10 bài), có thể chọn nhiều nguồn và thấy dữ liệu **đa dạng nguồn thật sự** trong 1 lần chạy, thay vì luôn chỉ nhận được bài từ 1 nguồn.

## Yêu cầu đã chốt (qua brainstorming với user)

1. Thêm 1 công tắc mới trong `.env`: `EVEN_DISTRIBUTE_ACROSS_SOURCES` (boolean)
   - **Mặc định tắt** (`false`/không khai) — giữ nguyên hành vi tuần tự hiện tại, không phá job đang chạy thật
   - Khi bật (`true`): `MAX_ARTICLES_PER_JOB` được **chia đều cho các nguồn đã chọn** trong `job.source_ids`, theo đúng thứ tự user chọn ở FE
2. Số dư khi chia không hết → dồn cho các nguồn **đầu tiên** theo thứ tự đã chọn (VD 5 bài / 3 nguồn → 2/2/1, không phải 1/2/2 hay ngẫu nhiên)
3. Nguồn nào không đủ bài trong khoảng ngày để lấp đầy quota của nó → lấy được bao nhiêu hay bấy nhiêu, **không bù** từ nguồn khác (tổng thật có thể ít hơn `MAX_ARTICLES_PER_JOB` đã cấu hình — chấp nhận đánh đổi này để giữ logic đơn giản, không quay lại đúng vấn đề "1 nguồn ăn hết ngân sách bù")

## Thiết kế

### Hàm phân bổ thuần (pure function, dễ test độc lập)

```python
def _distribute_evenly(total: int, n: int) -> list[int]:
    """Chia total thành n phần gần bằng nhau, dư dồn cho các phần tử đầu."""
```

- `quota[i] = total // n + (1 if i < total % n else 0)`
- Ví dụ: `_distribute_evenly(5, 3) == [2, 2, 1]`, `_distribute_evenly(6, 3) == [2, 2, 2]`, `_distribute_evenly(2, 5) == [1, 1, 0, 0, 0]`
- Không phụ thuộc DB/Job — test thuần bằng input/output

### Tích hợp vào `_crawl_sources()`

- Đọc cờ mới: `even_distribute = os.environ.get("EVEN_DISTRIBUTE_ACROSS_SOURCES", "false").lower() == "true"`
- Nếu `even_distribute` và `max_articles is not None` và `job.source_ids` không rỗng:
  - Tính `per_source_quota = _distribute_evenly(max_articles, len(job.source_ids))` 1 lần trước khi vào loop
- Đổi `for source_id in job.source_ids:` → `for idx, source_id in enumerate(job.source_ids):` để lấy đúng index tương ứng quota
- Thêm điều kiện dừng crawl **theo từng nguồn**: đếm số `Article` đã insert cho đúng `source_id` này trong job (cả `status="error"` lẫn thành công — nhất quán với cách `crawled_count()` hiện tại đang đếm mọi trạng thái), dừng vòng lặp candidate của nguồn đó khi đạt `per_source_quota[idx]`
- Điều kiện dừng toàn job hiện có (`crawled_count() >= max_articles`) **vẫn giữ nguyên** làm lưới an toàn tổng — về lý thuyết sẽ không kích hoạt trước khi hết quota từng nguồn vì tổng quota luôn bằng đúng `max_articles`, nhưng giữ lại phòng trường hợp logic quota có sai sót
- Khi cờ tắt: `per_source_quota = None`, hành vi giữ nguyên y hệt code hiện tại (chỉ check tổng job)
- `failed_locs` (lỗi sub-sitemap) **không đổi** — vẫn insert `status="error"` ngay sau `_get_candidates()`, không qua kiểm tra quota, giữ đúng hành vi hiện có

### Không đổi

- `MAX_ARTICLES_PER_JOB` vẫn là biến duy nhất quyết định tổng số bài — không thêm biến số lượng riêng
- Cơ chế dedup URL (`seen_urls`, composite UNIQUE DB) không đổi
- Không đổi API contract (`POST /api/reports/create`) — đây là cấu hình vận hành qua `.env`, không phải tham số request

## Testing

- **Unit test `_distribute_evenly()`** (không cần DB): chia hết, chia dư (dư dồn đầu), tổng < số nguồn (có nguồn nhận 0)
- **Test tích hợp `test_report_job.py`** (theo đúng pattern hiện có — mock `get_article_urls`/`fetch_article_dispatch`, dùng `db_session` thật):
  - Bật cờ + `MAX_ARTICLES_PER_JOB=5` + 3 nguồn đều có ≥2 candidate mỗi nguồn → crawl đúng 2/2/1 theo đúng thứ tự `source_ids`
  - Bật cờ nhưng 1 nguồn chỉ có 1 candidate (thiếu hụt so với quota 2) → lấy đúng 1 bài từ nguồn đó, **không** crawl thêm bù từ nguồn khác, tổng job < `MAX_ARTICLES_PER_JOB`
  - Tắt cờ (mặc định, không set env) → hành vi giữ nguyên như test hiện có (1 nguồn có thể ăn hết ngân sách) — test regression đảm bảo không đổi hành vi cũ

## Docs cần cập nhật

- `.env.example`: thêm dòng `EVEN_DISTRIBUTE_ACROSS_SOURCES=` kèm comment giải thích
- `.claude/rules/06-crawler-strategy.md`: thêm 1 quy tắc mới mô tả cơ chế chia quota + link tới quyết định "không bù thiếu hụt"
- `CLAUDE.md`: thêm entry vào "Đã hoàn thành" sau khi implement + verify xong (không phải phần của spec này, sẽ làm ở bước cuối implementation plan)
