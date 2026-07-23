from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.audit.logger import log_action
from backend.auth.dependencies import require_permission
from backend.db import get_db
from backend.models import Campaign, SystemSetting, User

router = APIRouter(prefix="/api/system-settings", tags=["system-settings"])


@router.get("")
def list_settings(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("system", "configure")),
):
    rows = db.query(SystemSetting).order_by(SystemSetting.setting_key).all()
    return {
        "settings": [
            {
                "setting_key": r.setting_key,
                "setting_value": r.setting_value,
                "data_type": r.data_type,
                "description": r.description,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]
    }


class SettingUpdateRequest(BaseModel):
    setting_value: str


@router.put("/{key}")
def update_setting(
    key: str,
    payload: SettingUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("system", "configure")),
):
    setting = db.get(SystemSetting, key)
    if setting is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cấu hình")

    old_value = {"setting_value": setting.setting_value}
    setting.setting_value = payload.setting_value
    setting.updated_at = datetime.now(timezone.utc)
    setting.updated_by = current_user.user_id

    # Tắt SCHEDULER_ENABLED trong khi còn Campaign CONTINUOUS ACTIVE khiến chúng "ACTIVE
    # giả" — không crawl gì nhưng vẫn hiện đang giám sát (đúng vấn đề đã chặn ở
    # activate_campaign). Tự chuyển PAUSED ngay để trạng thái luôn phản ánh đúng thực tế
    # — đánh đổi: bật lại Scheduler sau đó KHÔNG tự crawl lại, phải Kích hoạt lại thủ
    # công (chấp nhận được vì tắt Scheduler là hành động có chủ đích, xác nhận 2026-07-23).
    paused_campaign_ids: list[str] = []
    if key == "SCHEDULER_ENABLED" and payload.setting_value == "false":
        active_continuous = db.query(Campaign).filter(Campaign.mode == "CONTINUOUS", Campaign.status == "ACTIVE").all()
        for campaign in active_continuous:
            campaign.status = "PAUSED"
            paused_campaign_ids.append(str(campaign.campaign_id))
        if paused_campaign_ids:
            log_action(
                db,
                user_id=current_user.user_id,
                action="UPDATE",
                entity_type="campaign",
                entity_id=None,
                old_value={"status": "ACTIVE"},
                new_value={"status": "PAUSED", "reason": "SCHEDULER_ENABLED tắt", "campaign_ids": paused_campaign_ids},
                request=request,
            )

    log_action(
        db,
        user_id=current_user.user_id,
        action="UPDATE",
        entity_type="system_setting",
        entity_id=None,
        old_value=old_value,
        new_value={"setting_value": setting.setting_value},
        request=request,
    )
    db.commit()

    return {
        "setting_key": setting.setting_key,
        "setting_value": setting.setting_value,
        "data_type": setting.data_type,
        "description": setting.description,
        "updated_at": setting.updated_at,
        "paused_campaign_ids": paused_campaign_ids,
    }
