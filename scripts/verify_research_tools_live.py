"""Opt-in real loopback integration evidence; never part of offline tests."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="store_true", help="Make four actual sequential local Ollama requests")
    parser.add_argument("--cases", help="Comma-separated case names to run")
    args = parser.parse_args()
    cases = [
        ("jpj_catalog", "/api/run", {"tool": "jpj.catalog", "arguments": {}}),
        ("jpj_brand_compare", "/api/run", {"tool": "jpj.query", "arguments": {"query_id": "brand_compare", "parameters": {
            "start_month": "2026-01", "end_month": "2026-08", "makers": ["BYD", "TESLA"], "metric": "registrations"}}}),
        ("missing_dates", "/api/run", {"tool": "jpj.query", "arguments": {"query_id": "brand_compare", "parameters": {"makers": ["BYD", "TESLA"]}}}),
        ("wrong_metric", "/api/run", {"tool": "jpj.query", "arguments": {"query_id": "monthly_registrations", "parameters": {
            "start_month": "2026-01", "end_month": "2026-08", "metric": "sales"}}}),
        ("literature_catalog", "/api/run", {"tool": "literature.catalog", "arguments": {}}),
        ("literature_search", "/api/run", {"tool": "literature.search", "arguments": {"query": "thermal model", "limit": 3}}),
    ]
    if args.model:
        cases = [(name, "/api/model", {"prompt": prompt}) for name, prompt in [
            ("model_brand_compare", "对比2026年1月至8月BYD和TESLA的汽车登记量，给出数据来源"),
            ("model_missing_dates", "对比BYD和TESLA登记量"),
            ("model_wrong_metric", "2026年1-8月BYD销量"),
            ("model_literature", "查电池热模型的资料，给出处"),
        ]]
    if args.cases:
        selected = set(args.cases.split(","))
        cases = [case for case in cases if case[0] in selected]
    out = ROOT / "output" / ("research-model-evidence.json" if args.model else "research-live-evidence.json")
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "endpoint": "http://127.0.0.1:8779", "cases": []}
    if out.exists():
        report["cases"] = json.loads(out.read_text(encoding="utf-8")).get("cases", [])
    out.parent.mkdir(parents=True, exist_ok=True)
    for name, route, payload in cases:
        print("RUN " + name, flush=True)
        req = Request("http://127.0.0.1:8779" + route, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=600) as response:
            value = json.load(response)
        report["cases"].append({"case": name, "request": payload, "response": value})
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"case": name, "status": value.get("status"), "run_id": value.get("run_id"),
              "tools": [e.get("tool") for e in value.get("events", []) if e.get("type") == "tool_start"]}, ensure_ascii=False), flush=True)
    print("Evidence: " + str(out), flush=True)


if __name__ == "__main__":
    main()
