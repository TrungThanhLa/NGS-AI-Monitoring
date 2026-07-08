import asyncio
import json

import httpx
import pytest

from backend.ai.ollama_client import analyze_article, analyze_articles_batch
from backend.ai.prompts.v1 import PROMPT_VERSION

VALID_JSON = """{
  "topics": ["Tin giả và thông tin sai lệch"],
  "keywords": ["deepfake", "lừa đảo"],
  "sentiment": "negative",
  "emotion": "Fear",
  "confidence": 0.85,
  "summary": "Tóm tắt bài viết."
}"""


def _client_with_responses(responses: list[str]) -> httpx.AsyncClient:
    state = {"i": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        text = responses[min(state["i"], len(responses) - 1)]
        state["i"] += 1
        return httpx.Response(200, json={"response": text})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_parses_valid_json_response_and_attaches_prompt_version(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:8b")
    client = _client_with_responses([VALID_JSON])

    result = asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))

    assert result["topics"] == ["Tin giả và thông tin sai lệch"]
    assert result["sentiment"] == "negative"
    assert result["emotion"] == "Fear"
    assert result["confidence"] == 0.85
    assert result["prompt_version"] == PROMPT_VERSION
    assert result["needs_review"] is False
    assert result["ai_model"] == "qwen3:8b"


def test_strips_markdown_code_fence_around_json():
    fenced = f"```json\n{VALID_JSON}\n```"
    client = _client_with_responses([fenced])

    result = asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))

    assert result["sentiment"] == "negative"


def test_flags_needs_review_when_confidence_below_threshold():
    low_confidence = VALID_JSON.replace('"confidence": 0.85', '"confidence": 0.4')
    client = _client_with_responses([low_confidence])

    result = asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))

    assert result["needs_review"] is True


def test_retries_once_on_invalid_json_then_succeeds():
    client = _client_with_responses(["không phải json", VALID_JSON])

    result = asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))

    assert result["sentiment"] == "negative"


def test_raises_after_invalid_json_twice():
    client = _client_with_responses(["không phải json", "vẫn không phải json"])

    with pytest.raises(ValueError):
        asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))


def test_returns_analysis_duration_seconds():
    client = _client_with_responses([VALID_JSON])

    result = asyncio.run(analyze_article("Tiêu đề", "Nội dung bài viết", client=client))

    assert result["analysis_duration_seconds"] > 0


def test_truncates_content_at_sentence_boundary_not_mid_word(monkeypatch):
    monkeypatch.setenv("AI_MAX_CONTENT_LENGTH", "20")
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["prompt"] = json.loads(request.content)["prompt"]
        return httpx.Response(200, json={"response": VALID_JSON})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    content = "Câu đầu tiên ngắn. Câu thứ hai dài hơn nhiều và sẽ bị cắt bỏ."
    asyncio.run(analyze_article("Tiêu đề", content, client=client))

    assert "Câu đầu tiên ngắn." in captured["prompt"]
    assert "Câu thứ hai" not in captured["prompt"]


def test_analyze_articles_batch_respects_concurrency_limit():
    state = {"current": 0, "max_seen": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        state["current"] += 1
        state["max_seen"] = max(state["max_seen"], state["current"])
        await asyncio.sleep(0.05)
        state["current"] -= 1
        return httpx.Response(200, json={"response": VALID_JSON})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    articles = [(f"Tiêu đề {i}", "Nội dung") for i in range(6)]

    results = asyncio.run(analyze_articles_batch(articles, concurrency=2, client=client))

    assert len(results) == 6
    assert all(isinstance(r, dict) for r in results)
    assert state["max_seen"] == 2


def test_analyze_articles_batch_isolates_single_failure_from_others():
    call_count = {"i": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        idx = call_count["i"]
        call_count["i"] += 1
        # 2 lệnh gọi đầu (bài đầu tiên, retry 1 lần) trả JSON lỗi -> ValueError,
        # các lệnh gọi sau (bài 2, 3) trả JSON hợp lệ.
        if idx < 2:
            return httpx.Response(200, json={"response": "không phải json"})
        return httpx.Response(200, json={"response": VALID_JSON})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    articles = [("Bài lỗi", "Nội dung"), ("Bài ổn 1", "Nội dung"), ("Bài ổn 2", "Nội dung")]

    # concurrency=1 để đảm bảo thứ tự gọi đúng như handler giả lập ở trên
    results = asyncio.run(analyze_articles_batch(articles, concurrency=1, client=client))

    assert isinstance(results[0], ValueError)
    assert isinstance(results[1], dict)
    assert isinstance(results[2], dict)


def test_analyze_articles_batch_rejects_concurrency_below_1():
    with pytest.raises(ValueError):
        asyncio.run(analyze_articles_batch([("Tiêu đề", "Nội dung")], concurrency=0))


def test_analyze_articles_batch_returns_empty_list_for_no_articles():
    results = asyncio.run(analyze_articles_batch([], concurrency=1))

    assert results == []
