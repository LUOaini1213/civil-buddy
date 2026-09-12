#!/usr/bin/env python3
"""Repeatable local-tool serial/parallel comparison; no network or model charges."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from packing_assistant.runtime.tender_workflow import load_workflow, run_tender_workflow
from packing_assistant.runtime.worker_context import canonical
from packing_assistant.sandbox import guarded_write_text

TENDER = "★投标人须提供营业执照复印件。\n施工组织方案评分20分，须编制施工专项方案。\n工期60日历天。"
SOURCES = [{"source_id": "tender-1", "title": "测试招标资料", "role": "tender", "text": TENDER},
           {"source_id": "response-1", "title": "测试响应资料", "role": "response", "text": "已附营业执照复印件。施工方案待补。"}]


def benchmark(*, repeats=3, delay_s=0.2, output_root=None):
    """Measure real exports with a deterministic, cancellable analysis latency probe.

    Quality records source coverage, unresolved items, and forbidden claims; it
    does not score actual LLM professional accuracy or claim production speedup.
    """
    if not 1 <= repeats <= 10 or not 0 <= delay_s <= 2:
        raise ValueError("repeats must be 1..10; delay_s must be 0..2")
    root = Path(output_root or ROOT / "output" / ("tender-benchmark-" + uuid4().hex[:10])).resolve()
    if not root.is_relative_to((ROOT / "output").resolve()):
        raise ValueError("Benchmark output must stay under workspace/output")

    def runner(messages, *, max_tokens, cancel_event):
        cancel_event.wait(delay_s)
        if cancel_event.is_set():
            raise InterruptedError("benchmark cancelled")
        evidence = json.loads(messages[-1]["content"])["data"]["evidence"]
        return canonical({"conclusions": [{"text": "应核对投标附件与所列招标要求", "evidence_refs": [evidence[0]["source_id"]]}],
                          "unresolved": ["签章与资质材料待人工核验"]})

    warmup = run_tender_workflow(TENDER, session_id="benchmark-warmup", output_root=root, sources=SOURCES)
    if not warmup["ok"]:
        raise AssertionError(warmup)
    results = {"serial": [], "parallel": []}
    for iteration in range(repeats):
        for name in ("serial", "parallel") if iteration % 2 == 0 else ("parallel", "serial"):
            began = time.monotonic()
            result = run_tender_workflow(TENDER, session_id=f"benchmark-{name}-{iteration}", output_root=root,
                                         sources=SOURCES, parallel=name == "parallel", model_runner=runner)
            if not result["ok"] or result["metrics"]["model_calls"] != 2 or not result["submit_blocked"]:
                raise AssertionError(result)
            recovered = load_workflow(root, result["session_id"], result["run_id"])
            if recovered["active"] or recovered["state"] != "done":
                raise AssertionError("workflow did not release active ownership")
            results[name].append({"elapsed_ms": round((time.monotonic() - began) * 1000),
                                  "run_id": result["run_id"], "directory": result["directory"],
                                  "metrics": result["metrics"], "artifacts": result["artifacts"]})
    all_runs = results["serial"] + results["parallel"]
    quality = all_runs[0]["metrics"]["quality"]
    if any(item["metrics"]["quality"] != quality for item in all_runs):
        raise AssertionError("serial/parallel evidence quality changed")
    medians = {name: statistics.median(item["elapsed_ms"] for item in items) for name, items in results.items()}
    report = {"schema": "civil.tender.benchmark.v1", "network_calls": 0,
              "analysis_mode": "injected deterministic latency probe", "model_delay_s": delay_s,
              "repeats": repeats, "quality_equal": True, "quality": quality,
              "median_ms": medians, "observed_speedup": round(medians["serial"] / max(medians["parallel"], 1), 3),
              "note": "真实本地解析与Office导出，模型为延迟探针；耗时只代表本机本样例，不代表在线模型质量或生产性能。",
              "runs": results}
    path = guarded_write_text(root / "benchmark.json", json.dumps(report, ensure_ascii=False, indent=2))
    return path, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--delay-s", type=float, default=0.2)
    parser.add_argument("--output-root")
    args = parser.parse_args()
    path, report = benchmark(repeats=args.repeats, delay_s=args.delay_s, output_root=args.output_root)
    print(json.dumps({"report": str(path), "median_ms": report["median_ms"], "observed_speedup": report["observed_speedup"],
                      "quality_equal": report["quality_equal"], "network_calls": 0}, ensure_ascii=False))
