# Campaign — giới hạn phạm vi crawl ONE_SHOT, tự dừng CONTINUOUS, tiến độ crawl — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sửa 3 gap thật phát hiện qua smoke test Docker đầu tiên của Phase 7: ONE_SHOT Campaign hiện crawl backlog toàn cục của Nguồn thay vì đúng phạm vi ngày đã chọn; CONTINUOUS không tự dừng khi tới `end_date`; người dùng không thấy được tiến độ crawl thật của Campaign đang xem.

**Architecture:** Tách 1 đường crawl Celery riêng cho ONE_SHOT (`campaign_tasks.crawl_campaign_source_once`) — Discover đúng `date_from`/`date_to` của Campaign, tái sử dụng `Article` đã có sẵn (theo `url_hash`) thay vì fetch lại, ghi tiến độ vào bảng mới `campaign_crawl_progress`. CONTINUOUS tự chuyển `COMPLETED` qua 1 bước thêm vào task Beat có sẵn `check_due_sources`. FE thêm 1 Card "Tiến độ crawl" trong `CampaignDetail.tsx`, đọc từ endpoint mới `GET /api/campaigns/{id}/crawl-progress` (nội dung khác nhau theo `mode`).

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Celery (`chord`), pytest (fixture `db_session` — transaction rollback per test), React + AntD (Vite, không dùng react-query/zustand).

## Global Constraints

- Không đụng `continuous_crawl.crawl_task`/`fetch_pending_urls`/`discover_source_urls` hiện có (dùng cho CONTINUOUS) — chỉ thêm 1 đường xử lý mới song song cho ONE_SHOT, không refactor lại cơ chế cũ.
- Mọi task Celery mới phải theo đúng "thin wrapper" pattern đã chốt trong dự án: hàm `_xxx(db, ...)` chứa logic thật (test gọi thẳng qua fixture `db_session`, không patch `SessionLocal`), hàm `@celery_app.task` chỉ mở/đóng `SessionLocal()` rồi gọi hàm trong.
- Mọi task Celery là thành viên của `chord` (ONE_SHOT) không được để exception thoát ra ngoài — nếu raise, callback `mark_crawl_done` không chạy, Campaign kẹt `ACTIVE` mãi (bug thật đã tìm và sửa ở Phase 7 final review, xem `backend/workers/continuous_crawl.py` `crawl_task`).
- Không tạo circular import: gọi hàm của `continuous_crawl.py` từ `campaign_tasks.py` qua `from backend.workers import continuous_crawl` (bind module, gọi `continuous_crawl.tên_hàm(...)` bên trong hàm) — **không** `from backend.workers.continuous_crawl import tên_hàm` ở top-level (rủi ro cycle qua `celery_app.py`, xem comment trong `scheduler.py`).
- Test mock delay crawl bằng `monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")` — không để test thật sự `time.sleep(1.5)`.
- Ngày hôm nay dùng trong toàn bộ plan này: hệ thống chạy với `date.today()`/`datetime.now(timezone.utc)` thật của server — không hardcode ngày cụ thể trong code (chỉ test data dùng ngày cố định trong quá khứ, an toàn với mọi thời điểm chạy CI).

---

### Task 1: Model + migration `campaign_crawl_progress`

**Files:**
- Create: `backend/models/campaign_crawl_progress.py`
- Modify: `backend/models/__init__.py`
- Create: `backend/alembic/versions/0022_add_campaign_crawl_progress.py`
- Test: `backend/tests/test_campaign_tasks.py` (thêm vào cuối file)

**Interfaces:**
- Produces: `CampaignCrawlProgress` model — cột `campaign_id` (UUID, FK `campaigns.campaign_id`, PK), `source_id` (UUID, FK `sources.source_id`, PK), `total_urls` (Integer, nullable), `done_urls` (Integer, default 0), `status` (String(20), default `'pending'`), `updated_at` (TIMESTAMP, default `now()`). Export tên `CampaignCrawlProgress` từ `backend.models`.

- [ ] **Step 1: Viết model**

`backend/models/campaign_crawl_progress.py`:
```python
from sqlalchemy import Column, ForeignKey, Integer, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class CampaignCrawlProgress(Base):
    __tablename__ = "campaign_crawl_progress"

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.campaign_id"), primary_key=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.source_id"), primary_key=True)
    total_urls = Column(Integer)
    done_urls = Column(Integer, server_default="0")
    status = Column(String(20), server_default="pending")
    updated_at = Column(TIMESTAMP, server_default=func.now())
```

- [ ] **Step 2: Đăng ký model trong `backend/models/__init__.py`**

Thêm dòng import (giữ đúng thứ tự alphabet của file, chèn sau dòng `from backend.models.campaign_articles import CampaignArticle`):
```python
from backend.models.campaign_crawl_progress import CampaignCrawlProgress
```
Thêm `"CampaignCrawlProgress",` vào list `__all__` (chèn sau `"CampaignArticle",`).

- [ ] **Step 3: Viết migration**

`backend/alembic/versions/0022_add_campaign_crawl_progress.py`:
```python
"""thêm bảng campaign_crawl_progress — theo dõi tiến độ crawl từng Source của Campaign
ONE_SHOT (Discover xong bao nhiêu URL, đã fetch/tái sử dụng xong bao nhiêu) để FE hiển
thị progress UI trực quan thay vì chỉ thấy status=ACTIVE chung chung

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "campaign_crawl_progress",
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.campaign_id"), primary_key=True),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("sources.source_id"), primary_key=True),
        sa.Column("total_urls", sa.Integer),
        sa.Column("done_urls", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.text("now()")),
    )


def downgrade():
    op.drop_table("campaign_crawl_progress")
```

- [ ] **Step 4: Chạy migration trên DB test/dev qua Docker**

Run: `docker compose exec backend alembic upgrade head`
Expected: log hiện `Running upgrade 0021 -> 0022`, không lỗi.

Run: `docker compose exec backend alembic downgrade -1 && docker compose exec backend alembic upgrade head`
Expected: cả 2 lệnh chạy sạch, không lỗi — xác nhận `downgrade()` đúng.

- [ ] **Step 5: Viết test roundtrip**

Thêm vào cuối `backend/tests/test_campaign_tasks.py`:
```python
from backend.models import CampaignCrawlProgress


def test_campaign_crawl_progress_model_roundtrip(db_session):
    campaign = _make_campaign(db_session)
    source = _make_source(db_session)
    db_session.add(CampaignCrawlProgress(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    row = db_session.query(CampaignCrawlProgress).filter_by(campaign_id=campaign.campaign_id).one()
    assert row.source_id == source.source_id
    assert row.total_urls is None
    assert row.done_urls == 0
    assert row.status == "pending"
```

- [ ] **Step 6: Chạy test**

Run: `docker compose exec backend pytest backend/tests/test_campaign_tasks.py::test_campaign_crawl_progress_model_roundtrip -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/models/campaign_crawl_progress.py backend/models/__init__.py backend/alembic/versions/0022_add_campaign_crawl_progress.py backend/tests/test_campaign_tasks.py
git commit -m "feat: thêm bảng campaign_crawl_progress cho tiến độ crawl ONE_SHOT"
```

---

### Task 2: Validate `end_date` bắt buộc, `<= hôm nay` cho ONE_SHOT

**Files:**
- Modify: `backend/routers/campaigns.py`
- Test: `backend/tests/test_campaigns_router.py`

**Interfaces:**
- Produces: hàm `_validate_one_shot_date_range(mode: str, end_date_value) -> None` trong `campaigns.py` — raise `HTTPException(400, ...)` nếu `mode == "ONE_SHOT"` và `end_date_value` là `None`, hoặc là ngày ở tương lai. `end_date_value` nhận cả `str` (ISO `"YYYY-MM-DD"`, từ payload) lẫn `datetime`/`None` (từ `campaign.end_date` đã load từ DB).

