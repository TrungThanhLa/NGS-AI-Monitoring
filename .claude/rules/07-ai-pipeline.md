---
description: AI pipeline — Ollama prompt template, 8 nhóm chủ đề, confidence threshold
alwaysApply: false
---

# 8 Nhóm chủ đề chuẩn (dùng cho AI classification)

```python
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
```

---

# 6 Nhóm cảm xúc chuẩn (dùng cho bảng 3.15 — Emotion Analysis)

```python
EMOTION_GROUPS = ["Trust", "Fear", "Anger", "Surprise", "Sadness", "Happy"]
```

> Khác với `sentiment` (3 lớp positive|neutral|negative) — `emotion` là phân loại cảm xúc chi tiết hơn, lấy trong cùng 1 lần gọi AI, không gọi riêng lần thứ 2.

---

## Ollama prompt template

```python
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
```

## Gọi Ollama API

```python
import httpx

async def analyze_article(title: str, content: str) -> dict:
    prompt = CLASSIFICATION_PROMPT.format(
        title=title,
        content_snippet=content[:2000],
        topic_list="\n".join(f"- {t}" for t in TOPIC_GROUPS)
    )
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            "http://localhost:11434/api/generate",
            json={"model": "qwen3:8b", "prompt": prompt, "stream": False}
        )
    raw = response.json()["response"]
    result = json.loads(raw.strip())
    if result.get("confidence", 1.0) < 0.6:
        result["needs_review"] = True
    return result
```

**Quy tắc xử lý output:**
- `confidence < 0.6` → flag `needs_review=true`, vẫn lưu và đưa vào báo cáo (không xóa)
- AI trả về JSON không hợp lệ → parse với try/except, retry 1 lần, nếu vẫn lỗi thì skip bài đó

---

## Môi trường & Cấu hình

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

AI_CONFIDENCE_THRESHOLD=0.6
AI_MAX_CONTENT_LENGTH=2000
AI_TIMEOUT_SECONDS=120
```
