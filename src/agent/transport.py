"""Small DeepSeek-compatible JSON chat transport."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from src.agent.tracing import record_usage


def extract_json_object(content: str) -> dict[str, Any]:
    text = str(content or "").strip()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("planner response must be a JSON object")
    return payload


def post_chat_completion(
    *,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    base_url: str,
    temperature: float,
    timeout_seconds: float,
    max_tokens: int,
) -> str:
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "stream": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        raise ValueError("DeepSeek response did not contain a completion choice")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise ValueError("DeepSeek completion choice was malformed")
    finish_reason = choice.get("finish_reason")
    if finish_reason != "stop":
        raise ValueError(f"DeepSeek finish_reason was {finish_reason!r}, expected 'stop'")
    message = choice.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("DeepSeek response content was empty")
    if isinstance(payload, dict):
        usage = payload.get("usage")
        if isinstance(usage, dict):
            record_usage(usage)
    return content
