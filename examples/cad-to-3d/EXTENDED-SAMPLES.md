# 扩展格式合成样例

这里的图纸均由 `generate_extended_samples.py` 生成，用来验证确定性几何，**不是真实工程图纸，不能替代实际项目验收**。

- `synthetic-curved-building-mm.dxf`：独立 LINE 组成墙体内外轮廓；四个 INSERT 实例引用同一个圆柱块；楼板含 CIRCLE 孔洞。对应参数文件为 `synthetic-curved-building-config.json`。
- `synthetic-bulge-section-mm.dxf`：正 bulge 半圆组成圆管内外轮廓。对应参数文件为 `synthetic-bulge-section-config.json`。

两份图纸均明确使用毫米。参数文件中的 3 m 墙柱高、0.12 m 板厚和 2 m 拉伸长是合成测试输入；默认曲线弦高误差为 0.1 mm。上传后仍应在界面确认图层用途和实体区域。

复现：安装 `requirements-cad.txt` 后运行 `python examples/cad-to-3d/generate_extended_samples.py`。原有直线样例不会被该脚本修改。
