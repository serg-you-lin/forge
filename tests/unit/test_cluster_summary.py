"""
tests/unit/test_cluster_summary.py
-------------------------------
`describe_features()` (MAP.md D8, D44): i conteggi feature che prima
produceva `inject()` scrivendo in `cluster.custom`, poi `ForgeCluster.summary`
per intero (D8), ora sono il livello "ricco" separato dal modello — vive in
`tools.detect` perché serve le costanti `HOLE_TYPE_*` (branch
refactor/detect-overlay).
"""

import unittest

from shapely.geometry import Polygon, LineString

from forge.model.cluster import ForgeCluster
from forge.model.contour import ForgeContour
from forge.model.role import ContourRole
from forge.tools.manufacturing_role import HOLE, BEND, ENGRAVE
from forge.tools.detect import describe_features
from forge.tools.model import (
    Hole, HOLE_TYPE_PLAIN, HOLE_TYPE_COUNTERSINK, HOLE_TYPE_THREADED,
    BendingLine, Engraving, DetectedFeatures,
)


def _part(**detected_kw):
    """
    ForgeCluster con `detected` popolato dai kwargs (`holes=[...]`,
    `bending_lines=[...]`, `engrave_lines=[...]`) — stessa comodità di prima
    del refactor, ma passando per `DetectedFeatures.attach()` invece di
    campi fissi sul cluster.
    """
    outer = ForgeContour(polygon=Polygon([(0, 0), (100, 0), (100, 100), (0, 100)]),
                         role=ContourRole.OUTER)
    cluster = ForgeCluster(outer=outer)
    if detected_kw:
        cluster.detected = DetectedFeatures()
        for name, items in detected_kw.items():
            cluster.detected.attach(name, items)
    return cluster


def _hole(t):
    return Hole(role=HOLE,
                polygon=Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                diameter=1.0, center=(0.5, 0.5), hole_type=t)


class TestDescribeFeatures(unittest.TestCase):

    def test_empty_part_all_zero(self):
        s = describe_features(_part())
        self.assertEqual(s, {
            "plain_holes_count": 0, "countersink_count": 0,
            "threaded_holes_count": 0, "bending_lines": 0,
            "total_engrave_length": 0.0, "total_marking_length": 0.0,
        })

    def test_holes_counted_by_type(self):
        cluster = _part(holes=[_hole(HOLE_TYPE_PLAIN), _hole(HOLE_TYPE_PLAIN),
                               _hole(HOLE_TYPE_COUNTERSINK), _hole(HOLE_TYPE_THREADED)])
        s = describe_features(cluster)
        self.assertEqual(s["plain_holes_count"], 2)
        self.assertEqual(s["countersink_count"], 1)
        self.assertEqual(s["threaded_holes_count"], 1)

    def test_engrave_length_summed(self):
        eng = [Engraving(role=ENGRAVE, length=10.0),
               Engraving(role=ENGRAVE, length=5.5)]
        cluster = _part(engrave_lines=eng)
        self.assertEqual(describe_features(cluster)["total_engrave_length"], 15.5)

    def test_bending_collinear_grouped(self):
        # due segmenti collineari sulla stessa retta → una piega logica
        bl = [
            BendingLine(role=BEND, geometry=LineString([(0, 50), (40, 50)]), length=40),
            BendingLine(role=BEND, geometry=LineString([(60, 50), (100, 50)]), length=40),
            BendingLine(role=BEND, geometry=LineString([(50, 0), (50, 100)]), length=100),
        ]
        cluster = _part(bending_lines=bl)
        self.assertEqual(describe_features(cluster)["bending_lines"], 2)

    def test_marking_length_from_custom_entities(self):
        p = _part()
        p.custom["marking_entities"] = [{"length": 3.0}, {"length": 4.0}]
        self.assertEqual(describe_features(p)["total_marking_length"], 7.0)


class TestClusterSummaryGeneric(unittest.TestCase):
    """`cluster.summary` — property, sempre disponibile, conteggio grezzo."""

    def test_no_detected_is_empty(self):
        self.assertEqual(_part().summary, {})

    def test_generic_count_per_name(self):
        cluster = _part(holes=[_hole(HOLE_TYPE_PLAIN), _hole(HOLE_TYPE_COUNTERSINK)])
        self.assertEqual(cluster.summary, {"holes_count": 2})

    def test_works_for_any_custom_name(self):
        cluster = _part()
        cluster.detected = DetectedFeatures()
        cluster.detected.attach("flange_view_hint", [object(), object(), object()])
        self.assertEqual(cluster.summary, {"flange_view_hint_count": 3})


class TestSummaryMatchesGoldenFixtures(unittest.TestCase):
    """
    Prova di equivalenza: i conteggi salvati nei golden fixture (prodotti dal
    vecchio inject()) devono coincidere con `describe_features()` della
    pipeline attuale — è il livello ricco che ha preso il posto del vecchio
    `cluster.summary` per intero.
    """

    def test_golden_summary_matches_pipeline(self):
        import json
        from pathlib import Path
        import forge

        ex = Path(__file__).resolve().parents[1] / "examples"
        gdir = ex / "golden" / "json"
        if not gdir.exists():
            self.skipTest("golden fixtures assenti")

        GLOBAL_LABEL_MAP = {"MARK": "engrave", "Signature": "engrave"}
        checked = 0
        for jf in sorted(gdir.glob("*.json")):
            golden = json.loads(jf.read_text(encoding="utf-8"))
            dxf = ex / "golden" / golden["source_file"]
            if not dxf.exists():
                continue
            cfg_p = ex / "config" / f"{dxf.stem}.json"
            cfg = json.loads(cfg_p.read_text(encoding="utf-8")) if cfg_p.exists() else {}
            tol = cfg.get("tolerance", 0.5)
            lm = {**GLOBAL_LABEL_MAP, **cfg.get("label_map", {})}
            try:
                result = forge.heal_and_detect(
                    forge.load_dxf(str(dxf), explode_inserts=True,
                                   flatten_z_flag=True, label_map=lm),
                    tolerance=tol,
                )
            except Exception:
                continue
            if not result.is_valid:
                continue
            for i, (cluster, pg) in enumerate(zip(result.clusters, golden["clusters"])):
                rich = describe_features(cluster)
                for key, expected in (pg.get("summary") or {}).items():
                    actual = rich.get(key)
                    checked += 1
                    if isinstance(expected, float):
                        self.assertAlmostEqual(actual, expected, delta=0.01,
                                               msg=f"{jf.name}[{i}].{key}")
                    else:
                        self.assertEqual(actual, expected,
                                         msg=f"{jf.name}[{i}].{key}")
        self.assertGreater(checked, 0, "nessun conteggio verificato")


if __name__ == "__main__":
    unittest.main()
