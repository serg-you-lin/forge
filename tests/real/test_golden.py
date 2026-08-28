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

from shapely import wkt as shapely_wkt

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.adapters.dxf.layers import (
    LAYER_BENDING, LAYER_ENGRAVE, LAYER_MARKING,
    LAYER_COUNTERSINK, LAYER_THREADED_HOLE,
)


EXAMPLES_DIR = project_root / "tests" / "examples"
GOLDEN_DXF_DIR = EXAMPLES_DIR / "golden"
GOLDEN_JSON_DIR = GOLDEN_DXF_DIR / "json"

DEFAULT_TOLERANCE = 0.5

TOL_AREA = 0.1
TOL_PERIMETER = 0.5
TOL_SHAPE = 1.0


GLOBAL_LABEL_MAP = {
    "MARK": "engrave",
    "Signature": "engrave",
}

# Rimappa i layer prodotti da forge in output sui rispettivi work_type, così
# il round-trip (to_dxf → reload → heal) ricostruisce gli stessi ruoli.
ROUNDTRIP_LABEL_MAP = {
    LAYER_BENDING:       "bending",
    LAYER_ENGRAVE:       "engrave",
    LAYER_MARKING:       "marking",
    LAYER_COUNTERSINK:   "countersink",
    LAYER_THREADED_HOLE: "threaded_hole",
}

# Contorni misti SplineSeg + linee/archi: materializzati come SPLINE native +
# LWPOLYLINE aperte con endpoint coincidenti (mai discretizzati). Il round-trip
# li ricuce via grafo — nessuna perdita nota al momento.
ROUNDTRIP_KNOWN_LOSSY = set()


def _load_config(dxf_path):
    path = EXAMPLES_DIR / "config" / f"{dxf_path.stem}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _load_golden_files():
    if not GOLDEN_JSON_DIR.exists():
        return []
    return sorted(GOLDEN_JSON_DIR.glob("*.json"))


