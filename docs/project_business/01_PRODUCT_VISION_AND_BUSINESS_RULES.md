# NGS Monitor — Tầm nhìn mở rộng & Business Rules đề xuất

> Mô tả hướng mở rộng nghiệp vụ từ mô hình on-demand hiện tại (1 lần bấm "Tạo báo cáo" = 1 lần chạy trọn vẹn) sang mô hình **continuous monitoring** (chiến dịch giám sát chạy nền liên tục, có cảnh báo và điều tra vụ việc đi kèm). Phạm vi nguồn dữ liệu **giữ nguyên như hiện tại: website/báo điện tử tiếng Việt qua sitemap/listing/CSS-selector** — không mở rộng sang mạng xã hội (Facebook/YouTube/TikTok/Zalo/Telegram), theo đúng quyết định MVP đã chốt.

---

## 1. Tầm nhìn mở rộng

**Mục tiêu:** từ một công cụ "tạo báo cáo tin giả theo yêu cầu" trở thành một **nền tảng giám sát liên tục**: người dùng định nghĩa 1 lần "cần theo dõi chủ đề gì, từ nguồn nào", hệ thống tự động crawl định kỳ, tự phân tích AI, tự cảnh báo khi có dấu hiệu bất thường, và hỗ trợ chuyên viên lập hồ sơ điều tra khi cần — báo cáo Word chỉ còn là **một trong các đầu ra**, không còn là đích đến duy nhất của hệ thống.

**Vấn đề thực tế cần giải quyết thêm (so với hiện tại):**
- Hiện tại: muốn biết tin tức mới về 1 chủ đề, người dùng phải tự nhớ quay lại bấm "Tạo báo cáo" mỗi lần.
- Mở rộng: hệ thống tự biết khi nào có tin mới liên quan, tự đánh giá mức độ cần chú ý, và chủ động báo cho người phụ trách.

**Đối tượng sử dụng:** giữ nguyên như hiện tại — cơ quan nhà nước/tổ chức phòng chống tin giả tại Việt Nam. Không mở rộng sang doanh nghiệp/báo chí trừ khi có yêu cầu riêng.

**5 vai trò người dùng đề xuất (hiện dự án chưa có Auth — đây là thiết kế mới hoàn toàn):**

| Vai trò | Trách nhiệm chính |
|---|---|
| **ADMIN** | Toàn quyền — quản trị người dùng, cấu hình hệ thống, dữ liệu dùng chung, nguồn dữ liệu |
| **MANAGER** | Tạo/kích hoạt chiến dịch giám sát, xử lý cảnh báo, duyệt và tạo vụ việc, duyệt báo cáo |
| **ANALYST** | Xem dữ liệu, đánh giá nội dung, xử lý cảnh báo, tạo vụ việc — không được xóa dữ liệu hay cấu hình hệ thống |
| **OPERATOR** | Quản lý nguồn dữ liệu, theo dõi/vận hành crawler, xử lý lỗi crawl — không xử lý nội dung/duyệt báo cáo |
| **VIEWER** | Chỉ xem dashboard và báo cáo — không sửa dữ liệu |

**Business flow mở rộng (10 bước, thay cho 8 bước hiện tại):**

```
Tạo Chiến dịch giám sát → Chọn từ khóa cần theo dõi → Chọn nguồn dữ liệu (website)
→ Kích hoạt Chiến dịch → Scheduler tự động crawl định kỳ theo từng nguồn
→ Chuẩn hóa & loại trùng dữ liệu → AI phân tích (tóm tắt/chủ đề/cảm xúc/mức độ cần chú ý)
→ Hệ thống tự sinh Cảnh báo khi vượt ngưỡng → Chuyên viên xem & đánh giá nội dung
→ (tùy chọn) Tạo Vụ việc để điều tra sâu → Tạo Báo cáo tổng hợp theo chiến dịch
```

So với 8 bước hiện tại, khác biệt cốt lõi: **Chiến dịch (Campaign) là thực thể sống** (có vòng đời, chạy nền liên tục), thay vì **Job đơn lẻ** (chạy 1 lần rồi kết thúc).

---

## 2. Business Rules — bộ mã thống nhất theo domain

> Mã rule dùng tiền tố theo domain (`BR-<DOMAIN>-NN`) để không bao giờ trùng số giữa các domain khác nhau. Rule nào là đề xuất mặc định có thể điều chỉnh được đánh dấu **⚠️**.

### 2.1 Nguyên tắc hệ thống chung

