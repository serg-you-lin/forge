# tests/unit/core/test_shape.py
"""`contour_shape`: fatti di forma di un contorno chiuso (D68)."""

import math
import unittest

import forge
from forge.core.primitives.segments import ArcSeg, CircleSeg, LineSeg
from forge.core.geometry.shape import CIRCLE, OTHER, POLYGON, RECTANGLE, STADIUM, contour_shape
from forge.core.topology.edge import Edge
from forge.model.document import ForgeDocument

# max_gap non ha default (D98); island_gap non esiste più (D99)
MAX_GAP = 0.5


def _ring(*pts):
    return [LineSeg(start=pts[i], end=pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def _stadium(c1, c2, r):
    """Stadio orizzontale fra i centri c1 e c2 (stessa y), percorsa in senso antiorario."""
    (x1, y), (x2, _) = c1, c2
    return [
        LineSeg(start=(x1, y - r), end=(x2, y - r)),
        ArcSeg(center=c2, radius=r, start_angle=-math.pi / 2, end_angle=math.pi / 2, ccw=True),
        LineSeg(start=(x2, y + r), end=(x1, y + r)),
        ArcSeg(center=c1, radius=r, start_angle=math.pi / 2, end_angle=3 * math.pi / 2, ccw=True),
    ]


class TestContourShape(unittest.TestCase):

    def test_cerchio(self):
        s = contour_shape([CircleSeg(center=(10, 20), radius=3)])
        self.assertEqual(s.kind, CIRCLE)
        self.assertAlmostEqual(s.diameter, 6)
        self.assertEqual(s.center, (10, 20))
        self.assertIsNone(s.angle)

    def test_cerchio_in_quattro_archi(self):
        arcs = [ArcSeg(center=(0, 0), radius=5, start_angle=k * math.pi / 2,
                       end_angle=(k + 1) * math.pi / 2) for k in range(4)]
        s = contour_shape(arcs)
        self.assertEqual(s.kind, CIRCLE)
        self.assertAlmostEqual(s.diameter, 10)

    def test_stadio(self):
        s = contour_shape(_stadium((0, 0), (20, 0), 4))
        self.assertEqual(s.kind, STADIUM)
        self.assertAlmostEqual(s.length, 28)
        self.assertAlmostEqual(s.width, 8)
        self.assertAlmostEqual(s.angle, 0)
        self.assertEqual(s.center, (10, 0))

    def test_rettangolo_ruotato(self):
        c, a = math.cos(math.radians(30)), math.sin(math.radians(30))
        pts = [(0, 0), (40 * c, 40 * a), (40 * c - 10 * a, 40 * a + 10 * c), (-10 * a, 10 * c)]
        s = contour_shape(_ring(*pts))
        self.assertEqual(s.kind, RECTANGLE)
        self.assertAlmostEqual(s.length, 40)
        self.assertAlmostEqual(s.width, 10)
        self.assertAlmostEqual(s.angle, 30)

    def test_lato_spezzato_resta_rettangolo(self):
        s = contour_shape(_ring((0, 0), (50, 0), (100, 0), (100, 30), (0, 30)))
        self.assertEqual(s.kind, RECTANGLE)
        self.assertEqual(s.sides, 4)

    def test_poligono(self):
        s = contour_shape(_ring((0, 0), (10, 0), (5, 8)))
        self.assertEqual(s.kind, POLYGON)
        self.assertEqual(s.sides, 3)

    def test_altro(self):
        # rettangolo con un angolo raccordato
        segs = [LineSeg(start=(0, 0), end=(20, 0)),
                LineSeg(start=(20, 0), end=(20, 5)),
                ArcSeg(center=(15, 5), radius=5, start_angle=0, end_angle=math.pi / 2),
                LineSeg(start=(15, 10), end=(0, 10)),
                LineSeg(start=(0, 10), end=(0, 0))]
        self.assertEqual(contour_shape(segs).kind, OTHER)

    def test_vuoto(self):
        self.assertIsNone(contour_shape([]))


def _edge(seg):
    pts = seg.discretize()
    return Edge(role="unknown", start=pts[0], end=pts[-1], segment=seg)


class TestContourShapeSuIsole(unittest.TestCase):
    """Stesso fatto di forma dalle due letture."""

    def _doc(self):
        segs = (_ring((0, 0), (100, 0), (100, 50), (0, 50))
                + [CircleSeg(center=(15, 25), radius=4)]
                + _stadium((40, 25), (70, 25), 5))
        return ForgeDocument(edges=[_edge(s) for s in segs], annotations=[],
                             source_meta={"tolerance": 0.05}, source_path="")

    def _kinds(self, cluster):
        return sorted(contour_shape(c).kind for c in cluster.inners)

    def test_island(self):
        cluster = forge.island(self._doc(), max_gap=MAX_GAP).clusters[0]
        self.assertEqual(contour_shape(cluster.outer).kind, RECTANGLE)
        self.assertEqual(self._kinds(cluster), [CIRCLE, STADIUM])

    def test_heal(self):
        cluster = forge.heal(self._doc()).clusters[0]
        self.assertEqual(contour_shape(cluster.outer).kind, RECTANGLE)
        self.assertEqual(self._kinds(cluster), [CIRCLE, STADIUM])


if __name__ == "__main__":
    unittest.main()
