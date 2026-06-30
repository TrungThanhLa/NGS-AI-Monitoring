from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import Source

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("")
def list_sources(db: Session = Depends(get_db)):
    # Chỉ trả nguồn active — FE dùng để render sidebar chọn nguồn (Slice 2)
    rows = db.query(Source).filter_by(is_active=True).order_by(Source.group_name, Source.name).all()
    return {
        "sources": [
            {
                "source_id": str(s.source_id),
                "name": s.name,
                "domain": s.domain,
                "group_name": s.group_name,
            }
            for s in rows
        ]
    }
