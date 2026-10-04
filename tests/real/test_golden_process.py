"""
tests/real/test_golden_process.py
---------------------------------
La metà di processo dei golden: fori, pieghe, incisioni e summary letti da
detect_flat(). La geometria (outer, perimetri) è in test_golden.py. Questo
file e i suoi JSON passano a snapbend insieme a detect_flat (MAP.md D88).

DXF sorgente: tests/data/golden/, tests/data/golden_multipli/
Golden JSON:  tests/data/golden/process/, tests/data/golden_multipli/process/
"""

import unittest
import json
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

from shapely import wkt as shapely_wkt

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.adapters.dxf.layers import role_to_dxf_layer
from forge.tools.detect import describe_features


EXAMPLES_DIR = project_root / "tests" / "data"
GOLDEN_DXF_DIR = EXAMPLES_DIR / "golden"
GOLDEN_JSON_DIR = GOLDEN_DXF_DIR / "process"

DEFAULT_TOLERANCE = 0.5

TOL_AREA = 0.1
TOL_PERIMETER = 0.5
TOL_SHAPE = 1.0



GLOBAL_NAME_ROLES = {
    "MARK": "engrave",
    "Signature": "engrave",
}



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
        name_roles = {
            **GLOBAL_NAME_ROLES,
            **config.get("name_roles", {})
        }

        from forge.tools.manufacturing_role import is_structural
        result = forge.heal(
            forge.load_dxf(
                str(dxf_path),
                upgrade=True,
                explode_inserts=True,
                flatten_z_flag=True,
                tolerance=config.get("tolerance", DEFAULT_TOLERANCE),
                role_rules=forge.name_rules(name_roles),
            ),
            tolerance=config.get("tolerance", DEFAULT_TOLERANCE),
            is_structural=is_structural,
        )

        forge.detect_flat(result, features="all")

        # --- cluster count ---
        self.assertEqual(
            result.cluster_count,
            golden["cluster_count"],
        )

        for idx, (cluster, expected) in enumerate(
            zip(result.clusters, golden["clusters"])
        ):
            label = f"{golden['source_file']} parte {idx+1}"

            holes = sorted(cluster.features("holes"), key=lambda x: x.area, reverse=True)
            inners = sorted(cluster.inners, key=lambda x: x.area, reverse=True)

            # --- area ---
            self.assertAlmostEqual(
                round(cluster.area, 4),
                expected["area_mm2"],
                delta=TOL_AREA,
                msg=f"{label} area",
            )

            # --- holes ---
            self.assertEqual(
                len(holes),
                expected["holes_count"],
                msg=f"{label} holes count",
            )

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
                    len(cluster.features("bending_lines")),
                    expected.get("bending_lines_count", 0),
                    msg=f"{label} bending_lines count",
                )
                for j, (bl, exp_bl) in enumerate(
                    zip(cluster.features("bending_lines"), expected["bending_lines"])
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
                    round(sum(e.length for e in cluster.features("engrave_lines")), 4),
                    expected.get("total_engrave_length", 0),
                    delta=TOL_PERIMETER,
                    msg=f"{label} total_engrave_length",
                )
                self.assertEqual(
                    len(cluster.features("engrave_lines")),
                    expected.get("engrave_lines_count", 0),
                    msg=f"{label} engrave_lines count",
                )
                for j, (eng, exp_eng) in enumerate(
                    zip(cluster.features("engrave_lines"), expected["engrave_lines"])
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

            # --- summary (conteggi feature, ex cluster.custom via inject) ---
            # Fixture vecchi usano la chiave "custom", i nuovi "summary": stesso
            # contenuto, ora prodotto da cluster.summary invece che da inject().
            expected_summary = expected.get("summary", expected.get("custom", {}))
            # Stessa unione usata da generate_golden.py per costruire "summary"
            # (conteggi grezzi di cluster.summary + conteggi ricchi di
            # describe_features): confrontare solo contro describe_features
            # fa fallire sempre qualunque chiave presente solo nell'altro
            # dizionario (es. bending_lines_count vs bending_lines), a
            # prescindere dalla geometria.
            rich_summary = {**cluster.summary, **describe_features(cluster)}
            for key, value in expected_summary.items():
                actual = rich_summary.get(key)
                if isinstance(value, float):
                    self.assertAlmostEqual(
                        actual, value, delta=0.01,
                        msg=f"{label} summary {key}",
                    )
                else:
                    self.assertEqual(
                        actual, value,
                        msg=f"{label} summary {key}",
                    )

    test.__name__ = f"test_{path.stem}"
    return test


class TestGoldenProcess(unittest.TestCase):
    pass


for golden in _load_golden_files():
    setattr(
        TestGoldenProcess,
        f"test_{golden.stem}",
        _make_test(golden),
    )


# ---------------------------------------------------------------------------
# Fogli multipli: per ogni pezzo, area dopo detect_flat, layer dei contorni
# interni (un foro ha il suo layer) e summary.
# ---------------------------------------------------------------------------
MULTIPLI_DIR = project_root / "tests" / "data" / "golden_multipli"
MULTIPLI_PROC_DIR = MULTIPLI_DIR / "process"


@lru_cache(maxsize=None)
def _multipli_clusters(parent_path: Path, tolerance: float):
    result = forge.heal(forge.load_dxf(parent_path, explode_inserts=True, tolerance=tolerance),
                        tolerance=tolerance)
    if result.is_valid and result.clusters:
        forge.detect_flat(result, features="all")
    return result.clusters if result.is_valid else []


def _make_multipli_test(path):

    def test(self):
        golden = json.loads(path.read_text(encoding="utf-8"))
        parent_path = MULTIPLI_DIR / golden["parent_file"]
        if not parent_path.exists():
            self.skipTest(str(parent_path))
        config_path = MULTIPLI_DIR / "config" / f"{parent_path.stem}.json"
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}

        clusters = _multipli_clusters(parent_path, config.get("tolerance", DEFAULT_TOLERANCE))
        self.assertLess(golden["part_index"], len(clusters), msg=f"{path.stem}: pezzo mancante")
        cluster = clusters[golden["part_index"]]
        label = path.stem

        self.assertAlmostEqual(round(cluster.area, 4), golden["area_mm2"], delta=TOL_AREA,
                               msg=f"{label} area")
        self.assertLess(cluster.outer.polygon.symmetric_difference(
            shapely_wkt.loads(golden["outer_wkt"])).area, TOL_SHAPE, msg=f"{label} outer shape")

        layers = [role_to_dxf_layer(c.role) for c in cluster.features("holes") + cluster.inners]
        self.assertEqual(Counter(layers), Counter(golden["inners_layers"]),
                         msg=f"{label} inners_layers")

        rich = {**cluster.summary, **describe_features(cluster)}
        for key, value in golden["summary"].items():
            if isinstance(value, float):
                self.assertAlmostEqual(rich.get(key), value, delta=TOL_PERIMETER,
                                       msg=f"{label} summary {key}")
            else:
                self.assertEqual(rich.get(key), value, msg=f"{label} summary {key}")

    test.__name__ = f"test_{path.stem}"
    return test


class TestGoldenProcessMultipli(unittest.TestCase):
    pass


for golden in sorted(MULTIPLI_PROC_DIR.glob("*.json")):
    setattr(TestGoldenProcessMultipli, f"test_{golden.stem}", _make_multipli_test(golden))


if __name__ == "__main__":
    unittest.main()
