from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Article, ArticleAnalysis, Source

TOP_KEYWORDS_LIMIT = 20
UNKNOWN_EMOTION_LABEL = "Không xác định"


def aggregate_basic(db: Session, job_id: UUID) -> dict:
    rows = db.execute(
        select(Article, ArticleAnalysis, Source)
        .join(ArticleAnalysis, ArticleAnalysis.article_id == Article.article_id)
        .join(Source, Source.source_id == Article.source_id)
        .where(Article.job_id == job_id)
    ).all()

    articles = []
    sentiment_counts: Counter = Counter()
    emotion_counts: Counter = Counter()
    source_counts: Counter = Counter()
    topic_counts: Counter = Counter()
    keyword_counts: Counter = Counter()
    monthly_counts: Counter = Counter()
    needs_review_count = 0

    for article, analysis, source in rows:
        sentiment_counts[analysis.sentiment] += 1
        emotion_counts[analysis.emotion or UNKNOWN_EMOTION_LABEL] += 1
        source_counts[source.group_name] += 1
        for topic in analysis.topics:
            topic_counts[topic] += 1
        for keyword in analysis.keywords:
            keyword_counts[keyword] += 1
        if article.published_at is not None:
            monthly_counts[article.published_at.strftime("%Y-%m")] += 1
        if analysis.needs_review:
            needs_review_count += 1

        articles.append(
            {
                "title": article.title,
                "url": article.url,
                "source": source.name,
                "published_at": article.published_at,
                "sentiment": analysis.sentiment,
                "emotion": analysis.emotion,
                "topics": analysis.topics,
                "confidence": analysis.confidence,
                "needs_review": analysis.needs_review,
                "summary": analysis.summary,
            }
        )

    sorted_keywords = sorted(keyword_counts.items(), key=lambda kv: kv[1], reverse=True)[:TOP_KEYWORDS_LIMIT]

    return {
        "articles": articles,
        "sentiment_counts": dict(sentiment_counts),
        "emotion_counts": dict(emotion_counts),
        "source_counts": dict(sorted(source_counts.items(), key=lambda kv: kv[1], reverse=True)),
        "topic_counts": dict(sorted(topic_counts.items(), key=lambda kv: kv[1], reverse=True)),
        "keyword_counts": dict(sorted_keywords),
        "monthly_counts": dict(sorted(monthly_counts.items())),
        "summary_stats": {
            "Tổng số bài": len(rows),
            "Tổng số cơ quan": len(source_counts),
            "Số bài cần review (needs_review)": needs_review_count,
        },
    }
