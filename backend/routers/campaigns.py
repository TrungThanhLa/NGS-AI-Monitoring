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
