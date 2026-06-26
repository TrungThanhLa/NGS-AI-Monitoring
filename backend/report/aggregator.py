from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Article, ArticleAnalysis, Source


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

    for article, analysis, source in rows:
        sentiment_counts[analysis.sentiment] += 1
        emotion_counts[analysis.emotion] += 1
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

    return {
        "articles": articles,
        "sentiment_counts": dict(sentiment_counts),
        "emotion_counts": dict(emotion_counts),
    }
