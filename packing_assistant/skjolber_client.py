"""调用 Spring skjolber-service 的 HTTP 客户端。

服务未起时：快速失败 + 负缓存，避免拖死单线程 uvicorn。
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# (ok, reason, expire_monotonic)
_HEALTH_CACHE: Optional[Tuple[bool, str, float]] = None
_NEG_TTL = float(os.getenv("SKJOLBER_NEG_CACHE_SEC") or 120)
_POS_TTL = float(os.getenv("SKJOLBER_POS_CACHE_SEC") or 30)


def skjolber_base_url() -> str:
    if (os.getenv("PACKING_SKIP_SKJOLBER") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return ""
    return (os.getenv("SKJOLBER_URL") or os.getenv("PACKER_URL") or "").rstrip("/")


def is_skjolber_configured() -> bool:
    return bool(skjolber_base_url())


def clear_health_cache() -> None:
    global _HEALTH_CACHE
    _HEALTH_CACHE = None


def health_check(timeout: float = 0.25, *, use_cache: bool = True) -> Dict[str, Any]:
    """默认极短超时 + 负缓存：未起服务时不反复卡 0.5–2s。"""
    global _HEALTH_CACHE
    base = skjolber_base_url()
    if not base:
        return {"ok": False, "reason": "SKJOLBER skipped or URL not set", "cached": False}

    now = time.monotonic()
    if use_cache and _HEALTH_CACHE is not None:
        ok, reason, exp = _HEALTH_CACHE
        if now < exp:
            return {"ok": ok, "reason": reason, "cached": True, "body": None if not ok else {}}

    try:
        req = Request(base + "/api/v1/packer/health", method="GET")
        with urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        _HEALTH_CACHE = (True, "ok", now + _POS_TTL)
        return {"ok": True, "body": body, "cached": False}
    except Exception as e:
        reason = str(e)
        _HEALTH_CACHE = (False, reason, now + _NEG_TTL)
        return {"ok": False, "reason": reason, "cached": False}


def pack_via_skjolber(
    boxes: List[Dict[str, Any]],
    plan: Dict[str, Any],
    *,
    request_id: str = "",
    timeout: float = 12.0,
) -> Dict[str, Any]:
    """
    POST /api/v1/packer/pack
    成功返回 container_plan；失败抛 RuntimeError。
    """
    base = skjolber_base_url()
    if not base:
        raise RuntimeError("SKJOLBER_URL 未配置或已 SKIP")

    # 先看缓存/快探活，失败直接抛，别硬等到 timeout
    hc = health_check(timeout=0.25)
    if not hc.get("ok"):
        raise RuntimeError(f"skjolber 不可用: {hc.get('reason')}")

    payload = {
        "requestId": request_id or "py-client",
        "plan": {
            "strategy": plan.get("strategy") or "LARGEST_AREA_FIT_FIRST",
            "container_type": plan.get("container_type") or "40HQ",
            "maxContainers": int(plan.get("max_containers") or 1),
            "priority_order": plan.get("priority_order") or [],
            "special_rules": plan.get("special_rules") or [],
            "allowRotation": True,
            "timeoutMs": int(os.getenv("SKJOLBER_TIMEOUT_MS") or 8000),
        },
        "boxes": [
            {
                "box_id": b.get("box_id"),
                "box_type": b.get("box_type"),
                "outer_size_mm": b.get("outer_size_mm"),
                "gross_weight_kg": b.get("gross_weight_kg"),
                "net_weight_kg": b.get("net_weight_kg"),
                "special_attributes": b.get("special_attributes") or [],
                "allowRotate": "超长" not in (b.get("special_attributes") or []),
                "stackable": "超长" not in (b.get("special_attributes") or []),
            }
            for b in boxes
        ],
        "containerCatalog": None,
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        base + "/api/v1/packer/pack",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"skjolber HTTP {e.code}: {err}") from e
    except URLError as e:
        clear_health_cache()
        raise RuntimeError(f"skjolber 连接失败: {e}") from e

    if "container_plan" in body:
        plan_out = body["container_plan"]
    else:
        plan_out = body

    plan_out.setdefault("engine", body.get("engine") or "skjolber")
    plan_out.setdefault(
        "unpacked_box_ids",
        body.get("unpackedBoxIds") or body.get("unpacked_box_ids") or [],
    )
    plan_out.setdefault("layout", plan_out.get("layout") or [])
    plan_out.setdefault("can_fit", body.get("success", plan_out.get("can_fit", False)))
    return plan_out
