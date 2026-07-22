# Campaign — giới hạn phạm vi crawl ONE_SHOT, tự dừng CONTINUOUS, hiển thị tiến độ crawl

**Ngày:** 2026-07-22
**Bối cảnh:** Phát hiện qua smoke test Docker thật đầu tiên của Phase 7 (chưa từng kiểm tra kịch bản này trước đó). Không thuộc scope Phase 7 gốc — đây là 3 gap thật của cơ chế Scheduler/Crawl (Phase 3), lộ ra khi dùng ONE_SHOT thật với 1 Nguồn đã có backlog lớn từ trước.

## Vấn đề

1. **ONE_SHOT dính backlog toàn cục của Nguồn.** `crawl_task(source_id)` (continuous_crawl.py) được tái dùng nguyên vẹn cho cả CONTINUOUS lẫn ONE_SHOT. Bước Discover luôn quét cửa sổ 30 ngày cố định (`_DISCOVER_LOOKBACK_DAYS`), không quan tâm `date_from`/`date_to` của Campaign. Bước Fetch (`fetch_pending_urls`) luôn tải **toàn bộ** URL đang `pending` của Nguồn — kể cả URL tồn đọng từ Campaign/lượt crawl khác không liên quan. Kết quả thật quan sát được: 1 Campaign ONE_SHOT với `date_range` 2 ngày kéo theo crawl ~4300 URL backlog của VTV News, mất hàng giờ thay vì vài phút như tên gọi "Tạo báo cáo nhanh" ngụ ý.
2. **CONTINUOUS không tự dừng ở `end_date`.** Cột `campaigns.end_date` tồn tại và cho phép đặt cho cả 2 mode, nhưng không có bất kỳ đoạn code nào đọc lại nó để so sánh với thời gian hiện tại — Campaign CONTINUOUS đặt `end_date` xong vẫn `ACTIVE`/crawl mãi mãi cho tới khi có người bấm Tạm dừng/Lưu trữ thủ công. Đây là thiếu đặc tả (schema có sẵn, chưa từng có rule định nghĩa hành vi), không phải lỗi lệch spec.
3. **Không có cách nào biết tiến độ crawl thật của 1 Campaign.** FE chỉ hiện `status=ACTIVE` chung chung — không biết đang crawl tới đâu, bao nhiêu bài, bao nhiêu %.

## Mục tiêu

- ONE_SHOT chỉ crawl đúng phạm vi `date_from`–`date_to` đã khai, không đụng backlog không liên quan của Nguồn dùng chung.
- CONTINUOUS tự chuyển `COMPLETED` khi tới `end_date`, không cần thao tác thủ công.
- Người dùng thấy được tiến độ crawl thật của từng Campaign đang xem, ngay trên trang chi tiết.

## Kiến trúc

### 1. ONE_SHOT — đường crawl riêng, tách khỏi CONTINUOUS

**Validate ở `POST`/`PUT /api/campaigns`:** khi `mode=ONE_SHOT` → bắt buộc có `end_date`, và `end_date` (dạng date, so theo giờ VN/server) `<= hôm nay`. Trả `400` nếu vi phạm. Validate lại (defense-in-depth) ở `activate_campaign`, cạnh check BR-CAMP-03 hiện có — phòng trường hợp Campaign cũ trước khi có rule này bị kích hoạt.

**Task Celery mới** `campaign_tasks.crawl_campaign_source_once(campaign_id, source_id, date_from, date_to)` — thay thế việc dùng chung `continuous_crawl.crawl_task` trong `chord` của `activate_campaign` khi `mode=ONE_SHOT` (CONTINUOUS giữ nguyên `crawl_task` như cũ, không đổi):

1. Set `campaign_crawl_progress` (bảng mới, xem dưới) status=`discovering`, commit.
2. Discover: gọi lại `_get_candidates(source, date_from, date_to)` (continuous_crawl.py, không đổi hàm này) — dùng đúng `date_from`/`date_to` của Campaign, không qua `_DISCOVER_LOOKBACK_DAYS`.
3. Set `total_urls = len(candidates)`, status=`fetching`, commit.
4. Với mỗi URL ứng viên:
   - Tính `url_hash`, tra `Article` theo `(source_id, url_hash)`.
   - **Đã tồn tại** → tái sử dụng, gọi `match_campaigns_for_article(db, article)` (không đổi hàm, chỉ thêm guard idempotent — xem dưới).
   - **Chưa tồn tại** → fetch mới qua `fetch_article_dispatch` (đúng delay/retry hiện có, không đổi), insert `Article` nếu thành công, gọi `match_campaigns_for_article`. Lỗi/hết retry → log, bỏ qua URL đó (không chặn URL còn lại).
   - Sau mỗi URL (dù thành công hay bỏ qua): `done_urls += 1`, commit ngay — để FE poll thấy tăng dần theo thời gian thực.
5. Set status=`done`, commit.
6. Toàn bộ bọc `try/except Exception` (log, không raise) giống `crawl_task` hiện tại — không được phá `chord` (nếu raise, `mark_crawl_done` không chạy, Campaign kẹt `ACTIVE` mãi — đúng bug đã tìm và sửa ở Phase 7 final review, giữ nguyên nguyên tắc đó).
7. **Không tự phục hồi nếu crash giữa chừng** (khác CONTINUOUS) — muốn crawl lại thì kích hoạt lại; rẻ vì bước tái sử dụng khiến URL đã fetch trước đó không bị fetch lại.

