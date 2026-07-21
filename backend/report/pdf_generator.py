from weasyprint import HTML


def _render_count_table(label_column: str, counts: dict) -> str:
    rows = "".join(f"<tr><td>{key}</td><td>{count}</td></tr>" for key, count in counts.items())
    return f"<table border='1' cellspacing='0' cellpadding='4'><tr><th>{label_column}</th><th>Số lượng</th></tr>{rows}</table>"


def generate_pdf(date_from, date_to, aggregates: dict, output_path: str) -> None:
    # Dùng WeasyPrint render PDF từ HTML thuần (không cần template file riêng) — tái dùng
    # đúng cấu trúc bảng như docx_generator.py, giữ số liệu nhất quán giữa các định dạng.
    articles_rows = "".join(
        f"<tr><td>{a['title'] or ''}</td><td>{a['url'] or ''}</td><td>{a['sentiment'] or ''}</td>"
        f"<td>{a['emotion'] or ''}</td><td>{a['confidence']}</td><td>{a['needs_review']}</td></tr>"
        for a in aggregates["articles"]
    )
    html = f"""
    <html><head><meta charset="utf-8"><style>
      body {{ font-family: sans-serif; font-size: 12px; }}
      table {{ border-collapse: collapse; margin-bottom: 16px; width: 100%; }}
      td, th {{ border: 1px solid #ccc; padding: 4px; }}
      h1 {{ font-size: 18px; }} h2 {{ font-size: 14px; }}
    </style></head><body>
      <h1>Báo cáo NGS Monitor</h1>
      <p>Khoảng thời gian: {date_from} – {date_to}</p>
      <h2>Số lượng nội dung theo cơ quan</h2>{_render_count_table("Cơ quan", aggregates["source_counts"])}
      <h2>Số lượng nội dung theo chủ đề</h2>{_render_count_table("Chủ đề", aggregates["topic_counts"])}
      <h2>Top từ khóa</h2>{_render_count_table("Từ khóa", aggregates["keyword_counts"])}
      <h2>Thống kê theo tháng</h2>{_render_count_table("Tháng", aggregates["monthly_counts"])}
      <h2>Sentiment Analysis</h2>{_render_count_table("Sentiment", aggregates["sentiment_counts"])}
      <h2>Emotion Analysis</h2>{_render_count_table("Emotion", aggregates["emotion_counts"])}
      <h2>Thống kê tổng hợp</h2>{_render_count_table("Chỉ số", aggregates["summary_stats"])}
      <h2>Danh sách bài viết</h2>
      <table><tr><th>Tiêu đề</th><th>URL</th><th>Sentiment</th><th>Emotion</th><th>Confidence</th><th>Needs review</th></tr>
        {articles_rows}</table>
    </body></html>
    """
    HTML(string=html).write_pdf(output_path)