- **BR-SYS-01:** Mọi bảng nghiệp vụ áp dụng soft-delete — không xóa vật lý. Bảng phải có `created_at/by`, `updated_at/by`, `deleted_at/by`, `is_active`. Ngoại lệ: bảng `audit_logs` bất biến, không soft-delete (không sửa/xóa dưới bất kỳ hình thức nào).
- **BR-SYS-02:** Mọi thao tác thay đổi dữ liệu (tạo/sửa/xóa/duyệt/từ chối/đăng nhập/đăng xuất/xuất file) phải ghi Audit Log.
- **BR-SYS-03:** Mọi API phải kiểm tra Authentication + Authorization (RBAC) ở tầng backend — không được chỉ dựa vào việc ẩn nút ở giao diện.
- **BR-SYS-04:** Toàn hệ thống dùng múi giờ `Asia/Ho_Chi_Minh` (UTC+7).

### 2.2 Người dùng & Phân quyền

- **BR-USER-01:** 5 vai trò mặc định: `ADMIN, MANAGER, ANALYST, OPERATOR, VIEWER`. Vai trò hệ thống (`is_system=true`) không được xóa.
- **BR-USER-02:** Quyền hạn của từng vai trò theo bảng ở mục 1 — chi tiết từng permission ở `04_SCREENS_UI_RBAC.md`.
- **BR-USER-03:** Người dùng phải thuộc ít nhất 1 vai trò.
- **BR-USER-04:** Tài khoản bị vô hiệu hóa (disabled) không đăng nhập được.
- **BR-USER-05:** Không được xóa tài khoản ADMIN cuối cùng của hệ thống.
- **BR-USER-06:** Permission có dạng `resource.action` (VD `campaign.create`). Giao diện ẩn menu/nút khi thiếu quyền — chỉ mang tính UX, không thay thế kiểm tra ở backend.
- **BR-USER-07:** Đăng nhập sai tối đa **5 lần** → khóa tài khoản **30 phút**. Phiên đăng nhập hết hạn sau **60 phút** (access token), refresh token 7 ngày. Mật khẩu tối thiểu 8 ký tự, có chữ hoa/chữ thường/số. Băm mật khẩu bằng BCrypt.

### 2.3 Chiến dịch giám sát (Campaign)

- **BR-CAMP-01:** Chiến dịch phải có Tên, Thời gian bắt đầu, Người phụ trách (`owner_id`).
- **BR-CAMP-02:** Trạng thái: `DRAFT → ACTIVE → PAUSED/COMPLETED → ARCHIVED`.
- **BR-CAMP-03 (đã chốt, 2026-07-16):** Chiến dịch chỉ chuyển được sang `ACTIVE` khi có **≥1 nguồn dữ liệu VÀ ≥1 từ khóa**. Từ khóa dùng để **lọc phạm vi** (không chỉ gắn nhãn) — matching diễn ra ở bước hậu-crawl, không lọc ngay tại bước crawl (xem `06_OPEN_DECISIONS.md` mục 2 và bảng `campaign_articles` ở `02_DOMAIN_MODEL_AND_DATABASE.md`).
- **BR-CAMP-04:** Chiến dịch `ARCHIVED` chỉ được xem, không được sửa hoặc kích hoạt lại.
- **BR-CAMP-05:** Không xóa vật lý chiến dịch đã có dữ liệu — chỉ cho phép chuyển `ARCHIVED` (dừng crawl, giữ nguyên dữ liệu cũ).
- **BR-CAMP-06:** 1 Chiến dịch có thể theo dõi nhiều Nguồn; 1 Nguồn có thể được dùng ở nhiều Chiến dịch (quan hệ N:N).
- **BR-CAMP-07 (đã chốt, 2026-07-16):** Campaign có `mode = CONTINUOUS` (mặc định, giám sát liên tục) hoặc `ONE_SHOT` (crawl đúng 1 lần rồi tự `COMPLETED`, thay thế hoàn toàn mô hình Job on-demand hiện tại — không còn bảng `jobs`/API `POST /api/reports/create` riêng, mọi report đều tạo qua `POST /api/campaigns`).

### 2.4 Nguồn dữ liệu (Source)

- **BR-SRC-01:** Mỗi nguồn thuộc đúng 1 Nhóm nguồn (VD: Chính phủ, Bộ ngành, Báo chí) — nhóm nguồn là dữ liệu dùng chung, quản trị qua Admin.
- **BR-SRC-02:** URL/domain của nguồn là duy nhất trong toàn hệ thống.
- **BR-SRC-03:** Trạng thái nguồn: `ACTIVE` (đang crawl bình thường), `INACTIVE` (bị tắt thủ công bởi Admin/Operator), `ERROR` (tự động chuyển khi kiểm tra kết nối thất bại hoặc crawl lỗi liên tiếp quá ngưỡng — đề xuất ngưỡng **10 lần liên tiếp ⚠️**).
- **BR-SRC-04:** Nguồn ở trạng thái `INACTIVE` hoặc `ERROR` không được đưa vào lịch crawl tự động.
- **BR-SRC-05:** Không được xóa nguồn đang được tham chiếu bởi ít nhất 1 Chiến dịch `ACTIVE`.

