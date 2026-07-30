#!/usr/bin/env python3
"""扫描 knowledge_base，补全 frontmatter 关键字段，生成 INDEX.yaml 与 chunks manifest。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "knowledge_base"
TODAY = date.today().isoformat()
HARNESS = ">=0.6.3"

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def parse_fm(raw: str):
    m = FM_RE.match(raw)
    if not m:
        return {}, raw, False
    fm_text, body = m.group(1), m.group(2)
    meta = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return meta, body, True


def ensure_fm(path: Path, raw: str) -> str:
    meta, body, has = parse_fm(raw)
    if not has:
        # wrap
        cat = "domain"
        rel = path.relative_to(KB).as_posix()
        if rel.startswith("01_"):
            cat = "rules"
        elif rel.startswith("02_"):
            cat = "tools"
        elif rel.startswith("03_"):
            cat = "trajectories"
        elif rel.startswith("04_"):
            cat = "strategies"
        elif rel.startswith("05_"):
            cat = "multi_agent"
        elif rel.startswith("06_"):
            cat = "competition"
        meta = {
            "category": cat,
            "priority": "medium",
            "type": cat if cat != "multi_agent" else "protocol",
            "tags": "[]",
            "source": "internal",
        }
        body = raw
    # required keys
    if "updated" not in meta:
        meta["updated"] = f'"{TODAY}"'
    elif not str(meta["updated"]).startswith('"'):
        meta["updated"] = f'"{str(meta["updated"]).strip(chr(34))}"'
    if "harness" not in meta:
        meta["harness"] = f'"{HARNESS}"'
    elif not str(meta["harness"]).startswith('"'):
        meta["harness"] = f'"{str(meta["harness"]).strip(chr(34))}"'
    if "status" not in meta:
        meta["status"] = "active"
    # rebuild
    order = [
        "category",
        "subcategory",
        "priority",
        "type",
        "tags",
        "source",
        "updated",
        "harness",
        "status",
    ]
    lines = ["---"]
    seen = set()
    for k in order:
        if k in meta:
            lines.append(f"{k}: {meta[k]}")
            seen.add(k)
    for k, v in meta.items():
        if k not in seen:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    if not body.startswith("\n") and body:
        pass
    return "\n".join(lines) + body.lstrip("\n") if body else "\n".join(lines) + "\n"


def extract_meta_for_index(path: Path, raw: str) -> dict:
    meta, body, _ = parse_fm(raw)
    title_m = re.search(r"^#\s+(.+)$", body, re.M)
    tags = meta.get("tags", "[]")
    return {
        "path": path.relative_to(KB).as_posix(),
        "title": title_m.group(1).strip() if title_m else path.stem,
        "category": str(meta.get("category", "")).strip("\"'"),
        "priority": str(meta.get("priority", "medium")).strip("\"'"),
        "type": str(meta.get("type", "")).strip("\"'"),
        "tags": tags,
        "status": str(meta.get("status", "active")).strip("\"'"),
    }


def chunks_for(path: Path, raw: str) -> list:
    meta, body, _ = parse_fm(raw)
    rel = path.relative_to(KB).as_posix()
    parts = re.split(r"(?m)^(## .+)$", body)
    out = []
    if len(parts) == 1:
        out.append({"path": rel, "heading": "", "chars": len(body)})
        return out
    # parts[0] preamble, then heading, content, heading, content...
    preamble = parts[0]
    if preamble.strip():
        out.append({"path": rel, "heading": "(preamble)", "chars": len(preamble)})
    i = 1
    while i < len(parts):
        h = parts[i].strip()
        c = parts[i + 1] if i + 1 < len(parts) else ""
        out.append({"path": rel, "heading": h, "chars": len(c)})
        i += 2
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="only verify, no write")
    ap.add_argument("--patch-fm", action="store_true", help="write missing frontmatter fields")
    args = ap.parse_args()

    mds = sorted(p for p in KB.rglob("*.md") if p.is_file())
    docs = []
    all_chunks = []
    missing = []
    for p in mds:
        raw = p.read_text(encoding="utf-8")
        meta, _, has = parse_fm(raw)
        need = []
        for k in ("updated", "harness", "status"):
            if k not in meta:
                need.append(k)
        if need:
            missing.append((p.relative_to(KB).as_posix(), need))
        if args.patch_fm and not args.check:
            new_raw = ensure_fm(p, raw)
            if new_raw != raw:
                p.write_text(new_raw, encoding="utf-8")
                raw = new_raw
        docs.append(extract_meta_for_index(p, raw))
        all_chunks.extend(chunks_for(p, raw))

    index = {
        "version": 2,
        "root": "knowledge_base",
        "generated": TODAY,
        "priority_order": [
            "01_rules",
            "02_tools",
            "05_multi_agent",
            "06_competition",
            "03_trajectories",
            "04_strategies",
            "07_domain_knowledge",
        ],
        "chunking": {
            "rules": "split_on_h2",
            "tools": "one_file_one_chunk_preferred",
            "trajectories": "goal_steps_final",
        },
        "mysql_division": {
            "knowledge_base": "rules, tool docs, trajectories, strategies (retrieval)",
            "knowledge_json": "numeric box type specs",
            "mysql_or_session": "runs, checkpoints, bookings, scores, material rows",
            "output_local": "artifacts, not for git",
        },
        "documents": docs,
    }

    # YAML-ish dump without pyyaml dependency
    def dump_yaml(obj, indent=0):
        sp = "  " * indent
        lines = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{sp}{k}:")
                    lines.append(dump_yaml(v, indent + 1))
                else:
                    if isinstance(v, str) and (":" in v or v.startswith(">") or " " in v):
                        lines.append(f'{sp}{k}: "{v}"')
                    else:
                        lines.append(f"{sp}{k}: {v}")
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    first = True
                    for k, v in item.items():
                        if first:
                            if isinstance(v, (dict, list)):
                                lines.append(f"{sp}- {k}:")
                                lines.append(dump_yaml(v, indent + 2))
                            else:
                                lines.append(f"{sp}- {k}: {v}")
                            first = False
                        else:
                            if isinstance(v, (dict, list)):
                                lines.append(f"{sp}  {k}:")
                                lines.append(dump_yaml(v, indent + 2))
                            else:
                                lines.append(f"{sp}  {k}: {v}")
                else:
                    lines.append(f"{sp}- {item}")
        return "\n".join(lines)

    yaml_text = (
        "# 知识库索引（scripts/gen_kb_index.py 生成）\n"
        + dump_yaml(index)
        + "\n"
    )

    if args.check:
        print(f"docs={len(docs)} missing_fm_fields={len(missing)}")
        for p, need in missing[:15]:
            print(f"  {p}: {need}")
        # compare INDEX if exists
        idx_path = KB / "INDEX.yaml"
        if not idx_path.exists():
            print("FAIL: INDEX.yaml missing")
            return 1
        if missing:
            print("FAIL: frontmatter incomplete")
            return 1
        print("PASS")
        return 0

    (KB / "INDEX.yaml").write_text(yaml_text, encoding="utf-8")
    (KB / ".chunks_manifest.json").write_text(
        json.dumps({"version": 1, "chunks": all_chunks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote INDEX.yaml ({len(docs)} docs) and .chunks_manifest.json ({len(all_chunks)} chunks)")
    if missing and not args.patch_fm:
        print(f"Note: {len(missing)} files still missing fm fields; re-run with --patch-fm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
