#!/usr/bin/env python3
"""civil.toml lite parser: '#' is data only inside one well-formed quoted value; every other line reads as before."""

from __future__ import annotations

import os
import random
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BS = "\\"

FIXED = [
    ('[workspace]\njob_root = "C:/projects/civil#2026"', {"job_root": "C:/projects/civil#2026"}),
    ("job_root = 'C:/projects/civil#2026'", {"job_root": "C:/projects/civil#2026"}),
    ('job_root = "C:/p/civil#2026"  # 备注 "x#y"', {"job_root": "C:/p/civil#2026"}),
    ('job_root="C:/a#b"#c', {"job_root": "C:/a#b"}),
    ('job_root = "C:/a#b"\t# tab comment', {"job_root": "C:/a#b"}),
    ('job_root\t=\t"C:/a#b"', {"job_root": "C:/a#b"}),
    ('[model]\nname = "qwen#3"', {"model.name": "qwen#3"}),
    ('model = "a=b#c"', {"model": "a=b#c"}),
    ('job_root = "C:' + BS + "Users" + BS + 'x#1"', {"job_root": "C:" + BS + "Users" + BS + "x#1"}),
    ("model = \"'quoted'\"", {"model": "'quoted'"}),
    ('sandbox = "read-only#x"', {"sandbox": "read-only#x"}),  # accepted change: no longer truncated into a valid mode
]

# Same result as before the fix. The malformed and out-of-dialect ones are pinned, not claimed correct.
UNCHANGED = [
    ('sandbox = "workspace-write"   # read-only | workspace-write', {"sandbox": "workspace-write"}),
    ("sandbox = read-only # ro\nmax_steps = 12 # n", {"sandbox": "read-only", "max_steps": "12"}),
    ('# job_root = "C:/x#1"\n[workspace]  # ws = "x#y"\njob_root = "C:/a"', {"job_root": "C:/a"}),
    ("job_root = C:/Users/O'Brien/x # c", {"job_root": "C:/Users/O'Brien/x"}),
    ('job_root = "C:' + BS + "jobs" + BS + '"  # c', {"job_root": "C:" + BS + "jobs" + BS}),
    ('model = "a' + BS + '"#b"', {"model": "a" + BS}),
    ('[ civil ]\r\nsandbox = "read-only"\r\n', {"sandbox": "read-only"}),
    ("model = \"it's\"  # don't", {"model": "it's"}),
    ('job_root = ""  # none', {"job_root": ""}),
    ('sandbox = "read-only  # 没收口', {"sandbox": "read-only"}),
    ('sandbox = "read-only   # 也可写 "ro"', {"sandbox": "read-only"}),
    ("sandbox = 'read-only   # don't use workspace-write", {"sandbox": "read-only"}),
    ('approval = "untrusted  # "never" 是全自动', {"approval": "untrusted"}),
    ('max_parallel = "2 # "并发"', {"max_parallel": "2"}),
    ('job_root = "C:/a#b', {"job_root": "C:/a"}),
    ('model = "a" "b#c"', {"model": 'a" "b'}),
    ('model = """x#y"""', {"model": "x"}),
    ('[x = "a#b"]', {"[x": "a"}),
    ('[x] y = "1"  # see [docs]\nsandbox = "read-only"', {"[x] y": "1", "sandbox": "read-only"}),
    ("job_root = \u201cC:/工地#2026\u201d", {"job_root": "\u201cC:/工地"}),
]


def _reference(text: str) -> dict:
    """The parser as shipped before the fix, plus one branch: a well-formed quoted line yields its inner text."""
    out: dict = {}
    section = ""
    for raw in text.splitlines():
        head, eq, tail = raw.partition("=")
        value = tail.lstrip()
        end = value.find(value[0], 1) if value[:1] in ('"', "'") else -1
        rest = value[end + 1:].strip()
        if eq and "#" not in head and end > 0 and (not rest or rest.startswith("#")):
            key, val = head.strip(), value[1:end]
        else:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip()
                continue
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            key, val = k.strip(), v.strip().strip('"').strip("'")
        if section and section not in {"civil", "workspace", ""}:
            key = f"{section}.{key}"
        out[key] = val
    return out


def main() -> int:
    from packing_assistant.runtime import civil_config as cc

    def cfg_of(text: str):
        cfg = cc.CivilConfig()
        cc._apply_map(cfg, cc._parse_toml_lite(text))
        return cfg

    for text, want in FIXED + UNCHANGED:
        got = cc._parse_toml_lite(text)
        assert got == want, (text, got, want)
        assert _reference(text) == want, (text, _reference(text), want)

    assert cfg_of('sandbox = "read-only   # 也可写 "ro"').sandbox == "read-only"
    assert cfg_of("sandbox = 'read-only   # don't use workspace-write").sandbox == "read-only"
    assert cfg_of('approval = "untrusted  # "never" 是全自动').approval == "untrusted"
    assert cfg_of('max_parallel = "2 # "并发"').max_parallel == 2
    assert cfg_of('[x] y = "1"  # see [docs]\nsandbox = "read-only"').sandbox == "read-only"
    assert cfg_of('job_root = ""  # none').job_root == ""

    example = (ROOT / "civil.toml.example").read_text(encoding="utf-8")
    assert cc._parse_toml_lite(example) == {"sandbox": "workspace-write", "approval": "on-request", "max_steps": "8", "max_parallel": "4"}
    assert cc._parse_toml_lite(example.replace("# job_root", "job_root"))["job_root"] == "C:/Users/LW/Documents/某工地"

    rng = random.Random(7)
    alpha = ['"', "'", "#", "=", " ", "[", "]", BS, "a", "read-only", "2", "\t", "\u3000", "x]", "工地"]
    heads = ["sandbox", "job_root", "[x] y", "[a", ""]
    docs = 20000
    for _ in range(docs):
        lines = []
        for _ in range(rng.randint(1, 3)):
            junk = "".join(rng.choice(alpha) for _ in range(rng.randint(0, 8)))
            lines.append(rng.choice([
                "[civil]",
                "[model]",
                junk,
                rng.choice(heads) + " = " + junk,
                rng.choice(heads) + '="' + rng.choice(["ro", "a#b", "x]", "'q'"]) + '"' + rng.choice(["", "  # see [docs]", " " + junk]),
            ]))
        text = "\n".join(lines)
        assert cc._parse_toml_lite(text) == _reference(text), (text, cc._parse_toml_lite(text), _reference(text))

    saved = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith("CIVIL_")}
    try:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            job = tmp / "工地#2026"
            job.mkdir()
            (tmp / "工地").mkdir()
            conf = tmp / "civil.toml"
            body = f'sandbox = "read-only"  # 只读\nmax_parallel = 2\n[workspace]\njob_root = "{job.as_posix()}"  # 本工地\n'
            conf.write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))
            with patch.object(cc, "config_paths", return_value=[conf]):
                cfg = cc.load_config()
            assert cfg.job_root == job.as_posix(), cfg
            assert Path(cfg.job_root).is_dir(), cfg
            assert cfg.sandbox == "read-only", cfg
            assert cfg.max_parallel == 2, cfg
    finally:
        os.environ.update(saved)

    print("PASS test_civil_config", f"fixed={len(FIXED)}", f"unchanged={len(UNCHANGED)}", f"differential_docs={docs}", "bom_e2e=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
