# CONTINUOUS — Discover theo hợp (union) khoảng ngày các Campaign, thay cửa sổ 30 ngày cố định

**Ngày:** 2026-07-23
**Bối cảnh:** Phát hiện qua trao đổi thực tế khi user test CONTINUOUS sau khi Phase "campaign-crawl-scope-progress" hoàn thành — `start_date` của Campaign CONTINUOUS hiện **hoàn toàn không được tôn trọng**: Discover luôn dùng cửa sổ trượt 30 ngày cố định tính từ hôm nay (`_DISCOVER_LOOKBACK_DAYS`, có từ Phase 3), bất kể Campaign nào yêu cầu theo dõi từ bao giờ. Bài đăng trước cửa sổ 30 ngày, dù nằm trong `start_date` của Campaign, **vĩnh viễn không bao giờ được match** (do `match_campaigns_for_article` chỉ chạy trên bài MỚI fetch, không hồi tố — giới hạn đã ghi nhận từ trước trong CLAUDE.md).

## Vấn đề

- `start_date` của Campaign CONTINUOUS chỉ mang tính hiển thị, không ảnh hưởng gì tới việc crawl thật.
- Không có cách nào cho 1 Campaign "theo dõi từ 1 mốc xa hơn 30 ngày" mà không phải chờ dữ liệu tự tích lũy dần theo thời gian thực (VD Campaign tạo hôm nay, muốn có dữ liệu từ 3 tháng trước, sẽ không bao giờ có được, trừ khi tự tạo Campaign ONE_SHOT riêng để bù).

## Mục tiêu

Campaign CONTINUOUS tôn trọng đúng `start_date` — khi kích hoạt, hệ thống tự "quét bù" (backfill) đủ xa để phủ đúng nhu cầu, mà **không** tăng số lượng task Celery hay gây trùng lặp Discover giữa các Campaign chia sẻ chung 1 Nguồn.

## Kiến trúc đã cân nhắc

- **Option B (loại):** tách 1 task Celery riêng/Campaign+Nguồn (giống ONE_SHOT). Bị loại vì: bùng nổ số lượng task định kỳ khi nhiều Campaign chia sẻ 1 Nguồn, Discover trùng lặp trong vùng ngày chồng lấn giữa các Campaign, `crawl_frequency` (hiện thuộc `sources`, dùng chung) phải tách theo từng cặp Campaign+Nguồn — phức tạp hóa mô hình dữ liệu không cần thiết.
- **Option C (chọn):** giữ nguyên 1 task/Nguồn, chỉ đổi cách tính cửa sổ Discover thành **hợp (union)** nhu cầu của mọi Campaign CONTINUOUS đang `ACTIVE` theo dõi Nguồn đó — chi tiết dưới đây.

## Thiết kế

### 1. Validate — cap 180 ngày cho `start_date` của Campaign CONTINUOUS

Chặn cứng ở `POST`/`PUT /api/campaigns` và `POST .../activate` (giống hệt pattern `_validate_one_shot_date_range` đã làm cho ONE_SHOT, không phải cơ chế mới): nếu `mode=CONTINUOUS` và `start_date` xa hơn 180 ngày tính từ hôm nay → `400`. Đây là chặn **rõ ràng, ngay lúc tạo/kích hoạt** — không phải cap ngầm lúc backfill (người dùng biết ngay giới hạn, không có hành vi âm thầm).

### 2. Schema — thêm `sources.discover_backfilled_from`

```sql
ALTER TABLE sources ADD COLUMN discover_backfilled_from TIMESTAMP;
```

Ý nghĩa: **mốc xa nhất mà Discover đã chắc chắn quét xong** cho Nguồn đó — kiểu "high-water mark" (mốc nước cao nhất từng đạt), không phải "mốc Campaign nào đó cần". `NULL` = chưa từng backfill đặc biệt gì (hành vi khởi điểm giống hệt cửa sổ cố định trước đây).

### 3. Logic tính cửa sổ Discover — sửa `discover_source_urls` (continuous_crawl.py)

Không đổi chữ ký `crawl_task(source_id)` — toàn bộ logic mới nằm gọn trong `discover_source_urls`, tính lại **mỗi lần chạy** (không truyền tham số đã tính sẵn từ `list_due_sources`/`check_due_sources`, tránh rủi ro dữ liệu cũ nếu tập Campaign đổi giữa lúc Beat enqueue và lúc worker thực sự chạy):

1. Tính `required_floor` = `MIN(start_date)` trong số Campaign `mode=CONTINUOUS AND status=ACTIVE` đang theo dõi `source_id` này qua `campaign_sources` — cap tối đa 180 ngày trước hôm nay (lưới an toàn thứ 2, dù đã chặn ở bước 1).
2. So `required_floor` với `source.discover_backfilled_from`:
   - `discover_backfilled_from IS NULL` hoặc `required_floor < discover_backfilled_from` → **cần backfill**: `date_from = required_floor`.
   - Ngược lại → cửa sổ hẹp bình thường cho phần incremental: `date_from = today - 5 ngày` (hằng số mới `_INCREMENTAL_LOOKBACK_DAYS = 5`, thay cho `_DISCOVER_LOOKBACK_DAYS = 30` cũ), không phải đúng `last_crawled_at` — giữ biên độ an toàn nhỏ để giữ tính tự phục hồi nếu Beat gián đoạn vài ngày, đúng tinh thần cửa sổ 30 ngày gốc (Phase 3), chỉ thu hẹp lại vì phần "phủ xa theo Campaign" giờ đã tách riêng thành cơ chế backfill ở bước 2.
