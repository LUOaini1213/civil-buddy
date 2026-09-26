#!/usr/bin/env python3
"""Façade demo: one curtain-wall subcontractor's three jobs, run on the SYNTHETIC files in examples/facade-demo.

  1 tender     解析招标 facade_itt_doc.md, then 技术标 and 废标检查 read the same session's hand-off
  2 packing    按 facade_panels_zh.xlsx 装柜 (and the English list): container plan + the conservation line
  3 site docs  项目日报 from daily_report_input.txt; 安全交底 from wah_briefing_input.txt, a high-risk post
               that writes nothing until a licensed person types the sign-off sentence. This script never
               types it: pass --sign "<the sentence>" yourself, the way `civil exec --confirm` is yours to pass.

Every turn goes through civil.run_task (what `civil exec` calls) in steps mode: offline, no model key.
It runs inside a job folder this script creates (default: a new temp folder, kept so the drafts can be
opened) and writes nothing outside it. Exit 1 when a flow errors, 2 on bad arguments.

  python scripts/demo_facade.py [--job NEW_DIR] [--sign SENTENCE]
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.dont_write_bytecode = True          # not even __pycache__ outside the job folder
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "facade-demo"
INPUTS = ("facade_itt_doc.md", "facade_panels.xlsx", "facade_panels_zh.xlsx", "daily_report_input.txt", "wah_briefing_input.txt")
PROJECT = "合成示例办公楼幕墙分包"
SESSION = "civil-cli"
TENDER_ROWS = ("招标编号", "注册资格/工作类别", "投标截止", "工期", "投标有效期", "履约担保", "缺陷责任期/质保期", "备选投标方案")
# Section 4 of the ITT, and two appendix rows, by a token only that clause carries.
FACADE_CLAUSES = (("PMU mock-up", "PMU"), ("VMU mock-up", "VMU"), ("heat soak", "14179"), ("site water test", "hose"),
                  ("PE-endorsed calcs/shop drawings", "Professional Engineer"), ("warranty", "water tightness"),
                  ("A-frame delivery", "A-frame"), ("insurance", "All Risks"))
APPENDIX_ROWS = (("liquidated damages", "per day of delay"), ("retention", "progress payment"))
PANELS = ("facade_panels_zh.xlsx", "facade_panels.xlsx")
DAILY_ROWS = ("日期", "天气", "部位", "形象进度", "出勤", "机械材料", "安全质量记事", "明日计划")


def tables(md: str) -> List[Dict[str, str]]:
    """Every row of every Markdown table, as {column: cell}."""
    rows: List[Dict[str, str]] = []
    header: Optional[List[str]] = None
    for raw in md.splitlines():
        line = raw.strip()
        if not (line.startswith("|") and line.endswith("|")):
            header = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            continue
        if header is None:
            header = cells
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def first_cells(md: str) -> Dict[str, List[str]]:
    """First cell -> the second cell of each row that starts with it."""
    found: Dict[str, List[str]] = {}
    for row in tables(md):
        values = list(row.values())
        if len(values) > 1:
            found.setdefault(values[0], []).append(values[1])
    return found


def section(md: str, title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}[^\n]*\n(.*?)(?=^## |\Z)", md, re.S | re.M)
    return match.group(1).strip() if match else ""


def draft(out: Dict[str, Any]) -> str:
    path = next((Path(f["path"]) for f in out.get("files") or [] if str(f.get("path", "")).endswith(".md")), None)
    return path.read_text(encoding="utf-8") if path and path.is_file() else ""


class Demo:
    def __init__(self, job: Path, sign: str = "") -> None:
        self.job, self.sign = job, sign
        self.errors: List[str] = []
        self.result: Dict[str, Any] = {"job": str(job)}

    def say(self, line: str = "") -> None:
        print(line, flush=True)

    def rel(self, path: Any) -> str:
        try:
            return Path(str(path)).resolve().relative_to(self.job).as_posix()
        except (OSError, ValueError):
            return str(path)

    def turn(self, flow: str, text: str, skill: str, *, session: str = SESSION, confirm: bool = False,
             command: str = "") -> Dict[str, Any]:
        from packing_assistant.civil import run_task

        self.say(f"  $ civil exec {command or repr(text)}")
        out = run_task(text, session_id=session, confirm=confirm)
        if out.get("skill") != skill:
            self.errors.append(f"{flow}: routed to {out.get('skill')!r}, expected {skill!r}")
        self.say("  reply: " + str(out.get("reply") or "").splitlines()[0][:160] if out.get("reply") else "  reply: (none)")
        files = [self.rel(f.get("path")) for f in out.get("files") or [] if isinstance(f, dict) and f.get("path")]
        if files:
            self.say("  wrote: " + ", ".join(files))
        return out

    def expect_written(self, flow: str, out: Dict[str, Any]) -> str:
        md = draft(out)
        if not (out.get("ok") and out.get("wrote") and md):
            self.errors.append(f"{flow}: no draft written (ok={out.get('ok')}, error={out.get('error_code')})")
        return md

    # 1 ---------------------------------------------------------------------------------------------
    def tender(self) -> None:
        self.say("\n== 1 Tender review: parse the ITT, then the bid posts read its hand-off")
        out = self.turn("tender", "解析招标 facade_itt_doc.md", "bid-parse")
        md = self.expect_written("tender", out)
        cells = first_cells(md)
        rows = {name: cells.get(name, ["(no row)"])[0] for name in TENDER_ROWS}
        for name, value in rows.items():
            self.say(f"    {name}: {value}")
        scoring = [v[0] for k, v in cells.items() if k.startswith("评分点：")]
        rejections = [v[0] for k, v in cells.items() if k.startswith("否决条款")]
        blanks = sum(cell.count("未在原文检出") for values in cells.values() for cell in values)
        shown = [name for name, token in FACADE_CLAUSES if token in md]
        self.say(f"    scoring points: {len(scoring)} ({'; '.join(scoring)})")
        self.say(f"    rejection clauses listed one by one: {len(rejections)}")
        self.say(f"    rows left 未在原文检出 for a person to check against the ITT: {blanks}")
        self.say(f"    façade specification clauses (ITT section 4) shown in tender.parse.md: {len(shown)} of {len(FACADE_CLAUSES)}"
                 + (f"; not yet: {', '.join(n for n, _ in FACADE_CLAUSES if n not in shown)}" if len(shown) < len(FACADE_CLAUSES) else ""))
        self.say("    appendix rows shown: " + ", ".join(f"{n} {'yes' if t in md else 'no'}" for n, t in APPENDIX_ROWS))
        self.result["tender"] = {"ok": out.get("ok"), "skill": out.get("skill"), "rows": rows, "scoring": scoring,
                                 "rejections": rejections, "facade_clauses_shown": shown, "submit_blocked": out.get("submit_blocked")}
        tech = self.turn("bid-tech", "出一份技术标提纲", "bid-tech")
        tech_md = self.expect_written("bid-tech", tech)
        self.say(f"    chapters from scoring points: {len(re.findall(r'^### ', tech_md, re.M))} · "
                 f"cells left [A001] for the bid team: {tech_md.count('[A001]')}")
        comp = self.turn("bid-compliance", "出一份废标检查表", "bid-compliance")
        comp_md = self.expect_written("bid-compliance", comp)
        states = [row.get("三态", "") for row in tables(comp_md)]
        self.say(f"    requirements with no response yet (未响应): {states.count('未响应')} · rejection clauses to tick by hand: "
                 f"{len(tables(section(comp_md, '10 否决与拒收条款自查清单')))}")
        self.result["bid_tech"] = {"ok": tech.get("ok"), "skill": tech.get("skill"), "written": bool(tech_md)}
        self.result["bid_compliance"] = {"ok": comp.get("ok"), "skill": comp.get("skill"), "written": bool(comp_md),
                                         "unanswered": states.count("未响应")}
        self.say("  sign-off: bid posts are low risk, so no sentence is asked; submit_blocked stays true and every"
                 " P0 (qualification / rejection) row waits for a person.")

    # 2 ---------------------------------------------------------------------------------------------
    def packing(self) -> None:
        self.say("\n== 2 Packing and shipping: 24 unitised panels into 40HQ containers")
        plans = {}
        for name, session in zip(PANELS, (SESSION, SESSION + "-en")):
            out = self.turn("packing", f"按 {name} 装柜，柜型 40HQ", "pack-ship", session=session)
            plan = (out.get("pack_ship") or {}).get("plan") or {}
            cons = plan.get("conservation") or {}
            if not (out.get("ok") and plan.get("source") == "solver" and plan.get("can_fit") is True):
                self.errors.append(f"packing {name}: no usable plan (ok={out.get('ok')}, error={out.get('error_code')})")
            if cons.get("ok") is not True:
                self.errors.append(f"packing {name}: conservation check did not pass: {cons}")
            structure = plan.get("structure") or {}
            self.say(f"    plan: {plan.get('containers_used')} × {plan.get('container_type')} · N0 {plan.get('n0')}"
                     f" · can_fit {plan.get('can_fit')} · binding {plan.get('binding_constraint')} · crates {plan.get('n_boxes')} for {cons.get('pieces_in')} panels"
                     f" · space {plan.get('utilization')} · weight {plan.get('weight_utilization')}")
            self.say(f"    conservation (list -> crates): pieces {cons.get('pieces_in')} -> {cons.get('pieces_out')} · "
                     f"kg {cons.get('kg_in')} -> {cons.get('kg_out')} · {'ok' if cons.get('ok') else 'FAILED'}")
            self.say(f"    crate structure: pass {structure.get('pass')} · reinforce {structure.get('needs_reinforcement')} · fail "
                     f"{structure.get('fail')} · 待详设 {structure.get('pending_design')} (the engine does not invent a pass)")
            plans[name] = plan
        control = self.without_notes(self.job / "inputs" / "facade_panels.xlsx")
        out = self.turn("packing", f"按 {control.name} 装柜，柜型 40HQ", "pack-ship", session=SESSION + "-control")
        plans[control.name] = (out.get("pack_ship") or {}).get("plan") or {}
        keys = ("containers_used", "n0", "n_boxes", "utilization", "weight_utilization", "binding_constraint")
        changed = [name for name in PANELS if any(plans[name].get(k) != plans[control.name].get(k) for k in keys)]
        self.say("    handling notes (glass / upright / no stack), against the same list with the notes removed: "
                 + (f"they change the plan for {', '.join(changed)}" if changed else "no effect on the plan, in either language"))
        library = (ROOT / "knowledge" / "packing_knowledge_base.json").read_text(encoding="utf-8").lower()
        if "stillage" not in library and "a-frame" not in library:
            self.say("    not modelled: A-frame stillages (the ITT asks for them). That needs the contractor's"
                     " stillage size, tare and capacity.")
        zh = plans["facade_panels_zh.xlsx"]
        self.result["packing"] = {"plan": {k: zh.get(k) for k in (*keys, "container_type", "can_fit")},
                                  "conservation": zh.get("conservation"), "notes_change_plan": changed}
        self.say("  sign-off: pack-plan.md is an internal draft (不可直接订舱); a person confirms the plan in the workbench"
                 " HITL step, and lashing / VGM are signed separately.")

    @staticmethod
    def without_notes(source: Path) -> Path:
        """The control list: the same rows with the note column emptied, next to the source in the job folder."""
        import openpyxl

        target = source.with_name("panels_no_notes.xlsx")
        wb = openpyxl.load_workbook(source)
        ws = wb["materials"]
        column = [c.value for c in ws[1]].index("note") + 1
        for row in range(2, ws.max_row + 1):
            ws.cell(row=row, column=column).value = None
        wb.save(target)
        return target

    # 3 ---------------------------------------------------------------------------------------------
    def daily(self) -> None:
        self.say("\n== 3 Site documents: daily report, then the work-at-height briefing")
        daily_text = (self.job / "inputs" / "daily_report_input.txt").read_text(encoding="utf-8").strip()
        out = self.turn("daily", daily_text, "pm-daily", command="- < inputs/daily_report_input.txt")
        md = self.expect_written("daily", out)
        cells = first_cells(md)
        for name in DAILY_ROWS:
            self.say(f"    {name}: {cells.get(name, ['(no row)'])[0][:90]}")
        blanks = [who for who in ("填报人", "审核人") if f"{who}空栏" in md]
        if blanks:
            self.say(f"  sign-off: {' / '.join(blanks)} left blank for a person; low-risk post, no sentence asked.")
        self.result["daily"] = {"ok": out.get("ok"), "skill": out.get("skill"), "written": bool(md),
                                "rows": {k: cells.get(k, [""])[0] for k in DAILY_ROWS}}

    def briefing(self) -> None:
        from packing_assistant.civil import CONFIRM

        brief_text = (self.job / "inputs" / "wah_briefing_input.txt").read_text(encoding="utf-8").strip()
        out = self.turn("briefing", brief_text, "safety-brief", command="- < inputs/wah_briefing_input.txt")
        refused = bool(out.get("hitl_pending")) and not out.get("wrote") and not out.get("files")
        if not refused:
            self.errors.append("briefing: the high-risk post wrote without the sign-off sentence")
        self.say(f"  SIGN-OFF NEEDED HERE: 安全交底 is a high-risk post. It wrote nothing: a licensed person must type"
                 f" 「{CONFIRM}」 (civil desktop / TUI dialog, or `civil exec --confirm` run by that person).")
        brief = {"refused_without_sentence": refused, "written": False}
        if not self.sign:
            self.say("  This demo does not supply the sentence. To see the draft, the person reruns with --sign and types it.")
        else:
            out = self.turn("briefing", brief_text, "safety-brief", confirm=True, command="--confirm - < inputs/wah_briefing_input.txt")
            md = self.expect_written("briefing (signed)", out)
            sign_row = next((row for row in tables(section(md, "11 签字栏"))), {})
            self.say("    cover: " + section(md, "1 封面")[:90])
            self.say("    signature row: " + " · ".join(f"{k} {v}" for k, v in sign_row.items()) + " (names are never pre-filled)")
            brief.update(written=bool(md), file=next((self.rel(f["path"]) for f in out.get("files") or []
                                                      if str(f.get("path", "")).endswith(".md")), ""))
        self.result["briefing"] = brief

    def run(self) -> Dict[str, Any]:
        for flow in (self.tender, self.packing, self.daily, self.briefing):
            try:
                flow()
            except Exception as exc:  # a flow that raises is reported, and the next one still runs
                self.errors.append(f"{flow.__name__}: {type(exc).__name__}: {exc}")
                self.say(f"  ERROR {flow.__name__}: {type(exc).__name__}: {exc}")
        self.result["errors"] = list(self.errors)
        return self.result


def make_job(job: Optional[Path]) -> Path:
    """A new job folder holding the fixtures under inputs/ and a CIVIL.md with the two stated facts."""
    from packing_assistant.runtime.project_instructions import TEMPLATE

    if job is None:
        job = Path(tempfile.mkdtemp(prefix="civil-facade-demo-"))
    elif job.exists():
        raise FileExistsError(f"{job} already exists; the demo only writes into a folder it creates")
    job = job.resolve()
    (job / "inputs").mkdir(parents=True)
    for name in INPUTS:
        shutil.copyfile(FIXTURES / name, job / "inputs" / name)
    civil_md = re.sub(r"^- 辖区：.*$", "- 辖区：SG", TEMPLATE.replace("- 项目：\n", f"- 项目：{PROJECT}\n", 1), count=1, flags=re.M)
    (job / "CIVIL.md").write_text(civil_md, encoding="utf-8")
    return job


def run_demo(job: Optional[Path] = None, sign: str = "") -> Dict[str, Any]:
    """Create the job folder, enter it and run the three flows.

    Leaves the process inside the job folder, with tempfile.tempdir pointing into it."""
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    os.environ["CIVIL_AGENT_MODE"] = "steps"
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from packing_assistant.civil import enter_workspace

    job = make_job(job)
    scratch = job / ".civil-buddy" / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(scratch)                             # a library's temp files (openpyxl) stay in the job folder
    os.environ["MPLCONFIGDIR"] = str(scratch / "matplotlib")    # and so does matplotlib's config folder
    enter_workspace(str(job))
    print(f"SYNTHETIC façade demo · job folder {job}\n"
          "All inputs are invented fixtures (examples/facade-demo); no contractor's data.", flush=True)
    return Demo(job, sign).run()


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--job", default="", help="a folder that does not exist yet, created as the job folder; default: a new temp folder")
    parser.add_argument("--sign", default="", help="the licensed person types the sign-off sentence here; never filled in for you")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    from packing_assistant.civil import CONFIRM

    if args.sign and args.sign.strip() != CONFIRM:
        print(f"--sign must be the sentence exactly: {CONFIRM}", file=sys.stderr)
        return 2
    try:
        result = run_demo(Path(args.job).expanduser().absolute() if args.job else None, sign=args.sign.strip())
    except (FileExistsError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print()
    if result["errors"]:
        print("FAIL demo_facade: " + " | ".join(result["errors"]))
        return 1
    print(f"PASS demo_facade · drafts under {result['job']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
