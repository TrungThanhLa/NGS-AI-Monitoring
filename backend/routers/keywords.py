from fastapi import APIRouter, Depends, HTTPException, Request
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
