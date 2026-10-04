"""
tests/real/test_golden.py
-------------------------
Test di regressione geometrica contro i golden file: solo heal(), nessuna
lettura di processo — un foro è un contorno interno, una piega un edge non
strutturale (MAP.md D88). Fori, pieghe e incisioni: test_golden_process.py.

DXF sorgente: tests/data/golden/
Golden JSON:  tests/data/golden/json/
"""

import unittest
import json
import sys
from pathlib import Path

from shapely import wkt as shapely_wkt

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.adapters.dxf.layers import role_to_dxf_layer


EXAMPLES_DIR = project_root / "tests" / "data"
GOLDEN_DXF_DIR = EXAMPLES_DIR / "golden"
GOLDEN_JSON_DIR = GOLDEN_DXF_DIR / "json"

DEFAULT_TOLERANCE = 0.5

TOL_AREA = 0.1
TOL_PERIMETER = 0.5
TOL_SHAPE = 1.0

# Solo per TestGoldenWriteBack: write-back DXF -> reload introduce rumore di
# arrotondamento sub-mm indipendente da forge (v. MAP.md D52, bisect a
# ac68da1). TOL_AREA/TOL_SHAPE restano stretti per TestGolden (output live
# vs golden salvato) -- qui il confronto e' output vs se stesso dopo un giro
# di scrittura/rilettura, un rumore diverso e piu' permissivo per natura.
TOL_AREA_ROUNDTRIP = 20.0
TOL_SHAPE_ROUNDTRIP = 30.0


GLOBAL_NAME_ROLES = {
    "MARK": "engrave",
    "Signature": "engrave",
}

# L'unico ruolo che i golden assegnano al load (MARK/Signature → engrave):
# il round-trip lo rilegge dal layer su cui to_dxf l'ha scritto.
ROUNDTRIP_NAME_ROLES = {
    role_to_dxf_layer("engrave"): "engrave",
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
        )

        # --- cluster count ---
        self.assertEqual(
            result.cluster_count,
            golden["cluster_count"],
        )

        for idx, (cluster, expected) in enumerate(
            zip(result.clusters, golden["clusters"])
        ):
            label = f"{golden['source_file']} parte {idx+1}"

            inners = sorted(cluster.inners, key=lambda x: x.area, reverse=True)

            # --- area ---
            self.assertAlmostEqual(
                round(cluster.area, 4),
                expected["area_mm2"],
                delta=TOL_AREA,
                msg=f"{label} area",
            )

            # --- perimetro outer ---
            self.assertAlmostEqual(
                round(cluster.outer.polygon.exterior.length, 4),
                expected["outer_perimeter_mm"],
                delta=TOL_PERIMETER,
                msg=f"{label} outer perimeter",
            )

            # --- perimetro inner totale ---
            actual_inner_p = round(
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
                cluster.outer.polygon.exterior.length +
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
                cluster.outer.polygon.symmetric_difference(outer).area,
                TOL_SHAPE,
                msg=f"{label} outer shape",
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
        name_roles = {**GLOBAL_NAME_ROLES, **config.get("name_roles", {})}

        def _pipeline(doc):
            return forge.heal(doc, tolerance=tol)

        result = _pipeline(
            forge.load_dxf(
                str(dxf_path), upgrade=True, explode_inserts=True,
                flatten_z_flag=True, tolerance=tol, role_rules=forge.name_rules(name_roles),
            )
        )
        source_doc = forge.load_dxf(
            str(dxf_path), upgrade=True, explode_inserts=True,
            flatten_z_flag=True, tolerance=tol, role_rules=forge.name_rules(name_roles),
        )
        doc_out = forge.to_dxf(result, source_doc)
        rt_result = _pipeline(
            forge.document_from_msp(
                doc_out.modelspace(), tolerance=tol, role_rules=forge.name_rules(ROUNDTRIP_NAME_ROLES),
            )
        )

        src = golden["source_file"]
        self.assertEqual(
            rt_result.cluster_count, result.cluster_count,
            msg=f"{src} round-trip cluster_count "
                f"(l'exporter ha perso o inventato una parte)",
        )

        unmatched = list(rt_result.clusters)
        for i, cluster in enumerate(result.clusters):
            match = min(
                unmatched,
                key=lambda p: p.outer.polygon.centroid.distance(
                    cluster.outer.polygon.centroid
                ),
                default=None,
            )
            self.assertIsNotNone(match, msg=f"{src} parte {i+1} senza corrispondenza")
            unmatched.remove(match)
            label = f"{src} round-trip parte {i+1}"

            self.assertAlmostEqual(
                match.area, cluster.area, delta=TOL_AREA_ROUNDTRIP, msg=f"{label} area",
            )
            self.assertAlmostEqual(
                match.outer.polygon.exterior.length,
                cluster.outer.polygon.exterior.length,
                delta=TOL_PERIMETER, msg=f"{label} outer perimeter",
            )
            self.assertLess(
                match.outer.polygon.symmetric_difference(cluster.outer.polygon).area,
                TOL_SHAPE_ROUNDTRIP, msg=f"{label} outer shape",
            )
            self.assertEqual(
                len(match.inners), len(cluster.inners), msg=f"{label} inners count",
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