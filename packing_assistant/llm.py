"""统一 LLM 客户端（OpenAI 兼容，默认 DeepSeek Flash）。"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional


def llm_config() -> Dict[str, str]:
    """
    优先级：
    1) DEEPSEEK_API_KEY + 官方 base
    2) OPENAI_API_KEY / LLM_API_KEY + OPENAI_BASE_URL
    """
    deepseek_key = os.getenv("DEEPSEEK_API_KEY") or ""
    api_key = (
        deepseek_key
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("LLM_API_KEY")
        or ""
    )
    if deepseek_key and not os.getenv("OPENAI_BASE_URL") and not os.getenv("LLM_BASE_URL"):
        base_url = os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
    else:
        base_url = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("LLM_BASE_URL")
            or os.getenv("DEEPSEEK_BASE_URL")
            or "https://api.deepseek.com"
        )
    model = (
        os.getenv("LLM_MODEL")
        or os.getenv("DEEPSEEK_MODEL")
        or "deepseek-v4-flash"
    )
    return {"api_key": api_key, "base_url": base_url.rstrip("/"), "model": model}


def llm_available() -> bool:
    return bool(llm_config().get("api_key"))


def chat(
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 2000,
) -> Optional[str]:
    """调用 Chat Completions；失败返回 None。"""
    cfg = llm_config()
    if not cfg["api_key"]:
        return None
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        # 短超时：避免 UI/pipeline 被远端 API 挂死（默认 8s，可用 LLM_TIMEOUT 覆盖）
        _to = float(os.getenv("LLM_TIMEOUT") or 8)
        llm = ChatOpenAI(
            model=cfg["model"],
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=_to,
            max_retries=0,
        )
        resp = llm.invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        text = str(resp.content or "").strip()
        return text or None
    except Exception as e:
        return f"[LLM_ERROR] {type(e).__name__}: {e}"


def chat_json_array(system: str, user: str) -> Optional[List[Dict[str, Any]]]:
    text = chat(system, user, temperature=0.1, max_tokens=3000)
    if not text or text.startswith("[LLM_ERROR]"):
        return None
    return _extract_json_array(text)


def _extract_json_array(text: str) -> Optional[List[Dict[str, Any]]]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "materials" in data:
            return data["materials"]
    except json.JSONDecodeError:
        pass
    start, end = text.find("["), text.rfind("]")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            return None
    return None
