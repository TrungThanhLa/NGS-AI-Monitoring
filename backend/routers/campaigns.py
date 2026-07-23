from datetime import date, datetime, timedelta, timezone
import uuid

from celery import chord
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.audit.logger import log_action
from backend.auth.dependencies import require_permission
from backend.db import get_db
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
from backend.workers.campaign_tasks import crawl_campaign_source_once, generate_campaign_report, mark_crawl_done
from backend.workers.celery_app import celery_app

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])

_VALID_REPORT_FORMATS = {"docx", "json", "pdf", "xlsx", "csv"}
_REPORT_MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "json": "application/json",
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
}

_VALID_MODES = {"CONTINUOUS", "ONE_SHOT"}


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
    if len(sources) != len(set(uuids)):
        raise HTTPException(status_code=400, detail="Có source_id không tồn tại")
    return sources


def _resolve_keywords(db: Session, keyword_ids: list[str]) -> list[Keyword]:
    try:
        uuids = [uuid.UUID(kid) for kid in keyword_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="Có keyword_id không hợp lệ")
    kws = db.query(Keyword).filter(Keyword.keyword_id.in_(uuids)).all()
    if len(kws) != len(set(uuids)):
        raise HTTPException(status_code=400, detail="Có keyword_id không tồn tại")
    return kws


@router.post("", status_code=201)
def create_campaign(
    payload: CampaignCreateRequest,
    request: Request,
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
    _validate_one_shot_date_range(payload.mode, payload.end_date)

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
        request=request,
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
    request: Request,
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

    _validate_one_shot_date_range(campaign.mode, campaign.end_date)

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
        request=request,
    )
    db.commit()

    return _serialize_campaign(db, campaign)


@router.delete("/{campaign_id}")
def delete_campaign(
    campaign_id: str,
    request: Request,
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
        request=request,
    )
    db.commit()

    return _serialize_campaign(db, campaign)


@router.post("/{campaign_id}/activate")
def activate_campaign(
    campaign_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("campaign", "update")),
):
    campaign = _get_campaign_or_404(db, campaign_id)

    if campaign.status not in ("DRAFT", "PAUSED"):
        raise HTTPException(
            status_code=400,
            detail=f"Không thể kích hoạt chiến dịch đang ở trạng thái {campaign.status}",
        )
    _validate_one_shot_date_range(campaign.mode, campaign.end_date)

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
        request=request,
    )
    db.commit()

    # ONE_SHOT: crawl NGAY toàn bộ Source đã chọn, không đợi Celery Beat (BR-CAMP-07 —
    # "không đăng ký Celery Beat"). Dùng chord: group các crawl_task (1/Source) chạy
    # song song, callback mark_crawl_done chỉ chạy SAU KHI TẤT CẢ đã xong.
    if campaign.mode == "ONE_SHOT":
        source_ids = _campaign_source_ids(db, campaign.campaign_id)
        existing_progress = {
            str(p.source_id): p
            for p in db.query(CampaignCrawlProgress).filter_by(campaign_id=campaign.campaign_id).all()
        }

        # Kích hoạt lại (VD sau khi Pause giữa chừng): Nguồn nào đã done từ lượt trước thì
        # GIỮ NGUYÊN, không xóa/crawl lại — Discover+matching lại 1 Nguồn đã xong hoàn toàn
        # là lãng phí thuần túy (bài đã fetch được tái sử dụng, nhưng vẫn tốn request Discover
        # + duyệt lại toàn bộ candidate + chạy matching lại), phát hiện qua smoke test thật
        # 2026-07-23. Nguồn chưa done (pending/discovering/fetching/error) thì xóa dòng cũ,
        # tạo lại mới — các Nguồn này KHÔNG có cơ chế resume dở dang (Discover không lưu
        # trạng thái từng phần), chấp nhận restart từ đầu (quyết định đã chốt ở Task 4).
        pending_source_ids = []
        for sid in source_ids:
            prior = existing_progress.get(sid)
            if prior is not None and prior.status == "done":
                continue
            if prior is not None:
                db.delete(prior)
            pending_source_ids.append(sid)
        # Flush riêng DELETE trước khi ADD dòng mới cùng PRIMARY KEY (campaign_id, source_id)
        # — db.delete() là thao tác ORM-tracked (khác bulk .query().delete()), nếu không
        # flush trước, unit-of-work coi delete+add cùng identity là xung đột, giữ nguyên
        # trạng thái object cũ thay vì tạo mới (bug thật phát hiện lúc viết test này)
        db.flush()
        for sid in pending_source_ids:
            db.add(CampaignCrawlProgress(campaign_id=campaign.campaign_id, source_id=uuid.UUID(sid)))
        db.commit()

        if pending_source_ids:
            date_from = campaign.start_date.date().isoformat()
            date_to = campaign.end_date.date().isoformat()
            chord(
                (
                    crawl_campaign_source_once.s(str(campaign.campaign_id), sid, date_from, date_to)
                    for sid in pending_source_ids
                ),
                mark_crawl_done.s(str(campaign.campaign_id)),
            ).apply_async()
        else:
            # Mọi Nguồn đều đã done từ lượt trước — không còn gì để crawl, tự chuyển
            # COMPLETED ngay, không cần dispatch Celery (chord với group rỗng không đáng tin cậy)
            campaign.status = "COMPLETED"
            db.commit()

    return _serialize_campaign(db, campaign)


