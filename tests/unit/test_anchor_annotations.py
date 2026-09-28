"""
tests/unit/test_anchor_annotations.py
--------------------------------------
`anchor_annotations()`: assegna `cluster_ref` (indice della parte contenitrice)
alle annotazioni del modello. Fase separata e opzionale (forge/tools/).
"""

import unittest

from shapely.geometry import Point, Polygon

import forge
from forge.model.cluster import ForgeCluster
from forge.model.contour import ForgeContour
from forge.model.result import ForgeResult
from forge.model.role import ContourRole
from forge.model.annotation import Leader, Note
from forge.tools.anchor import anchor_annotations, resolve_target


def _part(x0, y0, x1, y1):
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return ForgeCluster(outer=ForgeContour(polygon=poly, role=ContourRole.OUTER))


def _result(*clusters, annotations=()):
    return ForgeResult(clusters=list(clusters), annotations=list(annotations))


class TestAnchorAnnotations(unittest.TestCase):

    def test_containment_assigns_part_index(self):
        res = _result(
            _part(0, 0, 100, 100),
            _part(200, 0, 300, 100),
            annotations=[
                Note(position=(50, 50), text="dentro parte 0"),
                Note(position=(250, 50), text="dentro parte 1"),
            ],
        )
        anchor_annotations(res)
        self.assertEqual(res.annotations[0].cluster_ref, 0)
        self.assertEqual(res.annotations[1].cluster_ref, 1)

    def test_outside_all_parts_stays_none(self):
        res = _result(
            _part(0, 0, 100, 100),
            annotations=[Note(position=(500, 500), text="cartiglio")],
        )
        anchor_annotations(res)
        self.assertIsNone(res.annotations[0].cluster_ref)

    def test_snap_distance_assigns_near_part(self):
        res = _result(
            _part(0, 0, 100, 100),
            annotations=[Note(position=(105, 50), text="callout appena fuori")],
        )
        anchor_annotations(res, snap_distance=0.0)
        self.assertIsNone(res.annotations[0].cluster_ref)

        anchor_annotations(res, snap_distance=10.0)
        self.assertEqual(res.annotations[0].cluster_ref, 0)

    def test_first_covering_part_wins_on_overlap(self):
        res = _result(
            _part(0, 0, 100, 100),
            _part(50, 50, 150, 150),   # sovrapposta alla prima
            annotations=[Note(position=(75, 75), text="nella zona comune")],
        )
        anchor_annotations(res)
        self.assertEqual(res.annotations[0].cluster_ref, 0)

    def test_no_parts_is_noop(self):
        res = _result(annotations=[Note(position=(1, 1), text="x")])
        anchor_annotations(res)
        self.assertIsNone(res.annotations[0].cluster_ref)


def _plate_with_holes():
    """Piastra 100x50 con due fori: Ø8 in (20, 25), Ø20 in (70, 25)."""
    return forge.load_geometry([
        {"type": "polyline", "closed": True, "points": [(0, 0), (100, 0), (100, 50), (0, 50)]},
        {"type": "circle", "center": (20, 25), "radius": 4},
        {"type": "circle", "center": (70, 25), "radius": 10},
    ])


def _leader(*vertices):
    return Leader(position=vertices[-1], text="M8", vertices=list(vertices))


class TestLeaderTarget(unittest.TestCase):
    """`Leader.target`: l'elemento su cui cade la punta della freccia (D66)."""

    def _island(self, *leaders):
        result = forge.island(_plate_with_holes())
        result.annotations = list(leaders)
        return anchor_annotations(result)

    def _inner_at(self, result, center):
        return next(i for i, c in enumerate(result.clusters[0].inners)
                    if c.polygon.centroid.distance(Point(center)) < 0.1)

    def test_punta_sul_bordo_del_foro(self):
        result = self._island(_leader((24, 25), (40, 60)))
        k = self._inner_at(result, (20, 25))
        self.assertEqual(result.annotations[0].target, f"clusters[0].inners[{k}]")
        self.assertIs(resolve_target(result, result.annotations[0].target), result.clusters[0].inners[k])

    def test_punta_dentro_il_foro(self):
        result = self._island(_leader((72, 27), (90, 70)))
        k = self._inner_at(result, (70, 25))
        self.assertEqual(result.annotations[0].target, f"clusters[0].inners[{k}]")

    def test_punta_sul_contorno_esterno(self):
        result = self._island(_leader((100, 40), (120, 60)))
        self.assertEqual(result.annotations[0].target, "clusters[0].outer")

    def test_freccia_lontana_nessun_target(self):
        # freccia di sezione: si ferma a 5 mm dal pezzo
        result = self._island(_leader((-5, 25), (-15, 25)))
        self.assertIsNone(result.annotations[0].target)

    def test_senza_vertici_nessun_target(self):
        result = self._island(Leader(position=(20, 25), text="M8"))
        self.assertIsNone(result.annotations[0].target)

    def test_feature_di_detect(self):
        # pezzo piano: detect sposta i fori in `holes`, il target segue
        result = forge.heal_and_detect(_plate_with_holes())
        result.annotations = [_leader((24, 25), (40, 60))]
        anchor_annotations(result)
        hole = resolve_target(result, result.annotations[0].target)
        self.assertIn(".holes[", result.annotations[0].target)
        self.assertAlmostEqual(hole.polygon.centroid.x, 20, places=1)


if __name__ == "__main__":
    unittest.main()
