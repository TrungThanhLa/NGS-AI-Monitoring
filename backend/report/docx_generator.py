import json

from docx import Document


def generate_docx(job, aggregates: dict, output_path: str) -> None:
    doc = Document()
    doc.add_heading("Báo cáo NGS Monitor", level=1)
    doc.add_paragraph(f"Khoảng thời gian: {job.date_from} – {job.date_to}")

    doc.add_heading("Danh sách bài viết", level=2)
    table = doc.add_table(rows=1, cols=6)
    header = table.rows[0].cells
    for i, name in enumerate(["Tiêu đề", "URL", "Sentiment", "Emotion", "Confidence", "Needs review"]):
        header[i].text = name
    for article in aggregates["articles"]:
        cells = table.add_row().cells
        cells[0].text = article["title"] or ""
        cells[1].text = article["url"] or ""
        cells[2].text = article["sentiment"] or ""
        cells[3].text = article["emotion"] or ""
        cells[4].text = str(article["confidence"])
        cells[5].text = str(article["needs_review"])

    doc.add_heading("Thống kê Sentiment", level=2)
    sentiment_table = doc.add_table(rows=1, cols=2)
    sentiment_table.rows[0].cells[0].text = "Sentiment"
    sentiment_table.rows[0].cells[1].text = "Số bài"
    for sentiment, count in aggregates["sentiment_counts"].items():
        cells = sentiment_table.add_row().cells
        cells[0].text = sentiment
        cells[1].text = str(count)

    doc.add_heading("Thống kê Emotion", level=2)
    emotion_table = doc.add_table(rows=1, cols=2)
    emotion_table.rows[0].cells[0].text = "Emotion"
    emotion_table.rows[0].cells[1].text = "Số bài"
    for emotion, count in aggregates["emotion_counts"].items():
        cells = emotion_table.add_row().cells
        cells[0].text = emotion
        cells[1].text = str(count)

    doc.save(output_path)


def export_json(job, aggregates: dict, output_path: str) -> None:
    data = {
        "job_id": str(job.job_id),
        "date_from": str(job.date_from),
        "date_to": str(job.date_to),
        **aggregates,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
