"""打包海之子杯「补充资料」zip（官方：可选，≤200MB，创意材料 + 其他补充材料）。

原则：只放**能自证**的东西——能跑的包、真跑出来的图、带日期核验的文档。
不放二手转述、不放未验证的截图。
"""
import shutil
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(r"C:\Users\LW\civil-buddy")
SHOTS = Path(r"C:\Users\LW\AppData\Local\Temp\claude\C--Users-LW-packing-agent\2906bf0f-3c95-442b-b787-8a0af842d1b9\scratchpad\shots")
STAGE = ROOT / "output/submission/_extra_stage"
OUT = ROOT / "output/submission/04-补充资料-CivilBuddy.zip"

if STAGE.exists():
    shutil.rmtree(STAGE)

GUIDE = """# 补充资料 · 导读

Civil Buddy（土木版 Codex：66 岗智能体工作台）· 第一届「海之子」杯 AI 智能体挑战计划
队长：罗文杰 · 仓库：https://github.com/LUOaini1213/civil-buddy

本压缩包分四部分。**赶时间只看两样**：`01` 里的免安装试用包（双击就能跑），
和 `02` 里的五张截图（介绍视频的关键帧）。

---

## 01-免安装试用包
- `civil-buddy-workbench-0.4.0.zip` —— Windows 免安装，解压后双击 `start-workbench.bat`，
  浏览器自动打开工作台。**不用装 Python，不用配环境。**
- `.sha256` —— 校验码
- `给试用的人.md` —— 三分钟上手，含试用包边界（不含装箱引擎，输入「装箱」出说明卡）

> 需要自备 API Key：启动后点右上角「设置 → 模型设置」填自己的（DeepSeek / z.ai 等），
> 运行时生效、不落盘、不用重启。

## 02-产品截图与引擎出图
介绍视频的五个关键帧 + 一张装箱引擎的真实出图。
- `01` 工作台首屏（左栏工程项目树，中间只有一个聊天框）
- `02` 聊天框输入「装箱」→ 装柜台直接嵌在对话里打开
- `03` **停在确认闸**：非标预检 11 项，人不点头不放行
- `04` 拼柜可视化：三视角 + 重心 COG
- `05` 总览裁决：箱数 15 · 订柜有效体积 82% · 重量利用 94%（引擎算的，不是模型编的）
- `06` 引擎出图：40HQ 拼柜布局图，箱号与柜长坐标一一对应

## 03-证据与口径
- `66岗诚实分级.md` —— L1 知识库 66/66、L2 工具写盘 36/66、L3 引擎岗 1，每级挂可复跑验收。
  **我们不宣称 66 岗全部深度落地。**
- `评委5分钟演示脚本.md` —— 含冻结数字表与禁句表（对外只报 8.85，不报其他版本）
- `体验记分卡.md` —— 本地校准综合 8.85 / 10 的原始产出
- `装箱引擎架构.md` —— 大 Team ⊃ Team A + Team B，13 个固定专岗

## 04-创意材料
- `创意材料-工友侧.md` —— **官方指定的「创意材料」在这里。**
  主题是「为工友谋幸福」，所以这份写的是：如果把工作台翻过来对着工友那一面，
  能长成什么样（班前交底、隐患识别、工资咨询、技能传承），
  以及**我们明确不做什么**。每条都标了「已有什么 / 还差什么」，不把设想写成已交付。
- `UX设计规范-23轮迭代.md` —— 23 轮迭代的完整设计记录（约 10 万字）。
  附录 R 记的是最能说明「AI 纠偏」的一段：AI 写的功能静默失效、被门禁逮住、
  连人带 CI 一起修，包括 AI 自己报错的结论被人工复核纠正的实例。
- `用户路径图.html` —— 浏览器打开看流程图

---

**所有产出定位为内部讨论 AI 草稿，不是签认件。** 涉及结构安全与危大工程的内容，
必须由持证人员依据正式规范复核签字后方可实施。
"""

FILES = [
    # (源, 包内路径)
    ("dist/civil-buddy-workbench-0.4.0.zip", "01-免安装试用包/civil-buddy-workbench-0.4.0.zip"),
    ("dist/civil-buddy-workbench-0.4.0.zip.sha256", "01-免安装试用包/civil-buddy-workbench-0.4.0.zip.sha256"),
    ("给试用的人.md", "01-免安装试用包/给试用的人.md"),
    ("output/side_20260831_164936.png", "02-产品截图与引擎出图/06-引擎出图-40HQ拼柜布局.png"),
    ("docs/depth-ladder.md", "03-证据与口径/66岗诚实分级.md"),
    ("docs/competition-demo-script.md", "03-证据与口径/评委5分钟演示脚本.md"),
    ("output/competition/SCORECARD.md", "03-证据与口径/体验记分卡.md"),
    ("docs/harness-design.md", "03-证据与口径/装箱引擎架构.md"),
    ("docs/submission/创意材料-工友侧.md", "04-创意材料/创意材料-工友侧.md"),
    ("docs/ux/ux-design-spec.md", "04-创意材料/UX设计规范-23轮迭代.md"),
    ("docs/civil-buddy/user-flow.html", "04-创意材料/用户路径图.html"),
]

STAGE.mkdir(parents=True)
(STAGE / "00-先看这个.md").write_text(GUIDE, encoding="utf-8")

missing = []
for src, dst in FILES:
    s = ROOT / src
    if not s.is_file():
        missing.append(src)
        continue
    d = STAGE / dst
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(s, d)

# 截图（从演示视频抽的关键帧）
shots_dst = STAGE / "02-产品截图与引擎出图"
shots_dst.mkdir(parents=True, exist_ok=True)
n_shots = 0
for p in sorted(SHOTS.glob("*.png")):
    shutil.copy2(p, shots_dst / p.name)
    n_shots += 1

if missing:
    print("!! 缺文件:", missing)
    raise SystemExit(1)

if OUT.exists():
    OUT.unlink()
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p in sorted(STAGE.rglob("*")):
        if p.is_file():
            z.write(p, p.relative_to(STAGE).as_posix())

mb = OUT.stat().st_size / 1e6
with zipfile.ZipFile(OUT) as z:
    names = z.namelist()
print(f"OK {OUT.name}  {mb:.1f} MB  {len(names)} 个文件（截图 {n_shots} 张）")
assert mb <= 200, mb
for n in names:
    print("   ", n)
shutil.rmtree(STAGE)
