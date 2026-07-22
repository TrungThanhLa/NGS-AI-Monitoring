import uuid
from datetime import date, datetime

from backend.models import Article, ArticleAnalysis, Source
from backend.report.aggregator import aggregate_basic


def test_aggregates_sentiment_and_emotion_counts_and_lists_articles(db_session):
    source = Source(name="Test Source", domain=f"test-{uuid.uuid4()}.example", group_name="Test")
    db_session.add(source)
    db_session.flush()

    article1 = Article(
        source_id=source.source_id, url="https://vtv.vn/a1", url_hash=f"hash-{uuid.uuid4()}", title="Bài 1"
    )
    article2 = Article(
        source_id=source.source_id, url="https://vtv.vn/a2", url_hash=f"hash-{uuid.uuid4()}", title="Bài 2"
    )
    db_session.add_all([article1, article2])
    db_session.flush()

    db_session.add_all(
        [
            ArticleAnalysis(
                article_id=article1.article_id,
                topics=["A"],
                sentiment="negative",
                emotion="Fear",
                confidence=0.9,
                prompt_version=1,
                ai_model="qwen3:8b",
            ),
            ArticleAnalysis(
                article_id=article2.article_id,
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

    result = aggregate_basic(db_session, [article1.article_id, article2.article_id])

    assert result["sentiment_counts"] == {"negative": 2}
    assert result["emotion_counts"] == {"Fear": 1, "Trust": 1}
    titles = {a["title"] for a in result["articles"]}
    assert titles == {"Bài 1", "Bài 2"}


def test_source_counts_grouped_by_group_name_not_individual_source(db_session):
    source1 = Source(name="Báo CAND", domain=f"cand-{uuid.uuid4()}.example", group_name="Bộ Công an")
    source2 = Source(name="Cổng BCA", domain=f"bca-{uuid.uuid4()}.example", group_name="Bộ Công an")
    db_session.add_all([source1, source2])
    db_session.flush()

    a1 = Article(source_id=source1.source_id, url="https://cand.vn/a1", url_hash=f"h-{uuid.uuid4()}", title="Bài 1")
    a2 = Article(source_id=source2.source_id, url="https://bca.gov.vn/a1", url_hash=f"h-{uuid.uuid4()}", title="Bài 2")
    db_session.add_all([a1, a2])
    db_session.flush()

    db_session.add_all(
        [
            ArticleAnalysis(article_id=a1.article_id, topics=["A"], keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b"),
            ArticleAnalysis(article_id=a2.article_id, topics=["A"], keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b"),
        ]
    )
    db_session.flush()

    result = aggregate_basic(db_session, [a1.article_id, a2.article_id])

    assert result["source_counts"] == {"Bộ Công an": 2}


def test_topic_counts_counts_each_topic_across_multi_topic_articles(db_session):
    source = Source(name="Test", domain=f"t-{uuid.uuid4()}.example", group_name="Test")
    db_session.add(source)
    db_session.flush()
    a1 = Article(source_id=source.source_id, url="https://x/a1", url_hash=f"h-{uuid.uuid4()}", title="Bài 1")
    a2 = Article(source_id=source.source_id, url="https://x/a2", url_hash=f"h-{uuid.uuid4()}", title="Bài 2")
    db_session.add_all([a1, a2])
    db_session.flush()

    db_session.add_all(
        [
            ArticleAnalysis(
                article_id=a1.article_id, topics=["Tin giả và thông tin sai lệch", "Cảnh báo lừa đảo, giả mạo trên không gian mạng"],
                keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b",
            ),
            ArticleAnalysis(
                article_id=a2.article_id, topics=["Tin giả và thông tin sai lệch"],
                keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b",
            ),
        ]
    )
    db_session.flush()

    result = aggregate_basic(db_session, [a1.article_id, a2.article_id])

    assert result["topic_counts"] == {
        "Tin giả và thông tin sai lệch": 2,
        "Cảnh báo lừa đảo, giả mạo trên không gian mạng": 1,
    }


def test_keyword_counts_caps_at_top_20(db_session):
    source = Source(name="Test", domain=f"t-{uuid.uuid4()}.example", group_name="Test")
    db_session.add(source)
    db_session.flush()
    article_ids = []
    for i in range(22):
        article = Article(
            source_id=source.source_id, url=f"https://x/a{i}",
            url_hash=f"h-{uuid.uuid4()}", title=f"Bài {i}",
        )
        db_session.add(article)
        db_session.flush()
        article_ids.append(article.article_id)
        db_session.add(
            ArticleAnalysis(
                article_id=article.article_id, topics=["A"], keywords=[f"keyword-{i}"],
                sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b",
            )
        )
    db_session.flush()

    result = aggregate_basic(db_session, article_ids)

    assert len(result["keyword_counts"]) == 20


def test_monthly_counts_groups_by_year_month_and_ignores_missing_published_at(db_session):
    source = Source(name="Test", domain=f"t-{uuid.uuid4()}.example", group_name="Test")
    db_session.add(source)
    db_session.flush()
    a1 = Article(source_id=source.source_id, url="https://x/a1", url_hash=f"h-{uuid.uuid4()}", title="Bài 1", published_at=datetime(2026, 6, 5))
    a2 = Article(source_id=source.source_id, url="https://x/a2", url_hash=f"h-{uuid.uuid4()}", title="Bài 2", published_at=datetime(2026, 6, 20))
    a3 = Article(source_id=source.source_id, url="https://x/a3", url_hash=f"h-{uuid.uuid4()}", title="Bài không rõ ngày đăng")
    db_session.add_all([a1, a2, a3])
    db_session.flush()

    db_session.add_all(
        [
            ArticleAnalysis(article_id=a1.article_id, topics=["A"], keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b"),
            ArticleAnalysis(article_id=a2.article_id, topics=["A"], keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b"),
            ArticleAnalysis(article_id=a3.article_id, topics=["A"], keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, prompt_version=1, ai_model="qwen3:8b"),
        ]
    )
    db_session.flush()

    result = aggregate_basic(db_session, [a1.article_id, a2.article_id, a3.article_id])

    assert result["monthly_counts"] == {"2026-06": 2}
    assert sum(result["monthly_counts"].values()) == 2  # bài a3 (published_at=None) bị bỏ qua, không phải 3


def test_emotion_counts_labels_null_emotion_as_khong_xac_dinh(db_session):
    source = Source(name="Test", domain=f"t-{uuid.uuid4()}.example", group_name="Test")
    db_session.add(source)
    db_session.flush()
    article = Article(source_id=source.source_id, url="https://x/a1", url_hash=f"h-{uuid.uuid4()}", title="Bài 1")
    db_session.add(article)
    db_session.flush()

    db_session.add(
        ArticleAnalysis(
            article_id=article.article_id, topics=["A"], keywords=[],
            sentiment="negative", emotion=None, needs_review=True, confidence=0.9, prompt_version=1, ai_model="qwen3:8b",
        )
    )
    db_session.flush()

    result = aggregate_basic(db_session, [article.article_id])

    assert result["emotion_counts"] == {"Không xác định": 1}


def test_summary_stats_counts_total_articles_sources_and_needs_review(db_session):
    source1 = Source(name="A", domain=f"a-{uuid.uuid4()}.example", group_name="Nhóm A")
    source2 = Source(name="B", domain=f"b-{uuid.uuid4()}.example", group_name="Nhóm B")
    db_session.add_all([source1, source2])
    db_session.flush()
    a1 = Article(source_id=source1.source_id, url="https://x/a1", url_hash=f"h-{uuid.uuid4()}", title="Bài 1")
    a2 = Article(source_id=source2.source_id, url="https://x/a2", url_hash=f"h-{uuid.uuid4()}", title="Bài 2")
    db_session.add_all([a1, a2])
    db_session.flush()

    db_session.add_all(
        [
            ArticleAnalysis(article_id=a1.article_id, topics=["A"], keywords=[], sentiment="negative", emotion="Fear", confidence=0.9, needs_review=True, prompt_version=1, ai_model="qwen3:8b"),
            ArticleAnalysis(article_id=a2.article_id, topics=["A"], keywords=[], sentiment="negative", emotion="Fear", confidence=0.95, needs_review=False, prompt_version=1, ai_model="qwen3:8b"),
        ]
    )
    db_session.flush()

    result = aggregate_basic(db_session, [a1.article_id, a2.article_id])

    assert result["summary_stats"] == {
        "Tổng số bài": 2,
        "Tổng số cơ quan": 2,
        "Số bài cần review (needs_review)": 1,
    }
