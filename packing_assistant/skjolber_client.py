"""调用 Spring skjolber-service 的 HTTP 客户端。"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json


def skjolber_base_url() -> str:
    return (os.getenv("SKJOLBER_URL") or os.getenv("PACKER_URL") or "").rstrip("/")


def is_skjolber_configured() -> bool:
    return bool(skjolber_base_url())


def health_check(timeout: float = 2.0) -> Dict[str, Any]:
    base = skjolber_base_url()
    if not base:
        return {"ok": False, "reason": "SKJOLBER_URL not set"}
    try:
        req = Request(base + "/api/v1/packer/health", method="GET")
        with urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return {"ok": True, "body": body}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


def pack_via_skjolber(
    boxes: List[Dict[str, Any]],
    plan: Dict[str, Any],
    *,
    request_id: str = "",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    POST /api/v1/packer/pack
    成功返回 container_plan（api-spec）；失败抛 RuntimeError。
    """
    base = skjolber_base_url()
    if not base:
        raise RuntimeError("SKJOLBER_URL 未配置")

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
        raise RuntimeError(f"skjolber 连接失败: {e}") from e

    # 兼容直接返回 container_plan 或包在响应里
    if "container_plan" in body:
        plan_out = body["container_plan"]
    else:
        plan_out = body

    # 确保字段完整
    plan_out.setdefault("engine", body.get("engine") or "skjolber")
    plan_out.setdefault("unpacked_box_ids", body.get("unpackedBoxIds") or body.get("unpacked_box_ids") or [])
    plan_out.setdefault("layout", plan_out.get("layout") or [])
    plan_out.setdefault("can_fit", body.get("success", plan_out.get("can_fit", False)))
    return plan_out