### 2.5 Crawler & Thu thập dữ liệu

- **BR-CRAWL-01:** Crawler chỉ thu thập dữ liệu thô, không thực hiện phân tích AI.
- **BR-CRAWL-02:** Mỗi lần crawl phải sinh 1 bản ghi lịch sử (thời gian bắt đầu/kết thúc, trạng thái, số bài tìm thấy/đã lưu, lỗi nếu có).
- **BR-CRAWL-03:** Retry tối đa 3 lần, backoff `[1–2s, 5s, 15s]` cho mỗi request lỗi (giữ nguyên tham số `CRAWLER_DELAY_SECONDS`/`CRAWLER_MAX_RETRIES` hiện có).
- **BR-CRAWL-04:** Timeout mỗi lần fetch 1 bài viết: giữ nguyên `CRAWLER_TIMEOUT_SECONDS=30` hiện tại.
- **BR-CRAWL-05:** Delay 1–2 giây giữa các request tới cùng 1 domain — không đổi so với hiện tại.
- **BR-CRAWL-06 ⚠️ (phụ thuộc chế độ vận hành):** Chống trùng (dedup) theo `SHA256(url)`. Phạm vi áp dụng dedup (trong 1 lần chạy hay toàn cục theo nguồn) phụ thuộc việc có chuyển sang crawl định kỳ liên tục hay không — xem `06_OPEN_DECISIONS.md`.

### 2.6 Nội dung (Content)

- **BR-CONTENT-01:** Một nội dung tối thiểu phải có URL và (Tiêu đề hoặc Nội dung văn bản).
- **BR-CONTENT-02:** Trạng thái đánh giá nghiệp vụ: `NEW` (mới, chưa xem) → `REVIEWED` (đã xem) → `NEED_VERIFY` (cần kiểm chứng thêm) → `VERIFIED` (đã xác minh) / `NOT_RELEVANT` (không liên quan) → `CASE_CREATED` (đã tạo vụ việc từ nội dung này). Trạng thái này **tách biệt** với trạng thái kỹ thuật hiện có của pipeline crawl/AI (`pending_analysis/analyzed/error`) — không gộp chung 1 cột.
- **BR-CONTENT-03:** Chỉ vai trò `ANALYST` và `MANAGER` được thay đổi trạng thái đánh giá nghiệp vụ.
- **BR-CONTENT-04:** Nội dung chỉ được xóa mềm, không xóa vật lý.

### 2.7 AI Phân tích

- **BR-AI-01:** AI chỉ chạy sau khi nội dung đã được chuẩn hóa (strip HTML, chuẩn hóa Unicode).
- **BR-AI-02:** AI không thực hiện việc crawl.
- **BR-AI-03 (nguyên tắc bắt buộc, không thương lượng):** AI **không được phép** kết luận "đây là tin giả" — chỉ được gắn cờ `needs_review=true` kèm lý do (`reason`), quyết định cuối cùng luôn thuộc về con người. Đây là nguyên tắc đã có sẵn trong dự án hiện tại (`AI_CONFIDENCE_THRESHOLD`), giữ nguyên khi mở rộng.
- **BR-AI-04:** Output AI cho mỗi nội dung: tóm tắt 1 câu (`summary`), 1–N chủ đề trong 8 nhóm chuẩn (`topics[]`), từ khóa (`keywords[]`), cảm xúc 3 lớp (`sentiment`), cảm xúc chi tiết 6 lớp (`emotion`), độ tin cậy (`confidence`) — đúng như pipeline hiện có, không thay đổi.
- **BR-AI-05:** Chủ đề (`topics`) chỉ được chọn trong danh mục 8 nhóm đã cấu hình sẵn, AI không được tự sinh chủ đề mới.
- **BR-AI-06:** `confidence < 0.6` → `needs_review=true`, vẫn lưu và đưa vào báo cáo (không loại bỏ) — giữ nguyên ngưỡng hiện tại.
- **BR-AI-07:** Nếu AI lỗi/timeout, không ảnh hưởng tới crawler — dùng try/except + retry 1 lần, nếu vẫn lỗi thì đánh dấu bài đó `status=error` và tiếp tục các bài khác.

### 2.8 Cảnh báo (Alert) — module mới

- **BR-ALERT-01 ⚠️ (đề xuất bộ khởi điểm, mở rộng dần):** 3 loại cảnh báo ban đầu, tận dụng dữ liệu AI đã có sẵn — không cần thêm field mới:
  - `HIGH_ATTENTION` — nội dung có `confidence` cao và `sentiment=negative` xuất hiện.
  - `NEGATIVE_TREND` — tỷ lệ nội dung `sentiment=negative` tăng bất thường trong 1 khoảng thời gian ngắn cho cùng 1 chiến dịch.
  - `KEYWORD_SPIKE` — số lượng nội dung trúng 1 từ khóa cụ thể tăng đột biến so với trung bình các ngày trước.
