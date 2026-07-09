import csv
import sys

from backend.db import SessionLocal
from backend.models import Article, ArticleAnalysis


def export_analysis_csv(job_id: str, output_path: str) -> None:
    db = SessionLocal()
    try:
        rows = (
            db.query(Article, ArticleAnalysis)
            .join(ArticleAnalysis, ArticleAnalysis.article_id == Article.article_id)
            .filter(Article.job_id == job_id)
            .all()
        )
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "title", "url", "topics", "keywords", "sentiment", "emotion",
                    "confidence", "needs_review", "summary", "ai_model",
                ]
            )
            for article, analysis in rows:
                writer.writerow(
                    [
                        article.title,
                        article.url,
                        ";".join(analysis.topics or []),
                        ";".join(analysis.keywords or []),
                        analysis.sentiment,
                        analysis.emotion,
                        analysis.confidence,
                        analysis.needs_review,
                        analysis.summary,
                        analysis.ai_model,
                    ]
                )
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m backend.scripts.export_analysis_csv <job_id> <output_path>")
        sys.exit(1)
    export_analysis_csv(sys.argv[1], sys.argv[2])