def _make_test(path):

    def _role_value(role):
        return getattr(role, "value", role)

    def _assert_shapes_match_unordered(self, actual_shapes, expected_wkts, label, kind):
        expected_polys = [shapely_wkt.loads(wkt) for wkt in expected_wkts]
        unmatched = list(range(len(expected_polys)))

        for idx, actual_shape in enumerate(actual_shapes):
            best_idx = None
            best_score = None
            for expected_idx in unmatched:
                score = actual_shape.polygon.symmetric_difference(
                    expected_polys[expected_idx]
                ).area
                if best_score is None or score < best_score:
                    best_idx = expected_idx
                    best_score = score

            self.assertIsNotNone(best_idx, msg=f"{label} {kind}[{idx}] match")
            self.assertLess(
                best_score,
                TOL_SHAPE,
                msg=f"{label} {kind}[{idx}] shape",
            )
            unmatched.remove(best_idx)

    def test(self):

        golden = json.loads(path.read_text(encoding="utf-8"))
        dxf_path = GOLDEN_DXF_DIR / golden["source_file"]

        if not dxf_path.exists():
            self.skipTest(str(dxf_path))

        config = _load_config(dxf_path)
        label_map = {
            **GLOBAL_LABEL_MAP,
            **config.get("label_map", {})
        }

        result = forge.heal(
            forge.load_dxf(
                str(dxf_path),
                upgrade=True,
                explode_inserts=True,
                flatten_z_flag=True,
                tolerance=config.get("tolerance", DEFAULT_TOLERANCE),
                label_map=label_map,
            ),
            tolerance=config.get("tolerance", DEFAULT_TOLERANCE),
        )

        forge.detect(result)
        forge.inject(result)

        # --- part count ---
        self.assertEqual(
            result.part_count,
            golden["part_count"],
        )

        for idx, (part, expected) in enumerate(
            zip(result.parts, golden["parts"])
        ):
            label = f"{golden['source_file']} parte {idx+1}"

            holes = sorted(part.holes, key=lambda x: x.area, reverse=True)
            inners = sorted(part.inners, key=lambda x: x.area, reverse=True)

            # --- area ---
            self.assertAlmostEqual(
                round(part.area, 4),
                expected["area_mm2"],
                delta=TOL_AREA,
                msg=f"{label} area",
            )

            # --- perimetro outer ---
            self.assertAlmostEqual(
                round(part.outer.polygon.exterior.length, 4),
                expected["outer_perimeter_mm"],
                delta=TOL_PERIMETER,
                msg=f"{label} outer perimeter",
            )

            # --- perimetro inner totale ---
            actual_inner_p = round(
                sum(h.polygon.exterior.length for h in holes) +
                sum(i.polygon.exterior.length for i in inners),
                4,
            )
            self.assertAlmostEqual(
                actual_inner_p,
                expected["inner_perimeter_mm"],
                delta=TOL_PERIMETER,
                msg=f"{label} inner perimeter",
            )

            # --- total perimeter ---
            actual_total_p = round(
                part.outer.polygon.exterior.length +
                sum(h.polygon.exterior.length for h in holes) +
                sum(i.polygon.exterior.length for i in inners),
                4,
            )
            self.assertAlmostEqual(
                actual_total_p,
                expected["total_perimeter_mm"],
                delta=TOL_PERIMETER,
                msg=f"{label} total perimeter",
            )

            # --- outer shape ---
            outer = shapely_wkt.loads(expected["outer_wkt"])
            self.assertLess(
                part.outer.polygon.symmetric_difference(outer).area,
                TOL_SHAPE,
                msg=f"{label} outer shape",
            )

            # --- holes ---
            self.assertEqual(
                len(holes),
                expected["holes_count"],
                msg=f"{label} holes count",
            )

            for j, (hole, exp_wkt) in enumerate(zip(holes, expected["holes_wkt"])):
                pass

            _assert_shapes_match_unordered(
                self,
                holes,
                expected["holes_wkt"],
                label,
                "hole",
            )

            # --- holes to_dict ---
            if "holes" in expected:
                remaining_expected = list(enumerate(expected["holes"]))
                for j, hole in enumerate(holes):
                    best_idx = None
                    best_score = None
                    actual_center = hole.to_dict().get("center", (0, 0))
                    for expected_idx, exp_hole_dict in remaining_expected:
                        exp_center = exp_hole_dict.get("center", (0, 0))
                        score = sum(
                            abs(act - exp)
                            for act, exp in zip(actual_center, exp_center)
                        )
                        if best_score is None or score < best_score:
                            best_idx = expected_idx
                            best_score = score
                    exp_hole_dict = expected["holes"][best_idx]
                    remaining_expected = [
                        item for item in remaining_expected
                        if item[0] != best_idx
                    ]
                    actual_dict = hole.to_dict()
                    for key in ["hole_type", "diameter", "role", "confidence", "source"]:
                        if key in exp_hole_dict:
                            if isinstance(exp_hole_dict[key], float):
                                self.assertAlmostEqual(
                                    actual_dict[key],
                                    exp_hole_dict[key],
                                    delta=0.01,
                                    msg=f"{label} hole[{j}].{key}",
                                )
                            else:
                                self.assertEqual(
                                    actual_dict[key],
                                    exp_hole_dict[key],
                                    msg=f"{label} hole[{j}].{key}",
                                )
                    if "center" in exp_hole_dict:
                        for k, (act, exp) in enumerate(
                            zip(actual_dict["center"], exp_hole_dict["center"])
                        ):
                            self.assertAlmostEqual(
                                act, exp, delta=0.01,
                                msg=f"{label} hole[{j}].center[{k}]",
                            )
                    if "outer_diameter" in exp_hole_dict:
                        self.assertAlmostEqual(
                            actual_dict.get("outer_diameter", 0),
                            exp_hole_dict["outer_diameter"],
                            delta=0.01,
                            msg=f"{label} hole[{j}].outer_diameter",
                        )

            # --- inners ---
            self.assertEqual(
                len(inners),
                expected["inners_count"],
                msg=f"{label} inners count",
            )

            for j, (inner, exp_wkt) in enumerate(zip(inners, expected["inners_wkt"])):
                pass

            _assert_shapes_match_unordered(
                self,
                inners,
                expected["inners_wkt"],
                label,
                "inner",
            )

            # --- inners to_dict ---
            if "inners" in expected:
                remaining_expected = list(enumerate(expected["inners"]))
                for j, inner in enumerate(inners):
                    best_idx = None
                    best_score = None
                    actual_dict = inner.to_dict()
                    actual_area = actual_dict.get("area", 0)
                    for expected_idx, exp_inner_dict in remaining_expected:
                        score = abs(actual_area - exp_inner_dict.get("area", 0))
                        if best_score is None or score < best_score:
                            best_idx = expected_idx
                            best_score = score
                    exp_inner_dict = expected["inners"][best_idx]
                    remaining_expected = [
                        item for item in remaining_expected
                        if item[0] != best_idx
                    ]
                    self.assertEqual(
                        actual_dict["role"],
                        exp_inner_dict["role"],
                        msg=f"{label} inner[{j}].role",
                    )
                    self.assertAlmostEqual(
                        actual_dict["area"],
                        exp_inner_dict["area"],
                        delta=TOL_AREA,
                        msg=f"{label} inner[{j}].area",
                    )

            # --- bending lines ---
            if "bending_lines" in expected:
                self.assertEqual(
                    len(part.bending_lines),
                    expected.get("bending_lines_count", 0),
                    msg=f"{label} bending_lines count",
                )
                for j, (bl, exp_bl) in enumerate(
                    zip(part.bending_lines, expected["bending_lines"])
                ):
                    actual_dict = bl.to_dict()
                    for key in ["length", "angle_deg"]:
                        if key in exp_bl:
                            self.assertAlmostEqual(
                                actual_dict[key],
                                exp_bl[key],
                                delta=0.01,
                                msg=f"{label} bending[{j}].{key}",
                            )
                    self.assertEqual(
                        _role_value(bl.role),
                        exp_bl.get("role", "bending"),
                        msg=f"{label} bending[{j}].role",
                    )

            # --- engrave lines ---
            if "engrave_lines" in expected:
                self.assertAlmostEqual(
                    round(sum(e.length for e in part.engrave_lines), 4),
                    expected.get("total_engrave_length", 0),
                    delta=TOL_PERIMETER,
                    msg=f"{label} total_engrave_length",
                )
                self.assertEqual(
                    len(part.engrave_lines),
                    expected.get("engrave_lines_count", 0),
                    msg=f"{label} engrave_lines count",
                )
                for j, (eng, exp_eng) in enumerate(
                    zip(part.engrave_lines, expected["engrave_lines"])
                ):
                    actual_dict = eng.to_dict()
                    for key in ["closed", "length"]:
                        if key in exp_eng:
                            if isinstance(exp_eng[key], float):
                                self.assertAlmostEqual(
                                    actual_dict[key],
                                    exp_eng[key],
                                    delta=0.01,
                                    msg=f"{label} engrave[{j}].{key}",
                                )
                            else:
                                self.assertEqual(
                                    actual_dict[key],
                                    exp_eng[key],
                                    msg=f"{label} engrave[{j}].{key}",
                                )
                    self.assertEqual(
                        _role_value(eng.role),
                        exp_eng.get("role", "engrave"),
                        msg=f"{label} engrave[{j}].role",
                    )

            # --- custom ---
            for key, value in expected.get("custom", {}).items():
                self.assertEqual(
                    part.custom.get(key),
                    value,
                    msg=f"{label} custom {key}",
                )

    test.__name__ = f"test_{path.stem}"
    return test


