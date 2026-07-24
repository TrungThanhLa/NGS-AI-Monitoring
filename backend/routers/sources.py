import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.audit.logger import log_action
from backend.auth.dependencies import require_permission
from backend.db import get_db
from backend.models import Source, SourceGroup, User

router = APIRouter(prefix="/api/sources", tags=["sources"])

_VALID_SOURCE_STATUSES = {"ACTIVE", "INACTIVE"}
# Ngưỡng tối thiểu chấp nhận qua API — chặn việc lỡ đặt crawl_frequency quá ngắn khiến
# Beat enqueue quá dày, spam request tới website thật (nguyên tắc "không spam request",
# rule 11) — phát hiện thật lúc smoke test Docker (2026-07-21) khi test với 60s. FE
# giới hạn tối thiểu 5 phút (300s) ở form, đây là chốt chặn thật ở tầng API.
_MIN_CRAWL_FREQUENCY_SECONDS = 300


@router.get("")
def list_sources(db: Session = Depends(get_db), _user=Depends(require_permission("source", "view"))):
    # Chỉ trả nguồn active — FE dùng để render sidebar chọn nguồn (Slice 2)
    rows = db.query(Source).filter_by(is_active=True).order_by(Source.group_name, Source.name).all()
    return {
        "sources": [
            {
                "source_id": str(s.source_id),
                "name": s.name,
                "domain": s.domain,
                "group_name": s.group_name,
                "source_group": s.source_group,
                "crawl_frequency": s.crawl_frequency,
                "status": s.status,
                "sitemap_url": s.sitemap_url,
                "parsing_rules": s.parsing_rules,
                "last_crawled_at": s.last_crawled_at,
                "discover_backfilled_from": s.discover_backfilled_from,
            }
            for s in rows
        ]
    }


class SourceUpdateRequest(BaseModel):
    source_group: str | None = None
    crawl_frequency: int | None = None
    status: str | None = None


@router.put("/{source_id}")
def update_source(
    source_id: str,
    payload: SourceUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("source", "update")),
):
    try:
        source = db.get(Source, uuid.UUID(source_id))
    except ValueError:
        source = None
    if source is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nguồn")

    # Chỉ ADMIN/OPERATOR (permission source.update) được sửa, và chỉ được set
    # ACTIVE/INACTIVE thủ công — ERROR là trạng thái hệ thống tự set (BR-SRC-03),
    # không cho gán qua API để tránh nhầm lẫn với cơ chế tự động phát hiện lỗi.
    if payload.status is not None and payload.status not in _VALID_SOURCE_STATUSES:
        raise HTTPException(status_code=400, detail=f"status phải là 1 trong {_VALID_SOURCE_STATUSES}")
    if payload.crawl_frequency is not None and payload.crawl_frequency < _MIN_CRAWL_FREQUENCY_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=f"crawl_frequency phải >= {_MIN_CRAWL_FREQUENCY_SECONDS} giây (tránh spam request)",
        )
    # source_group phải khớp đúng tên 1 Nhóm nguồn đang active trong bảng source_groups
    # (BR-SRC-01) — không cho gõ tay tự do nữa, tránh trôi dạt dữ liệu (typo, viết hoa/
    # thường khác nhau cho cùng 1 nhóm)
    if payload.source_group is not None:
        valid = db.query(SourceGroup).filter_by(name=payload.source_group, is_active=True).first()
        if valid is None:
            raise HTTPException(status_code=400, detail="Nhóm nguồn không hợp lệ hoặc đã ngừng dùng")

    old_value = {
        "source_group": source.source_group,
        "crawl_frequency": source.crawl_frequency,
        "status": source.status,
    }

    if payload.source_group is not None:
        source.source_group = payload.source_group
    if payload.crawl_frequency is not None:
        source.crawl_frequency = payload.crawl_frequency
    if payload.status is not None:
        source.status = payload.status

    log_action(
        db,
        user_id=current_user.user_id,
        action="UPDATE",
        entity_type="source",
        entity_id=source.source_id,
        old_value=old_value,
        new_value={
            "source_group": source.source_group,
            "crawl_frequency": source.crawl_frequency,
            "status": source.status,
        },
        request=request,
    )
    db.commit()

    return {
        "source_id": str(source.source_id),
        "name": source.name,
        "domain": source.domain,
        "group_name": source.group_name,
        "source_group": source.source_group,
        "crawl_frequency": source.crawl_frequency,
        "status": source.status,
    }
