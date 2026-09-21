"""Generate explicitly SYNTHETIC fixtures, never represented as customer drawings."""
from __future__ import annotations

import json
from pathlib import Path

import ezdxf

HERE = Path(__file__).resolve().parent


def drawing():
    doc = ezdxf.new("R2010")
    doc.units = 4  # mm: also require explicit confirmation in the workbench
    return doc


def ring(doc, layer, xmin, ymin, xmax, ymax):
    if layer not in doc.layers:
        doc.layers.new(layer)
    return doc.modelspace().add_lwpolyline(
        [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)],
        close=True, dxfattribs={"layer": layer})


def main():
    doc = drawing()
    ring(doc, "WALL", 0, 0, 6000, 4000)
    ring(doc, "WALL", 200, 200, 5800, 3800)
    for x, y in [(600, 600), (5000, 600), (600, 3000), (5000, 3000)]:
        ring(doc, "COLUMN", x, y, x + 400, y + 400)
    ring(doc, "SLAB", 0, 0, 6000, 4000)
    ring(doc, "SLAB", 2500, 1500, 3500, 2500)
    doc.saveas(HERE / "synthetic-building-mm.dxf")
    (HERE / "synthetic-building-config.json").write_text(json.dumps({
        "mode": "building", "unit": "mm", "confirmed_solid": True,
        "layers": {"WALL": "wall", "COLUMN": "column", "SLAB": "slab"},
        "parameters": {"wall": {"height_m": 3, "base_m": 0},
                       "column": {"height_m": 3, "base_m": 0},
                       "slab": {"height_m": 0.12, "base_m": -0.12}}, "overrides": {}
    }, indent=2) + "\n", encoding="utf-8")
    doc = drawing()
    ring(doc, "SECTION", 0, 0, 100, 100)
    ring(doc, "SECTION", 10, 10, 90, 90)
    doc.saveas(HERE / "synthetic-hollow-section-mm.dxf")
    (HERE / "synthetic-section-config.json").write_text(json.dumps({
        "mode": "section", "unit": "mm", "confirmed_solid": True,
        "layers": {"SECTION": "section"},
        "parameters": {"section": {"height_m": 2, "base_m": 0}}, "overrides": {}
    }, indent=2) + "\n", encoding="utf-8")
    doc = drawing()
    space = doc.modelspace()
    for name in ["OPEN", "SELF_CROSSING", "BULGE", "CIRCLE", "LINE", "ELEVATED", "BLOCK"]:
        doc.layers.new(name)
    space.add_lwpolyline([(0, 0), (100, 0), (100, 100)], dxfattribs={"layer": "OPEN"})
    space.add_lwpolyline([(200, 0), (300, 100), (200, 100), (300, 0)],
                         close=True, dxfattribs={"layer": "SELF_CROSSING"})
    space.add_lwpolyline([(400, 0, 0.5), (500, 0, 0), (500, 100, 0), (400, 100, 0)],
                         format="xyb", close=True, dxfattribs={"layer": "BULGE"})
    space.add_circle((650, 50), 50, dxfattribs={"layer": "CIRCLE"})
    space.add_line((750, 0), (750, 100), dxfattribs={"layer": "LINE"})
    entity = ring(doc, "ELEVATED", 800, 0, 900, 100)
    entity.dxf.elevation = 50
    block = doc.blocks.new("SYNTHETIC_BLOCK")
    block.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True)
    space.add_blockref("SYNTHETIC_BLOCK", (1000, 0), dxfattribs={"layer": "BLOCK"})
    doc.saveas(HERE / "synthetic-invalid-outlines.dxf")


if __name__ == "__main__":
    main()
