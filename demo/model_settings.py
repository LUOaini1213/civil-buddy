"""Process-local model settings matching the workbench /api/llm-config contract.

Only the shared LLM module holds raw credentials. Public payloads are masked;
updating settings never writes an environment file or contacts a provider.
"""

from __future__ import annotations

from threading import RLock
from urllib.parse import urlsplit, urlunsplit

from packing_assistant import llm

_LOCK = RLock()


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _public_base(base: str) -> str:
    """Also redact credentials accidentally included in an environment URL."""
    try:
        parts = urlsplit(base)
        host = parts.netloc.rsplit("@", 1)[-1]
        return urlunsplit((parts.scheme, host, parts.path, "", ""))
    except ValueError:
        return ""


def get_settings() -> dict:
    from context import policy, semantic_summary_enabled
    with _LOCK:
        override = llm.runtime_llm()
        config = override if override is not None else llm.llm_config()
        return {
            "ok": True,
            "source": "runtime" if override is not None else "env",
            "configured": bool(config["api_key"]),
            "base_url": _public_base(config["base_url"]),
            "model": config["model"],
            "key_masked": _mask_key(config["api_key"]),
            "semantic_summary": semantic_summary_enabled(),
            "context": policy(),
        }


def _text(payload: dict, name: str) -> str:
    value = payload.get(name, "")
    if not isinstance(value, str):
        raise ValueError(f"{name} 必须为文本")
    return value.strip()


def _validate(config: dict[str, str]) -> None:
    base = config["base_url"]
    if len(base) > 2048 or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in base):
        raise ValueError("Base URL 过长或包含空白、控制字符")
    try:
        parts = urlsplit(base)
        valid = (
            parts.scheme in {"http", "https"}
            and bool(parts.hostname)
            and parts.username is None
            and parts.password is None
            and not parts.query
            and not parts.fragment
            and "\\" not in base
        )
        _ = parts.port  # Access validates a malformed or out-of-range port.
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Base URL 必须为完整 HTTP(S) 地址，不能含凭据、查询参数或片段")
    model = config["model"]
    if not model or len(model) > 256 or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in model):
        raise ValueError("模型名称需为 1–256 个字符，不能含空白或控制字符")
    key = config["api_key"]
    if len(key) > 8192 or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in key):
        raise ValueError("API Key 过长或包含空白、控制字符")


def set_settings(payload: dict) -> dict:
    """Blank fields retain their current value; clear restores env defaults."""
    if not isinstance(payload, dict):
        raise ValueError("模型设置必须为 JSON 对象")
    clear = payload.get("clear", False)
    if not isinstance(clear, bool):
        raise ValueError("clear 必须为布尔值")
    if "semantic_summary" in payload and type(payload["semantic_summary"]) is not bool:
        raise ValueError("semantic_summary 必须为布尔值")
    with _LOCK:
        from context import policy, set_runtime_policy, set_semantic_summary, _validate_limits
        limits = None
        if "context_limit" in payload or "output_reserve" in payload:
            current = policy()
            limits = _validate_limits({"limit": payload.get("context_limit", current["limit"]),
                                       "reserve": payload.get("output_reserve", current["reserve"])})
        if clear:
            llm.set_runtime_llm(None)
            set_runtime_policy(None)
            set_semantic_summary(None)
        else:
            config = llm.llm_config()
            for name in ("api_key", "base_url", "model"):
                value = _text(payload, name)
                if value:
                    config[name] = value
            config["base_url"] = config["base_url"].rstrip("/")
            _validate(config)
            # All submitted fields have been validated before any setting moves.
            if limits is not None:
                set_runtime_policy(limits)
            if "semantic_summary" in payload:
                set_semantic_summary(payload["semantic_summary"])
            llm.set_runtime_llm(config)
        return get_settings()
