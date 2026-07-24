from datetime import datetime, timezone

from sqlalchemy import text

from backend.models import Campaign, CampaignSource, Source


def list_due_sources(db, now: datetime | None = None) -> list[Source]:
    """Nguồn nào đang được ≥1 Campaign ACTIVE theo dõi, status=ACTIVE, KHÔNG có
    crawl_task nào đang chạy dở (crawl_started_at IS NULL), và đã tới giờ crawl lại
    (chưa từng crawl lần nào, hoặc now - last_crawled_at >= crawl_frequency).
    DISTINCT theo source_id — 1 nguồn được nhiều Campaign ACTIVE theo dõi vẫn chỉ trả
    về đúng 1 lần, tránh Beat enqueue trùng nhiều lần trong 1 lượt quét (rule 17).

    [SỬA 2026-07-24] Thêm điều kiện crawl_started_at IS NULL — bug thật phát hiện qua
    smoke test: last_crawled_at chỉ ghi ở CUỐI fetch_pending_urls (sau khi xử lý xong
    TOÀN BỘ backlog). Nguồn có backlog quá lớn (>60s chưa xong 1 lượt) sẽ có
    last_crawled_at NULL mãi → mỗi lượt Beat (60s) lại tưởng "chưa ai xử lý", dispatch
    chồng thêm crawl_task mới dù task cũ vẫn đang chạy dở — quan sát thật: 22 task chồng
    chất trong 15 phút cho cùng 1 nguồn, chiếm hết worker pool."""
    now = now or datetime.now(timezone.utc)

    watched_source_ids = (
        db.query(CampaignSource.source_id)
        .join(Campaign, Campaign.campaign_id == CampaignSource.campaign_id)
        .filter(Campaign.status == "ACTIVE", Campaign.mode == "CONTINUOUS")
        .distinct()
        .all()
    )
    candidate_sources = (
        db.query(Source)
        .filter(
            Source.source_id.in_([sid for (sid,) in watched_source_ids]),
            Source.status == "ACTIVE",
            Source.crawl_started_at.is_(None),
        )
        .all()
    )

    due = []
    for source in candidate_sources:
        if source.last_crawled_at is None:
            due.append(source)
            continue
        # sources.last_crawled_at là TIMESTAMP không kèm timezone (migration 0018) — SQLAlchemy
        # đọc về dưới dạng datetime "naive" (không có tzinfo), trong khi now() ở trên là
        # datetime "aware" (có tzinfo=utc). Trừ 2 loại khác nhau sẽ raise TypeError, nên phải
        # gán tzinfo=utc cho last_crawled trước khi trừ.
        last_crawled = source.last_crawled_at
        if last_crawled.tzinfo is None:
            last_crawled = last_crawled.replace(tzinfo=timezone.utc)
        elapsed = (now - last_crawled).total_seconds()
        if elapsed >= source.crawl_frequency:
            due.append(source)
    return due


def complete_expired_continuous_campaigns(db, now: datetime | None = None) -> int:
    """Campaign CONTINUOUS có end_date đã qua nhưng vẫn ACTIVE → tự chuyển COMPLETED.
    Trước đây end_date chỉ lưu ở DB, không có cơ chế nào đọc lại — Campaign CONTINUOUS
    đặt end_date xong vẫn crawl mãi mãi cho tới khi có người bấm Tạm dừng/Lưu trữ thủ
    công (phát hiện qua smoke test thật 2026-07-22). Gọi ở đầu check_due_sources(), độc
    lập với SCHEDULER_ENABLED — vòng đời Campaign không nên phụ thuộc việc crawl có đang
    bật hay không."""
    now = now or datetime.now(timezone.utc)
    expired = (
        db.query(Campaign)
        .filter(
            Campaign.mode == "CONTINUOUS",
            Campaign.status == "ACTIVE",
            Campaign.end_date.isnot(None),
            Campaign.end_date <= now,
        )
        .all()
    )
    for campaign in expired:
        campaign.status = "COMPLETED"
    db.commit()
    return len(expired)


from backend.db import SessionLocal
from backend.system_settings import get_bool_setting, set_setting
from backend.workers.celery_app import celery_app
# Import module (không import thẳng "crawl_task") — tránh circular import: nếu điểm
# vào đầu tiên của process là backend.workers.continuous_crawl (VD test import thẳng
# module này), chuỗi continuous_crawl -> celery_app -> scheduler -> continuous_crawl sẽ
# chạy TRƯỚC KHI continuous_crawl kịp định nghĩa xong crawl_task ở cuối file (module
# report_job.py trước đây từng nằm giữa chuỗi này đã bị xóa ở Phase 7 khi campaigns thay
# thế hoàn toàn jobs — celery_app giờ import thẳng continuous_crawl). Import module
# (chỉ bind tên) rồi truy cập .crawl_task lúc gọi (trong hàm, không phải ở top-level)
# trì hoãn việc tra thuộc tính tới lúc task thực sự chạy — khi đó mọi module đã load xong.
from backend.workers import continuous_crawl


@celery_app.task(name="scheduler.check_due_sources")
def check_due_sources() -> None:
    db = SessionLocal()
    try:
        # Ghi NGAY từ dòng đầu tiên (trước mọi việc khác) — FE dùng giá trị này vẽ ring
        # loader đếm theo nhịp Beat thật (xem CLAUDE.md/hội thoại thiết kế 2026-07-24).
        # Nếu Beat chết hẳn (không chỉ 1 chu kỳ lỗi), giá trị này ngừng cập nhật — FE
        # phải tự phát hiện qua "đã lâu không thấy giá trị mới" để chuyển sang cảnh báo,
        # không được tự lặp vòng đếm giả vờ khỏe mạnh.
        now = datetime.now(timezone.utc)
        set_setting(db, "LAST_BEAT_TICK_AT", now.isoformat())
        complete_expired_continuous_campaigns(db)
        if not get_bool_setting(db, "SCHEDULER_ENABLED"):
            return
        for source in list_due_sources(db, now=now):
            # "Claim" nguyên tử NGAY LÚC quyết định dispatch — không đợi tới lúc
            # crawl_task thực sự được 1 worker rảnh nhận mới tự set crawl_started_at
            # (continuous_crawl.py vẫn tự set lại ở đầu, idempotent). Có độ trễ thật
            # giữa lúc gọi .delay() và lúc 1 worker rảnh thực sự nhận việc (worker pool
            # có thể đang bận) — nếu không claim ngay ở đây, lượt Beat kế tiếp (60s sau)
            # vẫn thấy crawl_started_at=NULL và dispatch chồng thêm, đúng bug đã xảy ra.
            # UPDATE nguyên tử WHERE crawl_started_at IS NULL (không đọc-rồi-ghi qua ORM)
            # — cùng pattern LEAST() atomic update đã dùng cho discover_backfilled_from
            # (continuous_crawl.py) — để không hở race dù rủi ro thực tế thấp (chỉ có 1
            # tiến trình Celery Beat trong triển khai hiện tại).
            claimed = db.execute(
                text(
                    "UPDATE sources SET crawl_started_at = :now "
                    "WHERE source_id = :source_id AND crawl_started_at IS NULL"
                ),
                {"now": now, "source_id": source.source_id},
            )
            db.commit()
            if claimed.rowcount == 0:
                continue
            continuous_crawl.crawl_task.delay(str(source.source_id))
    finally:
        db.close()
