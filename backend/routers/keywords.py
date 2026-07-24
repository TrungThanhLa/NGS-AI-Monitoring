import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.audit.logger import log_action
from backend.auth.dependencies import require_permission
from backend.db import get_db
from backend.models import Keyword, User

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


@router.get("")
def list_keywords(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("campaign", "view")),
):
    query = db.query(Keyword)
    if not include_inactive:
        query = query.filter_by(is_active=True)
    rows = query.order_by(Keyword.keyword).all()
    return {
        "keywords": [
            {
                "keyword_id": str(k.keyword_id),
                "keyword": k.keyword,
                "topic_group": k.topic_group,
                "is_active": k.is_active,
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
    request: Request,
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
        request=request,
    )
    db.commit()

    return {
        "keyword_id": str(new_keyword.keyword_id),
        "keyword": new_keyword.keyword,
        "topic_group": new_keyword.topic_group,
    }


class KeywordUpdateRequest(BaseModel):
    keyword: str | None = None
    topic_group: str | None = None
    is_active: bool | None = None


@router.put("/{keyword_id}")
def update_keyword(
    keyword_id: str,
    payload: KeywordUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("campaign", "update")),
):
    try:
        kw = db.get(Keyword, uuid.UUID(keyword_id))
    except ValueError:
        kw = None
    if kw is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy từ khóa")

    if payload.keyword is not None and not payload.keyword.strip():
        raise HTTPException(status_code=400, detail="Từ khóa không được để trống")

    old_value = {"keyword": kw.keyword, "topic_group": kw.topic_group, "is_active": kw.is_active}

    if payload.keyword is not None:
        kw.keyword = payload.keyword.strip()
    if payload.topic_group is not None:
        kw.topic_group = payload.topic_group
    if payload.is_active is not None:
        kw.is_active = payload.is_active

    log_action(
        db,
        user_id=current_user.user_id,
        action="UPDATE",
        entity_type="keyword",
        entity_id=kw.keyword_id,
        old_value=old_value,
        new_value={"keyword": kw.keyword, "topic_group": kw.topic_group, "is_active": kw.is_active},
        request=request,
    )
    db.commit()

    return {
        "keyword_id": str(kw.keyword_id),
        "keyword": kw.keyword,
        "topic_group": kw.topic_group,
        "is_active": kw.is_active,
    }
