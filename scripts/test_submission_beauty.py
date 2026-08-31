#!/usr/bin/env python3
"""海之子杯提交包门禁（v0.4.0 提交定稿版）。

历史：旧版驱动 build_submission_docs.py 重建 docx/PDF，但那个生成器硬编码了
另一台机器的官方模板路径（C:\\Users\\wenjie.luo\\Downloads\\*.docx），在本机必然
FileNotFoundError——门禁等于恒红。2026-08-31 提交定稿改为：

  - 视频：仍然**真重建**（build_demo_video.py + narration.json 全在仓内，
    cv2 渲染，无外部依赖），并卡官方限制（≤120s / ≤500MB）
  - 两份 PDF：**验收不重建**（它们由 output/submission/01|03 的 HTML 经
    Edge headless 打印，CI 环境没有 Edge；HTML 源已入仓可追溯）
  - 表单 txt：文件名对照

产物命名（Civil Buddy 品牌，2026-08-31 起）：
  00-提交表单填写.txt · 01-说明文档-CivilBuddy.pdf ·
  02-介绍视频-CivilBuddy.mp4 · 03-人机协同履历表-CivilBuddy.pdf

用法：python scripts/test_submission_beauty.py [--verify-only]
  --verify-only 跳过视频重建（快速核对四件是否在位）
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "submission"

PDF_DOC = OUT / "01-说明文档-CivilBuddy.pdf"
PDF_RESUME = OUT / "03-人机协同履历表-CivilBuddy.pdf"
MP4 = OUT / "02-介绍视频-CivilBuddy.mp4"
FORM = OUT / "00-提交表单填写.txt"


def _mp4_duration(path: Path) -> float:
    """读 mvhd 时长，不依赖 ffprobe。"""
    import struct

    d = path.read_bytes()
    i = d.find(b"mvhd")
    if i < 0:
        return -1.0
    ver = d[i + 4]
    if ver == 0:
        ts, dur = struct.unpack(">II", d[i + 16 : i + 24])
    else:
        ts = struct.unpack(">I", d[i + 24 : i + 28])[0]
        dur = struct.unpack(">Q", d[i + 28 : i + 36])[0]
    return dur / ts if ts else -1.0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    verify_only = "--verify-only" in sys.argv
    fails: list[str] = []

    if not verify_only:
        print("== rebuild video ==")
        r = subprocess.run(
            [sys.executable, str(OUT / "build_demo_video.py")],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=600,
        )
        if r.returncode != 0:
            print(r.stderr[-800:])
            fails.append("build_demo_video.py 重建失败")

    # 四件在位 + 基本体检
    for p, floor in ((PDF_DOC, 50_000), (PDF_RESUME, 50_000), (FORM, 200)):
        if not p.is_file() or p.stat().st_size < floor:
            fails.append(f"缺失或过小：{p.name}")
    for p in (PDF_DOC, PDF_RESUME):
        if p.is_file() and p.read_bytes()[:4] != b"%PDF":
            fails.append(f"不是 PDF：{p.name}")
        if p.is_file() and p.stat().st_size > 30 * 1024 * 1024:
            fails.append(f"超官方 30MB 限：{p.name}")

    # 注意：build_demo_video.py 的直接输出是脚本内部旧路径名，
    # 终版 02-介绍视频-CivilBuddy.mp4 由口播合流步骤产出——这里验收终版。
    if not MP4.is_file():
        fails.append(f"缺失：{MP4.name}")
    else:
        dur = _mp4_duration(MP4)
        mb = MP4.stat().st_size / 1e6
        print(f"video duration_s={dur:.1f} size_mb={mb:.2f}")
        if not (0 < dur <= 120.0):
            fails.append(f"视频时长超官方 2 分钟限：{dur:.1f}s")
        if mb > 500:
            fails.append(f"视频超官方 500MB 限：{mb:.1f}MB")

    # 口径红线：产物源里不许出现被禁数字/旧口径
    vsrc = (OUT / "build_demo_video.py").read_text(encoding="utf-8")
    nar = (OUT / "narration.json").read_text(encoding="utf-8")
    for banned in ("9.15", "9.75"):
        for name, text in (("build_demo_video.py", vsrc), ("narration.json", nar)):
            if banned in text:
                fails.append(f"禁句数字 {banned} 出现在 {name}")
    if "8.85" not in vsrc and "八点八五" not in nar:
        fails.append("对外唯一口径 8.85 在视频素材里消失了")

    # 表单：引用的三件必须在位（按 00/01/02/03 编号对照）
    if FORM.is_file():
        form_t = FORM.read_text(encoding="utf-8")
        for tag in ("01-说明文档", "02-介绍视频", "03-人机协同履历表"):
            if tag not in form_t:
                fails.append(f"表单未提及 {tag}")

    if fails:
        print("FAIL submission_beauty", fails)
        return 1
    print("ALL_PASS submission_beauty")
    for p in (PDF_DOC, PDF_RESUME, MP4, FORM):
        print(f"  {p.name}  {p.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
