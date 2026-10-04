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
from forge.model.annotation import Dimension, Leader, Note, RenderedGeometry, RenderedText
from forge.tools.anchor import anchor_annotations, dimension_references, resolve_target


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

    def test_elemento_dell_overlay(self):
        # un consumatore sposta un contorno in una sua collezione: il target segue
        from forge.model import DetectedFeatures
        result = forge.heal(_plate_with_holes())
        cluster = result.clusters[0]
        small = min(cluster.inners, key=lambda c: c.polygon.area)
        cluster.inners = [c for c in cluster.inners if c is not small]
        cluster.detected = DetectedFeatures()
        cluster.detected.attach("my_circles", [small])
        result.annotations = [_leader((24, 25), (40, 60))]
        anchor_annotations(result)
        target = resolve_target(result, result.annotations[0].target)
        self.assertIn(".my_circles[", result.annotations[0].target)
        self.assertAlmostEqual(target.polygon.centroid.x, 20, places=1)


class TestDimensionReferences(unittest.TestCase):
    """`Dimension.references`: gli elementi fra cui la quota misura (D69)."""

    def _result(self, *dims):
        result = forge.island(_plate_with_holes())
        result.annotations = list(dims)
        return anchor_annotations(result)

    def test_diametro_sul_foro(self):
        dim = Dimension(position=(40, 40), dim_type="diameter", measured_points=[(60, 25), (80, 25)])
        result = self._result(dim)
        self.assertEqual(len(dim.references), 1)
        hole = resolve_target(result, dim.references[0])
        self.assertAlmostEqual(forge.contour_shape(hole).diameter, 20)

    def test_raggio_sul_foro(self):
        dim = Dimension(position=(40, 40), dim_type="radius", measured_points=[(20, 29)])
        result = self._result(dim)
        self.assertAlmostEqual(forge.contour_shape(resolve_target(result, dim.references[0])).diameter, 8)

    def test_lineare_fra_due_elementi(self):
        # dal bordo sinistro del pezzo al bordo sinistro del foro Ø8
        dim = Dimension(position=(8, 60), measured_points=[(0, 25), (16, 25)])
        result = self._result(dim)
        self.assertEqual(dim.references[0], "clusters[0].outer")
        self.assertEqual(len(dim.references), 2)
        self.assertAlmostEqual(forge.contour_shape(resolve_target(result, dim.references[1])).diameter, 8)

    def test_punti_fuori_dalla_geometria(self):
        dim = Dimension(position=(0, 0), measured_points=[(-20, -20), (200, 200)])
        self._result(dim)
        self.assertEqual(dim.references, [])

    def test_senza_punti(self):
        result = forge.island(_plate_with_holes())
        self.assertEqual(dimension_references(result, Dimension(position=(0, 0))), [])


def _texts(*contents):
    return RenderedGeometry(texts=[RenderedText(content=c, position=(0, 0)) for c in contents])


class TestDimensionDisplayText(unittest.TestCase):

    def test_override_con_la_misura_disegnata(self):
        # il simbolo arriva come frammento a sé ("n" in un font di simboli): vale l'override
        d = Dimension(position=(0, 0), text_override="Ø<>", measured_value=6.5, rendered=_texts("n", "6.5"))
        self.assertEqual(d.display_text, "Ø6.5")

    def test_override_usa_la_precisione_del_disegno(self):
        d = Dimension(position=(0, 0), text_override="M<>", measured_value=5.000000004, rendered=_texts("M", "5"))
        self.assertEqual(d.display_text, "M5")

    def test_override_senza_testo_disegnato(self):
        d = Dimension(position=(0, 0), text_override="(<>)", measured_value=35.0)
        self.assertEqual(d.display_text, "(35)")

    def test_frammenti_uniti(self):
        d = Dimension(position=(0, 0), measured_value=6.625, rendered=_texts("∅5,3", "+0,05^-0"))
        self.assertEqual(d.display_text, "∅5,3+0,05^-0")

    def test_solo_misura(self):
        self.assertEqual(Dimension(position=(0, 0), measured_value=12.50).display_text, "12.5")


if __name__ == "__main__":
    unittest.main()
