#!/usr/bin/env python3
"""ux(round16) Vue 绑定守卫：模板里引用的标识符必须在 data/computed/methods 里有定义。

由来（真实事故，2026-08-31 提交日）：R14 往 frontend/workbench.html 加了左侧会话栏的
markup，却没落 JS 半边——cbNewTask / cbOpenSession / cbSessions / cbRelTime 四个绑定
全部未定义。Vue 2 把 `@click="cbNewTask"` 编译成 `on:{click: cbNewTask}`，在**渲染期**
就求值（不是点击时），于是整页白屏。当时四道门禁——符号纪律 / 零外链 / JS 语法 /
CI 标记断言——全绿，因为它们都只做静态扫描，不执行页面。

本守卫只查最容易漏且判定无歧义的两类裸标识符引用：
  - `@click="ident"` / `@change="ident"` 等事件绑定为**裸函数名**（无括号、无点号）
  - `v-for="x in ident"` 的数据源为裸标识符

定义面 = 同文件 script 内的 `ident:` / `ident(` / `async ident(` 行首声明。
表达式型绑定（带括号/点号/运算符）不在范围内，避免误报。

用法：python scripts/test_vue_bindings.py   （退出码 0=干净，1=有未定义引用）
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ["frontend/workbench.html", "frontend/index.html"]

# 事件绑定：@click="foo" / v-on:click="foo"，仅裸标识符
EVENT_RE = re.compile(r'(?:@|v-on:)[a-zA-Z][\w.:-]*\s*=\s*"([A-Za-z_$][\w$]*)"')
# 列表渲染：v-for="s in foo" / v-for="(s, i) in foo"，仅裸标识符数据源
VFOR_RE = re.compile(r'v-for\s*=\s*"[^"]*?\bin\s+([A-Za-z_$][\w$]*)\s*"')
# 定义面：缩进后的 `name:` 或 `name(` 或 `async name(`
DEF_RE = re.compile(r'^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*[:(]', re.M)

# Vue 内置 / 全局：不需要在组件里定义
BUILTIN = {
    "true", "false", "null", "undefined", "console", "window", "document",
    "$event", "$refs", "$nextTick", "Math", "JSON", "Date", "Number", "String",
}


def check(rel: str) -> list[str]:
    p = ROOT / rel
    if not p.is_file():
        return []
    text = p.read_text(encoding="utf-8")
    defined = set(DEF_RE.findall(text)) | BUILTIN

    bad: list[str] = []
    for regex, kind in ((EVENT_RE, "事件绑定"), (VFOR_RE, "v-for 数据源")):
        for m in regex.finditer(text):
            name = m.group(1)
            if name in defined:
                continue
            line = text.count("\n", 0, m.start()) + 1
            bad.append(f"{rel}:{line} {kind} `{name}` 未定义 —— 渲染期 ReferenceError 会整页白屏")
    return bad


def main() -> int:
    bad: list[str] = []
    for rel in TARGETS:
        bad.extend(check(rel))
    if bad:
        print(f"FAIL Vue 绑定 {len(bad)} 处未定义：")
        for b in bad:
            print("  " + b)
        print("修法：补上 data/computed/methods 里的定义，或删掉这段 markup——不要留半拉子。")
        return 1
    print("PASS Vue 绑定：模板事件绑定与 v-for 数据源均有定义")
    return 0


if __name__ == "__main__":
    sys.exit(main())
