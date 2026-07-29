"""装柜步骤工单：按柜、按层、从前到后给出装载顺序。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def build_load_sequence(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    layout = list(plan.get("layout") or [])
    if not layout:
        return {"steps": [], "containers": 0, "message": "无 layout"}

    name_map: Dict[str, str] = {}
    for b in boxes or []:
        bid = str(b.get("box_id") or "")
        if bid:
            name_map[bid] = str(b.get("box_type") or b.get("name") or bid)

    # 排序：柜号 → z 升序（先底后上）→ x 升序（从前/门侧约定 x=0 为门端时先远后近可配置）
    # 默认：先底层后上层，同层由门端向外（x 小先装贴门？海运常先装远端 x 大）
    # 工单采用：先装远端（大 x）再近门（小 x），便于最后封门
    def sort_key(p: Dict[str, Any]):
        pos = p.get("position") or {}
        return (
            int(p.get("container_no") or 1),
            int(pos.get("z") or 0),
            -int(pos.get("x") or 0),
            int(pos.get("y") or 0),
        )

    ordered = sorted(layout, key=sort_key)
    steps: List[Dict[str, Any]] = []
    for i, p in enumerate(ordered, 1):
        pos = p.get("position") or {}
        size = p.get("size") or {}
        bid = str(p.get("box_id") or "")
        steps.append(
            {
                "step": i,
                "container_no": int(p.get("container_no") or 1),
                "box_id": bid,
                "name": name_map.get(bid, bid),
                "layer": int(p.get("layer") or 1),
                "position_mm": {
                    "x": pos.get("x"),
                    "y": pos.get("y"),
                    "z": pos.get("z"),
                },
                "size_mm": {
                    "dx": size.get("dx"),
                    "dy": size.get("dy"),
                    "dz": size.get("dz"),
                },
                "instruction": (
                    f"柜{p.get('container_no') or 1} 层{p.get('layer') or 1}: "
                    f"放置 {name_map.get(bid, bid)} 于 "
                    f"x={pos.get('x')} y={pos.get('y')} z={pos.get('z')} mm"
                ),
            }
        )

    by_c: Dict[int, int] = {}
    for s in steps:
        by_c[s["container_no"]] = by_c.get(s["container_no"], 0) + 1

    return {
        "steps": steps,
        "containers": len(by_c),
        "steps_per_container": by_c,
        "message": f"共 {len(steps)} 步 / {len(by_c)} 柜（先底后上，先远端后近门）",
    }