- [ ] **Step 1: Thêm import `date`/`datetime` vào đầu `backend/routers/campaigns.py`**

Sửa dòng đầu file (dòng 1), thêm ngay trước `import uuid`:
```python
from datetime import date, datetime
```

- [ ] **Step 2: Viết hàm validate**

Thêm ngay sau khai báo `_VALID_MODES = {"CONTINUOUS", "ONE_SHOT"}` (khoảng dòng 27):
```python
def _validate_one_shot_date_range(mode: str, end_date_value) -> None:
    """BR-CAMP mới (2026-07-22): ONE_SHOT chỉ dùng cho dữ liệu quá khứ — bắt buộc có
    end_date và end_date <= hôm nay. Nhận end_date_value dạng str (payload thô, ISO
    'YYYY-MM-DD') hoặc datetime/None (campaign.end_date đã load từ DB) để dùng chung
    được ở cả create/update (payload) lẫn activate (giá trị đã lưu)."""
    if mode != "ONE_SHOT":
        return
    if end_date_value is None:
        raise HTTPException(
            status_code=400,
            detail="Chiến dịch 'Tạo báo cáo nhanh' (ONE_SHOT) bắt buộc phải có Ngày kết thúc",
        )
    if isinstance(end_date_value, str):
        parsed = date.fromisoformat(end_date_value)
    elif isinstance(end_date_value, datetime):
        parsed = end_date_value.date()
    else:
        parsed = end_date_value
    if parsed > date.today():
        raise HTTPException(
            status_code=400,
            detail="Chiến dịch 'Tạo báo cáo nhanh' (ONE_SHOT) chỉ áp dụng cho khoảng ngày trong quá khứ (Ngày kết thúc phải <= hôm nay)",
        )
```

- [ ] **Step 3: Gọi validate trong `create_campaign`**

Trong `create_campaign`, ngay sau khối:
```python
    if payload.mode not in _VALID_MODES:
        raise HTTPException(status_code=400, detail=f"mode phải là 1 trong {_VALID_MODES}")
```
thêm ngay dòng tiếp theo:
```python
    _validate_one_shot_date_range(payload.mode, payload.end_date)
```

- [ ] **Step 4: Gọi validate trong `update_campaign`**

Trong `update_campaign`, sau toàn bộ khối gán `if payload.xxx is not None: campaign.xxx = ...` (ngay sau dòng `campaign.alert_threshold = payload.alert_threshold`, TRƯỚC khối `if payload.source_ids is not None:`), thêm:
```python
    _validate_one_shot_date_range(campaign.mode, campaign.end_date)
```

- [ ] **Step 5: Gọi validate trong `activate_campaign` (defense-in-depth)**

Trong `activate_campaign`, ngay sau dòng:
```python
    if campaign.status not in ("DRAFT", "PAUSED"):
        raise HTTPException(
            status_code=400,
            detail=f"Không thể kích hoạt chiến dịch đang ở trạng thái {campaign.status}",
        )
```
thêm:
```python
    _validate_one_shot_date_range(campaign.mode, campaign.end_date)
```

- [ ] **Step 6: Cập nhật test có sẵn bị ảnh hưởng**

`test_activate_one_shot_campaign_dispatches_chord` (`backend/tests/test_campaigns_router.py`) hiện tạo Campaign `mode="ONE_SHOT"` không có `end_date` — sẽ vỡ vì validate mới. Sửa dòng khởi tạo Campaign trong test này thành:
```python
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="ONE_SHOT"
    )
```
(giữ nguyên toàn bộ phần còn lại của test không đổi.)

- [ ] **Step 7: Viết test mới cho validate**

Thêm vào cuối `backend/tests/test_campaigns_router.py`:
```python
def test_create_one_shot_campaign_requires_end_date(app_client, admin_user):
    response = app_client.post(
        "/api/campaigns",
        json={"name": "C", "owner_id": str(admin_user.user_id), "start_date": "2026-06-01", "mode": "ONE_SHOT"},
    )
    assert response.status_code == 400
    assert "Ngày kết thúc" in response.json()["detail"]


def test_create_one_shot_campaign_rejects_future_end_date(app_client, admin_user):
    response = app_client.post(
        "/api/campaigns",
        json={
            "name": "C", "owner_id": str(admin_user.user_id), "start_date": "2026-06-01",
            "end_date": "2099-01-01", "mode": "ONE_SHOT",
        },
    )
    assert response.status_code == 400
    assert "quá khứ" in response.json()["detail"]


def test_create_one_shot_campaign_accepts_past_end_date(app_client, admin_user):
    response = app_client.post(
        "/api/campaigns",
        json={
            "name": "C", "owner_id": str(admin_user.user_id), "start_date": "2026-06-01",
            "end_date": "2026-06-05", "mode": "ONE_SHOT",
        },
    )
    assert response.status_code == 201


def test_create_continuous_campaign_does_not_require_end_date(app_client, admin_user):
    response = app_client.post(
        "/api/campaigns",
        json={"name": "C", "owner_id": str(admin_user.user_id), "start_date": "2026-06-01", "mode": "CONTINUOUS"},
    )
    assert response.status_code == 201


def test_update_campaign_to_one_shot_without_end_date_rejected(app_client, admin_user, db_session):
    campaign = Campaign(name="C", start_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="CONTINUOUS")
    db_session.add(campaign)
    db_session.commit()

    response = app_client.put(f"/api/campaigns/{campaign.campaign_id}", json={"mode": "ONE_SHOT"})

    assert response.status_code == 400


def test_activate_one_shot_campaign_without_end_date_rejected(app_client, admin_user, source, keyword, db_session):
    # Campaign cũ tạo trước khi có validate này (ORM thẳng, bỏ qua create endpoint) —
    # activate vẫn phải chặn (defense-in-depth)
    campaign = Campaign(
        name="C", start_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.commit()

    response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 400
```

- [ ] **Step 8: Chạy toàn bộ test router**

Run: `docker compose exec backend pytest backend/tests/test_campaigns_router.py -v`
Expected: PASS toàn bộ, kể cả `test_activate_one_shot_campaign_dispatches_chord` đã sửa.

- [ ] **Step 9: Commit**

```bash
git add backend/routers/campaigns.py backend/tests/test_campaigns_router.py
git commit -m "feat: validate end_date bắt buộc + trong quá khứ cho Campaign ONE_SHOT"
```

---

### Task 3: Guard idempotent cho `match_campaigns_for_article`

**Files:**
- Modify: `backend/workers/continuous_crawl.py`
- Test: `backend/tests/test_continuous_crawl.py`

**Interfaces:**
- Consumes: không đổi chữ ký `match_campaigns_for_article(db, article: Article) -> None`.
- Produces: hàm không còn raise `IntegrityError` khi gọi 2 lần cho cùng `(campaign_id, article_id)`.

**Bối cảnh:** Task 4 (crawl ONE_SHOT) sẽ gọi lại hàm này cho bài viết "tái sử dụng" (đã tồn tại từ trước, có thể đã match Campaign này rồi nếu Campaign bị kích hoạt lại) — cần guard chống insert trùng trước khi Task 4 dùng tới.

- [ ] **Step 1: Viết test tái hiện lỗi (test phải FAIL trước khi sửa)**

