#!/usr/bin/env python3
"""pack-ship MCP 工具面必须真的连着装箱引擎。

这个测试守的是一件很容易悄悄退回去的事：pack_ship_mcp 原本是投影壳，
只抄调用方带来的 solver 快照，装箱表连 schema 校验都过不去，任何 MCP 宿主
挂上来拿到的都是 solver_connected=false 和一堆 UNSPECIFIED。

所以这里不走函数调用，而是按 `openclaw mcp add` 的方式起一个真实子进程，
用 JSON-RPC over stdio 说话，断言 plan 返回的是真柜数。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SERVER = ROOT / "demo" / "mcp_stdio.py"
SAMPLE = ROOT / "test" / "benchmarks" / "excel" / "case_b_long_frames_40hq.xlsx"


def rpc(calls, args=("--expert", "pack-ship"), timeout=300):
    """在仓库之外的工作目录起服务器，模拟外部宿主挂载。"""
    payload = "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in calls)
    proc = subprocess.run(
        [sys.executable, str(SERVER), *args],
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(ROOT.anchor or ROOT.parent),
        timeout=timeout,
    )
    out = {}
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") is not None:
            out[msg["id"]] = msg
    assert proc.returncode == 0, (proc.returncode, proc.stderr.decode("utf-8", "replace")[-800:])
    return out


def payload_of(message):
    result = message["result"]
    assert not result.get("isError"), result
    return json.loads(result["content"][0]["text"])


def main():
    assert SAMPLE.exists(), f"缺少样例装箱表: {SAMPLE}"
    got = rpc([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                    "clientInfo": {"name": "ci", "version": "0"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "pack-ship__ingest", "arguments": {"file_path": str(SAMPLE)}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "pack-ship__plan",
                    "arguments": {"file_path": str(SAMPLE), "container_type": "40HQ"}}},
    ])

    names = [t["name"] for t in got[2]["result"]["tools"]]
    assert "pack-ship__ingest" in names, names
    assert "pack-ship__plan" in names, names

    ingest = payload_of(got[3])
    assert ingest["ok"] is True, ingest
    assert ingest["n_rows"] >= 1, ingest
    assert ingest["needs_human"] == [], ingest

    plan = payload_of(got[4])
    # 这三条就是「不是投影壳」的定义
    assert plan["solver_connected"] is True, plan
    assert plan["source"] == "solver", plan
    assert isinstance(plan["containers_used"], int) and plan["containers_used"] >= 1, plan
    assert isinstance(plan["can_fit"], bool), plan
    assert plan["utilization"] != "UNSPECIFIED", plan
    # 引擎只装 N 个同型柜，不要在任何地方把它说成「箱型组合」
    assert plan["container_mix_supported"] is False, plan

    # 两处对外动作必须停在人工签认
    vgm = payload_of(rpc([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                    "clientInfo": {"name": "ci", "version": "0"}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "pack-ship__vgm", "arguments": {"file_path": str(SAMPLE)}}},
    ])[5])
    assert vgm["ok"] is True, vgm
    assert vgm["method"] == 2, vgm
    assert vgm["status"] == "needs_shipper_signature", vgm
    assert vgm["auto_submit_forbidden"] is True, vgm
    assert vgm["human_signoff_required"] is True, vgm

    booking = payload_of(rpc([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                    "clientInfo": {"name": "ci", "version": "0"}}},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
         "params": {"name": "pack-ship__booking_draft", "arguments": {"file_path": str(SAMPLE)}}},
    ])[6])
    assert booking["ok"] is True, booking
    assert booking["dry_run"] is True and booking["submitted"] is False, booking
    assert booking["booking_request"]["schema"].startswith("packing.tms.booking_request"), booking

    # 缺重量必须停下来问人，而不是当 0 公斤照装
    from packing_assistant.tools.pack_ship_solve import run_plan
    from packing_assistant.tools.table_mapper import rows_to_ir

    headers = ["Description of Goods", "Q'ty", "Dimensions (L x W x H) cm", "G.W. (kg)"]
    materials = rows_to_ir(
        [
            {"Description of Goods": "Bracket A", "Q'ty": 10,
             "Dimensions (L x W x H) cm": "100 x 40 x 30", "G.W. (kg)": 50.0},
            {"Description of Goods": "Rail B", "Q'ty": 4,
             "Dimensions (L x W x H) cm": "600 x 25 x 25", "G.W. (kg)": None},
        ],
        headers=headers,
    )
    gated = run_plan(materials=materials)
    assert gated["ok"] is False, gated
    assert gated["error"] == "missing_weight", gated
    assert len(gated["needs_human"]) == 1, gated
    assert gated["needs_human"][0]["name"] == "Rail B", gated
    assert "containers_used" not in gated, "缺重量时不允许给出柜数"

    # 自由文本不解析成装箱行：猜出来的行会一路变成看似确定的柜数
    guessed = run_plan(materials="20 crates steel brackets 1.2t each")
    assert guessed["ok"] is False and guessed["error"] == "no_materials", guessed

    # 两个草稿工具也必须被闸门拦住
    from packing_assistant.tools.pack_ship_solve import draft_booking, draft_vgm

    for fn in (draft_vgm, draft_booking):
        blocked = fn(materials=materials)
        assert blocked["ok"] is False and blocked["error"] == "missing_weight", (fn.__name__, blocked)

    print(
        f"PASS pack_ship_solver_mcp tools={len(names)} rows={ingest['n_rows']} "
        f"containers={plan['containers_used']} n0={plan['n0']} "
        f"util={plan['utilization']} vgm={vgm['status']} "
        f"booking=dry_run gate=needs_human"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
