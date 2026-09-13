from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx

from packing_assistant.llm import llm_config


class LLMError(RuntimeError):
    pass


def has_key() -> bool:
    return bool(llm_config()["api_key"])


def _headers(key: str) -> dict[str, str]:
    if not key:
        raise LLMError(
            "未配置 API Key，请在工作台「模型设置」中配置。"
        )
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _check_status(response: httpx.Response) -> None:
    status = response.status_code
    if 200 <= status < 300:
        return
    if status in {401, 403}:
        hint = "认证失败，请检查 API Key 和接口权限"
    elif status == 429:
        hint = "请求受限，请检查模型额度或稍后重试"
    elif status >= 500:
        hint = "模型服务暂不可用，请稍后重试"
    elif 300 <= status < 400:
        hint = "接口发生重定向，请检查 Base URL"
    else:
        hint = "模型请求失败，请检查 Base URL 和模型名称"
    # Provider responses may echo credentials or submitted documents.
    raise LLMError(f"LLM HTTP {status}：{hint}")


def _event_data(lines: Iterator[str]) -> Iterator[tuple[str, str]]:
    """Read SSE frames, including comments, data without spaces and multiline data."""
    event, data, size = "message", [], 0
    first = True
    for line in lines:
        if first:
            line = line.removeprefix("\ufeff")
            first = False
        if not line:
            if data:
                yield event, "\n".join(data)
            event, data, size = "message", [], 0
            continue
        if line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if not separator:
            value = ""
        if value.startswith(" "):
            value = value[1:]
        if field == "event":
            event = value
        elif field == "data":
            size += len(value)
            if size > 1024 * 1024:
                raise LLMError("模型流单条事件过大，已停止读取")
            data.append(value)
    if data:
        yield event, "\n".join(data)


def _stream_content(response: httpx.Response) -> Iterator[str]:
    has_text = False
    for event, data in _event_data(response.iter_lines()):
        if event == "error":
            raise LLMError("模型服务返回流错误，回复未完成，请重试")
        if data.strip() == "[DONE]":
            if not has_text:
                raise LLMError("模型未返回可显示的文本，请检查模型设置后重试")
            return
        try:
            chunk = json.loads(data)
        except ValueError:
            raise LLMError("模型流数据格式错误，回复未完成，请重试") from None
        if not isinstance(chunk, dict) or chunk.get("error") is not None:
            raise LLMError("模型服务返回错误响应，回复未完成，请重试")
        choices = chunk.get("choices")
        if not isinstance(choices, list):
            raise LLMError("模型流缺少有效回复数据，请检查接口兼容性")
        if not choices:  # Usage-only frames are allowed before the final marker.
            continue
        choice = choices[0]
        if not isinstance(choice, dict) or not isinstance(choice.get("delta"), dict):
            raise LLMError("模型流回复结构无效，请检查接口兼容性")
        piece = choice["delta"].get("content")
        if piece is not None and not isinstance(piece, str):
            raise LLMError("模型流文本格式无效，请检查接口兼容性")
        if piece:
            has_text = has_text or bool(piece.strip())
            yield piece
        reason = choice.get("finish_reason")
        if reason == "length":
            raise LLMError("模型达到回复长度限制，内容未完成，请缩小问题后重试")
        if reason is not None and reason != "stop":
            raise LLMError("模型提前停止回复，内容未完成，请检查请求后重试")
    raise LLMError("模型连接已结束但未收到完成标记，回复可能不完整，请重试")


class ModelConnection:
    """An httpx client plus every network stream its requests open.

    Cancellation (demo/turn_control.py) has to shut down the socket a request
    is blocked on. httpx only exposes that socket on a response, and a request
    still waiting for response headers has no response yet — so this records
    the streams as httpcore opens them, through httpcore's documented ``trace``
    request extension. A TLS stream supersedes the TCP stream it wrapped.
    """

    _OPENED = (".connect_tcp.complete", ".connect_unix_socket.complete", ".start_tls.complete")

    def __init__(self, timeout: float = 120.0):
        self.client = httpx.Client(timeout=timeout)
        self.network_streams: list[Any] = []

    def _trace(self, name: str, info: dict) -> None:
        if name.endswith(self._OPENED) and info.get("return_value") is not None:
            self.network_streams.append(info["return_value"])

    def stream(self, method: str, url: str, **kwargs):
        return self.client.stream(method, url, extensions={"trace": self._trace}, **kwargs)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "ModelConnection":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def chat(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    cancel_event=None,
) -> dict[str, Any]:
    budget = _request_budget(messages, tools=tools)
    if max_tokens is not None and (type(max_tokens) is not int or max_tokens < 1):
        raise LLMError("模型输出预算必须为正整数")
    reserve = min(budget["reserve"], max_tokens) if max_tokens is not None else budget["reserve"]
    config = llm_config()
    payload: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": reserve,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    try:
        from turn_control import interrupt_http, interrupt_event
        with ModelConnection() as connection, interrupt_http(connection), interrupt_event(connection, cancel_event):
            with connection.stream("POST", f"{config['base_url']}/chat/completions",
                                   headers=_headers(config["api_key"]), json=payload) as response:
                with interrupt_http(response), interrupt_event(response, cancel_event):
                    _check_status(response)
                    response.read()
                    try:
                        data = response.json()
                        if not isinstance(data, dict) or data.get("error") is not None:
                            raise ValueError("invalid response")
                        message = data["choices"][0]["message"]
                        if not isinstance(message, dict):
                            raise ValueError("invalid message")
                    except (ValueError, KeyError, IndexError, TypeError):
                        raise LLMError("模型返回了无效回复，请检查接口兼容性后重试") from None
                    return message
    except httpx.TimeoutException:
        raise LLMError("模型响应超时，请稍后重试") from None
    except (httpx.RequestError, httpx.InvalidURL):
        raise LLMError("无法连接模型接口，请检查 Base URL 和网络后重试") from None


def _request_budget(messages: list[dict], *, tools: list | None = None) -> dict:
    from context import validate_request
    try:
        return validate_request(messages, tools=tools)
    except ValueError as exc:
        raise LLMError(str(exc)) from None


def stream_plain(messages: list[dict[str, Any]], temperature: float = 0.6) -> Iterator[str]:
    from turn_control import interrupt_http
    budget = _request_budget(messages)
    config = llm_config()
    payload = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        "max_tokens": budget["reserve"],
    }
    try:
        with ModelConnection() as connection, interrupt_http(connection):
            with connection.stream(
                "POST",
                f"{config['base_url']}/chat/completions",
                headers=_headers(config["api_key"]),
                json=payload,
            ) as response:
                with interrupt_http(response):
                    _check_status(response)
                    yield from _stream_content(response)
    except httpx.TimeoutException:
        raise LLMError("模型响应超时，回复可能不完整，请重试") from None
    except (httpx.RequestError, httpx.InvalidURL):
        raise LLMError("模型连接异常，回复可能不完整，请检查网络后重试") from None
