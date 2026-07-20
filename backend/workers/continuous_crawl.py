from datetime import date

from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.crawler.article import compute_url_hash
from backend.models import CrawlQueue, Source
from backend.workers.report_job import _get_candidates

# Discover không giới hạn theo date_from/date_to như Job on-demand — lấy TOÀN BỘ URL
# hiện đang được sitemap/listing liệt kê, chống trùng đã có crawl_queue lo (ON CONFLICT
# DO NOTHING), không cần biết trước "khoảng ngày cần crawl" như mô hình Job cũ.
_DISCOVER_DATE_FROM = date(2000, 1, 1)


def discover_source_urls(db, source: Source, today: date | None = None) -> int:
    """Giai đoạn 1 (Discover): tìm URL ứng viên của nguồn (tái dùng nguyên xi
    _get_candidates của report_job.py — không đổi logic ưu tiên sitemap/listing),
    ghi vào crawl_queue. Trả về số URL MỚI vừa ghi (không tính URL đã có từ chu kỳ
    trước — ON CONFLICT DO NOTHING không ghi đè trạng thái cũ)."""
    today = today or date.today()
    candidates, _failed_locs = _get_candidates(source, _DISCOVER_DATE_FROM, today)

    if not candidates:
        return 0

    rows = [
        {
            "source_id": source.source_id,
            "url": c["url"],
            "url_hash": compute_url_hash(c["url"]),
            "status": "pending",
        }
        for c in candidates
    ]
    stmt = pg_insert(CrawlQueue).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["source_id", "url_hash"])
    result = db.execute(stmt)
    db.commit()
    return result.rowcount
