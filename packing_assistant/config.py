"""Harness 与算法版本配置（可配置、可追溯）。"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Set


HARNESS_VERSION = "0.6.2"
PACKING_ALGO_VERSION = "structure-design-facts-v1"
CONSOLIDATION_ALGO_VERSION = "linear-1d-v1"
RISK_RULES_VERSION = "rules-v1"
EVALUATOR_VERSION = "adaptive-weights-v1"

# 允许节点调用的工具白名单
TOOL_WHITELIST: Set[str] = {
    "run_packing",
    "run_consolidation",
    "check_risks",
    "draw_layout",
}

ALLOWED_CONTAINER_TYPES: Set[str] = {"20GP", "40GP", "40HQ", "45HQ"}

DEFAULT_CONTAINER_TYPE = os.getenv("PACKING_CONTAINER_TYPE", "40HQ")
OUTPUT_DIR = os.getenv("PACKING_OUTPUT_DIR", "output")
TRACE_DIR = os.getenv("PACKING_TRACE_DIR", "output/traces")

# 校验策略：strict=校验失败抛错；soft=写入 warnings 继续
VALIDATION_MODE = os.getenv("PACKING_VALIDATION_MODE", "soft")  # soft | strict


@dataclass
class HarnessMeta:
    """写入状态 / trace 的版本元信息。"""

    harness_version: str = HARNESS_VERSION
    packing_algo: str = PACKING_ALGO_VERSION
    consolidation_algo: str = CONSOLIDATION_ALGO_VERSION
    risk_rules: str = RISK_RULES_VERSION
    evaluator: str = EVALUATOR_VERSION
    validation_mode: str = VALIDATION_MODE
    architecture: str = "总分总分总"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def assert_tool_allowed(tool_name: str) -> None:
    if tool_name not in TOOL_WHITELIST:
        raise PermissionError(
            f"工具 '{tool_name}' 不在白名单 {sorted(TOOL_WHITELIST)} 中"
        )


def normalize_container_type(name: str | None) -> str:
    ctype = (name or DEFAULT_CONTAINER_TYPE).upper().strip()
    if ctype not in ALLOWED_CONTAINER_TYPES:
        return DEFAULT_CONTAINER_TYPE
    return ctype
