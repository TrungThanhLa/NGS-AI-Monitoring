from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.auth.dependencies import require_permission
from backend.db import get_db
from backend.models import Campaign, ReportHistory, User

router = APIRouter(prefix="/api/reports-history", tags=["reports-history"])


@router.get("")
def list_all_reports_history(db: Session = Depends(get_db), _user: User = Depends(require_permission("report", "view"))):
    rows = (
        db.query(ReportHistory, Campaign)
        .join(Campaign, Campaign.campaign_id == ReportHistory.campaign_id)
        .order_by(ReportHistory.created_at.desc())
        .all()
    )
    return {
        "history": [
            {
                "report_id": str(report.report_id),
                "campaign_id": str(campaign.campaign_id),
                "campaign_name": campaign.name,
                "format": report.format,
                "status": report.status,
                "created_at": report.created_at,
            }
            for report, campaign in rows
        ]
    }
