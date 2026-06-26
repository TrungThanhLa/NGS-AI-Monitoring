import json
import os
import re

import httpx

from backend.ai.prompts.v1 import CLASSIFICATION_PROMPT, PROMPT_VERSION, TOPIC_GROUPS

JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_response(raw: str) -> dict:
    match = JSON_BLOCK_RE.search(raw)
    if not match:
        raise ValueError(f"Ollama response không chứa JSON hợp lệ: {raw!r}")
    return json.loads(match.group(0))


def analyze_article(title: str, content: str, client: httpx.Client | None = None) -> dict:
    owns_client = client is None
    client = client or httpx.Client(timeout=int(os.environ.get("AI_TIMEOUT_SECONDS", "120")))

    max_content_length = int(os.environ.get("AI_MAX_CONTENT_LENGTH", "2000"))
    confidence_threshold = float(os.environ.get("AI_CONFIDENCE_THRESHOLD", "0.6"))
    prompt = CLASSIFICATION_PROMPT.format(
        title=title,
        content_snippet=content[:max_content_length],
        topic_list="\n".join(f"- {t}" for t in TOPIC_GROUPS),
    )

    try:
        result = None
        last_error: Exception | None = None
        for _attempt in range(2):
            response = client.post(
                f"{os.environ['OLLAMA_BASE_URL']}/api/generate",
                json={"model": os.environ["OLLAMA_MODEL"], "prompt": prompt, "stream": False},
            )
            raw = response.json()["response"]
            try:
                result = _parse_json_response(raw)
                break
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = exc
        if result is None:
            raise ValueError("Ollama trả về JSON không hợp lệ sau khi retry") from last_error

        result["needs_review"] = result.get("confidence", 1.0) < confidence_threshold
        result["prompt_version"] = PROMPT_VERSION
        return result
    finally:
        if owns_client:
            client.close()