**Fix bắt buộc đi kèm:** `match_campaigns_for_article` (continuous_crawl.py) hiện `db.add(CampaignArticle(...))` không kiểm tra tồn tại trước khi insert. Với luồng cũ (chỉ gọi 1 lần/bài mới fetch), điều này chưa từng là vấn đề. Với luồng "tái sử dụng" mới, hàm này có thể được gọi lại cho 1 bài đã match Campaign này từ trước (VD Campaign bị kích hoạt lại sau khi Pause) → vỡ `IntegrityError` do PK `(campaign_id, article_id)` trùng. Thêm guard: kiểm tra `CampaignArticle` đã tồn tại cho `(campaign_id, article_id)` trước khi insert, bỏ qua nếu có rồi.

### 2. CONTINUOUS — tự dừng ở `end_date`

Thêm 1 bước đầu trong `check_due_sources()` (scheduler.py, task Beat có sẵn chạy mỗi 60s — không thêm entry Beat mới):

```python
db.query(Campaign).filter(
    Campaign.mode == "CONTINUOUS",
    Campaign.status == "ACTIVE",
    Campaign.end_date.isnot(None),
    Campaign.end_date <= datetime.now(timezone.utc),
).update({"status": "COMPLETED"})
db.commit()
```

`list_due_sources()` không cần sửa — đã lọc `Campaign.status == "ACTIVE"`, tự động ngừng chọn Nguồn của Campaign này ở chu kỳ Beat kế tiếp.

### 3. Progress UI

**Schema mới — `campaign_crawl_progress`** (chỉ dùng cho ONE_SHOT; tạo 1 dòng/Source ngay khi `activate_campaign` dispatch `chord`, trước khi task chạy):

```sql
CREATE TABLE campaign_crawl_progress (
    campaign_id  UUID REFERENCES campaigns(campaign_id) ON DELETE RESTRICT,
    source_id    UUID REFERENCES sources(source_id) ON DELETE RESTRICT,
    total_urls   INTEGER,               -- NULL cho tới khi Discover xong
    done_urls    INTEGER DEFAULT 0,
    status       VARCHAR(20) DEFAULT 'pending',  -- pending|discovering|fetching|done|error
    updated_at   TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (campaign_id, source_id)
);
```

**Endpoint mới** `GET /api/campaigns/{id}/crawl-progress` (permission `campaign.view`, đủ vì chỉ đọc):
- `mode=ONE_SHOT`: đọc `campaign_crawl_progress`, trả `{sources: [{source_id, source_name, total_urls, done_urls, status}], overall_percent}` (`overall_percent = sum(done_urls)/sum(total_urls)`, `0` nếu `total_urls` toàn `NULL`/chưa Discover xong).
- `mode=CONTINUOUS`: tính trực tiếp, không cần bảng mới — với mỗi Source Campaign theo dõi: `sources.last_crawled_at`, `sources.status`, đếm `crawl_queue` có `source_id` tương ứng và `status='pending'`, đếm `campaign_articles` có `campaign_id` tương ứng và `matched_at >= now() - interval '24 hours'`.

**FE (`CampaignDetail.tsx`):** thêm Card "Tiến độ crawl", poll `GET .../crawl-progress` mỗi 3 giây — chỉ khi `campaign.status === 'ACTIVE'` (dừng khi `COMPLETED`/`PAUSED`/`ARCHIVED`, giống pattern polling report có sẵn). `mode=ONE_SHOT` → `Progress` (AntD) theo từng Source + 1 thanh tổng. `mode=CONTINUOUS` → `Table` liệt kê từng Source với 4 cột: Nguồn, Lần crawl gần nhất, Bài mới khớp (24h), Hàng đợi còn lại.

## Error handling

| Tình huống | Xử lý |
|---|---|
| `crawl_campaign_source_once` lỗi bất kỳ bước nào | Bắt ở top-level, log, set `campaign_crawl_progress.status='error'` cho dòng đó, không raise (giữ chord) |
| 1 URL cụ thể fetch lỗi hết retry | Bỏ qua URL đó, vẫn `done_urls += 1` (tính là "đã xử lý", không chặn tiến độ hiển thị đứng yên) |
| `match_campaigns_for_article` gọi lại cho bài đã match trước đó | Guard tồn tại, bỏ qua — không insert trùng |
| Campaign ONE_SHOT bị kích hoạt lại sau khi Pause giữa chừng | `campaign_crawl_progress` ghi đè theo `(campaign_id, source_id)` — Discover chạy lại, `total_urls` tính lại đúng cho lượt mới; URL đã fetch trước đó được tái sử dụng nên không tốn lại thời gian |

## Testing

- Unit test `crawl_campaign_source_once`: Discover đúng phạm vi ngày (mock `_get_candidates`), tái sử dụng Article có sẵn không gọi lại `fetch_article_dispatch`, tiến độ tăng đúng sau mỗi URL, guard `match_campaigns_for_article` không lỗi khi gọi 2 lần.
- Unit test validate `end_date` cho ONE_SHOT ở cả `create`/`update`/`activate`.
- Unit test `check_due_sources` tự chuyển CONTINUOUS quá hạn `end_date` sang `COMPLETED`, không đụng Campaign còn hạn/PAUSED/ONE_SHOT.
- Unit test endpoint `crawl-progress` cho cả 2 nhánh mode.
- Smoke test Docker thật: kích hoạt lại 1 Campaign ONE_SHOT nhỏ (1 nguồn, date_range 1-2 ngày) — xác nhận thời gian hoàn thành thực tế ngắn hẳn so với trước (không còn kéo theo backlog ~4300 URL), progress UI cập nhật đúng theo thời gian thực.
