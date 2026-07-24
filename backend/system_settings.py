from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.models import SystemSetting


def get_setting(db: Session, key: str) -> str | None:
    row = db.get(SystemSetting, key)
    return row.setting_value if row else None


def get_bool_setting(db: Session, key: str, default: bool = False) -> bool:
    value = get_setting(db, key)
    if value is None:
        return default
    return value.lower() == "true"


def set_setting(db: Session, key: str, value: str) -> None:
    """Upsert 1 setting — dùng cho giá trị hệ thống tự ghi (VD LAST_BEAT_TICK_AT ghi bởi
    check_due_sources mỗi chu kỳ), khác với PUT /api/system-settings/{key} (chỉ ADMIN,
    dành cho cấu hình người dùng chỉnh tay). Không seed sẵn qua migration — key chưa từng
    tồn tại sẽ tự được tạo ở lần gọi đầu tiên."""
    stmt = pg_insert(SystemSetting).values(setting_key=key, setting_value=value)
    stmt = stmt.on_conflict_do_update(index_elements=["setting_key"], set_={"setting_value": value})
    db.execute(stmt)
    db.commit()
