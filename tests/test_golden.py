"""
test_golden.py
--------------
Test di regressione geometrica contro i golden file.

Controlla per ogni DXF:
- part_count invariato
- area invariata (tolleranza 0.1 mm²)
- perimetri invariati (tolleranza 0.5 mm)
- geometria invariata via differenza simmetrica Shapely (tolleranza 1.0 mm²)
- layer assegnati invariati

Genera prima i golden file con:
    python generate_golden.py

Lancia i test con:
    python -m pytest tests/test_golden.py -v
    oppure
    python tests/test_golden.py
"""

import unittest
import json
import sys
from pathlib import Path
import ezdxf
from shapely import wkt as shapely_wkt

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import dxf_forge as forge

EXAMPLES_DIR = project_root / "tests" / "examples"
GOLDEN_DIR   = project_root / "tests" / "examples" / "golden"

# Tolleranze
TOL_AREA      = 0.1   # mm²
TOL_PERIMETER = 0.5   # mm
TOL_SHAPE     = 1.0   # mm² differenza simmetrica


def _load_golden_files() -> list:
    if not GOLDEN_DIR.exists():
        return []
    return sorted(GOLDEN_DIR.glob("*.json"))


class TestGolden(unittest.TestCase):
    pass


def _make_golden_test(golden_path: Path):
    def test_method(self):
        golden = json.loads(golden_path.read_text(encoding='utf-8'))
        dxf_name = golden["source_file"]
        dxf_path = EXAMPLES_DIR / dxf_name

        if not dxf_path.exists():
            self.skipTest(f"DXF non trovato: {dxf_path}")

        # --- Heal ---
        doc = ezdxf.readfile(dxf_path)
        if doc.dxfversion < 'AC1015':
            doc = forge.upgrade_to_r2010(doc)
        msp = doc.modelspace()
        result = forge.heal(msp, tolerance=0.5, write_to_msp=False)

        # --- part_count ---
        self.assertEqual(
            result.part_count, golden["part_count"],
            f"{dxf_name}: part_count {result.part_count} != atteso {golden['part_count']}"
        )

        for i, (part, exp) in enumerate(zip(result.parts, golden["parts"])):
            label = f"{dxf_name} parte {i+1}"

            # --- Area ---
            actual_area = round(part.outer.area - sum(h.area for h in part.inners), 4)
            self.assertAlmostEqual(
                actual_area, exp["area_mm2"], delta=TOL_AREA,
                msg=f"{label}: area {actual_area} != attesa {exp['area_mm2']} (tol={TOL_AREA})"
            )

            # --- Holes count ---
            self.assertEqual(
                len(part.inners), exp["holes_count"],
                f"{label}: holes_count {len(part.inners)} != atteso {exp['holes_count']}"
            )

            # --- Perimetri ---
            actual_outer_p = round(part.outer.polygon.exterior.length, 4)
            self.assertAlmostEqual(
                actual_outer_p, exp["outer_perimeter_mm"], delta=TOL_PERIMETER,
                msg=f"{label}: outer_perimeter {actual_outer_p} != atteso {exp['outer_perimeter_mm']}"
            )

            actual_inner_p = round(sum(h.polygon.exterior.length for h in part.inners), 4)
            self.assertAlmostEqual(
                actual_inner_p, exp["inner_perimeter_mm"], delta=TOL_PERIMETER,
                msg=f"{label}: inner_perimeter {actual_inner_p} != atteso {exp['inner_perimeter_mm']}"
            )

            # --- Geometria outer (WKT) ---
            expected_outer = shapely_wkt.loads(exp["outer_wkt"])
            diff = part.outer.polygon.symmetric_difference(expected_outer).area
            self.assertLess(
                diff, TOL_SHAPE,
                f"{label}: geometria outer cambiata (diff={diff:.4f} mm², tol={TOL_SHAPE})"
            )

            # --- Geometria inners (WKT) ---
            for j, (inner, exp_wkt) in enumerate(zip(part.inners, exp["inners_wkt"])):
                expected_inner = shapely_wkt.loads(exp_wkt)
                diff = inner.polygon.symmetric_difference(expected_inner).area
                self.assertLess(
                    diff, TOL_SHAPE,
                    f"{label} inner {j+1}: geometria cambiata (diff={diff:.4f} mm², tol={TOL_SHAPE})"
                )

            # --- Layer ---
            self.assertEqual(
                part.outer.layer, exp["outer_layer"],
                f"{label}: outer layer '{part.outer.layer}' != atteso '{exp['outer_layer']}'"
            )
            actual_inner_layers = [h.layer for h in part.inners]
            self.assertEqual(
                actual_inner_layers, exp["inners_layers"],
                f"{label}: inners layers {actual_inner_layers} != attesi {exp['inners_layers']}"
            )

    test_method.__name__ = f"test_{golden_path.stem}"
    test_method.__doc__  = f"Golden: {golden_path.name}"
    return test_method


# Genera dinamicamente un test per ogni golden file
for _golden_path in _load_golden_files():
    setattr(TestGolden, f"test_{_golden_path.stem}", _make_golden_test(_golden_path))


class TestGoldenSetup(unittest.TestCase):

    def test_001_golden_dir_exists(self):
        """La cartella tests/golden/ esiste."""
        self.assertTrue(
            GOLDEN_DIR.exists(),
            f"Cartella golden non trovata: {GOLDEN_DIR}\n"
            f"Genera i golden file con: python generate_golden.py"
        )

    def test_002_golden_not_empty(self):
        """La cartella tests/golden/ contiene almeno 1 golden file."""
        files = list(GOLDEN_DIR.glob("*.json")) if GOLDEN_DIR.exists() else []
        self.assertGreater(
            len(files), 0,
            f"Nessun golden file trovato in {GOLDEN_DIR}\n"
            f"Genera i golden file con: python generate_golden.py"
        )
        print(f"\n  Golden file trovati: {len(files)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