class TestGolden(unittest.TestCase):
    pass


for golden in _load_golden_files():
    setattr(
        TestGolden,
        f"test_{golden.stem}",
        _make_test(golden),
    )


def _make_roundtrip_test(path):
    """
    Round-trip dell'exporter: heal → to_dxf → reload → heal.

    Le asserzioni di TestGolden si fermano al modello in memoria e NON
    vedono mai la geometria scritta da to_dxf(): un bug dell'exporter
    (es. archi materializzati invertiti, contorni persi) passa inosservato.
    Qui la geometria SCRITTA viene ricaricata e ri-processata: deve
    riprodurre lo stesso modello che TestGolden ha già validato contro il
    golden. Confrontiamo quindi rt_result con result, non con il JSON —
    così il match delle parti è indipendente dall'ordine.
    """

    def test(self):
        golden = json.loads(path.read_text(encoding="utf-8"))
        dxf_path = GOLDEN_DXF_DIR / golden["source_file"]

        if not dxf_path.exists():
            self.skipTest(str(dxf_path))
        if golden["source_file"] in ROUNDTRIP_KNOWN_LOSSY:
            self.skipTest(f"{golden['source_file']}: write-back lossy noto (spline miste)")

        config = _load_config(dxf_path)
        tol = config.get("tolerance", DEFAULT_TOLERANCE)
        label_map = {**GLOBAL_LABEL_MAP, **config.get("label_map", {})}

        def _pipeline(doc):
            r = forge.heal(doc, tolerance=tol)
            forge.detect(r)
            return r

        result = _pipeline(
            forge.load_dxf(
                str(dxf_path), upgrade=True, explode_inserts=True,
                flatten_z_flag=True, tolerance=tol, label_map=label_map,
            )
        )
        source_doc = forge.load_dxf(
            str(dxf_path), upgrade=True, explode_inserts=True,
            flatten_z_flag=True, tolerance=tol, label_map=label_map,
        )
        doc_out = forge.to_dxf(result, source_doc)
        rt_result = _pipeline(
            forge.document_from_msp(
                doc_out.modelspace(), tolerance=tol, label_map=ROUNDTRIP_LABEL_MAP,
            )
        )

        src = golden["source_file"]
        self.assertEqual(
            rt_result.part_count, result.part_count,
            msg=f"{src} round-trip part_count "
                f"(l'exporter ha perso o inventato una parte)",
        )

        unmatched = list(rt_result.parts)
        for i, part in enumerate(result.parts):
            match = min(
                unmatched,
                key=lambda p: p.outer.polygon.centroid.distance(
                    part.outer.polygon.centroid
                ),
                default=None,
            )
            self.assertIsNotNone(match, msg=f"{src} parte {i+1} senza corrispondenza")
            unmatched.remove(match)
            label = f"{src} round-trip parte {i+1}"

            self.assertAlmostEqual(
                match.area, part.area, delta=TOL_AREA, msg=f"{label} area",
            )
            self.assertAlmostEqual(
                match.outer.polygon.exterior.length,
                part.outer.polygon.exterior.length,
                delta=TOL_PERIMETER, msg=f"{label} outer perimeter",
            )
            self.assertLess(
                match.outer.polygon.symmetric_difference(part.outer.polygon).area,
                TOL_SHAPE, msg=f"{label} outer shape",
            )
            self.assertEqual(
                len(match.holes), len(part.holes), msg=f"{label} holes count",
            )
            self.assertEqual(
                len(match.inners), len(part.inners), msg=f"{label} inners count",
            )

    test.__name__ = f"test_roundtrip_{path.stem}"
    return test


class TestGoldenWriteBack(unittest.TestCase):
    pass


for golden in _load_golden_files():
    setattr(
        TestGoldenWriteBack,
        f"test_roundtrip_{golden.stem}",
        _make_roundtrip_test(golden),
    )


class TestGoldenSetup(unittest.TestCase):

    def test_directory_exists(self):
        self.assertTrue(GOLDEN_JSON_DIR.exists())

    def test_has_files(self):
        self.assertGreater(len(_load_golden_files()), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)