import csv
import os
import uuid

from backend.report.csv_generator import generate_csv


def test_generate_csv_writes_article_rows_with_header(tmp_path):
    aggregates = {
        "articles": [
            {"title": "Bài 1", "url": "https://vtv.vn/a1", "sentiment": "negative",
             "emotion": "Fear", "confidence": 0.9, "needs_review": False},
            {"title": "Bài 2", "url": "https://vtv.vn/a2", "sentiment": "positive",
             "emotion": "Trust", "confidence": 0.8, "needs_review": True},
        ],
        "sentiment_counts": {}, "emotion_counts": {}, "source_counts": {},
        "topic_counts": {}, "keyword_counts": {}, "monthly_counts": {}, "summary_stats": {},
    }
    output_path = str(tmp_path / f"{uuid.uuid4()}.csv")

    generate_csv("2026-06-01", "2026-06-30", aggregates, output_path)

    assert os.path.exists(output_path)
    with open(output_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["Tiêu đề", "URL", "Sentiment", "Emotion", "Confidence", "Needs review"]
    assert rows[1] == ["Bài 1", "https://vtv.vn/a1", "negative", "Fear", "0.9", "False"]
    assert len(rows) == 3  # header + 2 bài
