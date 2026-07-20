# Phase 2 — Campaign & Master Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm data model Campaign (`campaigns`, `keywords`, `campaign_keywords`, `campaign_sources`) và API CRUD/activate/pause tương ứng, làm nền tảng cho Scheduler (Phase 3), Alert (Phase 5) và Report mở rộng (Phase 7) — theo đúng business rules BR-CAMP ở [16 · Campaign Management](../../../.claude/rules/16-campaign-management.md).

**Architecture:** Thêm 4 bảng mới qua 1 migration Alembic, 4 SQLAlchemy model mới, 2 router FastAPI mới (`campaigns.py`, `keywords.py`) theo đúng pattern `require_permission()` + `log_action()` đã dùng ở `routers/users.py`. **Không đụng** `jobs`, `/api/reports/*`, `report_job.py` — flow on-demand cũ tiếp tục chạy song song nguyên trạng cho tới khi Phase 3 (Scheduler) và Phase 7 (Report mở rộng) tới lượt.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + PostgreSQL, Pydantic request models, pytest + `TestClient` (theo pattern `tests/test_sources_router.py`/`test_users_router.py`).

## Global Constraints

- **Không đụng `jobs`, `routers/reports.py`, `workers/report_job.py`, bảng `report_history`** — quyết định đã chốt với user (2026-07-20): Phase 2 chỉ thêm schema/API Campaign mới, giữ nguyên flow on-demand cũ chạy song song.
- **Không migrate dữ liệu `jobs`/`report_history` cũ sang `campaigns`** — giữ nguyên trong DB, không cần hiển thị qua Campaign UI.
- **Không làm FE `/campaigns`** trong Phase 2 — route vẫn dùng mock data như hiện tại (`frontend/src/data/mockData.ts`), chỉ làm backend.
- **BR-CAMP-01 đến BR-CAMP-07** (xem [16 · Campaign Management](../../../.claude/rules/16-campaign-management.md)) là nguồn sự thật cho mọi validation.
- **RBAC:** dùng đúng permission code đã seed sẵn ở migration `0011` — không tạo permission mới. `campaign.view/create/update/archive` cho Campaign; **`campaign.create`/`campaign.view` dùng chung cho `/api/keywords`** (không có permission `keyword.*` riêng trong RBAC matrix hiện tại — quyết định đã chốt với user).
- **Mọi endpoint ghi dữ liệu phải gọi `log_action()`** (`backend/audit/logger.py`) — cùng pattern `routers/users.py`.
- Tiếng Việt cho mọi comment giải thích logic quan trọng, tiếng Việt cho mọi message lỗi (`HTTPException.detail`) — đúng convention toàn bộ codebase hiện có.
- Migration tiếp theo là `0017` (`down_revision = "0016"`), đặt tại `backend/alembic/versions/0017_add_campaign_tables.py`.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `backend/alembic/versions/0017_add_campaign_tables.py` | Migration: 4 bảng mới + cột `sources.source_group` |
| `backend/models/keywords.py` | Model `Keyword` |
| `backend/models/campaigns.py` | Model `Campaign` |
| `backend/models/campaign_keywords.py` | Model `CampaignKeyword` (association table) |
| `backend/models/campaign_sources.py` | Model `CampaignSource` (association table) |
| `backend/models/sources.py` | Sửa: thêm cột `source_group` |
| `backend/models/__init__.py` | Sửa: export 4 model mới |
| `backend/routers/keywords.py` | `GET /api/keywords`, `POST /api/keywords` |
| `backend/routers/campaigns.py` | `GET/POST /api/campaigns`, `GET/PUT/DELETE /api/campaigns/{id}`, `POST /api/campaigns/{id}/activate`, `POST /api/campaigns/{id}/pause` |
| `backend/main.py` | Sửa: `include_router` 2 router mới |
| `backend/tests/test_keywords_router.py` | Test `keywords.py` |
| `backend/tests/test_campaigns_router.py` | Test `campaigns.py` |

---

## Task 1: Migration — bảng `keywords`, `campaigns`, `campaign_keywords`, `campaign_sources` + `sources.source_group`

**Files:**
- Create: `backend/alembic/versions/0017_add_campaign_tables.py`

**Interfaces:**
- Produces: bảng `keywords(keyword_id, keyword, topic_group, is_active, created_at)`, `campaigns(campaign_id, code, name, description, objective, owner_id, status, mode, start_date, end_date, alert_threshold, is_active, created_at, updated_at, deleted_at)`, `campaign_keywords(campaign_id, keyword_id)`, `campaign_sources(campaign_id, source_id)`; cột `sources.source_group VARCHAR(255)`.

- [ ] **Step 1: Viết migration**

```python
"""thêm bảng campaigns/keywords/campaign_keywords/campaign_sources cho Phase 2
Campaign & Master Data + cột sources.source_group

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sources", sa.Column("source_group", sa.String(255)))

    op.create_table(
        "keywords",
        sa.Column("keyword_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("keyword", sa.String(500), nullable=False),
        sa.Column("topic_group", sa.String(255)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("now()")),
    )

    op.create_table(
        "campaigns",
        sa.Column("campaign_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), unique=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("objective", sa.Text),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="RESTRICT")),
        sa.Column("status", sa.String(50), server_default="DRAFT"),
        sa.Column("mode", sa.String(20), server_default="CONTINUOUS"),
        sa.Column("start_date", sa.TIMESTAMP, nullable=False),
        sa.Column("end_date", sa.TIMESTAMP),
        sa.Column("alert_threshold", sa.Integer, server_default="100"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP),
        sa.Column("deleted_at", sa.TIMESTAMP),
    )

    op.create_table(
        "campaign_keywords",
        sa.Column(
            "campaign_id", UUID(as_uuid=True),
            sa.ForeignKey("campaigns.campaign_id", ondelete="RESTRICT"), primary_key=True,
        ),
        sa.Column(
            "keyword_id", UUID(as_uuid=True),
            sa.ForeignKey("keywords.keyword_id", ondelete="RESTRICT"), primary_key=True,
        ),
    )

    op.create_table(
        "campaign_sources",
        sa.Column(
            "campaign_id", UUID(as_uuid=True),
            sa.ForeignKey("campaigns.campaign_id", ondelete="RESTRICT"), primary_key=True,
        ),
        sa.Column(
            "source_id", UUID(as_uuid=True),
            sa.ForeignKey("sources.source_id", ondelete="RESTRICT"), primary_key=True,
        ),
    )


def downgrade():
    op.drop_table("campaign_sources")
    op.drop_table("campaign_keywords")
    op.drop_table("campaigns")
    op.drop_table("keywords")
    op.drop_column("sources", "source_group")
```

