from backend.system_settings import get_bool_setting, get_setting


def test_get_setting_returns_seeded_value(db_session):
    assert get_setting(db_session, "SCHEDULER_ENABLED") == "false"


def test_get_setting_returns_none_for_unknown_key(db_session):
    assert get_setting(db_session, "KHONG_TON_TAI") is None


def test_get_bool_setting_parses_true_false(db_session):
    from backend.models import SystemSetting

    db_session.query(SystemSetting).filter_by(setting_key="AI_AUTO_TRIGGER").update({"setting_value": "true"})
    db_session.commit()

    assert get_bool_setting(db_session, "AI_AUTO_TRIGGER") is True
    assert get_bool_setting(db_session, "SCHEDULER_ENABLED") is False


def test_get_bool_setting_returns_default_for_unknown_key(db_session):
    assert get_bool_setting(db_session, "KHONG_TON_TAI", default=True) is True
    assert get_bool_setting(db_session, "KHONG_TON_TAI", default=False) is False
