---
description: AI pipeline — Ollama prompt template, 8 nhóm chủ đề, confidence threshold, AIProvider
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

## Prompt versioning — `[ĐÃ CODE]`

Prompt được lưu thành file versioned trong `backend/ai/prompts/` (`v1.py`, `v2.py`...) — **không sửa đè file cũ** khi tinh chỉnh prompt, luôn thêm file mới với `PROMPT_VERSION` tăng dần. Mỗi bản ghi `article_analysis` lưu `prompt_version` đã dùng (cột NOT NULL, xem [03 · Database Schema](03-database-schema.md)) — để không lẫn kết quả giữa các lần tinh chỉnh prompt.

```python
# backend/ai/prompts/v1.py
PROMPT_VERSION = 1
```

## Ollama prompt template — `[ĐÃ CODE]`

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

## Gọi Ollama API — `[ĐÃ CODE]`

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
- AI **không được phép** kết luận "đây là tin giả" — chỉ gắn cờ `needs_review=true` kèm lý do, quyết định cuối cùng luôn thuộc về con người (nguyên tắc không thương lượng, giữ nguyên khi mở rộng — xem [18 · Alert & Case Management](18-alert-case-management.md) mục AI Phân tích)

**Giới hạn đã biết — kết quả AI không đảm bảo giống hệt nhau giữa các lần gọi (2026-07-09):**
Do dedup hiện tại `[ĐÃ CODE]` chỉ trong phạm vi 1 job (xem [06 · Crawler Strategy](06-crawler-strategy.md)), cùng 1 bài viết có thể được phân tích AI nhiều lần ở các job khác nhau (job trùng phạm vi ngày). `qwen3:8b` qua Ollama không set `temperature`/seed cố định, output giữa các lần gọi **không đảm bảo giống hệt nhau** (`topics`/`sentiment`/`emotion`/`confidence` có thể khác nhau cho cùng 1 bài). Hạn chế này **tự động biến mất khi dedup chuyển sang toàn cục theo Source** ([06 · Crawler Strategy](06-crawler-strategy.md) mục Scheduler) — mỗi URL chỉ còn được phân tích đúng 1 lần.

---

## Môi trường & Cấu hình — `[ĐÃ CODE]`

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

AI_CONFIDENCE_THRESHOLD=0.6
AI_MAX_CONTENT_LENGTH=5000
AI_TIMEOUT_SECONDS=360
```

> `AI_MAX_CONTENT_LENGTH=5000` và `AI_TIMEOUT_SECONDS=360` là giải pháp tạm thời (2026-06-26) — cân nhắc nâng/hạ lại theo tần suất timeout thật gặp phải khi có thêm dữ liệu.

---

## AI Runtime — chuyển provider là thao tác THỦ CÔNG — `[CHƯA CODE]`

> Gọi thẳng Ollama REST API ở trên là **đang chạy thật**. Việc cần làm khi triển khai Continuous Monitoring: tách `AIProvider` interface khỏi `ollama_client.py` hiện có (refactor tối thiểu) để chuyển đổi thủ công sang server AI riêng/cloud LLM khi cần — không phải "tính năng thêm", mà là bọc lại code hiện có qua 1 lớp interface.

Không xây cơ chế tự động phát hiện tải cao rồi tự chuyển provider. Bắt đầu bằng Ollama local (`qwen3:8b`) như hiện tại — người vận hành tự quan sát rồi tự đổi cấu hình khi cần, qua lớp `AIProvider` interface:

```python
# backend/ai/providers/base.py
class AIProvider(ABC):
    @abstractmethod
    async def analyze(self, title: str, content: str) -> dict: ...

# backend/ai/providers/ollama_provider.py         — implementation hiện tại (bọc lại code trên)
# backend/ai/providers/remote_ollama_provider.py  — server AI riêng, chỉ đổi base_url
# backend/ai/providers/cloud_llm_provider.py      — API cloud (Claude/ChatGPT/Gemini/DeepSeek)
```

Chọn provider qua `AI_PROVIDER=ollama_local|ollama_remote|cloud_llm` (`.env`). Giữ nguyên format output JSON (`topics/keywords/sentiment/emotion/confidence/summary`) bất kể provider — không phải sửa `article_analysis` hay `docx_generator.py`.

**Ví dụ cụ thể khi chuyển sang ChatGPT:** (1) thêm `backend/ai/providers/openai_provider.py` implement `AIProvider`, gọi OpenAI Chat Completions API, trả về đúng format JSON hiện có; (2) thêm 1 nhánh nhỏ ở factory chọn provider theo `AI_PROVIDER`; (3) thêm `.env` (`AI_PROVIDER=cloud_llm`, `OPENAI_API_KEY=...`). **Không đổi:** nội dung prompt (`prompts/v1.py`), schema `article_analysis`, `aggregator.py`, `docx_generator.py`/PDF/Excel/CSV, crawler, Alert/Case.

**Công tắc `AI_AUTO_TRIGGER`** (bật/tắt AI tự động chạy sau khi crawl xong, tách rời khỏi việc chọn `AI_PROVIDER`) — business rule và ràng buộc vận hành chi tiết: xem [17 · Continuous Crawler & Scheduler](17-continuous-crawler-scheduler.md).
