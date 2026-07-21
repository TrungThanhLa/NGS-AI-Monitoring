import uuid
from datetime import date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models import (
    Article,
    ArticleAnalysis,
    AuditLog,
    Campaign,
    CampaignArticle,
    Role,
    Source,
    User,
    UserRole,
)
from backend.routers import contents


def _make_user_with_role(db_session, role_code):
    role = db_session.query(Role).filter_by(code=role_code).first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    user = User(username=f"{role_code.lower()}-{uuid.uuid4()}", password_hash="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db_session.commit()
    return user


@pytest.fixture
def admin_user(db_session):
    return _make_user_with_role(db_session, "ADMIN")


@pytest.fixture
def analyst_user(db_session):
    return _make_user_with_role(db_session, "ANALYST")


@pytest.fixture
def operator_user(db_session):
    return _make_user_with_role(db_session, "OPERATOR")


@pytest.fixture
def app_client(db_session, admin_user):
    app = FastAPI()
    app.include_router(contents.router)
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
def campaign(db_session, admin_user):
    c = Campaign(name="Chiến dịch test", owner_id=admin_user.user_id, start_date=date(2026, 8, 1))
    db_session.add(c)
    db_session.commit()
    return c


@pytest.fixture
def article(db_session, source):
    a = Article(
        source_id=source.source_id,
        url=f"https://example.com/{uuid.uuid4()}",
        url_hash=uuid.uuid4().hex,
        title="Bài viết test",
        content_raw="Nội dung test",
        published_at=datetime(2026, 7, 15),
        status="analyzed",
    )
    db_session.add(a)
    db_session.commit()
    return a


def _add_analysis(db_session, article_row, sentiment="negative", analyzed_at=None):
    analysis = ArticleAnalysis(
        article_id=article_row.article_id,
        topics=["Tin giả và thông tin sai lệch"],
        keywords=["tin giả"],
        sentiment=sentiment,
        emotion="Fear",
        confidence=0.9,
        needs_review=False,
        summary="Tóm tắt test",
        prompt_version=1,
        ai_model="qwen3:8b",
        analyzed_at=analyzed_at or datetime(2026, 7, 15, 10, 0, 0),
    )
    db_session.add(analysis)
    db_session.commit()
    return analysis


# ---------- Auth ----------

def test_list_contents_rejects_unauthenticated_request(db_session):
    app = FastAPI()
    app.include_router(contents.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get("/api/contents")
    assert response.status_code == 403


def test_get_content_rejects_unauthenticated_request(db_session, article):
    app = FastAPI()
    app.include_router(contents.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get(f"/api/contents/{article.article_id}")
    assert response.status_code == 403


def test_review_content_rejects_unauthenticated_request(db_session, article):
    app = FastAPI()
    app.include_router(contents.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.post(f"/api/contents/{article.article_id}/review", json={"review_status": "REVIEWED"})
    assert response.status_code == 403


# ---------- List ----------

def test_list_contents_returns_all_by_default(app_client, article):
    response = app_client.get("/api/contents")

    assert response.status_code == 200
    ids = [c["article_id"] for c in response.json()["contents"]]
    assert str(article.article_id) in ids


def test_list_contents_filters_by_source_id(app_client, db_session, article):
    other_source = Source(name="Other", domain=f"other-{uuid.uuid4()}.example", group_name="G2", is_active=True)
    db_session.add(other_source)
    db_session.commit()
    other_article = Article(
        source_id=other_source.source_id,
        url=f"https://other.example/{uuid.uuid4()}",
        url_hash=uuid.uuid4().hex,
        title="Bài khác nguồn",
    )
    db_session.add(other_article)
    db_session.commit()

    response = app_client.get("/api/contents", params={"source_id": str(article.source_id)})

    ids = [c["article_id"] for c in response.json()["contents"]]
    assert str(article.article_id) in ids
    assert str(other_article.article_id) not in ids


def test_list_contents_filters_by_campaign_id(app_client, db_session, article, campaign):
    db_session.add(CampaignArticle(campaign_id=campaign.campaign_id, article_id=article.article_id))
    db_session.commit()

    not_linked = Article(
        source_id=article.source_id,
        url=f"https://example.com/{uuid.uuid4()}",
        url_hash=uuid.uuid4().hex,
        title="Không thuộc campaign",
    )
    db_session.add(not_linked)
    db_session.commit()

    response = app_client.get("/api/contents", params={"campaign_id": str(campaign.campaign_id)})

    ids = [c["article_id"] for c in response.json()["contents"]]
    assert str(article.article_id) in ids
    assert str(not_linked.article_id) not in ids


def test_list_contents_filters_by_sentiment(app_client, db_session, article):
    _add_analysis(db_session, article, sentiment="negative")
    no_analysis_article = Article(
        source_id=article.source_id,
        url=f"https://example.com/{uuid.uuid4()}",
        url_hash=uuid.uuid4().hex,
        title="Chưa phân tích",
    )
    db_session.add(no_analysis_article)
    db_session.commit()

    response = app_client.get("/api/contents", params={"sentiment": "negative"})

    ids = [c["article_id"] for c in response.json()["contents"]]
    assert str(article.article_id) in ids
    assert str(no_analysis_article.article_id) not in ids


def test_list_contents_filters_by_review_status(app_client, db_session, article):
    reviewed = Article(
        source_id=article.source_id,
        url=f"https://example.com/{uuid.uuid4()}",
        url_hash=uuid.uuid4().hex,
        title="Đã review",
        review_status="REVIEWED",
    )
    db_session.add(reviewed)
    db_session.commit()

    response = app_client.get("/api/contents", params={"review_status": "REVIEWED"})

    ids = [c["article_id"] for c in response.json()["contents"]]
    assert str(reviewed.article_id) in ids
    assert str(article.article_id) not in ids


def test_list_contents_filters_by_date_range(app_client, db_session, article):
    out_of_range = Article(
        source_id=article.source_id,
        url=f"https://example.com/{uuid.uuid4()}",
        url_hash=uuid.uuid4().hex,
        title="Ngoài khoảng ngày",
        published_at=datetime(2020, 1, 1),
    )
    db_session.add(out_of_range)
    db_session.commit()

    response = app_client.get(
        "/api/contents", params={"date_from": "2026-07-01", "date_to": "2026-07-31"}
    )

    ids = [c["article_id"] for c in response.json()["contents"]]
    assert str(article.article_id) in ids
    assert str(out_of_range.article_id) not in ids


def test_list_contents_invalid_source_id_returns_400(app_client):
    response = app_client.get("/api/contents", params={"source_id": "not-a-uuid"})
    assert response.status_code == 400


def test_list_contents_invalid_campaign_id_returns_400(app_client):
    response = app_client.get("/api/contents", params={"campaign_id": "not-a-uuid"})
    assert response.status_code == 400


def test_list_contents_uses_latest_analysis_sentiment(app_client, db_session, article):
    # Bài bị AI phân tích lại (rule 07: qwen3:8b không cố định output giữa các lần gọi) —
    # list phải phản ánh đúng bản MỚI NHẤT, không phải bản đầu tiên/bất kỳ.
    _add_analysis(db_session, article, sentiment="negative", analyzed_at=datetime(2026, 7, 10))
    _add_analysis(db_session, article, sentiment="positive", analyzed_at=datetime(2026, 7, 20))

    response = app_client.get("/api/contents")

    row = next(c for c in response.json()["contents"] if c["article_id"] == str(article.article_id))
    assert row["sentiment"] == "positive"

    filtered = app_client.get("/api/contents", params={"sentiment": "positive"})
    assert str(article.article_id) in [c["article_id"] for c in filtered.json()["contents"]]

    filtered_old = app_client.get("/api/contents", params={"sentiment": "negative"})
    assert str(article.article_id) not in [c["article_id"] for c in filtered_old.json()["contents"]]


# ---------- Detail ----------

def test_get_content_detail_returns_full_payload_with_analysis(app_client, article, db_session):
    _add_analysis(db_session, article, sentiment="negative")

    response = app_client.get(f"/api/contents/{article.article_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["article_id"] == str(article.article_id)
    assert body["content_raw"] == "Nội dung test"
    assert body["analysis"]["sentiment"] == "negative"


def test_get_content_detail_without_analysis_returns_null_analysis(app_client, article):
    response = app_client.get(f"/api/contents/{article.article_id}")

    assert response.status_code == 200
    assert response.json()["analysis"] is None


def test_get_content_detail_returns_404_when_missing(app_client):
    response = app_client.get(f"/api/contents/{uuid.uuid4()}")
    assert response.status_code == 404


def test_get_content_detail_invalid_uuid_returns_404(app_client):
    response = app_client.get("/api/contents/not-a-uuid")
    assert response.status_code == 404


def test_get_content_detail_uses_latest_analysis(app_client, db_session, article):
    _add_analysis(db_session, article, sentiment="negative", analyzed_at=datetime(2026, 7, 10))
    _add_analysis(db_session, article, sentiment="positive", analyzed_at=datetime(2026, 7, 20))

    response = app_client.get(f"/api/contents/{article.article_id}")

    assert response.json()["analysis"]["sentiment"] == "positive"


# ---------- Review ----------

def test_review_content_success_updates_status_and_audit_log(app_client, admin_user, article, db_session):
    response = app_client.post(
        f"/api/contents/{article.article_id}/review",
        json={"review_status": "REVIEWED", "note": "Đã xem xét"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "REVIEWED"
    assert body["reviewer_note"] == "Đã xem xét"
    assert body["reviewed_by"] == str(admin_user.user_id)
    assert body["reviewed_at"] is not None

    log = (
        db_session.query(AuditLog)
        .filter_by(action="content.review", entity_id=article.article_id)
        .first()
    )
    assert log is not None


def test_review_content_forbidden_for_operator_role(db_session, operator_user, article):
    app = FastAPI()
    app.include_router(contents.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: operator_user
    client = TestClient(app)

    response = client.post(f"/api/contents/{article.article_id}/review", json={"review_status": "REVIEWED"})
    assert response.status_code == 403


def test_review_content_allowed_for_analyst_role(db_session, analyst_user, article):
    app = FastAPI()
    app.include_router(contents.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: analyst_user
    client = TestClient(app)

    response = client.post(f"/api/contents/{article.article_id}/review", json={"review_status": "REVIEWED"})
    assert response.status_code == 200


def test_review_content_rejects_invalid_status_value(app_client, article, db_session):
    response = app_client.post(
        f"/api/contents/{article.article_id}/review", json={"review_status": "BOGUS"}
    )

    assert response.status_code == 400
    assert db_session.query(AuditLog).filter_by(action="content.review", entity_id=article.article_id).first() is None


def test_review_content_returns_404_when_missing(app_client):
    response = app_client.post(
        f"/api/contents/{uuid.uuid4()}/review", json={"review_status": "REVIEWED"}
    )
    assert response.status_code == 404


def test_review_content_note_is_optional_and_does_not_clear_existing(app_client, article, db_session):
    article.reviewer_note = "Ghi chú cũ"
    db_session.commit()

    response = app_client.post(f"/api/contents/{article.article_id}/review", json={"review_status": "VERIFIED"})

    assert response.status_code == 200
    assert response.json()["reviewer_note"] == "Ghi chú cũ"
