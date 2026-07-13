import pytest

from backend.db import SessionLocal, engine


@pytest.fixture
def db_session():
    # Mỗi test chạy trong 1 transaction riêng (SAVEPOINT lồng trong 1 transaction
    # ngoài, qua join_transaction_mode="create_savepoint" — API chính thức của
    # SQLAlchemy 2.0 cho pattern này, tự xử lý đúng cả trường hợp test gọi
    # session.rollback() thủ công sau IntegrityError), rollback toàn bộ ở cuối
    # test — dù code dưới test gọi session.commit() (VD các endpoint FastAPI),
    # dữ liệu vẫn không bao giờ thật sự ghi vào DB dev. Tránh rác test rơi vào
    # DB dev thật (đã xảy ra thật — xem "Test Source" leak).
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
