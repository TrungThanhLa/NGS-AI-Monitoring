import csv
import uuid
from datetime import date

from backend.models import Article, ArticleAnalysis, Job, Source
from backend.scripts.export_analysis_csv import export_analysis_csv


def test_export_analysis_csv_writes_expected_row(db_session, tmp_path):
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        source_id=source.source_id,
        url="https://example.test/bai-viet",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Tiêu đề test",
        content_raw="Nội dung",
        status="analyzed",
    )
    db_session.add(article)
    db_session.flush()

    analysis = ArticleAnalysis(
        article_id=article.article_id,
        job_id=job.job_id,
        topics=["Tin giả và thông tin sai lệch"],
        keywords=["deepfake"],
        sentiment="negative",
        emotion="Fear",
        confidence=0.85,
        needs_review=False,
        summary="Tóm tắt.",
        prompt_version=1,
        ai_model="qwen3:8b",
    )
    db_session.add(analysis)
    db_session.commit()

    output_path = tmp_path / "export.csv"

    try:
        export_analysis_csv(str(job.job_id), str(output_path))

        with open(output_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 1
        assert rows[0]["title"] == "Tiêu đề test"
        assert rows[0]["url"] == "https://example.test/bai-viet"
        assert rows[0]["sentiment"] == "negative"
        assert rows[0]["ai_model"] == "qwen3:8b"
    finally:
        db_session.delete(analysis)
        db_session.delete(article)
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()