Thêm vào cuối phần test của `match_campaigns_for_article` trong `backend/tests/test_continuous_crawl.py` (ngay sau `test_match_campaigns_for_article_ignores_non_active_campaign`):
```python
def test_match_campaigns_for_article_is_idempotent_when_called_twice(db_session):
    source = _make_source(db_session, "MatchIdem")
    campaign = Campaign(name="C", start_date="2026-08-01", status="ACTIVE")
    kw = Keyword(keyword="lừa đảo")
    db_session.add_all([campaign, kw])
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=kw.keyword_id))
    article = Article(source_id=source.source_id, url="https://mi.example/a", url_hash="hmi", title="Cảnh báo lừa đảo")
    db_session.add(article)
    db_session.commit()

    match_campaigns_for_article(db_session, article)
    match_campaigns_for_article(db_session, article)  # gọi lại lần 2 — không được raise

    rows = db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id, article_id=article.article_id).all()
    assert len(rows) == 1
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_continuous_crawl.py::test_match_campaigns_for_article_is_idempotent_when_called_twice -v`
Expected: FAIL với `sqlalchemy.exc.IntegrityError` (duplicate key `campaign_articles` PK)

- [ ] **Step 3: Thêm guard trong `match_campaigns_for_article`**

Trong `backend/workers/continuous_crawl.py`, hàm `match_campaigns_for_article`, sửa vòng lặp `for (campaign_id,) in campaign_ids:` — ngay sau dòng `matched = [k for k in keywords if k.keyword.lower() in haystack]` và trước `if not matched: continue`, thêm guard tồn tại:
```python
        matched = [k for k in keywords if k.keyword.lower() in haystack]
        if not matched:
            continue

        already_matched = (
            db.query(CampaignArticle)
            .filter_by(campaign_id=campaign_id, article_id=article.article_id)
            .first()
        )
        if already_matched is not None:
            continue

        db.add(
```
(dòng `db.add(` cuối cùng ở trên chính là dòng `db.add(CampaignArticle(...))` đã có sẵn ngay sau — chỉ chèn khối guard vào giữa, không đổi phần còn lại của hàm.)

- [ ] **Step 4: Chạy lại test, xác nhận PASS**

Run: `docker compose exec backend pytest backend/tests/test_continuous_crawl.py::test_match_campaigns_for_article_is_idempotent_when_called_twice -v`
Expected: PASS

- [ ] **Step 5: Chạy toàn bộ test file để đảm bảo không phá vỡ hành vi cũ**

Run: `docker compose exec backend pytest backend/tests/test_continuous_crawl.py -v`
Expected: PASS toàn bộ

- [ ] **Step 6: Commit**

```bash
git add backend/workers/continuous_crawl.py backend/tests/test_continuous_crawl.py
git commit -m "fix: match_campaigns_for_article idempotent khi gọi lại cho bài đã match"
```

---

### Task 4: Task Celery `crawl_campaign_source_once` (crawl scoped riêng cho ONE_SHOT)

**Files:**
- Modify: `backend/workers/campaign_tasks.py`
- Test: `backend/tests/test_campaign_tasks.py`

**Interfaces:**
- Consumes: `continuous_crawl._get_candidates(source, date_from, date_to) -> tuple[list[dict], list[str]]` (mỗi dict có key `"url"`), `continuous_crawl.match_campaigns_for_article(db, article)`, `compute_url_hash(url) -> str`, `fetch_article_dispatch(url, parsing_rules) -> dict | None`, model `CampaignCrawlProgress` (Task 1).
- Produces: hàm `_crawl_campaign_source_once(db: Session, campaign_id: str, source_id: str, date_from: str, date_to: str) -> None` (logic thật, test gọi thẳng) và task `campaign_tasks.crawl_campaign_source_once` (`@celery_app.task`, chữ ký `(campaign_id: str, source_id: str, date_from: str, date_to: str)`) — dùng ở Task 5 trong `chord`.

- [ ] **Step 1: Thêm import cần thiết vào đầu `backend/workers/campaign_tasks.py`**

Thêm các import sau vào đầu file (giữ nguyên các import hiện có, chèn thêm):
```python
import time

from sqlalchemy.exc import IntegrityError

from backend.crawler.article import compute_url_hash
from backend.crawler.crawl4ai_client import fetch_article_dispatch
from backend.models import CampaignCrawlProgress, Source
from backend.workers import continuous_crawl
```
(`Article`, `Campaign`, `CampaignArticle`, `ReportHistory` đã import sẵn từ `backend.models` ở dòng có sẵn — chỉ cần thêm `CampaignCrawlProgress, Source` vào đúng dòng import đó, không tạo dòng import trùng `from backend.models import ...` thứ 2.)

- [ ] **Step 2: Viết test cho luồng "Discover rồi fetch mới" (test phải FAIL trước khi implement)**

Thêm vào cuối `backend/tests/test_campaign_tasks.py`:
```python
from unittest.mock import patch

from backend.models import CampaignArticle, CampaignKeyword, CampaignSource, CrawlQueue, Keyword
from backend.workers.campaign_tasks import _crawl_campaign_source_once


def _make_campaign_with_source_and_keyword(db_session, keyword_text="lừa đảo"):
    campaign = _make_campaign(db_session)
    source = _make_source(db_session)
    kw = Keyword(keyword=keyword_text)
    db_session.add(kw)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=kw.keyword_id))
    db_session.commit()
    return campaign, source


def test_crawl_campaign_source_once_fetches_new_candidates_and_tracks_progress(db_session, monkeypatch):
    campaign, source = _make_campaign_with_source_and_keyword(db_session)
    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")
    monkeypatch.setattr(
        "backend.workers.continuous_crawl._get_candidates",
        lambda src, date_from, date_to: ([{"url": "https://x.example/bai-1"}], []),
    )
    monkeypatch.setattr(
        "backend.workers.campaign_tasks.fetch_article_dispatch",
        lambda url, rules: {
            "url": url, "url_hash": "hash-bai-1", "title": "Cảnh báo lừa đảo", "content_raw": "Nội dung",
            "author": None, "published_at": None, "crawl_duration_seconds": 0.1,
        },
    )

    _crawl_campaign_source_once(db_session, str(campaign.campaign_id), str(source.source_id), "2026-06-01", "2026-06-05")

    article = db_session.query(Article).filter_by(source_id=source.source_id, url_hash="hash-bai-1").one()
    assert article.title == "Cảnh báo lừa đảo"
    ca = db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id, article_id=article.article_id).one()
    assert ca is not None

    progress = db_session.query(CampaignCrawlProgress).filter_by(
        campaign_id=campaign.campaign_id, source_id=source.source_id
    ).one()
    assert progress.total_urls == 1
    assert progress.done_urls == 1
    assert progress.status == "done"
```

