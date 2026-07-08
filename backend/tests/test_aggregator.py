import uuid
from datetime import date

from backend.models import Article, ArticleAnalysis, Job, Source
from backend.report.aggregator import aggregate_basic


def test_aggregates_sentiment_and_emotion_counts_and_lists_articles(db_session):
    source = Source(name="Test Source", domain=f"test-{uuid.uuid4()}.example", group_name="Test")
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article1 = Article(
        job_id=job.job_id, source_id=source.source_id, url="https://vtv.vn/a1", url_hash=f"hash-{uuid.uuid4()}", title="Bài 1"
    )
    article2 = Article(
        job_id=job.job_id, source_id=source.source_id, url="https://vtv.vn/a2", url_hash=f"hash-{uuid.uuid4()}", title="Bài 2"
    )
    db_session.add_all([article1, article2])
    db_session.flush()

    db_session.add_all(
        [
            ArticleAnalysis(
                article_id=article1.article_id,
                job_id=job.job_id,
                topics=["A"],
                sentiment="negative",
                emotion="Fear",
                confidence=0.9,
                prompt_version=1,
                ai_model="qwen3:8b",
            ),
            ArticleAnalysis(
                article_id=article2.article_id,
                job_id=job.job_id,
                topics=["B"],
                sentiment="negative",
                emotion="Trust",
                confidence=0.95,
                prompt_version=1,
                ai_model="qwen3:8b",
            ),
        ]
    )
    db_session.flush()

    result = aggregate_basic(db_session, job.job_id)

    assert result["sentiment_counts"] == {"negative": 2}
    assert result["emotion_counts"] == {"Fear": 1, "Trust": 1}
    titles = {a["title"] for a in result["articles"]}
    assert titles == {"Bài 1", "Bài 2"}
