# tests/unit/core/test_build.py
"""Costruttori di `forge.geometry` e `forge.load_segments` (D96): costruire e leggere usano le stesse misure."""

import math
import unittest

import forge
from forge.core.geometry import contour_shape
from forge.core.geometry.build import circle, polygon, rectangle, regular_polygon, stadium
from forge.core.primitives.segments import ArcSeg, CircleSeg, LineSeg


class TestBuild(unittest.TestCase):

    def test_poligono_si_chiude_da_solo(self):
        segs = polygon([(0, 0), (10, 0), (5, 8)])
        self.assertEqual(len(segs), 3)
        self.assertEqual(segs[-1].end, (0, 0))
        self.assertEqual(len(polygon([(0, 0), (10, 0), (5, 8), (0, 0)])), 3)

    def test_poligono_con_meno_di_tre_punti(self):
        with self.assertRaises(ValueError):
            polygon([(0, 0), (1, 1)])

    def test_rettangolo_ruotato_si_rilegge_uguale(self):
        s = contour_shape(rectangle(80, 30, center=(5, 5), angle=20))
        self.assertEqual(s.kind, "rectangle")
        self.assertAlmostEqual(s.length, 80)
        self.assertAlmostEqual(s.width, 30)
        self.assertAlmostEqual(s.angle, 20)
        self.assertAlmostEqual(s.center[0], 5)

    def test_poligono_regolare(self):
        segs = regular_polygon(6, 10, center=(1, 2))
        self.assertEqual(len(segs), 6)
        self.assertTrue(all(isinstance(s, LineSeg) for s in segs))
        self.assertAlmostEqual(math.dist(segs[0].start, (1, 2)), 10)
        with self.assertRaises(ValueError):
            regular_polygon(2, 10)

    def test_cerchio(self):
        (c,) = circle(5, center=(3, 4))
        self.assertIsInstance(c, CircleSeg)
        self.assertEqual(contour_shape([c]).diameter, 10)

    def test_stadio_con_archi_veri(self):
        segs = stadium(60, 20, center=(10, 5), angle=30)
        self.assertEqual(sum(isinstance(s, ArcSeg) for s in segs), 2)
        s = contour_shape(segs)
        self.assertEqual(s.kind, "stadium")
        self.assertAlmostEqual(s.length, 60)
        self.assertAlmostEqual(s.width, 20)
        self.assertAlmostEqual(s.angle, 30)
        with self.assertRaises(ValueError):
            stadium(10, 20)


class TestLoadSegments(unittest.TestCase):

    def test_due_rettangoli_e_un_cerchio(self):
        fg = forge.geometry
        doc = forge.load_segments(fg.rectangle(200, 100) + fg.rectangle(100, 50) + fg.circle(5, center=(70, 0)))
        result = forge.heal(doc)
        self.assertTrue(result.is_valid)
        (part,) = result.clusters
        self.assertEqual(fg.contour_shape(part.outer).kind, "rectangle")
        self.assertEqual(sorted(fg.contour_shape(i).kind for i in part.inners), ["circle", "rectangle"])
        self.assertAlmostEqual(part.area, 200 * 100 - 100 * 50 - math.pi * 25, places=0)

    def test_liste_annidate_e_ruolo(self):
        doc = forge.load_segments([rectangle(10, 10), circle(1)], role="outer")
        self.assertEqual(len(doc.edges), 5)
        self.assertTrue(all(e.role == "outer" for e in doc.edges))

    def test_load_geometry_poligono(self):
        doc = forge.load_geometry([{"type": "polygon", "points": [(0, 0), (10, 0), (10, 5), (0, 5)]}])
        self.assertEqual(len(doc.edges), 4)


if __name__ == "__main__":
    unittest.main()
