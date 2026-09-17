import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.post_drafts.design_basic import build_draft

text = """| 孔号 | 层号 | 岩土名称 |
|---|---|---|
| ZK1 | L1 | clay |"""

r = build_draft("geotech", "geotech__brief", text)

assert r
assert "ZK1" in r
assert "L1" in r
assert "UNSPECIFIED" in r
assert "可以开工" not in r

print("PASS geotech acceptance")
print("tool = geotech__brief")
print("hole_ref =", "ZK1" in r)
print("layer =", "L1" in r)
print("UNSPECIFIED =", "UNSPECIFIED" in r)
