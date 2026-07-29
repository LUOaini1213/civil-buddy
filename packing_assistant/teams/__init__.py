"""组织架构：大 Team 包小 Team A（成箱）+ 小 Team B（拼柜）。

通用 Agent = NL 输入 + 多工具；大 Team 负责编排/闸门/有界 critic/收口。
"""

from packing_assistant.teams.roster import AGENT_ROSTER, TEAM_ARCHITECTURE
from packing_assistant.teams.big_team import iter_big_team_run, run_big_team

__all__ = [
    "AGENT_ROSTER",
    "TEAM_ARCHITECTURE",
    "iter_big_team_run",
    "run_big_team",
]
