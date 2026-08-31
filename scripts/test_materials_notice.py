#!/usr/bin/env python3
"""ux(round22) 门禁：网关看见表格路径却没读成时，**必须在响应里说出来**。

钉住的是一个真实的坏行为（改造前实测）：
    给绝对路径 C:\\...\\我的表.xlsx  → 15 箱 / 利用率 0.675
    什么都不给，只说「帮我装箱」    → 15 箱 / 利用率 0.675   ← 完全一样
即路径被 `_load_materials_from_text` 的仓库沙箱丢弃后**静默回落到演示预设物料**，
不报错、照样返回一串很像样的柜数。演示时说「这是我的表」而屏幕上其实是样例数据。

沙箱本身是对的（user_input 里可能混着 LLM 生成或从文档粘来的内容，不能随便读盘），
所以不放宽它 —— 只要求「看见了但没用上」这件事必须写进 `materials_notice`。

纯单元级：直接调 gateway 的 `_apply_preset`，不起服务、不依赖网络。

用法：python scripts/test_materials_notice.py   （退出码 0=守住，1=破了）
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    from gateway.app import _apply_preset

    fails: list[str] = []

    # 1) 给了读不到的绝对路径 → 必须有 notice，且必须点明数字不是这张表的
    _m, _o, _k, _t, notice = _apply_preset(
        preset="high_util",
        user_input=r"pack C:\Users\nobody\Desktop\根本不存在的表.xlsx",
    )
    if not notice:
        fails.append("给了读不到的绝对路径却没有 notice —— 静默回落又回来了")
    elif "不是这张表算出来的" not in notice:
        fails.append(f"notice 没点明数字来源：{notice[:80]}")

    # 2) 仓库内可读的相对路径 → 不该有 notice
    rel = "test/sim_materials/small_one_container/materials.xlsx"
    if (ROOT / rel).is_file():
        _m, _o, _k, _t, notice2 = _apply_preset(preset="high_util", user_input=f"pack {rel}")
        if notice2:
            fails.append(f"可读路径不该报 notice：{notice2[:80]}")
    else:
        print(f"[skip] 夹具缺失：{rel}")

    # 3) 完全不提路径 → 不该有 notice（老行为零变化）
    _m, _o, _k, _t, notice3 = _apply_preset(preset="high_util", user_input="帮我装箱")
    if notice3:
        fails.append(f"没提路径却报 notice：{notice3[:80]}")

    # 4) 显式传了 materials → 路径无关，不该报 notice
    _m, _o, _k, _t, notice4 = _apply_preset(
        preset="high_util",
        user_input=r"pack C:\Users\nobody\不存在.xlsx",
        materials=[{"id": "X1", "name": "件", "quantity": 1,
                    "length_mm": 1000, "width_mm": 100, "height_mm": 100, "weight_kg": 10}],
    )
    if notice4:
        fails.append(f"显式给了 materials 不该报 notice：{notice4[:80]}")

    if fails:
        print(f"FAIL 物料来源诚实性 {len(fails)} 处：")
        for f in fails:
            print("  " + f)
        return 1
    print("PASS 物料来源诚实性：路径读不到时如实说明，可读/未提/显式 materials 三种情况不误报")
    return 0


if __name__ == "__main__":
    sys.exit(main())
