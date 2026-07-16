# NGS Monitor — Quyết định còn mở, cần chốt trước khi triển khai

> Danh sách các điểm mà file `01`–`05` đã chọn 1 phương án đề xuất (đánh dấu ⚠️ tại chỗ), nhưng bản chất vẫn là **quyết định nghiệp vụ cần bạn xác nhận**, không phải kỹ thuật thuần túy. Gom lại ở đây để không bị rải rác, dễ duyệt từng mục một.

---

## 1. "Job" (on-demand hiện tại) có biến mất hay tồn tại song song với "Campaign" (mới)? — ĐÃ CHỐT (2026-07-16)

**Quyết định: Phương án A mở rộng — gộp Job vào Campaign qua cột `campaigns.mode`, không giữ 2 hệ thống song song.**

- `campaigns.mode = 'ONE_SHOT'` — thay thế hoàn toàn Job cũ: chọn nguồn + khoảng ngày → kích hoạt → crawl đúng 1 lần cho khoảng ngày đó → KHÔNG đăng ký vào Celery Beat (không lặp lại) → xong tự chuyển `COMPLETED`. UI có thể vẫn gọi là "Tạo báo cáo nhanh" để giữ trải nghiệm quen thuộc, nhưng lưu chung 1 bảng `campaigns` với chế độ theo dõi liên tục.
- `campaigns.mode = 'CONTINUOUS'` (mặc định) — đúng như thiết kế continuous monitoring đã bàn ở file `03`/`05`.
- **Lý do gộp:** với công tắc `AI_AUTO_TRIGGER` đã có (xem `05` mục 2), khác biệt duy nhất còn lại giữa Job và Campaign chỉ là "crawl 1 lần" vs "crawl lặp lại theo lịch" — không đáng tách 2 schema/API riêng, gây trùng lặp logic không cần thiết.
- **Việc cần làm khi code (Phase 2):** `POST /api/reports/create` (API cũ) đổi thành `POST /api/campaigns` kèm `mode=ONE_SHOT` — breaking change, chấp nhận vì tính năng continuous monitoring chưa code dòng nào, đây là thời điểm rẻ nhất để đổi.

---

## 2. Từ khóa (Keyword) có bắt buộc để kích hoạt Campaign hay không? — ĐÃ CHỐT (2026-07-16)

**Quyết định: Phương án A — bắt buộc ≥1 từ khóa mới được `ACTIVE`, từ khóa dùng để LỌC phạm vi (không chỉ để gắn nhãn).**

**Cách lọc — hậu-crawl matching, KHÔNG lọc ngay tại bước crawl:** vì 1 Nguồn có thể dùng chung cho nhiều Campaign khác nhau (đã chốt ở mục 1), bước crawl **giữ nguyên, lấy hết và lưu theo `source_id`** như bình thường — không lọc gì ở bước này. Ngay sau khi crawl xong, hệ thống so khớp (text matching đơn giản trên tiêu đề/nội dung, không cần AI) từng bài với từ khóa của TỪNG Campaign đang theo dõi Nguồn đó, ghi kết quả vào bảng `campaign_articles` (mới, xem `02_DOMAIN_MODEL_AND_DATABASE.md`). Content list/Report/Alert của mỗi Campaign chỉ tính trên các bài đã match trong `campaign_articles` của chính nó — Campaign A và B cùng theo dõi 1 Nguồn nhưng khác từ khóa vẫn nhìn thấy đúng tập bài liên quan tới mình, không bị mất bài của nhau.

---

## 3. Phạm vi triển khai — làm hết hay dừng ở 1 mốc nào đó? — ĐÃ CHỐT (2026-07-16)

**Quyết định:** Report **không phụ thuộc** Alert/Case (xây trực tiếp từ `aggregator.py` đọc `articles` + `article_analysis`, xem `BR-REPORT-04`) — nên trình tự code có thể là **Phase 2 → Phase 3 → Phase 7 (Report)**, không cần đợi Phase 5/6 xong.

Phase 5 (Alert) và Phase 6 (Case) **vẫn giữ trong roadmap, không bỏ hẳn** — chỉ lùi lại, làm sau Report. Trong lúc chưa code backend thật cho 2 module này, FE dùng **UI tĩnh (mock)** cho các trang Alert/Case — đúng pattern đã áp dụng cho Dashboard/Campaigns/Contents/Cases/Jobs/System hiện tại (`frontend/src/data/mockData.ts`, xem `.claude/rules/09-frontend-ui.md`), không cần chờ có API thật mới hiển thị được giao diện.

Phase 8 (Monitoring Feed) vẫn đứng cuối cùng như cũ, không đổi thứ tự — chỉ có ý nghĩa sau khi Phase 3–5 chạy ổn định.

---

## 4. Dedup khi crawl liên tục — phạm vi áp dụng — ĐÃ CHỐT (2026-07-16)

**Quyết định: dedup theo `SHA256(url)` toàn cục theo Source** (đảo ngược quyết định "không dedup xuyên job" ngày 2026-07-09, ghi trong `CLAUDE.md`) — bắt buộc phải đổi vì crawl liên tục sẽ liệt kê lại URL cũ mỗi chu kỳ, nếu không dedup toàn cục dữ liệu sẽ phình to vô ích.