- [ ] **Step 3: Chạy test, xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_campaign_tasks.py::test_crawl_campaign_source_once_fetches_new_candidates_and_tracks_progress -v`
Expected: FAIL với `ImportError`/`AttributeError` (`_crawl_campaign_source_once` chưa tồn tại)

- [ ] **Step 4: Viết `_crawl_campaign_source_once` + task wrapper**

Thêm vào cuối `backend/workers/campaign_tasks.py`:
```python
def _crawl_campaign_source_once(db: Session, campaign_id: str, source_id: str, date_from: str, date_to: str) -> None:
    """Logic thật của crawl_campaign_source_once — tách khỏi mở/đóng session để test gọi
    thẳng với fixture db_session. Đường crawl RIÊNG cho ONE_SHOT (khác continuous_crawl.
    crawl_task dùng cho CONTINUOUS): Discover đúng [date_from, date_to] của Campaign
    (không qua cửa sổ 30 ngày cố định), với mỗi URL — đã có Article thì tái sử dụng
    (không fetch lại), chưa có thì fetch mới. Không tự phục hồi nếu crash giữa chừng
    (khác CONTINUOUS) — kích hoạt lại Campaign là đủ, nhờ cơ chế tái sử dụng ở trên nên
    crawl lại rẻ. Bọc try/except toàn bộ để không phá chord (xem crawl_task."""
    campaign_uuid = uuid.UUID(campaign_id)
    source_uuid = uuid.UUID(source_id)

    progress = db.get(CampaignCrawlProgress, (campaign_uuid, source_uuid))
    if progress is None:
        progress = CampaignCrawlProgress(campaign_id=campaign_uuid, source_id=source_uuid)
        db.add(progress)

    try:
        source = db.get(Source, source_uuid)
        if source is None:
            return

        progress.status = "discovering"
        progress.done_urls = 0
        db.commit()

        parsed_date_from = date.fromisoformat(date_from)
        parsed_date_to = date.fromisoformat(date_to)
        candidates, _failed = continuous_crawl._get_candidates(source, parsed_date_from, parsed_date_to)

        progress.total_urls = len(candidates)
        progress.status = "fetching"
        db.commit()

        delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))

        for candidate in candidates:
            url = candidate["url"]
            url_hash = compute_url_hash(url)
            article = db.query(Article).filter_by(source_id=source_uuid, url_hash=url_hash).first()

            if article is None:
                try:
                    parsed = fetch_article_dispatch(url, source.parsing_rules)
                except Exception:
                    parsed = None
                time.sleep(delay_seconds)

                if parsed is not None:
                    article = Article(
                        source_id=source_uuid,
                        url=parsed["url"],
                        url_hash=parsed["url_hash"],
                        title=parsed["title"],
                        content_raw=parsed["content_raw"],
                        author=parsed["author"],
                        published_at=parsed.get("published_at"),
                        crawl_duration_seconds=parsed.get("crawl_duration_seconds"),
                    )
                    db.add(article)
                    try:
                        db.commit()
                    except IntegrityError:
                        # Race hiếm: tiến trình khác (VD continuous_crawl.crawl_task cùng
                        # Source) đã insert đúng URL này trước — rollback, đọc lại bản đã có
                        db.rollback()
                        article = db.query(Article).filter_by(source_id=source_uuid, url_hash=url_hash).first()

            if article is not None:
                continuous_crawl.match_campaigns_for_article(db, article)

            progress.done_urls += 1
            db.commit()

        progress.status = "done"
        db.commit()
    except Exception:
        logger.exception(
            "crawl_campaign_source_once thất bại cho campaign_id=%s source_id=%s", campaign_id, source_id
        )
        db.rollback()
        progress.status = "error"
        db.commit()


@celery_app.task(name="campaign_tasks.crawl_campaign_source_once")
def crawl_campaign_source_once(campaign_id: str, source_id: str, date_from: str, date_to: str) -> None:
    """Thành viên của chord (mode=ONE_SHOT, xem routers/campaigns.py::activate_campaign) —
    1 task/Source. KHÔNG được raise ra ngoài (xử lý bên trong _crawl_campaign_source_once)
    — nếu raise, Celery không chạy callback mark_crawl_done, Campaign kẹt ACTIVE mãi."""
    db = SessionLocal()
    try:
        _crawl_campaign_source_once(db, campaign_id, source_id, date_from, date_to)
    finally:
        db.close()
```

- [ ] **Step 5: Chạy lại test, xác nhận PASS**

Run: `docker compose exec backend pytest backend/tests/test_campaign_tasks.py::test_crawl_campaign_source_once_fetches_new_candidates_and_tracks_progress -v`
Expected: PASS

- [ ] **Step 6: Viết test cho luồng "tái sử dụng Article đã có" (không gọi fetch lại)**

Thêm vào cuối `backend/tests/test_campaign_tasks.py`:
```python
def test_crawl_campaign_source_once_reuses_existing_article_without_refetching(db_session, monkeypatch):
    campaign, source = _make_campaign_with_source_and_keyword(db_session)
    existing = Article(
        source_id=source.source_id, url="https://x.example/bai-cu", url_hash="hash-cu",
        title="Cảnh báo lừa đảo cũ", content_raw="Nội dung cũ", status="analyzed",
    )
    db_session.add(existing)
    db_session.commit()

    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")
    monkeypatch.setattr(
        "backend.workers.continuous_crawl._get_candidates",
        lambda src, date_from, date_to: ([{"url": "https://x.example/bai-cu"}], []),
    )

    def _fail_if_called(url, rules):
        raise AssertionError("Không được gọi fetch_article_dispatch cho URL đã có Article")

    monkeypatch.setattr("backend.workers.campaign_tasks.fetch_article_dispatch", _fail_if_called)

    _crawl_campaign_source_once(db_session, str(campaign.campaign_id), str(source.source_id), "2026-06-01", "2026-06-05")

    ca = db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id, article_id=existing.article_id).one()
    assert ca is not None
    progress = db_session.query(CampaignCrawlProgress).filter_by(
        campaign_id=campaign.campaign_id, source_id=source.source_id
    ).one()
    assert progress.done_urls == 1
    assert progress.status == "done"


def test_crawl_campaign_source_once_handles_reactivation_without_duplicate_match(db_session, monkeypatch):
    # Kích hoạt lại Campaign (crawl lần 2 cho cùng URL đã match từ lần 1) không được vỡ
    # IntegrityError ở campaign_articles — dựa vào guard idempotent đã thêm ở Task 3
    campaign, source = _make_campaign_with_source_and_keyword(db_session)
    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")
    monkeypatch.setattr(
        "backend.workers.continuous_crawl._get_candidates",
        lambda src, date_from, date_to: ([{"url": "https://x.example/bai-2"}], []),
    )
    monkeypatch.setattr(
        "backend.workers.campaign_tasks.fetch_article_dispatch",
        lambda url, rules: {
            "url": url, "url_hash": "hash-bai-2", "title": "Lừa đảo", "content_raw": "Nội dung",
            "author": None, "published_at": None, "crawl_duration_seconds": 0.1,
        },
    )

    _crawl_campaign_source_once(db_session, str(campaign.campaign_id), str(source.source_id), "2026-06-01", "2026-06-05")
    _crawl_campaign_source_once(db_session, str(campaign.campaign_id), str(source.source_id), "2026-06-01", "2026-06-05")

    article = db_session.query(Article).filter_by(source_id=source.source_id, url_hash="hash-bai-2").one()
    rows = db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id, article_id=article.article_id).all()
    assert len(rows) == 1
```

- [ ] **Step 7: Chạy 2 test mới, xác nhận PASS**

Run: `docker compose exec backend pytest backend/tests/test_campaign_tasks.py -k "reuses_existing or reactivation" -v`
Expected: PASS cả 2

- [ ] **Step 8: Viết test cho trường hợp lỗi (status='error', không raise)**

Thêm vào cuối `backend/tests/test_campaign_tasks.py`:
```python
def test_crawl_campaign_source_once_sets_error_status_on_discover_failure(db_session, monkeypatch):
    campaign, source = _make_campaign_with_source_and_keyword(db_session)
    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")

    def _raise(src, date_from, date_to):
        raise RuntimeError("lỗi mạng giả lập")

    monkeypatch.setattr("backend.workers.continuous_crawl._get_candidates", _raise)

    _crawl_campaign_source_once(db_session, str(campaign.campaign_id), str(source.source_id), "2026-06-01", "2026-06-05")

    progress = db_session.query(CampaignCrawlProgress).filter_by(
        campaign_id=campaign.campaign_id, source_id=source.source_id
    ).one()
    assert progress.status == "error"
