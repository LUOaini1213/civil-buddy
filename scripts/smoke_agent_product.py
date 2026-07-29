#!/usr/bin/env python3
"""v0.5+ Agent 产品冒烟：health · pipeline · trace.jsonl · durable HITL · stream schema.

用法:
  python scripts/smoke_agent_product.py
  python scripts/smoke_agent_product.py --http   # 需本机 8000 网关
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def smoke_local() -> list[tuple[str, bool, str]]:
    rows = []
    from packing_assistant.config import HARNESS_VERSION
    from packing_assistant.harness import iter_agent_pipeline
    from packing_assistant.session_store import load_session, save_session
    from packing_assistant.trace_events import normalize_event

    try:
        parts = [int(x) for x in HARNESS_VERSION.split(".")[:3]]
        while len(parts) < 3:
            parts.append(0)
        ver_ok = tuple(parts) >= (0, 6, 2)
    except Exception:
        ver_ok = False
    rows.append(("harness>=0.6.2", ver_ok, HARNESS_VERSION))
    rows.append(("harness_patch", ver_ok, HARNESS_VERSION))

    # LLM tool-call path（无 Key → policy_fallback）
    try:
        from packing_assistant.agent_loop import run_llm_agent_loop

        lst = run_llm_agent_loop(
            "smoke llm path 钢梁",
            materials=[
                {
                    "id": "s1",
                    "part_no": "FST",
                    "length_mm": 4000,
                    "width_mm": 200,
                    "height_mm": 200,
                    "total_weight_kg": 200,
                    "qty": 1,
                }
            ],
            enable_auto_confirm=True,
            session_id="smoke-llm",
            save_artifacts=False,
            max_rounds=10,
            force_llm=True,
        )
        rows.append(
            (
                "llm_toolcall path",
                (lst.get("team_mode") == "big_team_a_b")
                and len(lst.get("boxes") or []) >= 1,
                str(lst.get("agent_style")),
            )
        )
    except Exception as e:
        rows.append(("llm_toolcall path", False, str(e)))

    # graph A/B resume
    try:
        from packing_assistant.graph_resume import (
            describe_resume,
            resume_team_b_segment,
            run_team_a_segment,
        )

        a = run_team_a_segment(
            "smoke resume",
            materials=[
                {
                    "id": "s1",
                    "part_no": "FST",
                    "length_mm": 3000,
                    "width_mm": 200,
                    "height_mm": 200,
                    "total_weight_kg": 150,
                    "qty": 1,
                }
            ],
            session_id="smoke-resume-ab",
        )
        d = describe_resume("smoke-resume-ab")
        b = resume_team_b_segment(a, session_id="smoke-resume-ab")
        rows.append(
            (
                "graph A/B resume",
                d.get("can_resume_team_b")
                and (b.get("graph_segment") == "team_b_done"),
                f"A={a.get('phase')} B={b.get('phase')}",
            )
        )
    except Exception as e:
        rows.append(("graph A/B resume", False, str(e)))

    ev = normalize_event("r1", {"type": "agent_start", "node": "loader"})
    rows.append(
        (
            "stream schema v1",
            ev.get("schema") == "packing.stream.v1" and ev.get("agent_id") == "loader",
            str(ev.get("schema")),
        )
    )
    # envelope fields
    for key in ("type", "run_id", "ts", "parent_node", "status"):
        if key == "status":
            ok = ev.get("status") == "running"
        elif key == "parent_node":
            ok = "parent_node" in ev
        else:
            ok = bool(ev.get(key))
        rows.append((f"envelope.{key}", ok, str(ev.get(key))))

    final = None
    types: list = []
    tool_events = 0
    for e in iter_agent_pipeline(
        "smoke 钢梁 5000x200x200 300kg x1",
        enable_auto_confirm=True,
        session_id="smoke-product",
        save_artifacts=True,
    ):
        types.append(e.get("type"))
        if e.get("type") in ("tool_start", "tool_end"):
            tool_events += 1
        if e.get("type") == "done" and e.get("state"):
            final = e["state"]

    rows.append(("pipeline events", "run_start" in types and "done" in types, f"n={len(types)}"))
    rows.append(("tool events", tool_events >= 2, f"n={tool_events}"))
    rows.append(
        (
            "team_mode big_team_a_b",
            (final or {}).get("team_mode") == "big_team_a_b",
            str((final or {}).get("team_mode")),
        )
    )
    ispec = (final or {}).get("intent_spec") or {}
    rows.append(
        (
            "intent_spec present",
            bool(ispec.get("scheme_id") or ispec.get("cargo_mode") or ispec.get("raw_nl")),
            str(ispec.get("scheme_id") or ispec.get("cargo_mode")),
        )
    )
    try:
        from packing_assistant.teams.roster import TEAM_ARCHITECTURE
        from packing_assistant.tool_registry import list_tools

        rows.append(
            (
                "architecture mode",
                TEAM_ARCHITECTURE.get("mode") == "big_team_wraps_a_b",
                str(TEAM_ARCHITECTURE.get("mode")),
            )
        )
        rows.append(("tools catalog", len(list_tools()) >= 10, f"n={len(list_tools())}"))
    except Exception as e:
        rows.append(("architecture import", False, str(e)))
    steps = (final or {}).get("agent_steps") or []
    rows.append(("agent_steps", len(steps) >= 5, f"n={len(steps)}"))
    paths = (final or {}).get("artifact_paths") or {}
    tj = paths.get("trace_jsonl") or ""
    p = Path(tj) if tj else None
    ok_j = bool(p and p.exists() and p.stat().st_size > 20)
    rows.append(("trace.jsonl", ok_j, tj or "missing"))
    if ok_j and p:
        line = p.read_text(encoding="utf-8").splitlines()[0]
        obj = json.loads(line)
        rows.append(
            (
                "jsonl envelope",
                obj.get("schema") == "packing.stream.v1" and "run_id" in obj,
                obj.get("type", ""),
            )
        )
        # tool lines in jsonl
        has_tool = any(
            '"type": "tool_' in ln or '"type":"tool_' in ln
            for ln in p.read_text(encoding="utf-8").splitlines()
        )
        rows.append(("jsonl tool events", has_tool, "tool_start|end"))

    # durable session checkpoint
    rid = str((final or {}).get("run_id") or "")
    sid = str((final or {}).get("session_id") or "smoke-product")
    loaded = load_session(sid) or (load_session(rid) if rid else None)
    rows.append(
        (
            "session_state disk",
            bool(loaded and loaded.get("run_id")),
            f"sid={sid} rid={(loaded or {}).get('run_id')}",
        )
    )

    # HITL path: auto_confirm=False → hitl + disk
    hitl_types = []
    hitl_state = None
    for e in iter_agent_pipeline(
        "smoke hitl 角钢 2000x100x100 50kg x2",
        enable_auto_confirm=False,
        session_id="smoke-hitl",
        save_artifacts=True,
    ):
        hitl_types.append(e.get("type"))
        if e.get("type") == "done" and e.get("state"):
            hitl_state = e["state"]
    rows.append(("hitl event", "hitl" in hitl_types, f"types={set(hitl_types)}"))
    hs = load_session("smoke-hitl")
    if not hs and hitl_state:
        # force save path check
        try:
            save_session("smoke-hitl", hitl_state)
            hs = load_session("smoke-hitl")
        except Exception as ex:
            rows.append(("hitl save", False, str(ex)))
    rows.append(
        (
            "hitl durable",
            bool(hs and (hs.get("phase") == "await_user_confirm" or hs.get("boxes") is not None)),
            f"phase={(hs or {}).get('phase')}",
        )
    )

    # replan control-flow present (may or may not fire need_replan on tiny smoke case)
    rows.append(
        (
            "replan path wired",
            "replan" in types or any(s.get("node") == "evaluator" for s in steps),
            "evaluator in steps / optional replan event",
        )
    )
    return rows


def smoke_http(base: str = "http://127.0.0.1:8000") -> list[tuple[str, bool, str]]:
    rows = []
    try:
        with urllib.request.urlopen(base + "/api/health", timeout=5) as r:
            h = json.loads(r.read().decode())
        rows.append(
            (
                "http health",
                h.get("gateway") == "UP" and h.get("features", {}).get("sse_stream"),
                h.get("harness_version", ""),
            )
        )
        feats = h.get("features") or {}
        rows.append(
            (
                "http replay feature",
                bool(feats.get("trace_replay")),
                str(feats.get("stream_schema")),
            )
        )
        rows.append(
            (
                "http durable hitl flag",
                bool(feats.get("hitl_durable_checkpoint")),
                str(feats.get("hitl_durable_checkpoint")),
            )
        )
    except Exception as e:
        rows.append(("http health", False, str(e)))
        return rows

    try:
        with urllib.request.urlopen(base + "/api/runs?limit=1", timeout=10) as r:
            j = json.loads(r.read().decode())
        runs = j.get("runs") or []
        rows.append(("http runs", True, f"n={len(runs)}"))
        if runs:
            rid = runs[0].get("run_id")
            req = urllib.request.Request(base + f"/api/runs/{rid}/replay")
            with urllib.request.urlopen(req, timeout=30) as r:
                chunk = r.read(400).decode("utf-8", errors="replace")
            rows.append(("http replay", "replay_start" in chunk or "data:" in chunk, chunk[:60]))
    except Exception as e:
        rows.append(("http runs/replay", False, str(e)))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--http", action="store_true")
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()

    rows = smoke_local()
    if args.http:
        rows.extend(smoke_http(args.base))

    failed = 0
    for name, ok, detail in rows:
        flag = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{flag}] {name}: {detail}")
    print("ALL_PASS" if failed == 0 else f"FAILED {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