- [ ] **Step 2: Chạy migration trên DB dev thật**

Run: `cd backend && alembic upgrade head`
Expected: log hiện `Running upgrade 0016 -> 0017`, không lỗi.

- [ ] **Step 3: Verify bằng psql (hoặc `docker compose exec db psql`)**

Run: `\d campaigns`, `\d keywords`, `\d campaign_keywords`, `\d campaign_sources`, `\d sources` — kiểm tra đúng cột/FK như migration.

- [ ] **Step 4: Verify downgrade rồi upgrade lại (đảm bảo migration reversible)**

Run: `alembic downgrade -1 && alembic upgrade head`
Expected: cả 2 lệnh chạy sạch, không lỗi FK/constraint.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0017_add_campaign_tables.py
git commit -m "feat: thêm bảng campaigns/keywords/campaign_keywords/campaign_sources (Phase 2)"
```

---

## Task 2: SQLAlchemy Models

**Files:**
- Create: `backend/models/keywords.py`
- Create: `backend/models/campaigns.py`
- Create: `backend/models/campaign_keywords.py`
- Create: `backend/models/campaign_sources.py`
- Modify: `backend/models/sources.py`
- Modify: `backend/models/__init__.py`

**Interfaces:**
- Consumes: bảng đã tạo ở Task 1.
- Produces: `Keyword(keyword_id, keyword, topic_group, is_active, created_at)`, `Campaign(campaign_id, code, name, description, objective, owner_id, status, mode, start_date, end_date, alert_threshold, is_active, created_at, updated_at, deleted_at)`, `CampaignKeyword(campaign_id, keyword_id)`, `CampaignSource(campaign_id, source_id)` — dùng ở Task 3/4/5/6.

- [ ] **Step 1: `backend/models/keywords.py`**

```python
import uuid

from sqlalchemy import Boolean, Column, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class Keyword(Base):
    __tablename__ = "keywords"

    keyword_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keyword = Column(String(500), nullable=False)
    topic_group = Column(String(255))
    is_active = Column(Boolean, server_default="true")
    created_at = Column(TIMESTAMP, server_default=func.now())
```

- [ ] **Step 2: `backend/models/campaigns.py`**

```python
import uuid

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    campaign_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True)
    name = Column(String(500), nullable=False)
    description = Column(Text)
    objective = Column(Text)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    status = Column(String(50), server_default="DRAFT")
    mode = Column(String(20), server_default="CONTINUOUS")
    start_date = Column(TIMESTAMP, nullable=False)
    end_date = Column(TIMESTAMP)
    alert_threshold = Column(Integer, server_default="100")
    is_active = Column(Boolean, server_default="true")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP)
    deleted_at = Column(TIMESTAMP)
```

- [ ] **Step 3: `backend/models/campaign_keywords.py`**

```python
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from backend.db import Base


class CampaignKeyword(Base):
    __tablename__ = "campaign_keywords"

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.campaign_id"), primary_key=True)
    keyword_id = Column(UUID(as_uuid=True), ForeignKey("keywords.keyword_id"), primary_key=True)
```

- [ ] **Step 4: `backend/models/campaign_sources.py`**

```python
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from backend.db import Base


class CampaignSource(Base):
    __tablename__ = "campaign_sources"

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.campaign_id"), primary_key=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.source_id"), primary_key=True)
```

- [ ] **Step 5: Sửa `backend/models/sources.py` — thêm cột `source_group`**

Thêm sau dòng `group_name = Column(String(255), nullable=False)` (dòng 16):

```python
    source_group = Column(String(255))
```

- [ ] **Step 6: Sửa `backend/models/__init__.py`**

```python
from backend.models.article_analysis import ArticleAnalysis
from backend.models.articles import Article
from backend.models.audit_log import AuditLog
from backend.models.campaign_keywords import CampaignKeyword
from backend.models.campaign_sources import CampaignSource
from backend.models.campaigns import Campaign
from backend.models.jobs import Job
from backend.models.keywords import Keyword
from backend.models.permissions import Permission
from backend.models.report_history import ReportHistory
from backend.models.role_permissions import RolePermission
from backend.models.roles import Role
from backend.models.sources import Source
from backend.models.user_roles import UserRole
from backend.models.users import User

__all__ = [
    "Source",
    "Job",
    "Article",
    "ArticleAnalysis",
    "ReportHistory",
    "User",
    "Role",
    "Permission",
    "UserRole",
    "RolePermission",
    "AuditLog",
    "Campaign",
    "Keyword",
    "CampaignKeyword",
    "CampaignSource",
]
```

- [ ] **Step 7: Verify import không lỗi**

Run: `cd backend && python -c "from backend.models import Campaign, Keyword, CampaignKeyword, CampaignSource; print('ok')"`
Expected: in ra `ok`, không traceback.

- [ ] **Step 8: Commit**

```bash
git add backend/models/keywords.py backend/models/campaigns.py backend/models/campaign_keywords.py backend/models/campaign_sources.py backend/models/sources.py backend/models/__init__.py
git commit -m "feat: thêm SQLAlchemy models Campaign/Keyword/CampaignKeyword/CampaignSource"
```

---

## Task 3: Router `keywords.py` — `GET`/`POST /api/keywords`

**Files:**
- Create: `backend/routers/keywords.py`
- Create: `backend/tests/test_keywords_router.py`
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: `Keyword` model (Task 2), `require_permission()` (`backend/auth/dependencies.py`), `log_action()` (`backend/audit/logger.py`).
- Produces: router `keywords.router` (prefix `/api/keywords`) — dùng ở `main.py` và tham chiếu `keyword_id` trong Task 4 (`POST /api/campaigns`).

- [ ] **Step 1: Viết test trước (`backend/tests/test_keywords_router.py`)**

```python
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models import Keyword, Role, User, UserRole
from backend.routers import keywords