```

- [ ] **Step 9: Chạy test, xác nhận PASS (không raise ra ngoài)**

Run: `docker compose exec backend pytest backend/tests/test_campaign_tasks.py::test_crawl_campaign_source_once_sets_error_status_on_discover_failure -v`
Expected: PASS

- [ ] **Step 10: Chạy toàn bộ test file**

Run: `docker compose exec backend pytest backend/tests/test_campaign_tasks.py -v`
Expected: PASS toàn bộ

- [ ] **Step 11: Commit**

```bash
git add backend/workers/campaign_tasks.py backend/tests/test_campaign_tasks.py
git commit -m "feat: task crawl_campaign_source_once — crawl ONE_SHOT scoped đúng date_range, tái sử dụng bài đã có"
```

---

### Task 5: Wire `activate_campaign` dùng `crawl_campaign_source_once` + tạo dòng tiến độ

**Files:**
- Modify: `backend/routers/campaigns.py`
- Test: `backend/tests/test_campaigns_router.py`

**Interfaces:**
- Consumes: `campaign_tasks.crawl_campaign_source_once` (Task 4), model `CampaignCrawlProgress` (Task 1).
- Produces: `activate_campaign` khi `mode=ONE_SHOT` tạo 1 dòng `campaign_crawl_progress` (`status='pending'`) cho mỗi Source TRƯỚC khi dispatch `chord`, và `chord` gọi `crawl_campaign_source_once.s(campaign_id, source_id, date_from, date_to)` thay vì `continuous_crawl.crawl_task.s(source_id)`.

- [ ] **Step 1: Đổi import ở đầu `backend/routers/campaigns.py`**

Xóa dòng:
```python
from backend.workers import continuous_crawl
```
Sửa dòng:
```python
from backend.workers.campaign_tasks import generate_campaign_report, mark_crawl_done
```
thành:
```python
from backend.workers.campaign_tasks import crawl_campaign_source_once, generate_campaign_report, mark_crawl_done
```

Thêm `CampaignCrawlProgress` vào dòng import model có sẵn — sửa:
```python
from backend.models import Campaign, CampaignKeyword, CampaignSource, Keyword, ReportHistory, Source, User
```
thành:
```python
from backend.models import Campaign, CampaignCrawlProgress, CampaignKeyword, CampaignSource, Keyword, ReportHistory, Source, User
```

- [ ] **Step 2: Sửa khối dispatch chord trong `activate_campaign`**

Tìm khối (đã tồn tại, cuối hàm `activate_campaign`):
```python
    if campaign.mode == "ONE_SHOT":
        source_ids = _campaign_source_ids(db, campaign.campaign_id)
        chord(
            (continuous_crawl.crawl_task.s(sid) for sid in source_ids),
            mark_crawl_done.s(str(campaign.campaign_id)),
        ).apply_async()
```
Thay bằng:
```python
    if campaign.mode == "ONE_SHOT":
        source_ids = _campaign_source_ids(db, campaign.campaign_id)
        for sid in source_ids:
            db.add(CampaignCrawlProgress(campaign_id=campaign.campaign_id, source_id=uuid.UUID(sid)))
        db.commit()

        date_from = campaign.start_date.date().isoformat()
        date_to = campaign.end_date.date().isoformat()
        chord(
            (crawl_campaign_source_once.s(str(campaign.campaign_id), sid, date_from, date_to) for sid in source_ids),
            mark_crawl_done.s(str(campaign.campaign_id)),
        ).apply_async()
```

- [ ] **Step 3: Thêm `CampaignCrawlProgress` vào import model của test file**

Trong `backend/tests/test_campaigns_router.py`, sửa dòng import đầu file:
```python
from backend.models import Campaign, CampaignKeyword, CampaignSource, Keyword, ReportHistory, Role, Source, User, UserRole
```
thành:
```python
from backend.models import (
    Campaign,
    CampaignCrawlProgress,
    CampaignKeyword,
    CampaignSource,
    Keyword,
    ReportHistory,
    Role,
    Source,
    User,
    UserRole,
)
```

- [ ] **Step 4: Sửa test `test_activate_one_shot_campaign_dispatches_chord` để verify đúng task mới được dùng**

Trong `backend/tests/test_campaigns_router.py`, sửa test (đã có `end_date` từ Task 2 Step 6) — thêm assertion mới vào cuối test, và đổi patch target:
```python
def test_activate_one_shot_campaign_dispatches_chord(app_client, admin_user, source, keyword, db_session):
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.commit()

    with patch("backend.routers.campaigns.chord") as mock_chord:
        mock_chord.return_value.return_value = MagicMock()
        response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"
    mock_chord.assert_called_once()
```
(Không đổi phần assert hiện có — chỉ đảm bảo `end_date` đã có sẵn từ Task 2, giữ nguyên logic test.)

Thêm test MỚI ngay sau test trên:
```python
def test_activate_one_shot_campaign_creates_progress_rows(app_client, admin_user, source, keyword, db_session):
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.commit()

    with patch("backend.routers.campaigns.chord") as mock_chord:
        mock_chord.return_value.return_value = MagicMock()
        app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    progress = db_session.query(CampaignCrawlProgress).filter_by(
        campaign_id=campaign.campaign_id, source_id=source.source_id
    ).one()
    assert progress.status == "pending"
```

- [ ] **Step 5: Chạy toàn bộ test router**

Run: `docker compose exec backend pytest backend/tests/test_campaigns_router.py -v`
Expected: PASS toàn bộ

- [ ] **Step 6: Chạy toàn bộ test suite backend để xác nhận không phá vỡ gì khác (VD test_continuous_crawl.py không còn phụ thuộc `continuous_crawl` import trong campaigns.py)**

Run: `docker compose exec backend pytest backend/tests/ -v`
Expected: PASS toàn bộ

- [ ] **Step 7: Commit**

```bash
git add backend/routers/campaigns.py backend/tests/test_campaigns_router.py
git commit -m "feat: activate_campaign ONE_SHOT dùng crawl_campaign_source_once + tạo dòng tiến độ"
```

---

### Task 6: Endpoint `GET /api/campaigns/{id}/crawl-progress`

**Files:**
- Modify: `backend/routers/campaigns.py`
- Test: `backend/tests/test_campaigns_router.py`

**Interfaces:**
- Produces: `GET /api/campaigns/{campaign_id}/crawl-progress` — permission `campaign.view`. Response `mode=ONE_SHOT`: `{"mode": "ONE_SHOT", "sources": [{"source_id": str, "source_name": str, "total_urls": int|None, "done_urls": int, "status": str}], "overall_percent": float}`. Response `mode=CONTINUOUS`: `{"mode": "CONTINUOUS", "sources": [{"source_id": str, "source_name": str, "last_crawled_at": datetime|None, "source_status": str, "pending_count": int, "matched_last_24h": int}]}`.

- [ ] **Step 1: Thêm import cần thiết**

Sửa dòng import ở đầu `backend/routers/campaigns.py` (đã sửa ở Task 2 Step 1):
```python
from datetime import date, datetime
```
thành:
```python
from datetime import date, datetime, timedelta, timezone
```

Sửa dòng import model (đã sửa ở Task 5 Step 1):
```python
from backend.models import Campaign, CampaignCrawlProgress, CampaignKeyword, CampaignSource, Keyword, ReportHistory, Source, User
```
thành:
```python
from backend.models import (
    Article,
    Campaign,
    CampaignArticle,
    CampaignCrawlProgress,
    CampaignKeyword,
    CampaignSource,
    CrawlQueue,
    Keyword,
    ReportHistory,
    Source,
    User,
)
```

- [ ] **Step 2: Thêm `Article`, `CampaignArticle`, `CrawlQueue` vào import model của test file**

Trong `backend/tests/test_campaigns_router.py`, sửa dòng import đã thêm `CampaignCrawlProgress` ở Task 5 Step 3:
```python
from backend.models import (
    Campaign,
    CampaignCrawlProgress,
    CampaignKeyword,
    CampaignSource,
    Keyword,
    ReportHistory,
    Role,
    Source,
    User,
    UserRole,
)
```
thành:
```python
from backend.models import (
    Article,
    Campaign,
    CampaignArticle,
    CampaignCrawlProgress,
    CampaignKeyword,
    CampaignSource,
    CrawlQueue,
    Keyword,
    ReportHistory,
    Role,
    Source,
    User,
    UserRole,
)
```

- [ ] **Step 3: Viết test cho nhánh ONE_SHOT (test phải FAIL trước khi implement — endpoint 404 vì chưa tồn tại)**

Thêm vào cuối `backend/tests/test_campaigns_router.py`:
```python
def test_crawl_progress_one_shot_returns_percent_from_progress_rows(app_client, admin_user, source, db_session):
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-01", status="ACTIVE",
        owner_id=admin_user.user_id, mode="ONE_SHOT",
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignCrawlProgress(
        campaign_id=campaign.campaign_id, source_id=source.source_id,
        total_urls=10, done_urls=4, status="fetching",
    ))
    db_session.commit()

    response = app_client.get(f"/api/campaigns/{campaign.campaign_id}/crawl-progress")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "ONE_SHOT"
    assert body["overall_percent"] == 40.0
    assert body["sources"][0]["total_urls"] == 10
    assert body["sources"][0]["done_urls"] == 4
    assert body["sources"][0]["status"] == "fetching"


