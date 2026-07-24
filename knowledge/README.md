# 知识库（最终版）

## 主文件

| 文件 | 说明 |
|------|------|
| [`packing_knowledge_base.json`](./packing_knowledge_base.json) | **可导入统一知识库**（集装箱 / 箱型 / 结构 / 合箱 / 风险 / 可视化 / 材料） |

## 加载方式

```python
from packing_assistant.knowledge import load_kb, standard_box_types_for_packing, risk_thresholds

kb = load_kb()
print(kb["version"], list(kb["box_types"].keys()))
```

环境变量（可选）：

```bash
set PACKING_KB_PATH=E:\REDACTED-PATH\knowledge\packing_knowledge_base.json
```

## 已接入代码

| 模块 | 使用的知识 |
|------|------------|
| `tools/packing.py` | 标准箱型参数、间隙、合箱超长阈值、安全系数 |
| `tools/structure_calc.py` | 许用应力、底面荷载、挠度限、间隙 |
| `tools/consolidation.py` / `bin3d.py` | 柜型内尺寸与限重 |
| `agents/risk_compliance.py` | 超重/偏载/重货在上/空隙阈值 |
| `agents/visualizer.py` | 箱型颜色 |
| `adapters.classify_material` | 超长/重件分类 |

## 维护

改 JSON 后**无需改代码**（重启进程以刷新 `lru_cache`）。  
新增箱型：在 `box_types` 增加条目并写上 `aliases`。