3. Sau khi Discover xong (dù backfill hay incremental), cập nhật mốc bằng **UPDATE nguyên tử ở tầng DB**, không đọc-rồi-ghi qua ORM (tránh race giữa 2 `crawl_task` cùng Nguồn chạy chồng lấn — race đã biết, từng gây bug thật ở `fetch_pending_urls`):
   ```sql
   UPDATE sources
   SET discover_backfilled_from = LEAST(COALESCE(discover_backfilled_from, :date_from), :date_from)
   WHERE source_id = :source_id
   ```

### 4. Không co lại khi Campaign rời đi

`discover_backfilled_from` **không bao giờ nới rộng lại** (tăng lên/gần hơn) khi Campaign có `start_date` xa nhất bị Pause/Archive — dữ liệu đã Discover/fetch không "hết hạn", giữ mốc cũ không tốn thêm chi phí gì, còn nới lại sẽ gây Discover thừa (quét lại đúng khoảng đã có sẵn) nếu sau này 1 Campaign khác cần lại đúng khoảng đó.

## Rollout — xóa sạch dữ liệu crawl cũ trước khi deploy

**Đã xác nhận với user, hành động phá hủy — cần xác nhận lại lần cuối lúc thực thi thật** (giống quy trình đã áp dụng khi xóa bảng `jobs` ở Phase 7): trước khi migration thêm cột `discover_backfilled_from` chạy trên môi trường thật, xóa sạch:

`articles`, `crawl_queue`, `campaign_articles`, `campaign_article_keywords`, `article_analysis`, `campaigns`, `campaign_keywords`, `campaign_sources`, `campaign_crawl_progress`, `report_history`, `keywords` — **chỉ giữ lại `sources`**.

Lý do: tránh phải xử lý tình huống "Nguồn đã có Campaign `ACTIVE` từ trước lúc migration chạy" (nếu không xóa, `discover_backfilled_from` bắt đầu `NULL` cho Nguồn đó trong khi đã có Campaign cũ với `start_date` xa — chu kỳ đầu tiên sau deploy sẽ đồng loạt backfill nhiều Nguồn cùng lúc, rủi ro tăng đột biến request). Xóa sạch → mọi Nguồn bắt đầu từ trạng thái sạch, Campaign tạo lại sau deploy sẽ backfill đúng, có kiểm soát, không đồng loạt.

## Error handling

| Tình huống | Xử lý |
|---|---|
| `start_date` Campaign CONTINUOUS xa hơn 180 ngày lúc tạo/sửa/kích hoạt | 400, chặn ngay (mục 1) |
| 2 `crawl_task` cùng Nguồn chạy chồng lấn, cùng cập nhật `discover_backfilled_from` | UPDATE nguyên tử `LEAST(...)` ở tầng DB — không mất cập nhật, không cần lock riêng |
| `required_floor` không tính được (Nguồn không còn Campaign CONTINUOUS `ACTIVE` nào theo dõi — trường hợp hiếm vì `list_due_sources` đã lọc trước) | Không xảy ra trong luồng bình thường (Discover chỉ chạy cho Nguồn đã qua `list_due_sources`) — nếu xảy ra, coi như không có backfill cần thiết, dùng cửa sổ incremental mặc định |
| Campaign có `start_date` xa nhất bị Pause/Archive | `discover_backfilled_from` giữ nguyên, không co lại (mục 4) |

## Testing

- Unit test `discover_source_urls`: tính đúng `required_floor` = MIN start_date các Campaign ACTIVE; cap 180 ngày; so sánh đúng với `discover_backfilled_from` (backfill khi cần, incremental khi không); cập nhật mốc đúng sau Discover.
- Unit test race: 2 lệnh gọi UPDATE `LEAST(...)` liên tiếp với giá trị khác nhau → mốc cuối cùng luôn là giá trị nhỏ nhất (không phụ thuộc thứ tự).
- Unit test validate `start_date <= 180 ngày` ở cả `create`/`update`/`activate` cho CONTINUOUS.
- Test không co lại: Campaign A backfill sâu → Pause A → Campaign B (nhu cầu gần hơn) kích hoạt → `discover_backfilled_from` không đổi, vẫn giữ mốc sâu của A.
- Smoke test Docker thật: sau khi xóa dữ liệu cũ + deploy, tạo Campaign CONTINUOUS `start_date` xa (VD 60 ngày trước), kích hoạt, xác nhận `SCHEDULER_ENABLED=true`, quan sát chu kỳ Discover đầu tiên backfill đúng 60 ngày (không phải 30 ngày cũ), bài cũ hơn 30 ngày trong phạm vi được match đúng vào Campaign.
