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


def test_list_keywords_include_inactive_param(app_client, db_session):
    # Campaign/Report form gọi GET mặc định (chỉ active) để chọn từ khóa — trang quản trị
    # (System > Danh mục dùng chung) cần thấy cả từ khóa đã ngừng dùng để bật lại được,
    # nên thêm query param riêng thay vì đổi hành vi mặc định (tránh phá 2 nơi đang gọi)
    active = Keyword(keyword="active-kw2", is_active=True)
    inactive = Keyword(keyword="inactive-kw2", is_active=False)
    db_session.add_all([active, inactive])
    db_session.commit()

    response = app_client.get("/api/keywords?include_inactive=true")

    kw_texts = [k["keyword"] for k in response.json()["keywords"]]
    assert "active-kw2" in kw_texts
    assert "inactive-kw2" in kw_texts


def test_update_keyword_topic_group_and_deactivate(app_client, db_session):
    kw = Keyword(keyword="tin giả covid", topic_group="Tin giả và thông tin sai lệch", is_active=True)
    db_session.add(kw)
    db_session.commit()

    response = app_client.put(
        f"/api/keywords/{kw.keyword_id}",
        json={"topic_group": "Kiểm chứng và xác thực thông tin", "is_active": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["topic_group"] == "Kiểm chứng và xác thực thông tin"
    assert body["is_active"] is False

    db_session.refresh(kw)
    assert kw.topic_group == "Kiểm chứng và xác thực thông tin"
    assert kw.is_active is False


def test_update_keyword_requires_nonempty_text_if_provided(app_client, db_session):
    kw = Keyword(keyword="giữ nguyên", is_active=True)
    db_session.add(kw)
    db_session.commit()

    response = app_client.put(f"/api/keywords/{kw.keyword_id}", json={"keyword": "   "})
    assert response.status_code == 400


def test_update_keyword_404_when_not_found(app_client):
    response = app_client.put(f"/api/keywords/{uuid.uuid4()}", json={"is_active": False})
    assert response.status_code == 404