@pytest.fixture
def admin_user(db_session):
    role = db_session.query(Role).filter_by(code="ADMIN").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    user = User(username=f"admin-{uuid.uuid4()}", password_hash="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db_session.commit()
    return user


@pytest.fixture
def app_client(db_session, admin_user):
    app = FastAPI()
    app.include_router(keywords.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(app)


def test_list_keywords_rejects_unauthenticated_request(db_session):
    app = FastAPI()
    app.include_router(keywords.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get("/api/keywords")
    assert response.status_code == 403


def test_create_and_list_keyword(app_client, db_session):
    response = app_client.post("/api/keywords", json={"keyword": "tin giả y tế", "topic_group": "Tin giả và thông tin sai lệch"})

    assert response.status_code == 201
    body = response.json()
    assert body["keyword"] == "tin giả y tế"
    assert body["topic_group"] == "Tin giả và thông tin sai lệch"

    list_response = app_client.get("/api/keywords")
    assert list_response.status_code == 200
    keywords_list = list_response.json()["keywords"]
    assert any(k["keyword"] == "tin giả y tế" for k in keywords_list)


def test_create_keyword_requires_nonempty_text(app_client):
    response = app_client.post("/api/keywords", json={"keyword": "  "})
    assert response.status_code == 400


def test_list_keywords_excludes_inactive(app_client, db_session):
    active = Keyword(keyword="active-kw", is_active=True)
    inactive = Keyword(keyword="inactive-kw", is_active=False)
    db_session.add_all([active, inactive])
    db_session.commit()

    response = app_client.get("/api/keywords")

    kw_texts = [k["keyword"] for k in response.json()["keywords"]]
    assert "active-kw" in kw_texts
    assert "inactive-kw" not in kw_texts
```

- [ ] **Step 2: Chạy test, xác nhận fail vì chưa có router**

Run: `cd backend && pytest tests/test_keywords_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.routers.keywords'`

- [ ] **Step 3: Viết `backend/routers/keywords.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.audit.logger import log_action
from backend.auth.dependencies import require_permission
from backend.db import get_db
from backend.models import Keyword, User

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


@router.get("")
def list_keywords(db: Session = Depends(get_db), _user: User = Depends(require_permission("campaign", "view"))):
    rows = db.query(Keyword).filter_by(is_active=True).order_by(Keyword.keyword).all()
    return {
        "keywords": [
            {
                "keyword_id": str(k.keyword_id),
                "keyword": k.keyword,
                "topic_group": k.topic_group,
            }
            for k in rows
        ]
    }


class KeywordCreateRequest(BaseModel):
    keyword: str
    topic_group: str | None = None


@router.post("", status_code=201)
def create_keyword(
    payload: KeywordCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("campaign", "create")),
):
    keyword_text = payload.keyword.strip()
    if not keyword_text:
        raise HTTPException(status_code=400, detail="Từ khóa không được để trống")

    new_keyword = Keyword(keyword=keyword_text, topic_group=payload.topic_group)
    db.add(new_keyword)
    db.flush()

    log_action(
        db,
        user_id=current_user.user_id,
        action="CREATE",
        entity_type="keyword",
        entity_id=new_keyword.keyword_id,
        new_value={"keyword": keyword_text, "topic_group": payload.topic_group},
    )
    db.commit()

    return {
        "keyword_id": str(new_keyword.keyword_id),
        "keyword": new_keyword.keyword,
        "topic_group": new_keyword.topic_group,
    }
```

- [ ] **Step 4: Chạy lại test, xác nhận pass**

Run: `cd backend && pytest tests/test_keywords_router.py -v`
Expected: 4 test PASS.

- [ ] **Step 5: Wire router vào `backend/main.py`**

```python
from backend.routers import audit_logs, auth, keywords, reports, roles, sources, users
```

Thêm dòng `app.include_router(keywords.router)` ngay sau `app.include_router(sources.router)`.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/keywords.py backend/tests/test_keywords_router.py backend/main.py
git commit -m "feat: thêm API GET/POST /api/keywords"
```

---

## Task 4: Router `campaigns.py` — tạo Campaign + list + detail

**Files:**
- Create: `backend/routers/campaigns.py`
- Create: `backend/tests/test_campaigns_router.py`
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: `Campaign`, `CampaignKeyword`, `CampaignSource`, `Keyword`, `Source`, `User` models (Task 2 + đã có sẵn), `require_permission()`, `log_action()`.
- Produces: hàm nội bộ `_serialize_campaign(db, campaign) -> dict` (dùng lại ở Task 5/6), router `campaigns.router` (prefix `/api/campaigns`).

- [ ] **Step 1: Viết test trước (`backend/tests/test_campaigns_router.py`)**

```python
import uuid
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models import Campaign, Keyword, Role, Source, User, UserRole
from backend.routers import campaigns


@pytest.fixture
def admin_user(db_session):
    role = db_session.query(Role).filter_by(code="ADMIN").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    user = User(username=f"admin-{uuid.uuid4()}", password_hash="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db_session.commit()
    return user


@pytest.fixture
def app_client(db_session, admin_user):
    app = FastAPI()
    app.include_router(campaigns.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(app)


@pytest.fixture
def source(db_session):
    s = Source(name="Test Source", domain=f"test-{uuid.uuid4()}.example", group_name="G1", is_active=True)
    db_session.add(s)
    db_session.commit()
    return s


@pytest.fixture
def keyword(db_session):
    k = Keyword(keyword="test-keyword", is_active=True)
    db_session.add(k)
    db_session.commit()
    return k


def test_create_campaign_rejects_unauthenticated_request(db_session):
    app = FastAPI()
    app.include_router(campaigns.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.post("/api/campaigns", json={"name": "X", "start_date": "2026-08-01", "owner_id": str(uuid.uuid4())})
    assert response.status_code == 403


def test_create_campaign_minimal_defaults_to_draft(app_client, admin_user):
    response = app_client.post(
        "/api/campaigns",
        json={"name": "Chiến dịch test", "start_date": "2026-08-01", "owner_id": str(admin_user.user_id)},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["mode"] == "CONTINUOUS"
    assert body["source_ids"] == []
    assert body["keyword_ids"] == []


def test_create_campaign_requires_name(app_client, admin_user):
    response = app_client.post(
        "/api/campaigns", json={"name": "  ", "start_date": "2026-08-01", "owner_id": str(admin_user.user_id)}
    )
    assert response.status_code == 400


def test_create_campaign_rejects_unknown_owner(app_client):
    response = app_client.post(
        "/api/campaigns", json={"name": "X", "start_date": "2026-08-01", "owner_id": str(uuid.uuid4())}
    )
    assert response.status_code == 400


def test_create_campaign_with_sources_and_keywords(app_client, admin_user, source, keyword):
    response = app_client.post(
        "/api/campaigns",
        json={
            "name": "Chiến dịch đầy đủ",
            "start_date": "2026-08-01",
            "owner_id": str(admin_user.user_id),
            "mode": "ONE_SHOT",
            "source_ids": [str(source.source_id)],
            "keyword_ids": [str(keyword.keyword_id)],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["mode"] == "ONE_SHOT"
    assert body["source_ids"] == [str(source.source_id)]
    assert body["keyword_ids"] == [str(keyword.keyword_id)]


def test_create_campaign_rejects_unknown_source_id(app_client, admin_user):
    response = app_client.post(
        "/api/campaigns",
        json={
            "name": "X",
            "start_date": "2026-08-01",
            "owner_id": str(admin_user.user_id),
            "source_ids": [str(uuid.uuid4())],
        },
    )
    assert response.status_code == 400


def test_list_campaigns_filters_by_status(app_client, admin_user, db_session):
    draft = Campaign(name="Draft camp", owner_id=admin_user.user_id, status="DRAFT", start_date=date(2026, 8, 1))
    active = Campaign(name="Active camp", owner_id=admin_user.user_id, status="ACTIVE", start_date=date(2026, 8, 1))
    db_session.add_all([draft, active])
    db_session.commit()

    response = app_client.get("/api/campaigns", params={"status": "ACTIVE"})

    names = [c["name"] for c in response.json()["campaigns"]]
    assert "Active camp" in names
    assert "Draft camp" not in names


def test_list_campaigns_filters_by_keyword_substring(app_client, admin_user, db_session):
    matched = Campaign(name="Chống tin giả y tế", owner_id=admin_user.user_id, start_date=date(2026, 8, 1))
    other = Campaign(name="Chiến dịch khác", owner_id=admin_user.user_id, start_date=date(2026, 8, 1))
    db_session.add_all([matched, other])
    db_session.commit()

    response = app_client.get("/api/campaigns", params={"keyword": "tin giả"})

    names = [c["name"] for c in response.json()["campaigns"]]
    assert "Chống tin giả y tế" in names
    assert "Chiến dịch khác" not in names


def test_get_campaign_detail_returns_404_when_missing(app_client):
    response = app_client.get(f"/api/campaigns/{uuid.uuid4()}")
    assert response.status_code == 404


def test_get_campaign_detail_returns_full_info(app_client, admin_user, source, keyword):
    create_response = app_client.post(
        "/api/campaigns",
        json={
            "name": "Chi tiết",
            "start_date": "2026-08-01",
            "owner_id": str(admin_user.user_id),
            "source_ids": [str(source.source_id)],
            "keyword_ids": [str(keyword.keyword_id)],
        },
    )
    campaign_id = create_response.json()["campaign_id"]

    response = app_client.get(f"/api/campaigns/{campaign_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Chi tiết"
    assert body["source_ids"] == [str(source.source_id)]
    assert body["keyword_ids"] == [str(keyword.keyword_id)]
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd backend && pytest tests/test_campaigns_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.routers.campaigns'`

- [ ] **Step 3: Viết `backend/routers/campaigns.py` (phần create/list/detail)**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.audit.logger import log_action
from backend.auth.dependencies import require_permission
from backend.db import get_db
from backend.models import Campaign, CampaignKeyword, CampaignSource, Keyword, Source, User

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])

_VALID_MODES = {"CONTINUOUS", "ONE_SHOT"}


def _campaign_source_ids(db: Session, campaign_id) -> list[str]:
    rows = db.query(CampaignSource.source_id).filter_by(campaign_id=campaign_id).all()
    return [str(r[0]) for r in rows]


def _campaign_keyword_ids(db: Session, campaign_id) -> list[str]:
    rows = db.query(CampaignKeyword.keyword_id).filter_by(campaign_id=campaign_id).all()
    return [str(r[0]) for r in rows]


def _serialize_campaign(db: Session, campaign: Campaign) -> dict:
    return {
        "campaign_id": str(campaign.campaign_id),
        "code": campaign.code,
        "name": campaign.name,
        "description": campaign.description,
        "objective": campaign.objective,
        "owner_id": str(campaign.owner_id) if campaign.owner_id else None,
        "status": campaign.status,
        "mode": campaign.mode,
        "start_date": campaign.start_date,
        "end_date": campaign.end_date,
        "alert_threshold": campaign.alert_threshold,
        "source_ids": _campaign_source_ids(db, campaign.campaign_id),
        "keyword_ids": _campaign_keyword_ids(db, campaign.campaign_id),
        "created_at": campaign.created_at,
        "updated_at": campaign.updated_at,
    }


def _get_campaign_or_404(db: Session, campaign_id: str) -> Campaign:
    try:
        campaign = db.get(Campaign, uuid.UUID(campaign_id))
    except ValueError:
        campaign = None
    if campaign is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy chiến dịch")
    return campaign


class CampaignCreateRequest(BaseModel):
    name: str
    description: str | None = None
    objective: str | None = None
    owner_id: str
    start_date: str
    end_date: str | None = None
    mode: str = "CONTINUOUS"
    alert_threshold: int = 100
    source_ids: list[str] = []
    keyword_ids: list[str] = []


def _resolve_sources(db: Session, source_ids: list[str]) -> list[Source]:
    try:
        uuids = [uuid.UUID(sid) for sid in source_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="Có source_id không hợp lệ")
    sources = db.query(Source).filter(Source.source_id.in_(uuids)).all()
    if len(sources) != len(source_ids):
        raise HTTPException(status_code=400, detail="Có source_id không tồn tại")
    return sources


def _resolve_keywords(db: Session, keyword_ids: list[str]) -> list[Keyword]:
    try:
        uuids = [uuid.UUID(kid) for kid in keyword_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="Có keyword_id không hợp lệ")
    kws = db.query(Keyword).filter(Keyword.keyword_id.in_(uuids)).all()
    if len(kws) != len(keyword_ids):
        raise HTTPException(status_code=400, detail="Có keyword_id không tồn tại")
    return kws


@router.post("", status_code=201)
def create_campaign(
    payload: CampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("campaign", "create")),
):
    # BR-CAMP-01: Tên, Thời gian bắt đầu, Người phụ trách bắt buộc
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tên chiến dịch không được để trống (BR-CAMP-01)")

    try:
        owner_uuid = uuid.UUID(payload.owner_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="owner_id không hợp lệ")
    if db.get(User, owner_uuid) is None:
        raise HTTPException(status_code=400, detail="owner_id không tồn tại")

    if payload.mode not in _VALID_MODES:
        raise HTTPException(status_code=400, detail=f"mode phải là 1 trong {_VALID_MODES}")

    sources = _resolve_sources(db, payload.source_ids)
    kws = _resolve_keywords(db, payload.keyword_ids)

    # BR-CAMP-02: mọi campaign mới luôn khởi tạo ở DRAFT — không cho tạo thẳng ACTIVE,
    # phải qua endpoint /activate để verify điều kiện BR-CAMP-03 riêng
    new_campaign = Campaign(
        name=name,
        description=payload.description,
        objective=payload.objective,
        owner_id=owner_uuid,
        status="DRAFT",
        mode=payload.mode,
        start_date=payload.start_date,
        end_date=payload.end_date,
        alert_threshold=payload.alert_threshold,
    )
    db.add(new_campaign)
    db.flush()

    for s in sources:
        db.add(CampaignSource(campaign_id=new_campaign.campaign_id, source_id=s.source_id))
    for k in kws:
        db.add(CampaignKeyword(campaign_id=new_campaign.campaign_id, keyword_id=k.keyword_id))

    log_action(
        db,
        user_id=current_user.user_id,
        action="CREATE",
        entity_type="campaign",
        entity_id=new_campaign.campaign_id,
        new_value={"name": name, "mode": payload.mode, "source_ids": payload.source_ids, "keyword_ids": payload.keyword_ids},
    )
    db.commit()

    return _serialize_campaign(db, new_campaign)


@router.get("")
def list_campaigns(
    status: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("campaign", "view")),
):
    query = db.query(Campaign)
    if status:
        query = query.filter(Campaign.status == status)
    if keyword:
        # "keyword" ở đây là ô tìm kiếm tự do trên tên chiến dịch (rule 05: filter status, keyword)
        # — không phải lọc theo keyword_id cụ thể (đã xác nhận với user 2026-07-20)
        query = query.filter(Campaign.name.ilike(f"%{keyword}%"))

    rows = query.order_by(Campaign.created_at.desc()).all()
    return {"campaigns": [_serialize_campaign(db, c) for c in rows]}


@router.get("/{campaign_id}")
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("campaign", "view")),
):
    campaign = _get_campaign_or_404(db, campaign_id)
    return _serialize_campaign(db, campaign)
```

- [ ] **Step 4: Chạy lại test, xác nhận pass**

Run: `cd backend && pytest tests/test_campaigns_router.py -v`
Expected: 10 test PASS (các test create/list/detail — chưa có update/delete/activate/pause, để Task 5/6).

- [ ] **Step 5: Wire router vào `backend/main.py`**

```python
from backend.routers import audit_logs, auth, campaigns, keywords, reports, roles, sources, users
```

Thêm dòng `app.include_router(campaigns.router)` sau `app.include_router(keywords.router)`.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/campaigns.py backend/tests/test_campaigns_router.py backend/main.py
git commit -m "feat: thêm API tạo/liệt kê/xem chi tiết Campaign"
```

---

## Task 5: Router `campaigns.py` — cập nhật (`PUT`) và xóa mềm (`DELETE` → `ARCHIVED`)

**Files:**
- Modify: `backend/routers/campaigns.py`
- Modify: `backend/tests/test_campaigns_router.py`

**Interfaces:**
- Consumes: `_serialize_campaign`, `_get_campaign_or_404`, `_resolve_sources`, `_resolve_keywords` (Task 4).
- Produces: `PUT /api/campaigns/{id}`, `DELETE /api/campaigns/{id}`.

- [ ] **Step 1: Thêm test vào `test_campaigns_router.py`**

```python
def test_update_campaign_changes_fields(app_client, admin_user, source, keyword):
    create_response = app_client.post(
        "/api/campaigns", json={"name": "Trước sửa", "start_date": "2026-08-01", "owner_id": str(admin_user.user_id)}
    )
    campaign_id = create_response.json()["campaign_id"]

    response = app_client.put(
        f"/api/campaigns/{campaign_id}",
        json={"name": "Sau sửa", "source_ids": [str(source.source_id)], "keyword_ids": [str(keyword.keyword_id)]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Sau sửa"
    assert body["source_ids"] == [str(source.source_id)]
    assert body["keyword_ids"] == [str(keyword.keyword_id)]


def test_update_campaign_rejects_when_archived(app_client, admin_user, db_session):
    campaign = Campaign(name="Đã archive", owner_id=admin_user.user_id, status="ARCHIVED", start_date=date(2026, 8, 1))
    db_session.add(campaign)
    db_session.commit()

    response = app_client.put(f"/api/campaigns/{campaign.campaign_id}", json={"name": "Sửa sau archive"})

    assert response.status_code == 400  # BR-CAMP-04: ARCHIVED chỉ được xem, không được sửa


def test_delete_campaign_soft_deletes_to_archived(app_client, admin_user):
    create_response = app_client.post(
        "/api/campaigns", json={"name": "Sẽ archive", "start_date": "2026-08-01", "owner_id": str(admin_user.user_id)}
    )
    campaign_id = create_response.json()["campaign_id"]

    response = app_client.delete(f"/api/campaigns/{campaign_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"

    detail = app_client.get(f"/api/campaigns/{campaign_id}")
    assert detail.json()["status"] == "ARCHIVED"  # BR-CAMP-05: không xóa vật lý


def test_delete_campaign_already_archived_returns_400(app_client, admin_user, db_session):
    campaign = Campaign(name="Archived rồi", owner_id=admin_user.user_id, status="ARCHIVED", start_date=date(2026, 8, 1))
    db_session.add(campaign)
    db_session.commit()

    response = app_client.delete(f"/api/campaigns/{campaign.campaign_id}")

    assert response.status_code == 400
```

- [ ] **Step 2: Chạy test, xác nhận 4 test mới fail (405 Method Not Allowed)**

Run: `cd backend && pytest tests/test_campaigns_router.py -v -k "update_campaign or delete_campaign"`
Expected: FAIL — 405, chưa có route PUT/DELETE.

- [ ] **Step 3: Thêm vào `backend/routers/campaigns.py`**

```python
class CampaignUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    objective: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    mode: str | None = None
    alert_threshold: int | None = None
    source_ids: list[str] | None = None
    keyword_ids: list[str] | None = None


@router.put("/{campaign_id}")
def update_campaign(
    campaign_id: str,
    payload: CampaignUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("campaign", "update")),
):
    campaign = _get_campaign_or_404(db, campaign_id)

    # BR-CAMP-04: chiến dịch ARCHIVED chỉ được xem, không được sửa
    if campaign.status == "ARCHIVED":
        raise HTTPException(status_code=400, detail="Chiến dịch đã lưu trữ (ARCHIVED), không thể sửa (BR-CAMP-04)")

    old_value = {"name": campaign.name, "status": campaign.status}

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Tên chiến dịch không được để trống (BR-CAMP-01)")
        campaign.name = name
    if payload.description is not None:
        campaign.description = payload.description
    if payload.objective is not None:
        campaign.objective = payload.objective
    if payload.start_date is not None:
        campaign.start_date = payload.start_date
    if payload.end_date is not None:
        campaign.end_date = payload.end_date
    if payload.mode is not None:
        if payload.mode not in _VALID_MODES:
            raise HTTPException(status_code=400, detail=f"mode phải là 1 trong {_VALID_MODES}")
        campaign.mode = payload.mode
    if payload.alert_threshold is not None:
        campaign.alert_threshold = payload.alert_threshold

    if payload.source_ids is not None:
        sources = _resolve_sources(db, payload.source_ids)
        db.query(CampaignSource).filter_by(campaign_id=campaign.campaign_id).delete()
        for s in sources:
            db.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=s.source_id))
    if payload.keyword_ids is not None:
        kws = _resolve_keywords(db, payload.keyword_ids)
        db.query(CampaignKeyword).filter_by(campaign_id=campaign.campaign_id).delete()
        for k in kws:
            db.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=k.keyword_id))

    log_action(
        db,
        user_id=current_user.user_id,
        action="UPDATE",
        entity_type="campaign",
        entity_id=campaign.campaign_id,
        old_value=old_value,
        new_value={"name": campaign.name, "status": campaign.status},
    )
    db.commit()

    return _serialize_campaign(db, campaign)


@router.delete("/{campaign_id}")
def delete_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("campaign", "archive")),
):
    campaign = _get_campaign_or_404(db, campaign_id)

    # BR-CAMP-05: không xóa vật lý, chỉ chuyển ARCHIVED (dừng crawl, giữ nguyên dữ liệu cũ)
    if campaign.status == "ARCHIVED":
        raise HTTPException(status_code=400, detail="Chiến dịch đã ở trạng thái ARCHIVED")

    old_status = campaign.status
    campaign.status = "ARCHIVED"

    log_action(
        db,
        user_id=current_user.user_id,
        action="DELETE",
        entity_type="campaign",
        entity_id=campaign.campaign_id,
        old_value={"status": old_status},
        new_value={"status": "ARCHIVED"},
    )
    db.commit()

    return _serialize_campaign(db, campaign)
```

- [ ] **Step 4: Chạy lại toàn bộ test file, xác nhận pass**

Run: `cd backend && pytest tests/test_campaigns_router.py -v`
Expected: tất cả test PASS (14 test).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/campaigns.py backend/tests/test_campaigns_router.py
git commit -m "feat: thêm API cập nhật và xóa mềm (ARCHIVED) Campaign"
```

---

## Task 6: Router `campaigns.py` — `activate` và `pause`

**Files:**
- Modify: `backend/routers/campaigns.py`
- Modify: `backend/tests/test_campaigns_router.py`

**Interfaces:**
- Consumes: `_serialize_campaign`, `_get_campaign_or_404` (Task 4), `CampaignSource`, `CampaignKeyword` (Task 2).
- Produces: `POST /api/campaigns/{id}/activate`, `POST /api/campaigns/{id}/pause`.

- [ ] **Step 1: Thêm test vào `test_campaigns_router.py`**

```python
def test_activate_campaign_requires_source_and_keyword(app_client, admin_user):
    create_response = app_client.post(
        "/api/campaigns", json={"name": "Thiếu source/keyword", "start_date": "2026-08-01", "owner_id": str(admin_user.user_id)}
    )
    campaign_id = create_response.json()["campaign_id"]

    response = app_client.post(f"/api/campaigns/{campaign_id}/activate")

    assert response.status_code == 400  # BR-CAMP-03


def test_activate_campaign_succeeds_with_source_and_keyword(app_client, admin_user, source, keyword):
    create_response = app_client.post(
        "/api/campaigns",
        json={
            "name": "Đủ điều kiện",
            "start_date": "2026-08-01",
            "owner_id": str(admin_user.user_id),
            "source_ids": [str(source.source_id)],
            "keyword_ids": [str(keyword.keyword_id)],
        },
    )
    campaign_id = create_response.json()["campaign_id"]

    response = app_client.post(f"/api/campaigns/{campaign_id}/activate")

    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"


def test_activate_campaign_rejects_when_archived(app_client, admin_user, db_session):
    campaign = Campaign(name="Archived", owner_id=admin_user.user_id, status="ARCHIVED", start_date=date(2026, 8, 1))
    db_session.add(campaign)
    db_session.commit()

    response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 400


def test_pause_campaign_requires_active_status(app_client, admin_user, db_session):
    campaign = Campaign(name="Draft chưa activate", owner_id=admin_user.user_id, status="DRAFT", start_date=date(2026, 8, 1))
    db_session.add(campaign)
    db_session.commit()

    response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/pause")

    assert response.status_code == 400


def test_pause_campaign_succeeds_from_active(app_client, admin_user, db_session):
    campaign = Campaign(name="Đang active", owner_id=admin_user.user_id, status="ACTIVE", start_date=date(2026, 8, 1))
    db_session.add(campaign)
    db_session.commit()

    response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/pause")

    assert response.status_code == 200
    assert response.json()["status"] == "PAUSED"
```

- [ ] **Step 2: Chạy test, xác nhận fail (404/405)**

Run: `cd backend && pytest tests/test_campaigns_router.py -v -k "activate or pause"`
Expected: FAIL — chưa có route.

- [ ] **Step 3: Thêm vào `backend/routers/campaigns.py`**

```python
@router.post("/{campaign_id}/activate")
def activate_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("campaign", "update")),
):
    campaign = _get_campaign_or_404(db, campaign_id)

    if campaign.status not in ("DRAFT", "PAUSED"):
        raise HTTPException(
            status_code=400,
            detail=f"Không thể kích hoạt chiến dịch đang ở trạng thái {campaign.status}",
        )

    # BR-CAMP-03: chỉ chuyển ACTIVE khi có >=1 nguồn VÀ >=1 từ khóa
    has_source = db.query(CampaignSource).filter_by(campaign_id=campaign.campaign_id).first() is not None
    has_keyword = db.query(CampaignKeyword).filter_by(campaign_id=campaign.campaign_id).first() is not None
    if not (has_source and has_keyword):
        raise HTTPException(
            status_code=400,
            detail="Chiến dịch cần ít nhất 1 nguồn dữ liệu và 1 từ khóa để kích hoạt (BR-CAMP-03)",
        )

    old_status = campaign.status
    campaign.status = "ACTIVE"

    log_action(
        db,
        user_id=current_user.user_id,
        action="UPDATE",
        entity_type="campaign",
        entity_id=campaign.campaign_id,
        old_value={"status": old_status},
        new_value={"status": "ACTIVE"},
    )
    db.commit()

    return _serialize_campaign(db, campaign)


@router.post("/{campaign_id}/pause")
def pause_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("campaign", "update")),
):
    campaign = _get_campaign_or_404(db, campaign_id)

    if campaign.status != "ACTIVE":
        raise HTTPException(
            status_code=400,
            detail=f"Chỉ tạm dừng được chiến dịch đang ACTIVE (hiện tại: {campaign.status})",
        )

    campaign.status = "PAUSED"

    log_action(
        db,
        user_id=current_user.user_id,
        action="UPDATE",
        entity_type="campaign",
        entity_id=campaign.campaign_id,
        old_value={"status": "ACTIVE"},
        new_value={"status": "PAUSED"},
    )
    db.commit()

    return _serialize_campaign(db, campaign)