def test_crawl_progress_one_shot_source_without_progress_row_shows_pending(app_client, admin_user, source, db_session):
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-01", status="ACTIVE",
        owner_id=admin_user.user_id, mode="ONE_SHOT",
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    response = app_client.get(f"/api/campaigns/{campaign.campaign_id}/crawl-progress")

    body = response.json()
    assert body["sources"][0]["status"] == "pending"
    assert body["sources"][0]["total_urls"] is None
    assert body["overall_percent"] == 0.0


def test_crawl_progress_continuous_returns_source_activity(app_client, admin_user, source, db_session):
    campaign = Campaign(
        name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id, mode="CONTINUOUS",
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CrawlQueue(source_id=source.source_id, url="https://x.example/p", url_hash="hp", status="pending"))
    article = Article(source_id=source.source_id, url="https://x.example/a", url_hash="ha")
    db_session.add(article)
    db_session.flush()
    db_session.add(CampaignArticle(campaign_id=campaign.campaign_id, article_id=article.article_id))
    db_session.commit()

    response = app_client.get(f"/api/campaigns/{campaign.campaign_id}/crawl-progress")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "CONTINUOUS"
    assert body["sources"][0]["pending_count"] == 1
    assert body["sources"][0]["matched_last_24h"] == 1
```

- [ ] **Step 4: Chạy test, xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_campaigns_router.py -k crawl_progress -v`
Expected: FAIL với `404 Not Found` (route chưa tồn tại)

- [ ] **Step 5: Viết endpoint**

Thêm vào cuối `backend/routers/campaigns.py`:
```python
@router.get("/{campaign_id}/crawl-progress")
def get_campaign_crawl_progress(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("campaign", "view")),
):
    campaign = _get_campaign_or_404(db, campaign_id)
    watched_sources = (
        db.query(Source)
        .join(CampaignSource, CampaignSource.source_id == Source.source_id)
        .filter(CampaignSource.campaign_id == campaign.campaign_id)
        .all()
    )

    if campaign.mode == "ONE_SHOT":
        progress_by_source = {
            p.source_id: p
            for p in db.query(CampaignCrawlProgress).filter_by(campaign_id=campaign.campaign_id).all()
        }
        sources = []
        total_sum = 0
        done_sum = 0
        for s in watched_sources:
            p = progress_by_source.get(s.source_id)
            total_urls = p.total_urls if p else None
            done_urls = p.done_urls if p else 0
            status = p.status if p else "pending"
            sources.append(
                {
                    "source_id": str(s.source_id),
                    "source_name": s.name,
                    "total_urls": total_urls,
                    "done_urls": done_urls,
                    "status": status,
                }
            )
            if total_urls:
                total_sum += total_urls
            done_sum += done_urls
        overall_percent = round(100 * done_sum / total_sum, 1) if total_sum > 0 else 0.0
        return {"mode": "ONE_SHOT", "sources": sources, "overall_percent": overall_percent}

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    sources = []
    for s in watched_sources:
        pending_count = db.query(CrawlQueue).filter_by(source_id=s.source_id, status="pending").count()
        matched_last_24h = (
            db.query(CampaignArticle)
            .join(Article, Article.article_id == CampaignArticle.article_id)
            .filter(
                CampaignArticle.campaign_id == campaign.campaign_id,
                Article.source_id == s.source_id,
                CampaignArticle.matched_at >= since,
            )
            .count()
        )
        sources.append(
            {
                "source_id": str(s.source_id),
                "source_name": s.name,
                "last_crawled_at": s.last_crawled_at,
                "source_status": s.status,
                "pending_count": pending_count,
                "matched_last_24h": matched_last_24h,
            }
        )
    return {"mode": "CONTINUOUS", "sources": sources}
```

- [ ] **Step 6: Chạy lại test, xác nhận PASS**

Run: `docker compose exec backend pytest backend/tests/test_campaigns_router.py -k crawl_progress -v`
Expected: PASS toàn bộ 3 test

- [ ] **Step 7: Chạy toàn bộ test router**

Run: `docker compose exec backend pytest backend/tests/test_campaigns_router.py -v`
Expected: PASS toàn bộ

- [ ] **Step 8: Commit**

```bash
git add backend/routers/campaigns.py backend/tests/test_campaigns_router.py
git commit -m "feat: endpoint GET /api/campaigns/{id}/crawl-progress"
```

---

### Task 7: CONTINUOUS tự chuyển `COMPLETED` khi tới `end_date`

**Files:**
- Modify: `backend/workers/scheduler.py`
- Test: `backend/tests/test_scheduler.py`

**Interfaces:**
- Produces: hàm `complete_expired_continuous_campaigns(db, now: datetime | None = None) -> int` (trả số Campaign vừa chuyển `COMPLETED`) — gọi ngay đầu task `check_due_sources()`, **trước** cả bước kiểm tra `SCHEDULER_ENABLED` (vòng đời Campaign không phụ thuộc việc Scheduler có đang bật crawl hay không).

- [ ] **Step 1: Viết test cho hàm mới (test phải FAIL — hàm chưa tồn tại)**

Thêm vào cuối `backend/tests/test_scheduler.py`:
```python
from backend.workers.scheduler import complete_expired_continuous_campaigns


def test_complete_expired_continuous_campaigns_marks_completed(db_session):
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-10", status="ACTIVE", mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.commit()

    count = complete_expired_continuous_campaigns(db_session, now=now)

    db_session.refresh(campaign)
    assert count == 1
    assert campaign.status == "COMPLETED"


def test_complete_expired_continuous_campaigns_ignores_campaign_without_end_date(db_session):
    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", mode="CONTINUOUS")
    db_session.add(campaign)
    db_session.commit()

    count = complete_expired_continuous_campaigns(db_session)

    db_session.refresh(campaign)
    assert count == 0
    assert campaign.status == "ACTIVE"


def test_complete_expired_continuous_campaigns_ignores_campaign_with_future_end_date(db_session):
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2099-01-01", status="ACTIVE", mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.commit()

    count = complete_expired_continuous_campaigns(db_session, now=now)

    db_session.refresh(campaign)
    assert count == 0
    assert campaign.status == "ACTIVE"


def test_complete_expired_continuous_campaigns_ignores_one_shot_campaign(db_session):
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-10", status="ACTIVE", mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.commit()

    count = complete_expired_continuous_campaigns(db_session, now=now)

    db_session.refresh(campaign)
    assert count == 0
    assert campaign.status == "ACTIVE"


def test_complete_expired_continuous_campaigns_ignores_already_paused_campaign(db_session):
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-10", status="PAUSED", mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.commit()

    count = complete_expired_continuous_campaigns(db_session, now=now)

    db_session.refresh(campaign)
    assert count == 0
    assert campaign.status == "PAUSED"
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `docker compose exec backend pytest backend/tests/test_scheduler.py -k complete_expired -v`
Expected: FAIL với `ImportError`

- [ ] **Step 3: Viết hàm trong `backend/workers/scheduler.py`**

Thêm ngay sau hàm `list_due_sources` (trước dòng trống + `from backend.db import SessionLocal`):
```python
def complete_expired_continuous_campaigns(db, now: datetime | None = None) -> int:
    """Campaign CONTINUOUS có end_date đã qua nhưng vẫn ACTIVE → tự chuyển COMPLETED.
    Trước đây end_date chỉ lưu ở DB, không có cơ chế nào đọc lại — Campaign CONTINUOUS
    đặt end_date xong vẫn crawl mãi mãi cho tới khi có người bấm Tạm dừng/Lưu trữ thủ
    công (phát hiện qua smoke test thật 2026-07-22). Gọi ở đầu check_due_sources(), độc
    lập với SCHEDULER_ENABLED — vòng đời Campaign không nên phụ thuộc việc crawl có đang
    bật hay không."""
    now = now or datetime.now(timezone.utc)
    expired = (
        db.query(Campaign)
        .filter(
            Campaign.mode == "CONTINUOUS",
            Campaign.status == "ACTIVE",
            Campaign.end_date.isnot(None),
            Campaign.end_date <= now,
        )
        .all()
    )
    for campaign in expired:
        campaign.status = "COMPLETED"
    db.commit()
    return len(expired)
