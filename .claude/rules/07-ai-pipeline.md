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

## Prompt versioning

Prompt được lưu thành file versioned trong `backend/ai/prompts/` (`v1.py`, `v2.py`...) — **không sửa đè file cũ** khi tinh chỉnh prompt ở Slice 3+, luôn thêm file mới với `PROMPT_VERSION` tăng dần. Mỗi bản ghi `article_analysis` lưu `prompt_version` đã dùng (cột NOT NULL, xem [03 · Database Schema](.claude/rules/03-database-schema.md)) — để không lẫn kết quả giữa các lần tinh chỉnh prompt.

```python
# backend/ai/prompts/v1.py
PROMPT_VERSION = 1
```

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
    result["prompt_version"] = PROMPT_VERSION  # từ backend/ai/prompts/v1.py — lưu kèm vào article_analysis
    return result
```

**Quy tắc xử lý output:**
- `confidence < 0.6` → flag `needs_review=true`, vẫn lưu và đưa vào báo cáo (không xóa)
- AI trả về JSON không hợp lệ → parse với try/except, retry 1 lần, nếu vẫn lỗi thì skip bài đó
- Nội dung dài hơn `AI_MAX_CONTENT_LENGTH` → cắt tại ranh giới câu gần nhất (`.`, `!`, `?`, xuống dòng), không cắt giữa câu/từ (`_truncate_at_sentence_boundary` trong `backend/ai/ollama_client.py`)

**Giới hạn đã biết — kết quả AI không đảm bảo giống hệt nhau giữa các lần gọi (2026-07-09):**
Sau khi bỏ dedup xuyên job (xem [06 · Crawler Strategy](06-crawler-strategy.md)), cùng 1 bài
viết có thể được phân tích AI nhiều lần ở các job khác nhau (job trùng phạm vi ngày). Do
`qwen3:8b` qua Ollama không set `temperature`/seed cố định, output giữa các lần gọi **không
đảm bảo giống hệt nhau** (`topics`/`sentiment`/`emotion`/`confidence` có thể khác nhau cho
cùng 1 bài). Đây là đánh đổi đã biết, chưa xử lý — xem "Vấn đề cần làm rõ" ở CLAUDE.md.

---

## Môi trường & Cấu hình

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

AI_CONFIDENCE_THRESHOLD=0.6
AI_MAX_CONTENT_LENGTH=5000
AI_TIMEOUT_SECONDS=360
```

> `AI_MAX_CONTENT_LENGTH=5000` và `AI_TIMEOUT_SECONDS=360` là giải pháp tạm thời (2026-06-26) — xem "Quyết định quan trọng & lý do" ở CLAUDE.md. Cân nhắc nâng/hạ lại theo tần suất timeout thật gặp phải khi có thêm dữ liệu (Slice 3).
