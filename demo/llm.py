from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


class LLMError(RuntimeError):
    pass


def has_key() -> bool:
    return bool(DEEPSEEK_API_KEY)


def _headers() -> dict[str, str]:
    if not DEEPSEEK_API_KEY:
        raise LLMError("未配置 DEEPSEEK_API_KEY。在 demo/.env 写入后重启。")
    return {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }


def chat(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.3,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=_headers(),
            json=payload,
        )
        if r.status_code >= 400:
            raise LLMError(f"DeepSeek {r.status_code}: {r.text[:400]}")
        return r.json()["choices"][0]["message"]


def stream_plain(messages: list[dict[str, Any]], temperature: float = 0.6) -> Iterator[str]:
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    with httpx.Client(timeout=120.0) as client:
        with client.stream(
            "POST",
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=_headers(),
            json=payload,
        ) as r:
            if r.status_code >= 400:
                body = r.read().decode("utf-8", errors="ignore")
                raise LLMError(f"DeepSeek {r.status_code}: {body[:400]}")
            for line in r.iter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data = line[6:]
                else:
                    continue
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta") or {}
                    piece = delta.get("content") or ""
                    if piece:
                        yield piece
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
