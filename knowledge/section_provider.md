# 方案 C：截面提供器

## 策略

```text
get_section(name)
  → steel_table.json 命中 → source=steel_table
  → 未命中且可解析几何（方管BxHxT / 木梁BxH）
       → 优先 sectionproperties
       → 否则 analytic_hollow / analytic_rect
  → 仍失败 → SectionNotFoundError（禁止静默瞎填）
```

严格模式：`SECTION_STRICT=1` 时，无 sectionproperties 库则直接报错（不做解析式兜底）。

## 文件

| 文件 | 说明 |
|------|------|
| `knowledge/steel_table.json` | 型钢表 + 箱型默认截面 |
| `packing_assistant/tools/section_provider.py` | 查询逻辑 |
| `packing_assistant/tools/calc_report.py` | Markdown 计算书 |
| `output/sample_calc_report.md` | 样例输出 |

## 用法

```python
from packing_assistant.tools.section_provider import get_section, get_box_default_sections

print(get_section("槽钢10#")["source"])  # steel_table
print(get_section("方管70x70x4")["source"])  # analytic_hollow 或 sectionproperties

d = get_box_default_sections("6米框")
print(d["frame"]["i_cm"], d["gamma"])
```

可选安装：

```bash
pip install sectionproperties
```
