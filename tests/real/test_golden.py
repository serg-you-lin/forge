

"""
test_golden.py
--------------
Test di regressione geometrica contro i golden file.
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

EXAMPLES_DIR = project_root / "tests" / "examples"
GOLDEN_DIR   = EXAMPLES_DIR / "golden"

TOL_AREA      = 0.1
TOL_PERIMETER = 0.5
TOL_SHAPE     = 1.0
DEFAULT_TOLERANCE = 0.5


def _load_config(dxf_path: Path) -> dict:
    config_path = EXAMPLES_DIR / "config" / f"{dxf_path.stem}.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def _load_golden_files():
    if not GOLDEN_DIR.exists():
        return []
    return sorted(GOLDEN_DIR.glob("*.json"))


class TestGolden(unittest.TestCase):
    pass


def _make_golden_test(golden_path: Path):
    def test_method(self):
        golden = json.loads(golden_path.read_text(encoding="utf-8"))

        dxf_name = golden["source_file"]
        dxf_path = EXAMPLES_DIR / dxf_name

        if not dxf_path.exists():
            self.skipTest(f"DXF non trovato: {dxf_path}")

        config = _load_config(dxf_path)
        tolerance = config.get("tolerance", DEFAULT_TOLERANCE)

        special_layers = config.get("special_layers") or {}
        special_layers["MARK"] = "engrave"
        special_layers["Signature"] = "engrave"

        doc = ezdxf.readfile(dxf_path)
        if doc.dxfversion < "AC1015":
            doc = forge.upgrade_to_r2010(doc)

        msp = doc.modelspace()

        result = forge.heal(
            msp,
            tolerance=tolerance,
            explode_inserts=True,
            ignore_layers={"MARK", "engrave"},
        )

        from dxf_forge.core.graph import build_node_graph
        from dxf_forge.core.geometry import round_point

        graph = build_node_graph(msp, decimals=2)
        branching = {n for n, nb in graph.items() if len(nb) > 2}
        print(f"nodi branching: {len(branching)}")
        for line in msp.query("LINE"):
            s = round_point((line.dxf.start.x, line.dxf.start.y), 2)
            e = round_point((line.dxf.end.x, line.dxf.end.y), 2)
            s_branch = s in branching
            e_branch = e in branching
            if s_branch or e_branch:
                print(f"  LINE s_branch={s_branch} e_branch={e_branch} layer={line.dxf.layer}")

        # print("trash nel test:", len(result.trash_entities))
        # for e in result.trash_entities:
        #     if e.dxf.hasattr("layer"):
        #         print(f"  {e.dxftype()} layer={e.dxf.layer}")
    
        forge.detect(
            result,
            msp,
            special_layers=special_layers,
        )

        # print("part_count:", result.part_count)
        # for i, part in enumerate(result.parts):
        #     print(f"Part {i+1}: inners={len(part.inners)} holes={len(part.holes)}")
        #     for j, inner in enumerate(part.inners):
        #         print(f"  inner[{j}] layer={inner.layer!r} source_layer={inner.source_layer!r} vs_id={inner.vs_id}")
                
        if special_layers:
            forge.inject(msp, result)

        all_inners = sorted(
            result.parts[0].holes + result.parts[0].inners,
            key=lambda x: x.area,
            reverse=True,
        )
        print("inners_layers actual:  ", [h.layer for h in all_inners])
        print("inners_layers expected:", golden["parts"][0]["inners_layers"])
        print("part_count actual:  ", result.part_count)
        print("part_count expected:", golden["part_count"])


        self.assertEqual(
            result.part_count,
            golden["part_count"],
        )

        for i, (part, exp) in enumerate(zip(result.parts, golden["parts"])):
            label = f"{dxf_name} parte {i+1}"

            # all_inners unifica fori e contorni interni — rispecchia la struttura
            # del golden che li conteneva tutti in part.inners prima di Hole.
            # L'ordine è: holes prima (erano CIRCLE, classificati per area desc),
            # poi inners (ForgeContour non-foro).
            all_inners = sorted(
                part.holes + part.inners,
                key=lambda x: x.area,
                reverse=True,
            )

            actual_area = round(part.area, 4)

            # print(f"\n[DEBUG] {label}")
            # print(f"  holes count     = {len(part.holes)}")
            # print(f"  inners count    = {len(part.inners)}")
            # print(f"  all_inners      = {len(all_inners)}")
            # print(f"  expected holes  = {exp['holes_count']}")
            # print(f"  special_layers  = {special_layers}")
            # print(f"  outer  = {part.outer.area}")
            # for k, h in enumerate(all_inners):
            #     print(f"  inner[{k}].layer = {h.layer!r}  area = {h.area:.4f}")
            # print(f"  actual_area     = {actual_area}")
            # print(f"  expected        = {exp['area_mm2']}")

            self.assertAlmostEqual(
                actual_area,
                exp["area_mm2"],
                delta=TOL_AREA,
                msg=label,
            )

            self.assertEqual(
                len(all_inners),
                exp["holes_count"],
                msg=label,
            )

            actual_outer_p = round(part.outer.polygon.exterior.length, 4)
            self.assertAlmostEqual(
                actual_outer_p,
                exp["outer_perimeter_mm"],
                delta=TOL_PERIMETER,
                msg=label,
            )

            actual_inner_p = round(
                sum(h.polygon.exterior.length for h in all_inners),
                4,
            )
            self.assertAlmostEqual(
                actual_inner_p,
                exp["inner_perimeter_mm"],
                delta=TOL_PERIMETER,
                msg=label,
            )

            expected_outer = shapely_wkt.loads(exp["outer_wkt"])
            diff = part.outer.polygon.symmetric_difference(expected_outer).area
            self.assertLess(diff, TOL_SHAPE, msg=f"{label} — outer shape")

            for j, (inner, exp_wkt) in enumerate(zip(all_inners, exp["inners_wkt"])):
                expected_inner = shapely_wkt.loads(exp_wkt)
                diff = inner.polygon.symmetric_difference(expected_inner).area
                print(f"  inner[{j}] diff={diff:.4f}  actual_area={inner.area:.4f}  expected_area={expected_inner.area:.4f}  layer={inner.layer!r}")
                self.assertLess(diff, TOL_SHAPE, msg=f"{label} — inner[{j}] shape")

            self.assertEqual(
                part.outer.layer,
                exp["outer_layer"],
                msg=label,
            )

            self.assertEqual(
                [h.layer for h in all_inners],
                exp["inners_layers"],
                msg=label,
            )

            if "custom" in exp:
                for key, expected_val in exp["custom"].items():
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


for _golden_path in _load_golden_files():
    setattr(TestGolden, f"test_{_golden_path.stem}", _make_golden_test(_golden_path))


class TestGoldenSetup(unittest.TestCase):

    def test_001_golden_dir_exists(self):
        self.assertTrue(GOLDEN_DIR.exists())

    def test_002_golden_not_empty(self):
        files = list(GOLDEN_DIR.glob("*.json")) if GOLDEN_DIR.exists() else []
        self.assertGreater(len(files), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)