```

- [ ] **Step 4: Chạy lại toàn bộ test file, xác nhận pass**

Run: `cd backend && pytest tests/test_campaigns_router.py -v`
Expected: tất cả test PASS (19 test).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/campaigns.py backend/tests/test_campaigns_router.py
git commit -m "feat: thêm API activate/pause Campaign (BR-CAMP-03)"
```

---

## Task 7: Verify toàn diện + test với dữ liệu thật (bước Commit của EPCC)

**Files:** không tạo file mới — chạy verify trên toàn bộ thay đổi Task 1–6.

- [ ] **Step 1: Chạy toàn bộ test suite backend**

Run: `cd backend && pytest -v`
Expected: toàn bộ PASS, không có test nào bị regression (đặc biệt `test_sources_router.py`, `test_users_router.py`, `test_reports_router.py` — xác nhận Phase 2 không đụng gì tới flow cũ).

- [ ] **Step 2: Lint + type check (nếu project có cấu hình sẵn)**

Run: `cd backend && ruff check .` (hoặc lệnh lint đang dùng trong CI — kiểm tra `backend/pyproject.toml`/`backend/setup.cfg` nếu chưa chắc lệnh chính xác)
Expected: không lỗi mới phát sinh từ file vừa thêm/sửa.

- [ ] **Step 3: Test thật với server đang chạy — dùng ít nhất 1 nguồn thực tế**

