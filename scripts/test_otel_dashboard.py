#!/usr/bin/env python3
"""Run a shipped node with OTEL file export, then hit the 大盘 API twice."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["PACKING_OTEL"] = "1"
os.environ["PACKING_OTEL_FILE"] = "1"


def main() -> int:
    from packing_assistant.otel_hooks import dashboard_payload, force_flush, list_spans
    from packing_assistant.tools.tender_parse import run_tender_pipeline

    pipe = run_tender_pipeline(
        "一、投标人须具备建筑工程施工资质。\n二、未实质性响应作废标处理。\n交货期 90 个日历天。",
        source="otel-dash-test",
        p0_confirmed=False,
    )
    run_id = pipe.get("run_id")
    assert run_id, pipe.keys()
    force_flush()

    file_spans = list_spans()
    hit = [
        s
        for s in file_spans
        if s.get("run_id") == run_id and (s.get("node") or s.get("tool") or s.get("name"))
    ]
    assert hit, {"run_id": run_id, "n": len(file_spans), "tail": file_spans[-3:]}
    identity = (hit[-1].get("name"), hit[-1].get("run_id"), hit[-1].get("duration_ms"))

    from fastapi.testclient import TestClient

    from gateway.app import app

    client = TestClient(app)
    r1 = client.get("/api/otel/dashboard")
    r2 = client.get("/api/otel/dashboard")
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    j1, j2 = r1.json(), r2.json()
    assert j1.get("fixture") is False and j2.get("fixture") is False
    assert j1.get("spans") and j2.get("spans")
    s1 = [s for s in j1["spans"] if s.get("run_id") == run_id]
    s2 = [s for s in j2["spans"] if s.get("run_id") == run_id]
    assert s1 and s2, {"j1": j1.get("n"), "j2": j2.get("n"), "run_id": run_id}
    assert s1[-1].get("name") == identity[0]
    assert s1[-1].get("run_id") == identity[1]
    assert s1[-1].get("duration_ms") is not None
    assert s2[-1].get("name") == s1[-1].get("name")
    assert s2[-1].get("run_id") == s1[-1].get("run_id")
    print(
        json.dumps(
            {
                "run_id": run_id,
                "name": s1[-1].get("name"),
                "node": s1[-1].get("node"),
                "tool": s1[-1].get("tool"),
                "duration_ms": s1[-1].get("duration_ms"),
                "n1": j1.get("n"),
                "n2": j2.get("n"),
            },
            ensure_ascii=False,
        )
    )
    print("PASS otel_dashboard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
