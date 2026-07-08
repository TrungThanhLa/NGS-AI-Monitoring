import asyncio
import json
import os
import re
import time

import httpx

from backend.ai.prompts.v1 import CLASSIFICATION_PROMPT, PROMPT_VERSION, TOPIC_GROUPS

JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_response(raw: str) -> dict:
    match = JSON_BLOCK_RE.search(raw)
    if not match:
        raise ValueError(f"Ollama response không chứa JSON hợp lệ: {raw!r}")
    return json.loads(match.group(0))


def _truncate_at_sentence_boundary(content: str, max_length: int) -> str:
    if len(content) <= max_length:
        return content
    window = content[:max_length]
    # Lùi về dấu kết câu gần nhất trong window để không cắt giữa câu/từ
    last_boundary = max(window.rfind(ch) for ch in ".!?\n")
    if last_boundary == -1:
        return window
    return window[: last_boundary + 1]


async def analyze_article(title: str, content: str, client: httpx.AsyncClient | None = None) -> dict:
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=int(os.environ.get("AI_TIMEOUT_SECONDS", "360")))

    max_content_length = int(os.environ.get("AI_MAX_CONTENT_LENGTH", "5000"))
    confidence_threshold = float(os.environ.get("AI_CONFIDENCE_THRESHOLD", "0.6"))
    prompt = CLASSIFICATION_PROMPT.format(
        title=title,
        content_snippet=_truncate_at_sentence_boundary(content, max_content_length),
        topic_list="\n".join(f"- {t}" for t in TOPIC_GROUPS),
    )

    try:
        start = time.perf_counter()
        result = None
        last_error: Exception | None = None
        for _attempt in range(2):
            response = await client.post(
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
        result["ai_model"] = os.environ["OLLAMA_MODEL"]
        result["analysis_duration_seconds"] = time.perf_counter() - start
        return result
    finally:
        if owns_client:
            await client.aclose()


async def analyze_articles_batch(
    articles: list[tuple[str, str]],
    concurrency: int,
    client: httpx.AsyncClient | None = None,
) -> list[dict | Exception]:
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=int(os.environ.get("AI_TIMEOUT_SECONDS", "360")))
    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded(title: str, content: str) -> dict:
        async with semaphore:
            return await analyze_article(title, content, client=client)

    try:
        tasks = [_bounded(title, content) for title, content in articles]
        # return_exceptions=True: 1 bài lỗi (JSON không hợp lệ / lỗi HTTP) không được raise
        # ra ngoài làm hỏng cả batch — trả về Exception ngay đúng vị trí bài đó, để caller
        # (_analyze_articles trong report_job.py) tự quyết định insert status="error".
        return await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        if owns_client:
            await client.aclose()