def _serialize_report(report: ReportHistory) -> dict:
    return {
        "report_id": str(report.report_id),
        "campaign_id": str(report.campaign_id),
        "format": report.format,
        "status": report.status,
        "error_log": report.error_log,
        "file_path": report.file_path,
        "created_at": report.created_at,
    }


def _get_campaign_report_or_404(db: Session, campaign_id: str, report_id: str) -> ReportHistory:
    try:
        report = db.get(ReportHistory, uuid.UUID(report_id))
    except ValueError:
        report = None
    if report is None or str(report.campaign_id) != campaign_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy báo cáo")
    return report


class CreateCampaignReportRequest(BaseModel):
    date_from: str
    date_to: str
    format: str = "docx"


@router.post("/{campaign_id}/reports", status_code=202)
def create_campaign_report(
    campaign_id: str,
    payload: CreateCampaignReportRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("report", "create")),
):
    campaign = _get_campaign_or_404(db, campaign_id)
    if payload.format not in _VALID_REPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f"format phải là 1 trong {_VALID_REPORT_FORMATS}")

    # Sinh task_id TRƯỚC khi gọi apply_async (không suy ra từ report_id) — cần lưu lại để
    # revoke được task thật khi người dùng bấm Hủy (POST .../reports/{report_id}/cancel)
    task_id = str(uuid.uuid4())
    report = ReportHistory(
        campaign_id=campaign.campaign_id,
        file_path="",
        format=payload.format,
        status="pending",
        celery_task_id=task_id,
    )
    db.add(report)
    db.commit()

    generate_campaign_report.apply_async(
        args=[str(report.report_id), str(campaign.campaign_id), payload.date_from, payload.date_to, payload.format],
        task_id=task_id,
    )

    return {"report_id": str(report.report_id), "status": report.status}


_CANCELABLE_REPORT_STATUSES = {"pending", "running"}


@router.post("/{campaign_id}/reports/{report_id}/cancel")
def cancel_campaign_report(
    campaign_id: str,
    report_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("report", "create")),
):
    _get_campaign_or_404(db, campaign_id)
    report = _get_campaign_report_or_404(db, campaign_id, report_id)

    if report.status not in _CANCELABLE_REPORT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể hủy báo cáo đang ở trạng thái {report.status}",
        )

    # Task bị kill bằng SIGTERM (không phải Python exception) nên tự nó không cập nhật
    # được status — endpoint tự set, giống cơ chế Hủy Job cũ (đã xóa cùng bảng jobs ở
    # Phase 7, xem rule 10-error-handling.md)
    if report.celery_task_id:
        celery_app.control.revoke(report.celery_task_id, terminate=True)
    report.status = "cancelled"
    db.commit()

    return {"report_id": str(report.report_id), "status": report.status}


@router.get("/{campaign_id}/reports")
def list_campaign_reports(
    campaign_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("report", "view")),
):
    _get_campaign_or_404(db, campaign_id)
    rows = (
        db.query(ReportHistory)
        .filter_by(campaign_id=uuid.UUID(campaign_id))
        .order_by(ReportHistory.created_at.desc())
        .all()
    )
    return {"reports": [_serialize_report(r) for r in rows]}


@router.get("/{campaign_id}/reports/{report_id}")
def get_campaign_report(
    campaign_id: str,
    report_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("report", "view")),
):
    _get_campaign_or_404(db, campaign_id)
    report = _get_campaign_report_or_404(db, campaign_id, report_id)
    return _serialize_report(report)


@router.get("/{campaign_id}/reports/{report_id}/download")
def download_campaign_report(
    campaign_id: str,
    report_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("report", "view")),
):
    _get_campaign_or_404(db, campaign_id)
    report = _get_campaign_report_or_404(db, campaign_id, report_id)
    if report.status != "completed":
        raise HTTPException(status_code=400, detail="Báo cáo chưa hoàn thành")

    return FileResponse(
        report.file_path,
        filename=f"{report_id}.{report.format}",
        media_type=_REPORT_MEDIA_TYPES[report.format],
    )


@router.post("/{campaign_id}/pause")
def pause_campaign(
    campaign_id: str,
    request: Request,
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
        request=request,
    )
    db.commit()

    return _serialize_campaign(db, campaign)


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
