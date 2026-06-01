"""
test_golden.py
--------------
Test di regressione geometrica contro i golden file.

DXF sorgente: tests/examples/golden/
Golden JSON:  tests/examples/golden/json/
"""

import unittest
import json
import sys
from pathlib import Path

import ezdxf
from shapely import wkt as shapely_wkt

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import dxf_forge as forge

EXAMPLES_DIR      = project_root / "tests" / "examples"
GOLDEN_DXF_DIR    = EXAMPLES_DIR / "golden"
GOLDEN_JSON_DIR   = EXAMPLES_DIR / "golden" / "json"
DEFAULT_TOLERANCE = 0.5

TOL_AREA      = 0.1
TOL_PERIMETER = 0.5
TOL_SHAPE     = 1.0

GLOBAL_SPECIAL_LAYERS = {
    "MARK":      "engrave",
    "Signature": "engrave",
}


def _load_config(dxf_path: Path) -> dict:
    config_path = EXAMPLES_DIR / "config" / f"{dxf_path.stem}.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def _load_golden_files():
    if not GOLDEN_JSON_DIR.exists():
        return []
    return sorted(GOLDEN_JSON_DIR.glob("*.json"))


def _make_golden_test(golden_path: Path):
    def test_method(self):
        golden = json.loads(golden_path.read_text(encoding="utf-8"))

        dxf_name = golden["source_file"]
        dxf_path = GOLDEN_DXF_DIR / dxf_name

        if not dxf_path.exists():
            self.skipTest(f"DXF non trovato: {dxf_path}")

        config         = _load_config(dxf_path)
        tolerance      = config.get("tolerance", DEFAULT_TOLERANCE)
        special_layers = {**GLOBAL_SPECIAL_LAYERS, **config.get("special_layers", {})}

        doc = ezdxf.readfile(dxf_path)
        if doc.dxfversion < "AC1015":
            doc = forge.upgrade_to_r2010(doc)
        msp = doc.modelspace()

        result = forge.heal(
            msp,
            tolerance=tolerance,
            explode_inserts=True,
            special_layers=special_layers,
        )

        forge.detect(
            result,
            msp,
        )

        forge.inject(msp, result)

        # --- part count ---
        self.assertEqual(
            result.part_count,
            golden["part_count"],
            msg=f"{dxf_name} — part_count",
        )

        for i, (part, exp) in enumerate(zip(result.parts, golden["parts"])):
            label  = f"{dxf_name} parte {i+1}"
            holes  = sorted(part.holes,  key=lambda x: x.area, reverse=True)
            inners = sorted(part.inners, key=lambda x: x.area, reverse=True)

            # --- area ---
            self.assertAlmostEqual(
                round(part.area, 4),
                exp["area_mm2"],
                delta=TOL_AREA,
                msg=f"{label} — area_mm2",
            )

            # --- perimetro outer ---
            self.assertAlmostEqual(
                round(part.outer.polygon.exterior.length, 4),
                exp["outer_perimeter_mm"],
                delta=TOL_PERIMETER,
                msg=f"{label} — outer_perimeter_mm",
            )

            # --- perimetro inner totale ---
            actual_inner_p = round(
                sum(h.polygon.exterior.length for h in holes) +
                sum(i.polygon.exterior.length for i in inners),
                4,
            )
            self.assertAlmostEqual(
                actual_inner_p,
                exp["inner_perimeter_mm"],
                delta=TOL_PERIMETER,
                msg=f"{label} — inner_perimeter_mm",
            )

            # --- outer layer ---
            self.assertEqual(
                part.outer.layer,
                exp["outer_layer"],
                msg=f"{label} — outer_layer",
            )

            # --- outer shape ---
            expected_outer = shapely_wkt.loads(exp["outer_wkt"])
            diff = part.outer.polygon.symmetric_difference(expected_outer).area
            self.assertLess(diff, TOL_SHAPE, msg=f"{label} — outer shape")

            # --- holes ---
            self.assertEqual(
                len(holes),
                exp["holes_count"],
                msg=f"{label} — holes_count",
            )
            self.assertEqual(
                [h.layer for h in holes],
                exp["holes_layers"],
                msg=f"{label} — holes_layers",
            )
            for j, (hole, exp_wkt) in enumerate(zip(holes, exp["holes_wkt"])):
                expected_hole = shapely_wkt.loads(exp_wkt)
                diff = hole.polygon.symmetric_difference(expected_hole).area
                self.assertLess(diff, TOL_SHAPE, msg=f"{label} — hole[{j}] shape")

            # --- inners ---
            self.assertEqual(
                len(inners),
                exp["inners_count"],
                msg=f"{label} — inners_count",
            )
            self.assertEqual(
                [i.layer for i in inners],
                exp["inners_layers"],
                msg=f"{label} — inners_layers",
            )
            for j, (inner, exp_wkt) in enumerate(zip(inners, exp["inners_wkt"])):
                expected_inner = shapely_wkt.loads(exp_wkt)
                diff = inner.polygon.symmetric_difference(expected_inner).area
                self.assertLess(diff, TOL_SHAPE, msg=f"{label} — inner[{j}] shape")

            # --- custom (features) ---
            for key, expected_val in exp.get("custom", {}).items():
                actual_val = part.custom.get(key)
                if isinstance(expected_val, float):
                    self.assertAlmostEqual(
                        actual_val,
                        expected_val,
                        delta=TOL_PERIMETER,
                        msg=f"{label} — custom[{key!r}]",
                    )
                else:
                    self.assertEqual(
                        actual_val,
                        expected_val,
                        msg=f"{label} — custom[{key!r}]",
                    )

    test_method.__name__ = f"test_{golden_path.stem}"
    test_method.__doc__  = f"Golden: {golden_path.name}"
    return test_method


class TestGolden(unittest.TestCase):
    pass


for _golden_path in _load_golden_files():
    setattr(TestGolden, f"test_{_golden_path.stem}", _make_golden_test(_golden_path))


class TestGoldenSetup(unittest.TestCase):

    def test_001_golden_dir_exists(self):
        self.assertTrue(GOLDEN_JSON_DIR.exists(), f"Golden JSON dir non trovata: {GOLDEN_JSON_DIR}")

    def test_002_golden_not_empty(self):
        files = list(GOLDEN_JSON_DIR.glob("*.json")) if GOLDEN_JSON_DIR.exists() else []
        self.assertGreater(len(files), 0, "Nessun golden JSON trovato")


if __name__ == "__main__":
    unittest.main(verbosity=2)