Khởi động backend (`uvicorn backend.main:app --reload` hoặc qua `docker compose up`), đăng nhập lấy access token qua `POST /api/auth/login`, rồi:

```bash
# 1. Tạo 1 keyword thật
curl -s -X POST http://localhost:8000/api/keywords \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"keyword": "tin giả y tế", "topic_group": "Tin giả và thông tin sai lệch"}'

# 2. Lấy 1 source thật đang có sẵn trong DB (VD VTV News)
curl -s http://localhost:8000/api/sources -H "Authorization: Bearer $TOKEN"

# 3. Tạo Campaign với source_id + keyword_id thật lấy được ở trên
curl -s -X POST http://localhost:8000/api/campaigns \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Test thật Phase 2", "start_date": "2026-08-01", "owner_id": "<user_id thật>", "source_ids": ["<source_id thật>"], "keyword_ids": ["<keyword_id thật>"]}'

# 4. Activate — kỳ vọng status=ACTIVE vì đã có đủ source+keyword
curl -s -X POST http://localhost:8000/api/campaigns/<campaign_id>/activate -H "Authorization: Bearer $TOKEN"

# 5. Pause — kỳ vọng status=PAUSED
curl -s -X POST http://localhost:8000/api/campaigns/<campaign_id>/pause -H "Authorization: Bearer $TOKEN"

# 6. Xác nhận /api/reports/create và /api/sources vẫn hoạt động bình thường (Phase 2 không phá vỡ flow cũ)
curl -s http://localhost:8000/api/reports/history -H "Authorization: Bearer $TOKEN"
```