- **BR-ALERT-02:** Mức độ cảnh báo: `LOW, MEDIUM, HIGH, CRITICAL`.
- **BR-ALERT-03:** Cảnh báo được sinh tự động khi điều kiện rule thỏa mãn — mỗi Chiến dịch có thể có ngưỡng cảnh báo riêng (`alert_threshold`).
- **BR-ALERT-04:** Trạng thái cảnh báo: `NEW → ACKNOWLEDGED → PROCESSING → RESOLVED → CLOSED`.
- **BR-ALERT-05:** Chỉ `MANAGER` và `ADMIN` được đóng (`CLOSED`) 1 cảnh báo.
- **BR-ALERT-06:** 1 cảnh báo có thể gắn với 1 nội dung cụ thể, hoặc không gắn nội dung nào (cảnh báo tổng hợp theo xu hướng, VD `NEGATIVE_TREND`/`KEYWORD_SPIKE`).

### 2.9 Vụ việc (Case) — module mới

- **BR-CASE-01:** Vụ việc được tạo từ 1 Cảnh báo và/hoặc gắn với 1/nhiều Nội dung cụ thể — luôn ghi nhận người tạo (`created_by`).
- **BR-CASE-02:** Trạng thái: `NEW → VERIFYING → PROCESSING → RESOLVED → CLOSED` (5 trạng thái).
- **BR-CASE-03:** Vụ việc `CLOSED` không được sửa.
- **BR-CASE-04:** Một Nội dung có thể thuộc nhiều Vụ việc khác nhau (N:N).
- **BR-CASE-05:** Vụ việc có file đính kèm (bằng chứng, tài liệu điều tra).

### 2.10 Báo cáo (Report)

- **BR-REPORT-01:** Báo cáo luôn build lại từ dữ liệu Database tại thời điểm tạo, không phụ thuộc dữ liệu thay đổi về sau (snapshot ngầm định do build-on-demand, không cần cơ chế snapshot riêng).
- **BR-REPORT-02 (đã chốt mở rộng, 2026-07-16):** Định dạng đầu ra: `Report.docx` + **`Report.pdf`** + **`Report.xlsx`** + **`Report.csv`** + `JSON raw data`.
- **BR-REPORT-03:** Lịch sử xuất báo cáo phải được lưu lại vĩnh viễn (không xóa).
- **BR-REPORT-04:** Nếu áp dụng mô hình Chiến dịch, báo cáo có thể gắn theo 1 Chiến dịch cụ thể hoặc theo khoảng ngày tùy chọn (không bắt buộc phải thuộc Chiến dịch).

### 2.11 Dữ liệu dùng chung (Master Data)

- **BR-MASTER-01:** Danh mục dùng chung gồm: Nhóm nguồn, 8 Nhóm chủ đề, Từ khóa, Mức độ cần chú ý.
- **BR-MASTER-02:** Không được xóa danh mục đang được tham chiếu bởi dữ liệu khác.
- **BR-MASTER-03:** Mã danh mục (`code`) phải duy nhất trong cùng 1 bảng danh mục.

### 2.12 Bảo mật & Hiệu năng

- **BR-SEC-01:** JWT Authentication + RBAC Authorization — bắt buộc cho mọi API.
- **BR-SEC-02:** Không hardcode secret/credential trong code hoặc file cấu hình mẫu commit vào git.
- **BR-PERF-01:** Thời gian phản hồi API mục tiêu **< 3 giây** (áp dụng cho các API tra cứu/danh sách — không áp dụng cho API kích hoạt job crawl/AI chạy nền).
- **BR-PERF-02 (chỉ áp dụng nếu triển khai Monitoring Feed real-time):** Nội dung mới xuất hiện trên Feed trong vòng **< 5 giây** sau khi crawl xong.

---

## 3. Nguyên tắc phát triển (kế thừa từ rule hiện có, áp dụng cho mọi module mới)

Không lặp lại toàn bộ — xem `.claude/rules/11-core-principles.md` và `.claude/rules/14-coding-behavior.md` hiện có của dự án. Bổ sung riêng cho các module mới trong tài liệu này:
- Mọi entity mới (Campaign, Alert, Case) đều phải tuân BR-SYS-01 (soft-delete) và BR-SYS-02 (audit log) ngay từ migration đầu tiên — không thêm sau.
- Không thiết kế permission cho tính năng chưa được lên kế hoạch code — mỗi permission thêm vào RBAC matrix phải có 1 module tương ứng đã nằm trong roadmap đã duyệt.
