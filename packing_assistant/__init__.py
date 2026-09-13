"""智能装箱与拼柜 — 大 Team ⊃ 小 Team A 成箱 + 小 Team B 拼柜；NL 通用 Agent。"""

from packing_assistant.config import HARNESS_VERSION
from packing_assistant.state import PackingState

# harness → graph.py → langgraph 是整个包里唯一的硬性顶层 langgraph 依赖。
# 以前在这里直接 import，导致「只想用表格解析器」或「只想起 MCP 工具面」的
# 进程也必须装上整套图执行栈，装不上就整个包 import 失败。改为按需加载：
# 名字仍然从 packing_assistant 取得到，但只有真的用到时才拉 harness。
_LAZY = (
    "apply_user_confirmation",
    "public_response",
    "run_agent_pipeline",
    "run_pipeline",
    "run_team_a",
    "run_team_b",
)


def __getattr__(name):
    if name in _LAZY:
        from packing_assistant import harness

        return getattr(harness, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(_LAZY))


__all__ = [
    "HARNESS_VERSION",
    "PackingState",
    "run_team_a",
    "run_team_b",
    "run_pipeline",
    "run_agent_pipeline",
    "apply_user_confirmation",
    "public_response",
]
