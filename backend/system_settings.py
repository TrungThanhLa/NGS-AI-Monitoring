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
