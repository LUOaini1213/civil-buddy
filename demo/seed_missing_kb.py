"""Create shared + private KB stubs for every builtin expert that has no folder yet."""

from __future__ import annotations

from catalog_seed import CATEGORIES, EXPERTS
from kbio import ensure_expert_kb, ensure_kb_root
from config import KB_ROOT

SHARED_BLURB = {
    "design": "审图专业共用：辖区族名、提资接口、禁止编条款。房建走建筑/结构/机电；土木走道路/桥梁/隧道。",
    "bim": "模型命名、坐标、拆分、碰撞等级。不算价。",
    "planning": "计划层级：总控 / 月 / 周。无定额不编资源用量。",
    "procurement": "无报价不编价。甲指与自采分开写。",
    "hr": "普法与流程草稿，不替代法务签字。",
    "admin": "公文与后勤口径。印章审批不省略。",
    "it": "不写进生产密码。权限变更留痕迹。",
    "finance": "不编具体账套分录。税务只给申报节点，不当税务意见书。",
    "lab": "无试验数据不给施工配合比。不合格样品 24 小时内升级。",
    "plant": "特种设备无证件不得进场。限额领料，账物相符。",
}


def main() -> None:
    ensure_kb_root()
    for cat in CATEGORIES:
        ensure_expert_kb(cat["id"], "_placeholder", "placeholder")
        ph = KB_ROOT / cat["id"] / "_placeholder"
        if ph.exists():
            import shutil

            shutil.rmtree(ph)
        shared = KB_ROOT / cat["id"] / "_shared" / "README.md"
        if cat["id"] in SHARED_BLURB and shared.exists() and shared.stat().st_size < 80:
            shared.write_text(
                f"# {cat['name']} 大类共享库\n\n{SHARED_BLURB[cat['id']]}\n",
                encoding="utf-8",
            )
    for exp in EXPERTS:
        ensure_expert_kb(exp.category, exp.id, exp.name)
        readme = KB_ROOT / exp.category / exp.id / "README.md"
        if readme.exists() and "只有本专家默认优先检索" in readme.read_text(encoding="utf-8"):
            readme.write_text(
                f"# {exp.name} 私库\n\n职责：{exp.title}\n默认交付：{exp.delivers}\n风险：{exp.risk}\n\n独立成稿时先读本文件和大类共享库。\n",
                encoding="utf-8",
            )
    print("experts", len(EXPERTS), "categories", len(CATEGORIES))


if __name__ == "__main__":
    main()
