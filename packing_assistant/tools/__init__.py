"""纯 Python 计算工具：装箱（含结构计算）、拼柜、规则风险、出图、体积估柜。"""

from packing_assistant.tools.packing import run_packing
from packing_assistant.tools.consolidation import run_consolidation
from packing_assistant.tools.risk_rules import check_risks
from packing_assistant.tools.visualize import draw_layout
from packing_assistant.tools.structure_calc import run_structure_calc, attach_calc_report_md
from packing_assistant.tools.section_provider import get_section, get_box_default_sections
from packing_assistant.tools.volume_estimate import (
    estimate_containers,
    pack_effective_m3,
    piece_solid_m3,
)

__all__ = [
    "run_packing",
    "run_consolidation",
    "check_risks",
    "draw_layout",
    "run_structure_calc",
    "attach_calc_report_md",
    "get_section",
    "get_box_default_sections",
    "estimate_containers",
    "pack_effective_m3",
    "piece_solid_m3",
]
