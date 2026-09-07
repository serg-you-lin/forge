"""
tests/unit/test_cluster_summary.py
-------------------------------
`ForgeCluster.summary` (MAP.md D8): i conteggi feature che prima produceva
`inject()` scrivendo in `cluster.custom`, ora derivati dal modello.
"""

import unittest

from shapely.geometry import Polygon, LineString

from forge.model.cluster import ForgeCluster, ForgeContour
from forge.model.hole import (
    Hole, HOLE_TYPE_PLAIN, HOLE_TYPE_COUNTERSINK, HOLE_TYPE_THREADED,
)
from forge.model.bending_line import BendingLine
from forge.model.engraving import Engraving
from forge.model.role import ContourRole


def _part(**kw):
    outer = ForgeContour(polygon=Polygon([(0, 0), (100, 0), (100, 100), (0, 100)]),
                         role=ContourRole.OUTER)
    return ForgeCluster(outer=outer, **kw)


def _hole(t):
    return Hole(role=ContourRole.HOLE,
                polygon=Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                diameter=1.0, center=(0.5, 0.5), hole_type=t)


class TestPartSummary(unittest.TestCase):

    def test_empty_part_all_zero(self):
        s = _part().summary
        self.assertEqual(s, {
            "plain_holes_count": 0, "countersink_count": 0,
            "threaded_holes_count": 0, "bending_lines": 0,
            "total_engrave_length": 0.0, "total_marking_length": 0.0,
        })

    def test_holes_counted_by_type(self):
        s = _part(holes=[_hole(HOLE_TYPE_PLAIN), _hole(HOLE_TYPE_PLAIN),
                         _hole(HOLE_TYPE_COUNTERSINK), _hole(HOLE_TYPE_THREADED)]).summary
        self.assertEqual(s["plain_holes_count"], 2)
        self.assertEqual(s["countersink_count"], 1)
        self.assertEqual(s["threaded_holes_count"], 1)

    def test_engrave_length_summed(self):
        eng = [Engraving(role=ContourRole.ENGRAVE, length=10.0),
               Engraving(role=ContourRole.ENGRAVE, length=5.5)]
        self.assertEqual(_part(engrave_lines=eng).summary["total_engrave_length"], 15.5)

    def test_bending_collinear_grouped(self):
        # due segmenti collineari sulla stessa retta → una piega logica
        bl = [
            BendingLine(role=ContourRole.BEND, geometry=LineString([(0, 50), (40, 50)]), length=40),
            BendingLine(role=ContourRole.BEND, geometry=LineString([(60, 50), (100, 50)]), length=40),
            BendingLine(role=ContourRole.BEND, geometry=LineString([(50, 0), (50, 100)]), length=100),
        ]
        self.assertEqual(_part(bending_lines=bl).summary["bending_lines"], 2)

    def test_marking_length_from_custom_entities(self):
        p = _part()
        p.custom["marking_entities"] = [{"length": 3.0}, {"length": 4.0}]
        self.assertEqual(p.summary["total_marking_length"], 7.0)


class TestSummaryMatchesGoldenFixtures(unittest.TestCase):
    """
    Prova di equivalenza: i conteggi salvati nei golden fixture (prodotti dal
    vecchio inject()) devono coincidere con cluster.summary della pipeline attuale.
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
                for key, expected in (pg.get("summary") or {}).items():
                    actual = cluster.summary.get(key)
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
