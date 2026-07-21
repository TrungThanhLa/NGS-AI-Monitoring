from datetime import date, timedelta

from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.crawler.article import compute_url_hash
from backend.models import CrawlQueue, Source

# Discover không giới hạn CỨNG theo date_from/date_to như Job on-demand — nhưng KHÔNG
# quét từ "vô hạn trong quá khứ" (đã thử date(2000,1,1) và phát hiện bug thật: với
# nguồn dùng _SITEMAP_URL_TEMPLATES sinh 1 URL sub-sitemap/tháng — VD vtv.vn — quét từ
# năm 2000 tạo ra ~300+ request HTTP mỗi chu kỳ, vi phạm nguyên tắc "không spam
# request" và có nguy cơ bị chặn IP — xem CLAUDE.md, phát hiện lúc smoke test thật
# 2026-07-21). Dùng cửa sổ trượt (rolling window) N ngày gần nhất tính từ `today` —
# đủ rộng để không bỏ lỡ bài nếu 1 chu kỳ bị gián đoạn vài ngày liên tiếp, chống
# trùng đã có crawl_queue lo (ON CONFLICT DO NOTHING).
_DISCOVER_LOOKBACK_DAYS = 30


def _get_candidates(source, date_from, date_to):
    # Import trì hoãn tới lúc gọi (không import ở đầu file) — report_job.py import
    # ngược lại celery_app (đăng ký cả continuous_crawl module này), nên nếu
    # report_job.py là entrypoint đầu tiên của tiến trình (VD `pytest
    # tests/test_report_job.py` chạy riêng lẻ), import ở top-level module sẽ tạo
    # vòng lặp: report_job → celery_app → continuous_crawl → report_job (lúc này
    # report_job vẫn đang khởi tạo dở, chưa định nghĩa xong _get_candidates thật).
    # Trì hoãn import xuống đây phá vòng lặp, đồng thời vẫn giữ được tên
    # continuous_crawl._get_candidates để test monkeypatch như cũ.
    from backend.workers.report_job import _get_candidates as _impl

    return _impl(source, date_from, date_to)


def discover_source_urls(db, source: Source, today: date | None = None) -> int:
    """Giai đoạn 1 (Discover): tìm URL ứng viên của nguồn (tái dùng nguyên xi
    _get_candidates của report_job.py — không đổi logic ưu tiên sitemap/listing),
    ghi vào crawl_queue. Trả về số URL MỚI vừa ghi (không tính URL đã có từ chu kỳ
    trước — ON CONFLICT DO NOTHING không ghi đè trạng thái cũ)."""
    today = today or date.today()
    date_from = today - timedelta(days=_DISCOVER_LOOKBACK_DAYS)
    candidates, _failed_locs = _get_candidates(source, date_from, today)

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
