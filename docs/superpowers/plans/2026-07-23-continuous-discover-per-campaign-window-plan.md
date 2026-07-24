# CONTINUOUS — Discover theo hợp khoảng ngày Campaign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Campaign CONTINUOUS tôn trọng đúng `start_date` — Discover tự tính cửa sổ theo hợp (union) nhu cầu của mọi Campaign CONTINUOUS `ACTIVE` đang theo dõi cùng 1 Nguồn (thay vì cửa sổ trượt 30 ngày cố định không quan tâm Campaign nào), có cơ chế "quét bù" (backfill) 1 lần + ghi nhớ mốc đã backfill để không lặp lại lãng phí.

**Architecture:** Giữ nguyên 1 Celery task/Nguồn (`crawl_task`), giữ nguyên Fetch/Matching/AI 100% — chỉ đổi hàm `discover_source_urls` tự tính `date_from` động mỗi lần chạy (không truyền tham số tính sẵn từ Beat, tránh dữ liệu cũ). Thêm 1 cột `sources.discover_backfilled_from` làm "mốc nước cao nhất" đã Discover chắc chắn, cập nhật bằng UPDATE nguyên tử `LEAST()` để an toàn khi 2 `crawl_task` cùng Nguồn chạy chồng lấn.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Celery, pytest (fixture `db_session` — transaction rollback per test).

## Global Constraints

- Không đổi chữ ký `crawl_task(source_id)`, không đổi chữ ký `discover_source_urls(db, source, today=None)` — toàn bộ logic mới nằm gọn bên trong hàm này.
- Không đổi Fetch (`fetch_pending_urls`), Matching (`match_campaigns_for_article`), AI (`maybe_analyze_article`) — 0 dòng thay đổi ở các hàm này.
- Cap backfill tối đa `180` ngày (`_MAX_CONTINUOUS_BACKFILL_DAYS` trong `continuous_crawl.py`, `_MAX_CONTINUOUS_START_DATE_DAYS` trong `campaigns.py` — 2 hằng số tách riêng theo module, cùng giá trị `180`, không chia sẻ qua import để tránh phụ thuộc chéo router↔worker không cần thiết).
- Cửa sổ incremental (khi không cần backfill): `_INCREMENTAL_LOOKBACK_DAYS = 5` ngày (hằng số mới, thay `_DISCOVER_LOOKBACK_DAYS = 30` cũ).
- `discover_backfilled_from` **không bao giờ co lại/nới rộng** khi Campaign rời đi (Pause/Archive) — chỉ có thể tiến xa hơn về quá khứ (giá trị nhỏ hơn), không bao giờ tiến gần hơn hiện tại.
- Cập nhật `discover_backfilled_from` bắt buộc qua `UPDATE ... SET discover_backfilled_from = LEAST(...)` (SQL nguyên tử ở tầng DB) — không đọc-rồi-ghi qua ORM.
- Validate cap 180 ngày cho `start_date` CONTINUOUS áp dụng ở **cả 3 nơi**: `create_campaign`, `update_campaign`, `activate_campaign` — đúng pattern `_validate_one_shot_date_range` đã có sẵn trong `backend/routers/campaigns.py`.

---

### Task 1: Migration xóa sạch dữ liệu crawl cũ (DESTRUCTIVE — cần xác nhận trước khi chạy trên môi trường thật)

> ⚠️ **Task này xóa dữ liệu thật, không thể hoàn tác.** User đã xác nhận rõ ràng trong buổi trao đổi thiết kế (2026-07-23): xóa sạch `articles`, `crawl_queue`, `campaign_articles`, `campaign_article_keywords`, `article_analysis`, `campaigns`, `campaign_keywords`, `campaign_sources`, `campaign_crawl_progress`, `report_history`, `keywords` — **chỉ giữ lại `sources`**. Trước khi CHẠY migration này trên bất kỳ DB nào ngoài DB test tự động (VD DB dev thật qua Docker), người thực thi (agent hoặc người) PHẢI dừng lại và xác nhận lại lần cuối với user — giống quy trình đã áp dụng khi xóa bảng `jobs` ở Phase 7 (migration `0021`, xem `backend/alembic/versions/0021_drop_jobs_and_finalize_campaign_reports.py` để tham khảo đúng pattern ngưỡng an toàn).

**Files:**
- Create: `backend/alembic/versions/0024_wipe_crawl_data_for_continuous_discover_redesign.py`

**Interfaces:**
- Không có interface code (migration thuần túy) — chỉ cần chạy sạch `upgrade()`/`downgrade()` (downgrade là no-op có ghi chú rõ không khôi phục được dữ liệu).

- [ ] **Step 1: Kiểm tra row count hiện tại trước khi viết ngưỡng an toàn**

Run: `docker compose exec backend python -c "
from backend.db import SessionLocal
from sqlalchemy import text
db = SessionLocal()
for t in ['articles','crawl_queue','campaigns','keywords','campaign_articles','report_history']:
    print(t, db.execute(text(f'SELECT COUNT(*) FROM {t}')).scalar())
"`

Ghi lại số liệu — dùng để xác nhận đây thực sự là dữ liệu quy mô dev/test (không phải dữ liệu lớn bất thường) trước khi viết ngưỡng an toàn ở Step 2.

