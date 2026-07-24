"""节点级 Trace：耗时、状态摘要、错误、校验告警。"""

from __future__ import annotations

import json
import os
import time
import traceback
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from packing_assistant.config import HARNESS_VERSION, TRACE_DIR, VALIDATION_MODE


NodeFn = Callable[[Dict[str, Any]], Dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _summarize_state(state: Dict[str, Any], keys: Optional[List[str]] = None) -> Dict[str, Any]:
    keys = keys or [
        "materials",
        "boxes",
        "container_plan",
        "risks",
        "phase",
        "container_type",
        "evaluation",
        "risk_report",
    ]
    out: Dict[str, Any] = {}
    for k in keys:
        if k not in state:
            continue
        v = state[k]
        if k == "materials":
            out[k] = {"count": len(v or [])}
        elif k == "boxes":
            out[k] = {"count": len(v or []), "ids": [b.get("箱号") for b in (v or [])[:12]]}
        elif k == "container_plan":
            plan = v or {}
            out[k] = {
                "柜型": plan.get("柜型"),
                "结论": plan.get("结论"),
                "空间利用率": plan.get("空间利用率"),
                "重量利用率": plan.get("重量利用率"),
                "布局数": len(plan.get("布局") or []),
            }
        elif k == "risks":
            out[k] = {"count": len(v or [])}
        else:
            out[k] = v
    return out


def make_trace_event(
    *,
    node: str,
    status: str,
    duration_ms: float,
    input_summary: Dict[str, Any],
    output_summary: Dict[str, Any],
    warnings: Optional[List[str]] = None,
    error: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "ts": _now_iso(),
        "run_id": run_id,
        "harness_version": HARNESS_VERSION,
        "node": node,
        "status": status,  # ok | error | skipped
        "duration_ms": round(duration_ms, 2),
        "input": input_summary,
        "output": output_summary,
        "warnings": warnings or [],
        "error": error,
    }


def instrument_node(node_name: str, fn: NodeFn) -> NodeFn:
    """
    包装图节点：计时 + 异常捕获 + 写入 traces / errors。

    注意：messages / traces / errors / validation_warnings 使用 operator.add 累加。
    """

    @wraps(fn)
    def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
        run_id = state.get("run_id")
        t0 = time.perf_counter()
        in_sum = _summarize_state(state)
        try:
            result = fn(state) or {}
            if not isinstance(result, dict):
                raise TypeError(f"节点 {node_name} 必须返回 dict，实际 {type(result)}")

            duration_ms = (time.perf_counter() - t0) * 1000
            # 合并后摘要
            merged = {**state, **{k: v for k, v in result.items() if k not in (
                "messages", "traces", "errors", "validation_warnings"
            )}}
            # 列表字段用 result 优先
            for lk in ("materials", "boxes", "risks"):
                if lk in result:
                    merged[lk] = result[lk]
            if "container_plan" in result:
                merged["container_plan"] = result["container_plan"]

            warnings = list(result.get("validation_warnings") or [])
            event = make_trace_event(
                node=node_name,
                status="ok",
                duration_ms=duration_ms,
                input_summary=in_sum,
                output_summary=_summarize_state(merged),
                warnings=warnings,
                run_id=run_id,
            )
            # 不覆盖节点自己写的 traces，而是追加
            extra_traces = list(result.get("traces") or [])
            result["traces"] = extra_traces + [event]
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - t0) * 1000
            err_msg = f"{node_name}: {type(e).__name__}: {e}"
            event = make_trace_event(
                node=node_name,
                status="error",
                duration_ms=duration_ms,
                input_summary=in_sum,
                output_summary={},
                error=err_msg,
                run_id=run_id,
            )
            # soft：记录错误继续（返回空更新 + error）；strict 在外层可再抛
            if VALIDATION_MODE == "strict":
                # 仍写入 trace 信息到异常上下文，再抛出
                raise
            return {
                "errors": [err_msg, traceback.format_exc(limit=3)],
                "traces": [event],
                "messages": [
                    {
                        "role": "system",
                        "content": f"[Harness] 节点 {node_name} 失败: {e}",
                    }
                ],
            }

    return wrapper


def save_trace(
    state: Dict[str, Any],
    path: Optional[str] = None,
    directory: str = TRACE_DIR,
) -> str:
    """将 run 的 traces 与关键结果落盘。"""
    os.makedirs(directory, exist_ok=True)
    run_id = state.get("run_id") or uuid.uuid4().hex[:12]
    if not path:
        path = os.path.join(directory, f"trace_{run_id}.json")

    payload = {
        "run_id": run_id,
        "harness_version": HARNESS_VERSION,
        "harness_meta": state.get("harness_meta"),
        "raw_input": state.get("raw_input"),
        "container_type": state.get("container_type"),
        "materials_count": len(state.get("materials") or []),
        "boxes_count": len(state.get("boxes") or []),
        "container_plan": state.get("container_plan"),
        "risks": state.get("risks"),
        "image_path": state.get("image_path"),
        "validation_warnings": state.get("validation_warnings"),
        "errors": state.get("errors"),
        "traces": state.get("traces") or [],
        "final_response_preview": (state.get("final_response") or "")[:500],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    return path


def new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
