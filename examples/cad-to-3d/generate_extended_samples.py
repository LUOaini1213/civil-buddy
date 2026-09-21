"""Generate explicitly synthetic extended DXFs; never use as real-project evidence."""
from pathlib import Path
import json

import ezdxf


ROOT = Path(__file__).resolve().parent


def lines(space, bounds, layer):
    x0, y0, x1, y1 = bounds
    points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for first, last in zip(points, [*points[1:], points[0]]):
        space.add_line(first, last, dxfattribs={"layer": layer})


def generate():
    building = ezdxf.new("R2010")
    building.units = 4
    for layer in ("WALL", "COLUMN", "SLAB"):
        building.layers.new(layer)
    space = building.modelspace()
    lines(space, (0, 0, 6000, 4000), "WALL")
    lines(space, (200, 200, 5800, 3800), "WALL")
    column = building.blocks.new("SYNTHETIC_ROUND_COLUMN")
    column.add_circle((0, 0), 150)
    for point in ((800, 800), (5200, 800), (5200, 3200), (800, 3200)):
        space.add_blockref(column.name, point, dxfattribs={"layer": "COLUMN"})
    space.add_lwpolyline([(0, 0), (6000, 0), (6000, 4000), (0, 4000)], close=True,
                        dxfattribs={"layer": "SLAB"})
    space.add_circle((3000, 2000), 500, dxfattribs={"layer": "SLAB"})
    building.saveas(ROOT / "synthetic-curved-building-mm.dxf")

    section = ezdxf.new("R2010")
    section.units = 4
    section.layers.new("SECTION")
    for radius in (100, 80):
        section.modelspace().add_lwpolyline([(-radius, 0, 1), (radius, 0, 1)], format="xyb",
                                           close=True, dxfattribs={"layer": "SECTION"})
    section.saveas(ROOT / "synthetic-bulge-section-mm.dxf")
    configs = {
        "synthetic-curved-building-config.json": {
            "mode": "building", "unit": "mm", "curve_tolerance_mm": 0.1, "confirmed_solid": True,
            "layers": {"WALL": "wall", "COLUMN": "column", "SLAB": "slab"},
            "parameters": {"wall": {"height_m": 3, "base_m": 0}, "column": {"height_m": 3, "base_m": 0},
                           "slab": {"height_m": 0.12, "base_m": -0.12}}, "overrides": {}},
        "synthetic-bulge-section-config.json": {
            "mode": "section", "unit": "mm", "curve_tolerance_mm": 0.1, "confirmed_solid": True,
            "layers": {"SECTION": "section"}, "parameters": {"section": {"height_m": 2, "base_m": 0}},
            "overrides": {}},
    }
    for filename, config in configs.items():
        (ROOT / filename).write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    generate()
