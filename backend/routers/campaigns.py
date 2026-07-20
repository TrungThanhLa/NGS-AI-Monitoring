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
