import json

import httpx
import pytest

from backend.ai.ollama_client import analyze_article
from backend.ai.prompts.v1 import PROMPT_VERSION

VALID_JSON = """{
  "topics": ["Tin giả và thông tin sai lệch"],
  "keywords": ["deepfake", "lừa đảo"],
  "sentiment": "negative",
  "emotion": "Fear",
  "confidence": 0.85,
  "summary": "Tóm tắt bài viết."
}"""


def _client_with_responses(responses: list[str]) -> httpx.Client:
    state = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        text = responses[min(state["i"], len(responses) - 1)]
        state["i"] += 1
        return httpx.Response(200, json={"response": text})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parses_valid_json_response_and_attaches_prompt_version():
    client = _client_with_responses([VALID_JSON])

    result = analyze_article("Tiêu đề", "Nội dung bài viết", client=client)

    assert result["topics"] == ["Tin giả và thông tin sai lệch"]
    assert result["sentiment"] == "negative"
    assert result["emotion"] == "Fear"
    assert result["confidence"] == 0.85
    assert result["prompt_version"] == PROMPT_VERSION
    assert result["needs_review"] is False


def test_strips_markdown_code_fence_around_json():
    fenced = f"```json\n{VALID_JSON}\n```"
    client = _client_with_responses([fenced])

    result = analyze_article("Tiêu đề", "Nội dung bài viết", client=client)

    assert result["sentiment"] == "negative"


def test_flags_needs_review_when_confidence_below_threshold():
    low_confidence = VALID_JSON.replace('"confidence": 0.85', '"confidence": 0.4')
    client = _client_with_responses([low_confidence])

    result = analyze_article("Tiêu đề", "Nội dung bài viết", client=client)

    assert result["needs_review"] is True


def test_retries_once_on_invalid_json_then_succeeds():
    client = _client_with_responses(["không phải json", VALID_JSON])

    result = analyze_article("Tiêu đề", "Nội dung bài viết", client=client)

    assert result["sentiment"] == "negative"


def test_raises_after_invalid_json_twice():
    client = _client_with_responses(["không phải json", "vẫn không phải json"])

    with pytest.raises(ValueError):
        analyze_article("Tiêu đề", "Nội dung bài viết", client=client)


def test_returns_analysis_duration_seconds():
    client = _client_with_responses([VALID_JSON])

    result = analyze_article("Tiêu đề", "Nội dung bài viết", client=client)

    assert result["analysis_duration_seconds"] > 0


def test_truncates_content_at_sentence_boundary_not_mid_word(monkeypatch):
    monkeypatch.setenv("AI_MAX_CONTENT_LENGTH", "20")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["prompt"] = json.loads(request.content)["prompt"]
        return httpx.Response(200, json={"response": VALID_JSON})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    content = "Câu đầu tiên ngắn. Câu thứ hai dài hơn nhiều và sẽ bị cắt bỏ."
    analyze_article("Tiêu đề", content, client=client)

    assert "Câu đầu tiên ngắn." in captured["prompt"]
    assert "Câu thứ hai" not in captured["prompt"]
