import os
import uuid

from backend.report.pdf_generator import generate_pdf


def test_generate_pdf_creates_valid_pdf_file(tmp_path):
    aggregates = {
        "articles": [{"title": "Bài 1", "url": "https://vtv.vn/a1", "sentiment": "negative",
                      "emotion": "Fear", "confidence": 0.9, "needs_review": False}],
        "sentiment_counts": {"negative": 1},
        "emotion_counts": {"Fear": 1},
        "source_counts": {"VTV": 1},
        "topic_counts": {"A": 1},
        "keyword_counts": {"kw1": 1},
        "monthly_counts": {"2026-06": 1},
        "summary_stats": {"Tổng số bài": 1},
    }
    output_path = str(tmp_path / f"{uuid.uuid4()}.pdf")

    generate_pdf("2026-06-01", "2026-06-30", aggregates, output_path)

    assert os.path.exists(output_path)
    with open(output_path, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-"