```

- [ ] **Step 4: Gọi hàm mới ở đầu `check_due_sources()`**

Sửa:
```python
@celery_app.task(name="scheduler.check_due_sources")
def check_due_sources() -> None:
    db = SessionLocal()
    try:
        if not get_bool_setting(db, "SCHEDULER_ENABLED"):
            return
        for source in list_due_sources(db):
            continuous_crawl.crawl_task.delay(str(source.source_id))
    finally:
        db.close()
```
thành:
```python
@celery_app.task(name="scheduler.check_due_sources")
def check_due_sources() -> None:
    db = SessionLocal()
    try:
        complete_expired_continuous_campaigns(db)
        if not get_bool_setting(db, "SCHEDULER_ENABLED"):
            return
        for source in list_due_sources(db):
            continuous_crawl.crawl_task.delay(str(source.source_id))
    finally:
        db.close()
```

- [ ] **Step 5: Chạy lại test, xác nhận PASS**

Run: `docker compose exec backend pytest backend/tests/test_scheduler.py -v`
Expected: PASS toàn bộ

- [ ] **Step 6: Commit**

```bash
git add backend/workers/scheduler.py backend/tests/test_scheduler.py
git commit -m "feat: CONTINUOUS Campaign tự chuyển COMPLETED khi tới end_date"
```

---

### Task 8: FE — Card "Tiến độ crawl" trong `CampaignDetail.tsx`

**Files:**
- Modify: `frontend/src/pages/Campaigns/CampaignDetail.tsx`

**Interfaces:**
- Consumes: `GET /api/campaigns/{id}/crawl-progress` (Task 6) — response `{mode, sources, overall_percent?}`.

- [ ] **Step 1: Thêm `Progress` vào import AntD**

Sửa dòng:
```tsx
import { App, Button, Card, Col, DatePicker, Descriptions, Row, Select, Space, Table, Tag, Tooltip } from 'antd'
```
thành:
```tsx
import { App, Button, Card, Col, DatePicker, Descriptions, Progress, Row, Select, Space, Table, Tag, Tooltip } from 'antd'
```

- [ ] **Step 2: Thêm type cho crawl progress**

Thêm ngay sau khối `type ReportRow = {...}` (trước `const FORMAT_OPTIONS`):
```tsx
type CrawlProgressSourceOneShot = {
  source_id: string
  source_name: string
  total_urls: number | null
  done_urls: number
  status: string
}
type CrawlProgressSourceContinuous = {
  source_id: string
  source_name: string
  last_crawled_at: string | null
  source_status: string
  pending_count: number
  matched_last_24h: number
}
type CrawlProgress =
  | { mode: 'ONE_SHOT'; sources: CrawlProgressSourceOneShot[]; overall_percent: number }
  | { mode: 'CONTINUOUS'; sources: CrawlProgressSourceContinuous[] }
```

- [ ] **Step 3: Thêm state + loader + polling**

Sửa khối state hiện có:
```tsx
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [reports, setReports] = useState<ReportRow[]>([])
  const [reportRange, setReportRange] = useState<[Dayjs, Dayjs] | null>(null)
  const [reportFormat, setReportFormat] = useState('docx')
  const [creatingReport, setCreatingReport] = useState(false)
  const hasPrefilledRange = useRef(false)
```
thành (thêm 1 dòng state mới):
```tsx
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [reports, setReports] = useState<ReportRow[]>([])
  const [reportRange, setReportRange] = useState<[Dayjs, Dayjs] | null>(null)
  const [reportFormat, setReportFormat] = useState('docx')
  const [creatingReport, setCreatingReport] = useState(false)
  const [crawlProgress, setCrawlProgress] = useState<CrawlProgress | null>(null)
  const hasPrefilledRange = useRef(false)
```

Thêm hàm loader ngay sau `loadReports`:
```tsx
  function loadCrawlProgress() {
    authFetch(`/api/campaigns/${id}/crawl-progress`).then((r) => r.json()).then(setCrawlProgress)
  }
```

Sửa `useEffect` load ban đầu:
```tsx
  useEffect(() => {
    loadCampaign()
    loadReports()
  }, [id])
```
thành:
```tsx
  useEffect(() => {
    loadCampaign()
    loadReports()
    loadCrawlProgress()
  }, [id])
```

Thêm `useEffect` polling mới ngay sau khối polling report có sẵn (`useEffect` đọc `reports`):
```tsx
  // Poll tiến độ crawl mỗi 3s khi Campaign đang ACTIVE — dừng khi COMPLETED/PAUSED/ARCHIVED
  useEffect(() => {
    if (campaign?.status !== 'ACTIVE') return
    const interval = setInterval(loadCrawlProgress, 3000)
    return () => clearInterval(interval)
  }, [campaign?.status])