- [ ] **Step 2: Viết migration**

`backend/alembic/versions/0024_wipe_crawl_data_for_continuous_discover_redesign.py`:
```python
"""xóa sạch dữ liệu crawl/campaign cũ trước khi triển khai lại cơ chế Discover CONTINUOUS
theo hợp (union) khoảng ngày Campaign — xác nhận với user 2026-07-23, GIỮ LẠI `sources`
(cấu hình nguồn thật, không phải dữ liệu test). Tránh phải xử lý tình huống "Nguồn đã có
Campaign ACTIVE từ trước lúc migration chạy" — mọi Nguồn bắt đầu sạch, không đồng loạt
backfill ngay lúc deploy (xem docs/superpowers/specs/2026-07-23-continuous-discover-per-
campaign-window-design.md mục Rollout).

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

# Ngưỡng an toàn — nếu bất kỳ bảng nào vượt quá, migration DỪNG LẠI thay vì xóa mù quáng
# (đúng pattern đã áp dụng ở migration 0021 khi xóa bảng jobs). Dữ liệu dev/test hiện tại
# nhỏ hơn nhiều so với ngưỡng này (xem log Step 1 lúc viết plan) — chỉ dùng làm lưới an
# toàn chống chạy nhầm vào DB không phải dev/test.
_MAX_SAFE_ROW_COUNT = 100_000


def upgrade():
    conn = op.get_bind()
    for table in ("articles", "campaigns", "crawl_queue"):
        count = conn.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
        if count > _MAX_SAFE_ROW_COUNT:
            raise RuntimeError(
                f"Migration 0024 dừng lại: bảng {table} có {count} dòng, vượt ngưỡng an "
                f"toàn {_MAX_SAFE_ROW_COUNT}. Đây có thể là dữ liệu thật, không phải dữ liệu "
                "dev/test. Xác nhận lại với người vận hành / backup thủ công trước khi chạy lại."
            )

    # Xóa theo đúng thứ tự phụ thuộc FK — con trước cha
    op.execute("DELETE FROM campaign_article_keywords")
    op.execute("DELETE FROM campaign_articles")
    op.execute("DELETE FROM campaign_crawl_progress")
    op.execute("DELETE FROM campaign_keywords")
    op.execute("DELETE FROM campaign_sources")
    op.execute("DELETE FROM report_history")
    op.execute("DELETE FROM article_analysis")
    op.execute("DELETE FROM articles")
    op.execute("DELETE FROM crawl_queue")
    op.execute("DELETE FROM campaigns")
    op.execute("DELETE FROM keywords")
    # sources KHÔNG bị đụng tới — giữ nguyên cấu hình nguồn thật


def downgrade():
    # Không thể khôi phục dữ liệu đã xóa — downgrade chỉ ghi nhận, không làm gì.
    pass
```

- [ ] **Step 2.5: Xác nhận lại lần cuối với user trước khi chạy trên DB dev thật**

Đây không phải bước tự động — trước khi thực thi Step 3 trên DB dev thật qua Docker (không phải DB test tự động), agent/người thực thi PHẢI dừng lại, trình bày số liệu đã ghi ở Step 1, và xin xác nhận rõ ràng từ user rằng vẫn muốn tiến hành xóa. Không tự ý bỏ qua bước này.

- [ ] **Step 3: Chạy migration trên DB dev thật qua Docker (SAU KHI đã xác nhận lại ở Step 2.5)**

Run: `docker compose exec backend bash -lc "cd /app/backend && alembic upgrade head"`
Expected: log hiện `Running upgrade 0023 -> 0024`, không lỗi `RuntimeError`.

- [ ] **Step 4: Xác nhận dữ liệu đã sạch, `sources` còn nguyên**

Run: `docker compose exec -T postgres psql -U ngs -d ngs_monitor -c "select count(*) from campaigns; select count(*) from articles; select count(*) from sources;"`
Expected: `campaigns`/`articles` = 0, `sources` > 0 (giữ nguyên số lượng nguồn thật đã cấu hình).

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0024_wipe_crawl_data_for_continuous_discover_redesign.py
git commit -m "chore: xóa sạch dữ liệu crawl/campaign cũ trước khi triển khai Discover CONTINUOUS theo Campaign"
```

---

### Task 2: Schema — thêm `sources.discover_backfilled_from`

**Files:**
- Modify: `backend/models/sources.py`
- Create: `backend/alembic/versions/0025_add_sources_discover_backfilled_from.py`
- Test: `backend/tests/test_scheduler_models.py` (thêm vào cuối file)

**Interfaces:**
- Produces: `Source.discover_backfilled_from` — cột mới (TIMESTAMP, nullable, không có default) trên model `Source` đã có sẵn.

- [ ] **Step 1: Thêm cột vào model**

Trong `backend/models/sources.py`, sửa:
```python
    consecutive_error_count = Column(Integer, server_default="0")
    created_at = Column(TIMESTAMP, server_default=func.now())