Expected: cả 6 bước trả đúng status code kỳ vọng, đặc biệt bước 6 xác nhận flow `jobs`/`reports` cũ không bị ảnh hưởng.

- [ ] **Step 4: Verify `audit_logs` ghi nhận đúng hành động**

```bash
curl -s http://localhost:8000/api/audit-logs -H "Authorization: Bearer $TOKEN"
```

Expected: thấy các dòng `entity_type=campaign`/`keyword` với `action=CREATE/UPDATE/DELETE` tương ứng các bước ở Step 3.

- [ ] **Step 5: Cập nhật `CLAUDE.md`**

Thêm 1 dòng vào mục "Phần đã code — `[ĐÃ CODE]`" và "Bước tiếp theo" xác nhận Phase 2 hoàn thành, sẵn sàng Phase 3. (Không tự làm trong plan này — nhắc để làm thủ công sau khi review xong toàn bộ Phase 2, theo đúng pattern đã làm ở Phase 1.)

---

## Self-Review — đối chiếu spec

**Spec coverage:**
- BR-CAMP-01 (Tên/start_date/owner bắt buộc) → Task 4 Step 3 (`create_campaign` validation).
- BR-CAMP-02 (5 trạng thái DRAFT→ACTIVE→PAUSED/COMPLETED→ARCHIVED) → cột `status`, Task 4 (khởi tạo DRAFT), Task 6 (activate/pause). `COMPLETED` không có endpoint riêng trong Phase 2 — đúng phạm vi đã chốt, vì `COMPLETED` là trạng thái Scheduler tự set khi `mode=ONE_SHOT` crawl xong (Phase 3), không phải hành động thủ công qua API.
- BR-CAMP-03 (>=1 nguồn + >=1 từ khóa mới ACTIVE) → Task 6 `activate_campaign`.
- BR-CAMP-04 (ARCHIVED không sửa/kích hoạt lại) → Task 5 `update_campaign` chặn, Task 6 `activate_campaign` chặn (status không thuộc DRAFT/PAUSED).
- BR-CAMP-05 (không xóa vật lý) → Task 5 `delete_campaign` chỉ set `status=ARCHIVED`.
- BR-CAMP-06 (N:N Campaign-Source) → bảng `campaign_sources` (Task 1/2), xử lý trong create/update (Task 4/5).
- BR-CAMP-07 (`mode` CONTINUOUS/ONE_SHOT) → cột `mode`, validate `_VALID_MODES` (Task 4).
- BR-SRC-01 (`source_group`) → cột thêm ở Task 1/2 (chỉ thêm cột, chưa có UI/API gán nhóm — đúng phạm vi Phase 2 "Sửa: sources — thêm source_group", không yêu cầu gì thêm).
- API `POST/GET/PUT/DELETE /api/campaigns`, `/activate` → Task 4/5/6. `/pause` → thêm theo quyết định đã chốt với user (rule 05 có, roadmap Phase 2 không liệt kê tường minh).