**Đánh đổi đã xác nhận chấp nhận:** dedup theo `url_hash` cứng nghĩa là hệ thống **sẽ không phát hiện được nếu 1 bài báo bị chỉnh sửa nội dung sau khi đăng** (URL trùng → bỏ qua ngay, không tải lại để so sánh nội dung mới/cũ). Chấp nhận đánh đổi này vì báo điện tử VN ít khi sửa nội dung sau khi đăng.

**Xử lý crawl bị lỗi/gián đoạn giữa chừng — ĐÃ CHỐT (2026-07-16):** tách `crawl_task` thành 2 giai đoạn qua bảng `crawl_queue` mới — Giai đoạn 1 (khám phá URL từ sitemap/listing, ghi vào hàng đợi ngay, rẻ và ít lỗi) tách khỏi Giai đoạn 2 (tải nội dung, cập nhật trạng thái theo từng URL). URL bị lỡ do đứt giữa chừng vẫn còn `status='pending'` trong hàng đợi, tự động được thử lại ở chu kỳ crawl kế tiếp — không phụ thuộc việc sitemap/listing của nguồn còn hiển thị URL đó hay không. Chi tiết thiết kế xem `03_SYSTEM_ARCHITECTURE.md` mục 4 và bảng `crawl_queue` ở `02_DOMAIN_MODEL_AND_DATABASE.md`.

---

## 5. Report — mở rộng định dạng — ĐÃ CHỐT (2026-07-16)

**Quyết định:** thêm định dạng xuất **PDF**, **Excel (XLSX)** và **CSV** bên cạnh `.docx`/`.json` hiện có — xem `01_PRODUCT_VISION_AND_BUSINESS_RULES.md` BR-REPORT-02.

---

## 6. Ngưỡng cụ thể cho Alert Rule — ĐÃ CHỐT TẠM THỜI (2026-07-16)

**Quyết định:** `confidence >= 0.8` cho `HIGH_ATTENTION` (file `05` mục 3) — chấp nhận làm ngưỡng khởi điểm để có cái chạy, **không phải số liệu cuối cùng** — sẽ điều chỉnh lại sau khi có đủ dữ liệu thật từ vận hành.

---

## 7. Ngưỡng "nguồn lỗi liên tiếp" chuyển sang trạng thái ERROR — ĐÃ CHỐT TẠM THỜI (2026-07-16)

**Quyết định:** giữ **10 lần liên tiếp** (`01` BR-SRC-03) làm ngưỡng khởi điểm — chấp nhận là số tham khảo ban đầu, sẽ điều chỉnh lại sau khi có dữ liệu vận hành thật (VD nếu nguồn báo chí VN có tỷ lệ lỗi tạm thời do rate-limit cao hơn mức này).

---

## 8. AI runtime — khi nào và theo hướng nào chuyển khỏi Ollama local — ĐÃ CHỐT (2026-07-16)

**Quyết định: chuyển đổi hoàn toàn THỦ CÔNG, không cần cơ chế tự động phát hiện tải rồi tự chuyển.** Bắt đầu bằng Ollama local (`qwen3:8b`) như hiện tại — sau này nếu dự án scale, bạn tự quyết định thời điểm và tự đổi cấu hình (biến `AI_PROVIDER` trong `.env`, hoặc sửa nhỏ nếu cần thêm 1 provider mới) sang server AI riêng tự build hoặc API cloud trả phí, dùng đúng lớp `AIProvider` interface đã thiết kế sẵn (`03_SYSTEM_ARCHITECTURE.md` mục 5).

**Hệ quả — các mục con từng treo ở đây không còn cần thiết:**
- Không cần "ngưỡng cụ thể để tự động chuyển" — vì không có cơ chế tự động, bạn quan sát thực tế vận hành rồi tự bấm chuyển khi thấy cần.
- Không cần chốt trước "hướng (a) hay (b) trước" — vì là lựa chọn thủ công, bạn có thể chọn bất kỳ lúc nào tùy tình huống thực tế, không phải quyết định trước.
- Phương án AI lai (local + cloud cho `needs_review=true`) và ngân sách vận hành — vẫn để dành cân nhắc sau trong quá trình test/vận hành thật (giữ nguyên như đã note 2026-07-16), không phải quyết định ngay.

**Việc kỹ thuật cần làm trước (không đổi):** tách `AIProvider` interface ra khỏi `ollama_client.py` hiện có ngay khi bắt đầu Phase 1–3 của roadmap, để việc đổi provider sau này chỉ là sửa cấu hình, không phải refactor lớn.

---

## Cách dùng file này

Khi bạn xác nhận từng mục (giữ nguyên đề xuất hoặc chọn phương án khác), cập nhật trực tiếp vào file `01`–`05` tương ứng (bỏ dấu ⚠️, ghi rõ là đã chốt) rồi xóa mục đó khỏi file này. Khi file này trống, toàn bộ `project_business/` sẵn sàng để chuyển hóa thành rule chính thức trong `.claude/rules/`.