```
thành:
```python
    consecutive_error_count = Column(Integer, server_default="0")
    created_at = Column(TIMESTAMP, server_default=func.now())
    # "Mốc nước cao nhất" Discover đã chắc chắn quét xong cho Nguồn này — dùng để quyết
    # định có cần "quét bù" (backfill) khi 1 Campaign CONTINUOUS mới cần dữ liệu xa hơn
    # mốc này hay không (xem continuous_crawl.py discover_source_urls). Không bao giờ
    # co lại/nới gần hơn hiện tại — chỉ tiến xa hơn về quá khứ.
    discover_backfilled_from = Column(TIMESTAMP)
```

- [ ] **Step 2: Viết migration**

`backend/alembic/versions/0025_add_sources_discover_backfilled_from.py`:
```python
"""thêm sources.discover_backfilled_from — "mốc nước cao nhất" Discover đã chắc chắn
quét xong cho từng Nguồn, phục vụ cơ chế backfill theo hợp (union) khoảng ngày các
Campaign CONTINUOUS đang ACTIVE (thay cửa sổ trượt 30 ngày cố định cũ)

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sources", sa.Column("discover_backfilled_from", sa.TIMESTAMP))


def downgrade():
    op.drop_column("sources", "discover_backfilled_from")
```

- [ ] **Step 3: Chạy migration**

Run: `docker compose exec backend bash -lc "cd /app/backend && alembic upgrade head"`
Expected: `Running upgrade 0024 -> 0025`, không lỗi.

Run: `docker compose exec backend bash -lc "cd /app/backend && alembic downgrade -1 && alembic upgrade head"`
Expected: cả 2 lệnh chạy sạch — xác nhận `downgrade()` đúng.

- [ ] **Step 4: Viết test roundtrip**

Thêm vào cuối `backend/tests/test_scheduler_models.py`:
```python
def test_source_discover_backfilled_from_defaults_to_none(db_session):
    source = Source(name="BF", domain=f"bf-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.commit()

    assert source.discover_backfilled_from is None
```

- [ ] **Step 5: Chạy test**

Run: `docker compose exec backend pytest backend/tests/test_scheduler_models.py -v`
Expected: PASS toàn bộ (test mới + test cũ trong file không bị ảnh hưởng)

- [ ] **Step 6: Commit**

```bash
git add backend/models/sources.py backend/alembic/versions/0025_add_sources_discover_backfilled_from.py backend/tests/test_scheduler_models.py
git commit -m "feat: thêm sources.discover_backfilled_from cho cơ chế backfill Discover CONTINUOUS"
```

---

### Task 3: Validate cap 180 ngày cho `start_date` Campaign CONTINUOUS

**Files:**
- Modify: `backend/routers/campaigns.py`
- Test: `backend/tests/test_campaigns_router.py`

**Interfaces:**
- Produces: hàm `_validate_continuous_start_date(mode: str, start_date_value) -> None` trong `campaigns.py` — raise `HTTPException(400, ...)` nếu `mode == "CONTINUOUS"` và `start_date_value` cũ hơn 180 ngày trước hôm nay. Nhận `start_date_value` dạng `str` (payload) hoặc `datetime`/`date` (đã load từ DB) — cùng kiểu polymorphism như `_validate_one_shot_date_range` đã có.

- [ ] **Step 1: Viết hàm validate**

Trong `backend/routers/campaigns.py`, thêm ngay sau hàm `_validate_one_shot_date_range` hiện có (kết thúc ở dòng chứa `)` đóng của raise thứ 2, trước `def _campaign_source_ids`):
```python
_MAX_CONTINUOUS_START_DATE_DAYS = 180


def _validate_continuous_start_date(mode: str, start_date_value) -> None:
    """BR-CAMP mới (2026-07-23): CONTINUOUS chỉ chấp nhận start_date trong vòng
    _MAX_CONTINUOUS_START_DATE_DAYS ngày trước hôm nay — Discover backfill bị cap cùng
    ngưỡng này (continuous_crawl.py _MAX_CONTINUOUS_BACKFILL_DAYS, giá trị trùng 180
    nhưng KHÔNG chia sẻ qua import, tránh phụ thuộc chéo router/worker không cần thiết).
    Chặn cứng ở đây để người dùng biết ngay giới hạn, không bị cap ngầm lúc backfill."""
    if mode != "CONTINUOUS":
        return
    if start_date_value is None:
        return  # start_date bắt buộc đã validate riêng ở BR-CAMP-01, không lặp lại ở đây
    if isinstance(start_date_value, str):
        parsed = date.fromisoformat(start_date_value)
    elif isinstance(start_date_value, datetime):
        parsed = start_date_value.date()
    else:
        parsed = start_date_value
    floor = date.today() - timedelta(days=_MAX_CONTINUOUS_START_DATE_DAYS)
    if parsed < floor:
        raise HTTPException(
            status_code=400,
            detail=f"Chiến dịch giám sát liên tục (CONTINUOUS) chỉ chấp nhận Ngày bắt đầu trong vòng {_MAX_CONTINUOUS_START_DATE_DAYS} ngày trước hôm nay",
        )
```

- [ ] **Step 2: Gọi validate trong `create_campaign`**

Sửa dòng:
```python
    if payload.mode not in _VALID_MODES:
        raise HTTPException(status_code=400, detail=f"mode phải là 1 trong {_VALID_MODES}")
    _validate_one_shot_date_range(payload.mode, payload.end_date)
```
thành:
```python
    if payload.mode not in _VALID_MODES:
        raise HTTPException(status_code=400, detail=f"mode phải là 1 trong {_VALID_MODES}")
    _validate_one_shot_date_range(payload.mode, payload.end_date)
    _validate_continuous_start_date(payload.mode, payload.start_date)
```

- [ ] **Step 3: Gọi validate trong `update_campaign`**

Sửa dòng:
```python
    _validate_one_shot_date_range(campaign.mode, campaign.end_date)

    if payload.source_ids is not None:
```
thành:
```python
    _validate_one_shot_date_range(campaign.mode, campaign.end_date)
    _validate_continuous_start_date(campaign.mode, campaign.start_date)

    if payload.source_ids is not None:
```

- [ ] **Step 4: Gọi validate trong `activate_campaign`**

Sửa dòng:
```python
    _validate_one_shot_date_range(campaign.mode, campaign.end_date)

    # BR-CAMP-03: chỉ chuyển ACTIVE khi có >=1 nguồn VÀ >=1 từ khóa
```
thành:
```python
    _validate_one_shot_date_range(campaign.mode, campaign.end_date)
    _validate_continuous_start_date(campaign.mode, campaign.start_date)

    # BR-CAMP-03: chỉ chuyển ACTIVE khi có >=1 nguồn VÀ >=1 từ khóa
```

- [ ] **Step 5: Viết test**

Thêm vào cuối `backend/tests/test_campaigns_router.py`:
```python
def test_create_continuous_campaign_rejects_start_date_older_than_180_days(app_client, admin_user):
    too_old = (date.today() - timedelta(days=200)).isoformat()
    response = app_client.post(
        "/api/campaigns",
        json={"name": "C", "owner_id": str(admin_user.user_id), "start_date": too_old, "mode": "CONTINUOUS"},
    )
    assert response.status_code == 400
    assert "180" in response.json()["detail"]


def test_create_continuous_campaign_accepts_start_date_within_180_days(app_client, admin_user):
    ok_date = (date.today() - timedelta(days=170)).isoformat()
    response = app_client.post(
        "/api/campaigns",
        json={"name": "C", "owner_id": str(admin_user.user_id), "start_date": ok_date, "mode": "CONTINUOUS"},
    )
    assert response.status_code == 201


def test_update_campaign_to_continuous_with_old_start_date_rejected(app_client, admin_user, db_session):
    too_old = date.today() - timedelta(days=200)
    campaign = Campaign(
        name="C", start_date=too_old, end_date=too_old, status="DRAFT", owner_id=admin_user.user_id, mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.commit()

    response = app_client.put(f"/api/campaigns/{campaign.campaign_id}", json={"mode": "CONTINUOUS"})

    assert response.status_code == 400
    assert "180" in response.json()["detail"]


def test_activate_continuous_campaign_with_old_start_date_rejected(app_client, admin_user, source, keyword, db_session):
    # Campaign cũ tạo trước khi có validate này (ORM thẳng, bỏ qua create endpoint) —
    # activate vẫn phải chặn (defense-in-depth, đúng pattern _validate_one_shot_date_range)
    too_old = date.today() - timedelta(days=200)
    campaign = Campaign(
        name="C", start_date=too_old, status="DRAFT", owner_id=admin_user.user_id, mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.commit()

    response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 400
    assert "180" in response.json()["detail"]
```

- [ ] **Step 6: Chạy test**

Run: `docker compose exec backend pytest backend/tests/test_campaigns_router.py -v -k "180"`
Expected: PASS toàn bộ 4 test

- [ ] **Step 7: Chạy toàn bộ test router (xác nhận không phá vỡ test CONTINUOUS có sẵn — chú ý các test dùng `start_date="2026-06-01"` cố định vẫn còn nằm trong 180 ngày tính từ ngày chạy test thật, KHÔNG cần sửa nếu ngày hệ thống hiện tại nằm trong khoảng an toàn — nếu FAIL vì lý do này, sửa các test đó dùng `date.today() - timedelta(days=N)` thay vì ngày cố định)**

Run: `docker compose exec backend pytest backend/tests/test_campaigns_router.py -v`
Expected: PASS toàn bộ. Nếu có test cũ FAIL do `start_date` cố định (VD `"2026-06-01"`) nay đã cách hôm nay hơn 180 ngày, sửa test đó dùng ngày động (`(date.today() - timedelta(days=30)).isoformat()`) thay vì hardcode — không đổi ý nghĩa test, chỉ đổi cách sinh ngày để test không phụ thuộc thời điểm chạy.

- [ ] **Step 8: Commit**

```bash
git add backend/routers/campaigns.py backend/tests/test_campaigns_router.py
git commit -m "feat: validate start_date CONTINUOUS trong vòng 180 ngày trước hôm nay"
```

---

### Task 4: Logic mới trong `discover_source_urls` — union + backfill + atomic update

**Files:**
- Modify: `backend/workers/continuous_crawl.py`
- Test: `backend/tests/test_continuous_crawl.py`

**Interfaces:**
- Consumes: `Campaign`, `CampaignSource` (đã import sẵn trong `continuous_crawl.py`), model `Source.discover_backfilled_from` (Task 2).
- Produces: hàm mới `_compute_required_floor(db, source: Source, today: date) -> date`. `discover_source_urls(db, source, today=None)` — **giữ nguyên chữ ký**, đổi logic tính `date_from` bên trong.

- [ ] **Step 1: Thêm import cần thiết**

Sửa dòng đầu `backend/workers/continuous_crawl.py`:
```python
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
```
thành:
```python
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
```

- [ ] **Step 2: Viết test cho `_compute_required_floor` (test phải FAIL trước khi implement)**

Thêm vào cuối `backend/tests/test_continuous_crawl.py`:
```python
from datetime import timedelta

from backend.models import Campaign, CampaignSource
from backend.workers.continuous_crawl import _compute_required_floor


def _make_continuous_campaign(db_session, start_date, status="ACTIVE"):
    campaign = Campaign(name=f"C-{uuid.uuid4()}", start_date=start_date, status=status, mode="CONTINUOUS")
    db_session.add(campaign)
    db_session.flush()
    return campaign


def test_compute_required_floor_returns_earliest_active_campaign_start_date(db_session):
    source = Source(name="RF1", domain=f"rf1-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.flush()
    today = date(2026, 7, 23)
    campaign_a = _make_continuous_campaign(db_session, date(2026, 6, 1))  # 52 ngày trước
    campaign_b = _make_continuous_campaign(db_session, date(2026, 7, 13))  # 10 ngày trước
    db_session.add(CampaignSource(campaign_id=campaign_a.campaign_id, source_id=source.source_id))
    db_session.add(CampaignSource(campaign_id=campaign_b.campaign_id, source_id=source.source_id))
    db_session.commit()

    floor = _compute_required_floor(db_session, source, today)

    assert floor == date(2026, 6, 1)  # mốc xa nhất (A), không phải B


def test_compute_required_floor_ignores_paused_campaign(db_session):
    source = Source(name="RF2", domain=f"rf2-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.flush()
    today = date(2026, 7, 23)
    campaign_a = _make_continuous_campaign(db_session, date(2026, 6, 1), status="PAUSED")
    campaign_b = _make_continuous_campaign(db_session, date(2026, 7, 13), status="ACTIVE")
    db_session.add(CampaignSource(campaign_id=campaign_a.campaign_id, source_id=source.source_id))
    db_session.add(CampaignSource(campaign_id=campaign_b.campaign_id, source_id=source.source_id))
    db_session.commit()

    floor = _compute_required_floor(db_session, source, today)

    assert floor == date(2026, 7, 13)  # A đang PAUSED, không tính


def test_compute_required_floor_caps_at_180_days(db_session):
    source = Source(name="RF3", domain=f"rf3-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.flush()
    today = date(2026, 7, 23)
    campaign = _make_continuous_campaign(db_session, date(2025, 1, 1))  # rất xa, quá 180 ngày
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    floor = _compute_required_floor(db_session, source, today)

    assert floor == today - timedelta(days=180)


def test_compute_required_floor_defaults_to_incremental_when_no_campaign_active(db_session):
    source = Source(name="RF4", domain=f"rf4-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.commit()
    today = date(2026, 7, 23)

    floor = _compute_required_floor(db_session, source, today)

    assert floor == today - timedelta(days=5)  # _INCREMENTAL_LOOKBACK_DAYS
```

- [ ] **Step 3: Chạy test, xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_continuous_crawl.py -k required_floor -v`
Expected: FAIL với `ImportError` (`_compute_required_floor` chưa tồn tại)

- [ ] **Step 4: Viết `_compute_required_floor` + đổi hằng số cũ**

Trong `backend/workers/continuous_crawl.py`, sửa khối:
```python
# Discover không giới hạn CỨNG theo date_from/date_to như Job on-demand — nhưng KHÔNG
# quét từ "vô hạn trong quá khứ" (đã thử date(2000,1,1) và phát hiện bug thật: với
# nguồn dùng _SITEMAP_URL_TEMPLATES sinh 1 URL sub-sitemap/tháng — VD vtv.vn — quét từ
# năm 2000 tạo ra ~300+ request HTTP mỗi chu kỳ, vi phạm nguyên tắc "không spam
# request" và có nguy cơ bị chặn IP — xem CLAUDE.md, phát hiện lúc smoke test thật
# 2026-07-21). Dùng cửa sổ trượt (rolling window) N ngày gần nhất tính từ `today` —
# đủ rộng để không bỏ lỡ bài nếu 1 chu kỳ bị gián đoạn vài ngày liên tiếp, chống
# trùng đã có crawl_queue lo (ON CONFLICT DO NOTHING).
_DISCOVER_LOOKBACK_DAYS = 30
```
thành:
```python
# [SỬA 2026-07-23] Trước đây Discover luôn dùng cửa sổ trượt 30 ngày cố định tính từ
# `today`, không quan tâm start_date của Campaign nào — bài đăng trước cửa sổ này
# không bao giờ được match (match_campaigns_for_article chỉ chạy trên bài MỚI fetch,
# không hồi tố). Giờ Discover tính động: hợp (union) start_date của mọi Campaign
# CONTINUOUS ACTIVE đang theo dõi Nguồn này (xem _compute_required_floor), cap tối đa
# _MAX_CONTINUOUS_BACKFILL_DAYS ngày (lưới an toàn thứ 2, dù đã chặn cứng lúc tạo/kích
# hoạt Campaign — xem routers/campaigns.py _validate_continuous_start_date). Khi không
# cần backfill (đã quét đủ xa từ trước, xem sources.discover_backfilled_from), dùng
# cửa sổ hẹp _INCREMENTAL_LOOKBACK_DAYS ngày — giữ tinh thần "tự phục hồi nếu Beat gián
# đoạn vài ngày" của cửa sổ 30 ngày gốc (Phase 3), chỉ thu hẹp vì phần "phủ xa theo
# Campaign" đã tách thành cơ chế backfill riêng.
_INCREMENTAL_LOOKBACK_DAYS = 5
_MAX_CONTINUOUS_BACKFILL_DAYS = 180


def _compute_required_floor(db, source: Source, today: date) -> date:
    """MIN(start_date) trong số Campaign CONTINUOUS đang ACTIVE theo dõi Nguồn này, cap
    tối đa _MAX_CONTINUOUS_BACKFILL_DAYS ngày trước `today`. Nếu không có Campaign nào
    (trường hợp hiếm — crawl_task chỉ được dispatch cho Nguồn đã qua list_due_sources,
    tức đã có ít nhất 1 Campaign ACTIVE), trả về cửa sổ incremental mặc định."""
    earliest_start = (
        db.query(func.min(Campaign.start_date))
        .join(CampaignSource, CampaignSource.campaign_id == Campaign.campaign_id)
        .filter(
            CampaignSource.source_id == source.source_id,
            Campaign.status == "ACTIVE",
            Campaign.mode == "CONTINUOUS",
        )
        .scalar()
    )
    if earliest_start is None:
        return today - timedelta(days=_INCREMENTAL_LOOKBACK_DAYS)
    earliest_start_date = earliest_start.date() if isinstance(earliest_start, datetime) else earliest_start
    floor_cap = today - timedelta(days=_MAX_CONTINUOUS_BACKFILL_DAYS)
    return max(earliest_start_date, floor_cap)
```

- [ ] **Step 5: Chạy lại test, xác nhận PASS**

Run: `docker compose exec backend pytest backend/tests/test_continuous_crawl.py -k required_floor -v`
Expected: PASS toàn bộ 4 test

- [ ] **Step 6: Viết test cho `discover_source_urls` — backfill vs incremental vs cập nhật mốc (test phải FAIL trước khi sửa hàm)**

Thêm vào cuối `backend/tests/test_continuous_crawl.py`:
```python
def test_discover_source_urls_uses_required_floor_when_backfill_needed(db_session, monkeypatch):
    source = Source(name="D1", domain=f"d1-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.flush()
    campaign = _make_continuous_campaign(db_session, date(2026, 6, 1))
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    captured = {}

    def fake_get_candidates(src, date_from, date_to):
        captured["date_from"] = date_from
        return [], []

    monkeypatch.setattr("backend.workers.continuous_crawl._get_candidates", fake_get_candidates)

    discover_source_urls(db_session, source, today=date(2026, 7, 23))

    assert captured["date_from"] == date(2026, 6, 1)  # backfill đúng tới start_date Campaign
    db_session.refresh(source)
    assert source.discover_backfilled_from.date() == date(2026, 6, 1)


def test_discover_source_urls_uses_incremental_window_when_already_backfilled(db_session, monkeypatch):
    source = Source(
        name="D2", domain=f"d2-{uuid.uuid4()}.example", group_name="G", is_active=True,
        discover_backfilled_from=date(2026, 6, 1),
    )
    db_session.add(source)
    db_session.flush()
    campaign = _make_continuous_campaign(db_session, date(2026, 7, 13))  # gần hơn mốc đã backfill
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    captured = {}

    def fake_get_candidates(src, date_from, date_to):
        captured["date_from"] = date_from
        return [], []

    monkeypatch.setattr("backend.workers.continuous_crawl._get_candidates", fake_get_candidates)

    discover_source_urls(db_session, source, today=date(2026, 7, 23))

    assert captured["date_from"] == date(2026, 7, 18)  # incremental 5 ngày, KHÔNG backfill lại
    db_session.refresh(source)
    assert source.discover_backfilled_from.date() == date(2026, 6, 1)  # mốc cũ giữ nguyên


def test_discover_source_urls_does_not_narrow_backfilled_from_after_campaign_leaves(db_session, monkeypatch):
    # Tái hiện đúng quyết định đã chốt: mốc backfill KHÔNG bao giờ co lại (nới gần hơn
    # hiện tại) dù Campaign từng cần mốc sâu nhất đã rời đi (Pause/Archive) — chạy 2 lượt
    # discover liên tiếp: lượt 1 backfill sâu (còn Campaign xa), lượt 2 Campaign đó đã
    # PAUSED (chỉ còn Campaign gần) — mốc phải giữ nguyên từ lượt 1
    source = Source(name="D3", domain=f"d3-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.flush()
    campaign_far = _make_continuous_campaign(db_session, date(2026, 6, 1))
    campaign_near = _make_continuous_campaign(db_session, date(2026, 7, 13))
    db_session.add(CampaignSource(campaign_id=campaign_far.campaign_id, source_id=source.source_id))
    db_session.add(CampaignSource(campaign_id=campaign_near.campaign_id, source_id=source.source_id))
    db_session.commit()

    monkeypatch.setattr("backend.workers.continuous_crawl._get_candidates", lambda src, date_from, date_to: ([], []))

    discover_source_urls(db_session, source, today=date(2026, 7, 23))
    db_session.refresh(source)
    assert source.discover_backfilled_from.date() == date(2026, 6, 1)

    campaign_far.status = "PAUSED"
    db_session.commit()

    discover_source_urls(db_session, source, today=date(2026, 7, 24))
    db_session.refresh(source)
    assert source.discover_backfilled_from.date() == date(2026, 6, 1)  # KHÔNG co lại về 2026-07-19


def test_discover_source_urls_updates_backfilled_from_even_when_no_candidates(db_session, monkeypatch):
    source = Source(name="D4", domain=f"d4-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.flush()
    campaign = _make_continuous_campaign(db_session, date(2026, 6, 1))
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    monkeypatch.setattr("backend.workers.continuous_crawl._get_candidates", lambda src, date_from, date_to: ([], []))

    inserted = discover_source_urls(db_session, source, today=date(2026, 7, 23))

    assert inserted == 0
    db_session.refresh(source)
    assert source.discover_backfilled_from.date() == date(2026, 6, 1)  # vẫn cập nhật dù 0 candidate
```

- [ ] **Step 7: Chạy test, xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_continuous_crawl.py -k "backfill or narrow" -v`
Expected: FAIL (hành vi cũ vẫn dùng cửa sổ 30 ngày cố định, không cập nhật `discover_backfilled_from`)

- [ ] **Step 8: Sửa `discover_source_urls`**

Sửa toàn bộ hàm:
```python
def discover_source_urls(db, source: Source, today: date | None = None) -> int:
    """Giai đoạn 1 (Discover): tìm URL ứng viên của nguồn (dùng _get_candidates ở trên
    — không đổi logic ưu tiên sitemap/listing), ghi vào crawl_queue. Trả về số URL MỚI
    vừa ghi (không tính URL đã có từ chu kỳ trước — ON CONFLICT DO NOTHING không ghi
    đè trạng thái cũ)."""
    today = today or date.today()
    date_from = today - timedelta(days=_DISCOVER_LOOKBACK_DAYS)
    candidates, _failed_locs = _get_candidates(source, date_from, today)

    if not candidates:
        return 0

    rows = [
        {
            "source_id": source.source_id,
            "url": c["url"],
            "url_hash": compute_url_hash(c["url"]),
            "status": "pending",
        }
        for c in candidates
    ]
    stmt = pg_insert(CrawlQueue).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["source_id", "url_hash"])
    result = db.execute(stmt)
    db.commit()
    return result.rowcount
```
thành:
```python
def discover_source_urls(db, source: Source, today: date | None = None) -> int:
    """Giai đoạn 1 (Discover): tìm URL ứng viên của nguồn (dùng _get_candidates ở trên
    — không đổi logic ưu tiên sitemap/listing), ghi vào crawl_queue. Trả về số URL MỚI
    vừa ghi (không tính URL đã có từ chu kỳ trước — ON CONFLICT DO NOTHING không ghi
    đè trạng thái cũ).

    [SỬA 2026-07-23] date_from giờ tính động theo _compute_required_floor thay vì cố
    định _DISCOVER_LOOKBACK_DAYS — xem comment ở _compute_required_floor. Cập nhật
    sources.discover_backfilled_from bằng UPDATE nguyên tử LEAST() SAU MỌI LƯỢT chạy
    (kể cả khi 0 candidate) — vì "đã Discover xong tới date_from" là sự thật bất kể có
    tìm thấy URL mới hay không; bỏ qua bước này sẽ khiến lượt sau lặp lại đúng backfill
    tốn kém vừa chạy. UPDATE nguyên tử (không đọc-rồi-ghi qua ORM) để 2 crawl_task cùng
    Nguồn chạy chồng lấn (race đã biết, từng gây bug thật ở fetch_pending_urls) không
    ghi đè nhầm lẫn lên nhau — LEAST() luôn giữ giá trị nhỏ nhất (xa nhất về quá khứ)
    dù 2 UPDATE chạy theo thứ tự nào."""
    today = today or date.today()
    backfilled_from = source.discover_backfilled_from
    backfilled_from_date = backfilled_from.date() if isinstance(backfilled_from, datetime) else backfilled_from

    required_floor = _compute_required_floor(db, source, today)
    if backfilled_from_date is None or required_floor < backfilled_from_date:
        date_from = required_floor
    else:
        date_from = today - timedelta(days=_INCREMENTAL_LOOKBACK_DAYS)

    candidates, _failed_locs = _get_candidates(source, date_from, today)

    inserted = 0
    if candidates:
        rows = [
            {
                "source_id": source.source_id,
                "url": c["url"],
                "url_hash": compute_url_hash(c["url"]),
                "status": "pending",
            }
            for c in candidates
        ]
        stmt = pg_insert(CrawlQueue).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["source_id", "url_hash"])
        result = db.execute(stmt)
        inserted = result.rowcount

    db.execute(
        text(
            "UPDATE sources "
            "SET discover_backfilled_from = LEAST(COALESCE(discover_backfilled_from, :date_from), :date_from) "
            "WHERE source_id = :source_id"
        ),
        {"date_from": date_from, "source_id": source.source_id},
    )
    db.commit()
    return inserted
```

- [ ] **Step 9: Chạy lại test, xác nhận PASS**

Run: `docker compose exec backend pytest backend/tests/test_continuous_crawl.py -v`
Expected: PASS toàn bộ (kể cả 3 test Discover gốc `test_discover_source_urls_inserts_new_pending_rows`/`_skips_already_known_url`/`_returns_zero_when_no_candidates` — không có Campaign nào theo dõi Nguồn trong các test đó nên `_compute_required_floor` trả về cửa sổ incremental mặc định, hành vi dedup/insert không đổi)

- [ ] **Step 10: Chạy toàn bộ test suite backend**

Run: `docker compose exec backend pytest backend/tests/ -q`
Expected: PASS toàn bộ, không có test nào khác bị ảnh hưởng (Fetch/Matching/AI không đổi)

- [ ] **Step 11: Commit**

```bash
git add backend/workers/continuous_crawl.py backend/tests/test_continuous_crawl.py
git commit -m "feat: Discover CONTINUOUS tính cửa sổ theo hợp khoảng ngày Campaign, backfill 1 lần + ghi nhớ mốc"
```

---

### Task 5: Smoke test Docker thật

**Files:** không có file mới — chỉ vận hành hệ thống thật qua Docker để verify.

- [ ] **Step 1: Rebuild + restart backend/celery-worker/celery-beat**

Run: `docker compose up -d --build backend celery-worker celery-beat`
Expected: cả 3 container `healthy`/`Up`

- [ ] **Step 2: Chạy toàn bộ test suite backend 1 lần cuối trong container thật**

Run: `docker compose exec backend pytest backend/tests/ -v`
Expected: PASS toàn bộ

- [ ] **Step 3: Xác nhận Task 1 đã chạy đúng trên DB dev thật (không phải chỉ DB test)**

Run: `docker compose exec -T postgres psql -U ngs -d ngs_monitor -c "select count(*) from campaigns; select count(*) from sources;"`
Expected: `campaigns=0`, `sources > 0` (nếu Task 1 chưa chạy trên DB dev thật vì lý do nào đó, dừng lại và chạy Task 1 Step 3 trước khi tiếp tục)

- [ ] **Step 4: Bật `SCHEDULER_ENABLED` (Admin, `/system/settings`)**

Thao tác thủ công: đăng nhập UI → `/system/settings` → bật "Giám sát liên tục".
Expected: `GET /api/system-settings` trả `SCHEDULER_ENABLED=true`.

- [ ] **Step 5: Tạo 2 Campaign CONTINUOUS thật, cùng theo dõi 1 Nguồn, khác `start_date`**

Thao tác thủ công: tạo Campaign A (`start_date` = 60 ngày trước, ≥1 từ khóa) và Campaign B (`start_date` = 5 ngày trước, ≥1 từ khóa khác) — cả 2 cùng chọn 1 Nguồn (VD VTV News). Kích hoạt cả 2.
Expected: cả 2 kích hoạt thành công (không bị chặn 180 ngày, không bị chặn `SCHEDULER_ENABLED`).

- [ ] **Step 6: Quan sát chu kỳ Discover đầu tiên**

Run: `docker compose logs celery-worker --since 5m -f` (theo dõi log lúc chu kỳ Beat tới hạn, tối đa 60s)
Expected: log Discover cho Nguồn đó chạy 1 lần, không chạy 2 lần trùng lặp cho 2 Campaign.

Run sau khi chu kỳ chạy xong: `docker compose exec -T postgres psql -U ngs -d ngs_monitor -c "select discover_backfilled_from from sources where name='VTV News';"`
Expected: giá trị = đúng ngày `start_date` của Campaign A (60 ngày trước), không phải 30 ngày như cơ chế cũ.

- [ ] **Step 7: Xác nhận bài cũ hơn 5 ngày (nằm trong phạm vi backfill) được match vào Campaign A**

Đợi ≥1 chu kỳ Fetch hoàn tất, sau đó kiểm tra:
Run: `docker compose exec -T postgres psql -U ngs -d ngs_monitor -c "select count(*) from campaign_articles ca join campaigns c on c.campaign_id=ca.campaign_id where c.name = '<tên Campaign A>';"`
Expected: > 0 nếu có bài thật khớp từ khóa đã chọn trong phạm vi 60 ngày (nếu = 0, kiểm tra lại từ khóa có xuất hiện trong nội dung thật của Nguồn hay không trước khi coi là lỗi — đây KHÔNG phải bug nếu từ khóa chọn quá hiếm, xem bài học từ smoke test ONE_SHOT trước đó).
