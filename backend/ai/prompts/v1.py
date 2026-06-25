PROMPT_VERSION = 1

TOPIC_GROUPS = [
    "Tin giả và thông tin sai lệch",
    "Phản bác, đính chính thông tin",
    "Kiểm chứng và xác thực thông tin",
    "Giải thích chính sách và cung cấp thông tin chính thống",
    "Cảnh báo lừa đảo, giả mạo trên không gian mạng",
    "AI, Deepfake và công nghệ tạo sinh",
    "An toàn thông tin và an ninh mạng",
    "Hướng dẫn nhận diện tin giả và nâng cao kỹ năng truyền thông số",
]

EMOTION_GROUPS = ["Trust", "Fear", "Anger", "Surprise", "Sadness", "Happy"]

CLASSIFICATION_PROMPT = """
Bạn là chuyên gia phân tích nội dung truyền thông Việt Nam.
Phân tích bài báo sau và trả về JSON hợp lệ, KHÔNG có text nào khác.

Tiêu đề: {title}
Nội dung (tóm tắt): {content_snippet}

Trả về JSON với cấu trúc sau:
{{
  "topics": ["<tên nhóm 1>", "<tên nhóm 2>"],
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "sentiment": "positive|neutral|negative",
  "emotion": "Trust|Fear|Anger|Surprise|Sadness|Happy",
  "confidence": 0.0-1.0,
  "summary": "<tóm tắt 1 câu>"
}}

Các nhóm chủ đề hợp lệ:
{topic_list}

Chỉ chọn nhóm thực sự phù hợp. Trả về JSON thuần túy.
"""
