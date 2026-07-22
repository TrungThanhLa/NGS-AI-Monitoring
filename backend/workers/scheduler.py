from datetime import datetime, timezone

from backend.models import Campaign, CampaignSource, Source


def list_due_sources(db, now: datetime | None = None) -> list[Source]:
    """Nguồn nào đang được ≥1 Campaign ACTIVE theo dõi, status=ACTIVE, và đã tới giờ
    crawl lại (chưa từng crawl lần nào, hoặc now - last_crawled_at >= crawl_frequency).
    DISTINCT theo source_id — 1 nguồn được nhiều Campaign ACTIVE theo dõi vẫn chỉ trả
    về đúng 1 lần, tránh Beat enqueue trùng nhiều lần trong 1 lượt quét (rule 17)."""
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
        .filter(Source.source_id.in_([sid for (sid,) in watched_source_ids]), Source.status == "ACTIVE")
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


from backend.db import SessionLocal
from backend.system_settings import get_bool_setting
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
        if not get_bool_setting(db, "SCHEDULER_ENABLED"):
            return
        for source in list_due_sources(db):
            continuous_crawl.crawl_task.delay(str(source.source_id))
    finally:
        db.close()
