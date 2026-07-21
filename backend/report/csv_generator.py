import csv


def generate_csv(date_from, date_to, aggregates: dict, output_path: str) -> None:
    # CSV chỉ xuất danh sách bài viết chi tiết (không xuất các bảng thống kê tổng hợp —
    # CSV là định dạng phẳng 1 bảng, không hợp để nhồi nhiều bảng khác nhau như
    # docx/pdf/excel; người cần số liệu tổng hợp dùng 1 trong 3 định dạng kia).
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Tiêu đề", "URL", "Sentiment", "Emotion", "Confidence", "Needs review"])
        for article in aggregates["articles"]:
            writer.writerow(
                [
                    article["title"] or "",
                    article["url"] or "",
                    article["sentiment"] or "",
                    article["emotion"] or "",
                    article["confidence"],
                    article["needs_review"],
                ]
            )
