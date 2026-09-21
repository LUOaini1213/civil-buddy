# CAD → 3D synthetic examples

**All drawings in this folder are synthetic software fixtures.** They are not
real project drawings, approved designs or evidence of acceptance on customer CAD.
Regenerate with `python examples/cad-to-3d/generate_samples.py` (requires ezdxf).

| File | Confirmed meaning for this synthetic fixture | Parameters |
| --- | --- | --- |
| `synthetic-building-mm.dxf` | A 6000 × 4000 mm outer wall ring, 200 mm wall thickness; four 400 × 400 mm columns; slab with a 1000 × 1000 mm through-hole | Walls/columns 3 m high at base 0; slab 0.12 m thick at base −0.12 m |
| `synthetic-hollow-section-mm.dxf` | A 100 × 100 mm section with an 80 × 80 mm inner void | 2 m extrusion length at base 0 |
| `synthetic-invalid-outlines.dxf` | Open, crossing, bulged, circular, LINE, elevated and block entities | Each must be explicitly reported as invalid/unsupported |

The two `*-config.json` files record fixture-only confirmation and explicit
parameters. In the interactive workbench the user must independently confirm
units, mappings, parameters and that boundaries represent solid material.
Never reuse these parameters as defaults for an actual job drawing.

The building fixture has six objects: one hollow wall, four columns and one
perforated slab. Section volume is 0.0072 m³. Different layers remain independent;
their intersections are not boolean-unioned. Windows/doors are not recognized.

The geometry engine accepts only closed, straight, zero-width LWPOLYLINE or 2D
POLYLINE contours on the world XY plane at Z=0. Nested boundaries on the same
layer preserve holes by even/odd depth. Touching/crossing rings, or an unsupported
entity on a selected layer, block that entire layer to avoid filling missing holes.
Separate annotations and unsupported geometry into ignored layers first.

Model coordinates are metres, Z-up, relative to the minimum XY of the selected
supported layers (ignored layers do not move the origin). Source origin/scale are
recorded. GLB uses metres and the proper rotation
`(x, y, z) → (x, z, −y)` to Y-up; original source handles and parameters are stored
as mesh metadata. JSON parameter exports preserve the original transform.

Preview and GLB use float32 vertex storage. Before showing or exporting a mesh,
the engine simulates that storage and rejects a layer if rounding collapses a
triangle, changes volume by more than 0.001%, or changes an axis coordinate/size
by more than the larger of 0.1 micrometres and 0.001% of that object's axis size.
Model tiny components that are extremely far apart in separate selections; the
first version reports a precision failure instead of silently flattening them.

**Remaining acceptance:** upload an actual DXF from the intended workflow,
confirm units and solid boundary roles, compare a known dimension and hole,
modify one object and reopen the exported GLB in an independent viewer.
