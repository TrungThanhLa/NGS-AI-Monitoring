# Báo cáo thực thi: 2026-07-23-continuous-discover-per-campaign-window-plan

## 1. Bảng trạng thái từng Task/Step

| Task | Trạng thái | Commit Hash | Ghi chú |
|---|---|---|---|
| Task 1: Wipe dữ liệu crawl/campaign cũ (Migration 0024) | ✅ Xong | `8623d20` | Đã chạy migration, kiểm tra db counts. |
| Task 2: Schema mới `sources.discover_backfilled_from` (Migration 0025) | ✅ Xong | `67e66be` | Đã chạy migration downgrade/upgrade, pass pytest. |
| Task 3: Validate `start_date` CONTINUOUS tối đa 180 ngày | ✅ Xong | `7c016dc` | Pass pytest 49 test cases trong `test_campaigns_router.py`. |
| Task 4: Logic mới trong `discover_source_urls` | ✅ Xong | `1186b8a` | Pass pytest 29 test cases trong `test_continuous_crawl.py`, pass toàn bộ test suite. |
| Task 5: Smoke test Docker thật | ⚠️ Dở dang | N/A | Hoàn thành Step 1-3. Step 4-7 chưa làm do yêu cầu thao tác UI thủ công. |

## 2. Bằng chứng verify thật

**Task 1: Verify DB Counts (Step 3)**
```text
 count
-------
     0
(1 row)

 count
-------
     0
(1 row)

 count
-------
     7
(1 row)
```

**Task 2 & 3 & 4: Pytest Output**
Task 2 (Scheduler models):
```text
============================== 5 passed in 0.08s ===============================
```
Task 3 (Campaigns router):
```text
======================== 49 passed, 1 warning in 2.30s =========================
```
Task 4 (Continuous crawl):
```text
============================== 29 passed in 1.35s ==============================
```

**Task 5 Step 1-3: Docker & Test Suite**
Lệnh build container thành công (`docker compose up -d --build backend celery-worker celery-beat`).
Output chạy toàn bộ Test Suite trên backend container (Step 2):
```text
=============================== warnings summary ===============================
../usr/local/lib/python3.12/site-packages/starlette/formparsers.py:12
  /usr/local/lib/python3.12/site-packages/starlette/formparsers.py:12: PendingDe
precationWarning: Please use `import python_multipart` instead.
    import multipart

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
297 passed, 1 warning in 23.33s
```

Output đếm lại DB trên Dev sau rebuild (Step 3):
```text
 count
-------
     0
(1 row)

 count
-------
     7
(1 row)
```

**Task 5 Step 4-7 (Smoke test qua UI/Docker thật):**
- **CHƯA LÀM**. Đây là các thao tác thủ công trên giao diện UI (bật setting, tạo campaign) và chờ Celery Beat chạy chu kỳ Discover. Cần User hoặc Claude Code trực tiếp xác nhận qua UI, hoặc user phải đồng ý cho viết script giả lập API.

## 3. Việc còn tồn đọng

- **Task 5 (Step 4, 5, 6, 7)**: Chưa thao tác kiểm tra smoke test thật trên giao diện UI. Lý do: Antigravity không thể trực tiếp click trên UI trình duyệt. Cần sự can thiệp của User để thao tác tạo Campaign, bật công tắc, và quan sát Worker Logs.

## 4. Sai khác so với plan gốc

- Trong Task 4, hàm `_compute_required_floor` có thêm ràng buộc kiểm tra an toàn biến `backfilled_from` (`if isinstance(backfilled_from, datetime) and backfilled_from`) để đề phòng lỗi `AttributeError` khi field nhận giá trị `None`.
- Chạy các lệnh verify Task 1, 2, 3 bằng bash command trực tiếp (với sự cho phép của user) chứ không qua subagent do cấu hình phân quyền môi trường đã chặn lệnh trước đó.
- Các block test trong `test_continuous_crawl.py` được append thay vì replace toàn bộ file để đảm bảo an toàn với các test cũ.

## 5. Cần lưu ý / cần quyết định

- **Quyết định cho việc Smoke Test**: User cần trực tiếp login vào UI để test Step 4-7, hoặc yêu cầu Antigravity viết script Python giả lập REST client gọi API/DB để tự động hoàn thành nốt các bước của Task 5.
- Cột `discover_backfilled_from` mặc định đang có giá trị `None` cho các Nguồn cũ, do đó lần Discover đầu tiên sau đợt cập nhật này sẽ tạo ra 1 lượng lớn request backfill lùi sâu đúng bằng `start_date` của Campaign. Cần chú ý theo dõi log celery worker trong chu kỳ đầu này.
- Dữ liệu `sources` (7 bản ghi) đã được giữ nguyên an toàn sau migration 0024 theo đúng logic thiết kế.