```

- [ ] **Step 4: Thêm Card hiển thị, ngay sau Card "Báo cáo"**

Tìm dòng cuối file:
```tsx
      </Card>
    </div>
  )
}
```
Sửa thành (thêm 1 Card mới trước `</div>`):
```tsx
      </Card>

      {crawlProgress && (
        <Card title="Tiến độ crawl" style={{ borderRadius: 12, marginTop: 16 }}>
          {crawlProgress.mode === 'ONE_SHOT' ? (
            <Space direction="vertical" style={{ width: '100%' }}>
              <Progress percent={crawlProgress.overall_percent} />
              {crawlProgress.sources.map((s) => (
                <div key={s.source_id} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>{s.source_name}</span>
                  <span>
                    {s.done_urls}/{s.total_urls ?? '…'} ({s.status})
                  </span>
                </div>
              ))}
            </Space>
          ) : (
            <Table
              rowKey="source_id"
              dataSource={crawlProgress.sources}
              pagination={false}
              columns={[
                { title: 'Nguồn', dataIndex: 'source_name' },
                {
                  title: 'Lần crawl gần nhất',
                  dataIndex: 'last_crawled_at',
                  render: (v: string | null) => (v ? new Date(v).toLocaleString('vi-VN') : 'Chưa crawl'),
                },
                { title: 'Bài mới khớp (24h)', dataIndex: 'matched_last_24h' },
                { title: 'Hàng đợi còn lại', dataIndex: 'pending_count' },
              ]}
            />
          )}
        </Card>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Type-check FE**

Run: `cd frontend && npm run build`
Expected: build thành công, không lỗi TypeScript

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Campaigns/CampaignDetail.tsx
git commit -m "feat: Card Tiến độ crawl trong CampaignDetail (ONE_SHOT % + CONTINUOUS hoạt động gần đây)"
```

---

### Task 9: FE — chặn chọn ngày tương lai cho ONE_SHOT (`CampaignForm.tsx`)

**Files:**
- Modify: `frontend/src/pages/Campaigns/CampaignForm.tsx`

- [ ] **Step 1: Thêm `useWatch` để theo dõi `mode` đang chọn**

Sửa dòng khai báo form:
```tsx
  const [form] = Form.useForm()
```
thành (thêm 1 dòng ngay sau):
```tsx
  const [form] = Form.useForm()
  const modeValue = Form.useWatch('mode', form)
```

- [ ] **Step 2: Sửa `Form.Item` của `end_date`**

Sửa khối:
```tsx
          <Space style={{ width: '100%' }}>
            <Form.Item name="start_date" label="Ngày bắt đầu" style={{ flex: 1 }} rules={[{ required: true, message: 'Bắt buộc' }]}>
              <DatePicker style={{ width: '100%' }} format="DD/MM/YYYY" />
            </Form.Item>
            <Form.Item name="end_date" label="Ngày kết thúc" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} format="DD/MM/YYYY" />
            </Form.Item>
          </Space>
```
thành:
```tsx
          <Space style={{ width: '100%' }}>
            <Form.Item name="start_date" label="Ngày bắt đầu" style={{ flex: 1 }} rules={[{ required: true, message: 'Bắt buộc' }]}>
              <DatePicker style={{ width: '100%' }} format="DD/MM/YYYY" />
            </Form.Item>
            <Form.Item
              name="end_date"
              label="Ngày kết thúc"
              style={{ flex: 1 }}
              rules={[
                {
                  required: modeValue === 'ONE_SHOT',
                  message: 'Chiến dịch "Tạo báo cáo nhanh" bắt buộc phải có Ngày kết thúc',
                },
              ]}
              extra={modeValue === 'ONE_SHOT' ? 'Chỉ chọn được ngày trong quá khứ (đến hôm nay)' : undefined}
            >
              <DatePicker
                style={{ width: '100%' }}
                format="DD/MM/YYYY"
                disabledDate={(d) => modeValue === 'ONE_SHOT' && d.isAfter(dayjs(), 'day')}
              />
            </Form.Item>
          </Space>
```

- [ ] **Step 3: Type-check FE**

Run: `cd frontend && npm run build`
Expected: build thành công

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Campaigns/CampaignForm.tsx
git commit -m "feat: chặn chọn Ngày kết thúc tương lai cho Campaign ONE_SHOT trên form"
```

---

### Task 10: FE — chặn chọn ngày tương lai trong `ReportCreate.tsx`

**Files:**
- Modify: `frontend/src/pages/Reports/ReportCreate.tsx`

**Bối cảnh:** `ReportCreate.tsx` luôn tạo Campaign `mode="ONE_SHOT"` (xem dòng `mode: "ONE_SHOT"` trong hàm submit) — cả 2 DatePicker (`dateFrom`/`dateTo`) đều cần chặn ngày tương lai để khớp validate backend mới (Task 2).

- [ ] **Step 1: Thêm `disabledDate` cho cả 2 DatePicker**

Sửa khối:
```tsx
                <div>
                  <Typography.Text>Từ ngày</Typography.Text>
                  <DatePicker value={dateFrom} onChange={(v) => v && setDateFrom(v)} style={{ display: "block" }} />
                </div>
                <div>
                  <Typography.Text>Đến ngày</Typography.Text>
                  <DatePicker value={dateTo} onChange={(v) => v && setDateTo(v)} style={{ display: "block" }} />
                </div>
```
thành:
```tsx
                <div>
                  <Typography.Text>Từ ngày</Typography.Text>
                  <DatePicker
                    value={dateFrom}
                    onChange={(v) => v && setDateFrom(v)}
                    style={{ display: "block" }}
                    disabledDate={(d) => d.isAfter(dayjs(), "day")}
                  />
                </div>
                <div>
                  <Typography.Text>Đến ngày</Typography.Text>
                  <DatePicker
                    value={dateTo}
                    onChange={(v) => v && setDateTo(v)}
                    style={{ display: "block" }}
                    disabledDate={(d) => d.isAfter(dayjs(), "day")}
                  />
                </div>
```

- [ ] **Step 2: Type-check FE**

Run: `cd frontend && npm run build`
Expected: build thành công

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Reports/ReportCreate.tsx
git commit -m "feat: chặn chọn ngày tương lai khi Tạo báo cáo nhanh (ONE_SHOT)"
```

---

### Task 11: Smoke test Docker thật (verify toàn bộ end-to-end)

**Files:** không có file mới — chỉ vận hành hệ thống thật qua Docker để verify.

- [ ] **Step 1: Rebuild + restart backend/celery-worker/celery-beat/frontend**

Run: `docker compose up -d --build backend celery-worker celery-beat frontend`
Expected: cả 4 container `healthy`/`Up`

- [ ] **Step 2: Chạy migration trên DB thật**

Run: `docker compose exec backend alembic upgrade head`
Expected: log hiện `0021 -> 0022`, không lỗi

- [ ] **Step 3: Chạy toàn bộ test suite backend 1 lần cuối trong container thật**

Run: `docker compose exec backend pytest backend/tests/ -v`
Expected: PASS toàn bộ, không skip ngoài dự kiến

- [ ] **Step 4: Tạo Campaign ONE_SHOT thật qua UI, kích hoạt, quan sát tiến độ**

Thao tác thủ công: đăng nhập UI (`admin`/mật khẩu thật) → `/campaigns/new` → chọn `mode=ONE_SHOT`, 1 Nguồn đã có backlog lớn (VD VTV News), `end_date` = hôm nay → Lưu → vào chi tiết Campaign → Kích hoạt.
Expected: Card "Tiến độ crawl" xuất hiện ngay, số `done_urls/total_urls` tăng dần mỗi ~3 giây; `total_urls` phải **nhỏ hẳn** so với ~4300 URL backlog quan sát được trước khi sửa (vì giờ chỉ Discover đúng phạm vi ngày đã chọn, không phải cửa sổ 30 ngày); Campaign tự chuyển `COMPLETED` trong thời gian hợp lý (phút, không phải giờ).

- [ ] **Step 5: Tạo báo cáo cho Campaign vừa xong, xác nhận dữ liệu đúng**

Thao tác thủ công: sau khi `COMPLETED`, bấm "Tạo báo cáo" (định dạng bất kỳ) → tải về → mở file.
Expected: file sinh ra có dữ liệu, không rỗng (đủ điều kiện có bài match từ khóa trong phạm vi ngày).

- [ ] **Step 6: Xác nhận CONTINUOUS Campaign hiện Card "Hoạt động gần đây" đúng**

Thao tác thủ công: vào chi tiết 1 Campaign `mode=CONTINUOUS` đang `ACTIVE` có sẵn.
Expected: bảng hiện đúng "Lần crawl gần nhất"/"Hàng đợi còn lại"/"Bài mới khớp (24h)" cho từng Nguồn, khớp số liệu thật khi đối chiếu trực tiếp DB (`SELECT` `sources.last_crawled_at`, đếm `crawl_queue`).

- [ ] **Step 7: Ghi log kết quả smoke test vào `.superpowers/sdd/progress.md` (nếu dùng subagent-driven-development) hoặc báo cáo trực tiếp cho user**

Không có lệnh cụ thể — ghi lại số liệu thật quan sát được (thời gian ONE_SHOT hoàn thành, số URL total_urls thực tế) để so sánh với vấn đề gốc (~4300 URL, hàng giờ).