**Gaps đã xác nhận KHÔNG thuộc phạm vi Phase 2 này (không phải thiếu sót — đã chốt với user hoặc đúng theo roadmap):**
- FE `/campaigns` List/Form — chưa nối API thật, vẫn mock.
- Migrate dữ liệu `jobs` cũ sang `campaigns` — không làm.
- `campaign_articles` (matching từ khóa hậu-crawl) — thuộc Phase 3, chưa cần bảng này ở Phase 2 vì chưa có Scheduler crawl gì để match.
- `PUT/DELETE /api/keywords` — chỉ làm `GET`/`POST` theo quyết định đã chốt (YAGNI).

**Placeholder scan:** không còn `TBD`/`TODO`/"tương tự Task N" nào trong các bước code — đã rà lại toàn bộ Step.

**Type consistency:** `_serialize_campaign`, `_get_campaign_or_404`, `_resolve_sources`, `_resolve_keywords` dùng thống nhất tên/signature xuyên suốt Task 4/5/6.

---

## Execution Handoff

Plan hoàn chỉnh, lưu tại `docs/superpowers/plans/2026-07-20-phase2-campaign-master-data.md`. Hai lựa chọn thực thi:

1. **Subagent-Driven (khuyến nghị)** — dispatch 1 subagent riêng cho mỗi Task, review giữa các Task, lặp nhanh.
2. **Inline Execution** — thực thi tuần tự trong session hiện tại, checkpoint theo batch.

Bạn muốn chọn cách nào?
