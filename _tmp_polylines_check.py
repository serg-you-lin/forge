import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from shapely import wkt as swkt
import forge

ex = Path("tests/examples")
g = json.loads((ex / "golden_multipli" / "golden" / "Polylines__000.json").read_text(encoding="utf-8"))
parent = ex / "golden_multipli" / "Polylines.dxf"
cfg = ex / "golden_multipli" / "config" / "Polylines.json"
c = json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() else {}
tol = c.get("tolerance", 0.5)

with tempfile.TemporaryDirectory() as td:
    with redirect_stdout(io.StringIO()):
        _, msp = forge.load_dxf(str(parent), explode_inserts=True)
        r = forge.heal(msp, tolerance=tol)
        forge.detect(r)
        forge.write(msp, r)
        forge.split(
            msp,
            r,
            output_folder=td,
            namer=lambda i, part: f"{part.label}_P{i + 1:03d}",
        )

    p = r.parts[g["part_index"]]
    all_in = sorted(p.holes + p.inners, key=lambda x: x.area, reverse=True)
    eo = swkt.loads(g["outer_wkt"])

    ai = sum(x.polygon.area for x in all_in)
    ei = sum(swkt.loads(w).area for w in g["inners_wkt"])

    print("actual_area", round(p.area, 4), "expected_area", g["area_mm2"], "delta", round(round(p.area, 4) - g["area_mm2"], 4))
    print("outer_area_actual", round(p.outer.polygon.area, 4), "outer_area_expected", round(eo.area, 4), "delta", round(round(p.outer.polygon.area, 4) - round(eo.area, 4), 4))
    print("inners_area_actual", round(ai, 4), "inners_area_expected", round(ei, 4), "delta", round(round(ai, 4) - round(ei, 4), 4))
    print("outer_diff_area", p.outer.polygon.symmetric_difference(eo).area)
    print("outer_perim_actual", round(p.outer.polygon.exterior.length, 4), "outer_perim_expected", g["outer_perimeter_mm"])
    print("inners_count", len(all_in), len(g["inners_wkt"]))
