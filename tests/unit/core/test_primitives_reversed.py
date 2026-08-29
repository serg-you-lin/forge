"""
tests/unit/core/test_primitives_reversed.py
-------------------------------------------
Fase 4:
  - `.reversed()` su LineSeg / ArcSeg / CircleSeg (D6)
  - regressione: ArcSeg.from_chord con archi maggiori (|bulge| > 1) — D7 ha
    esposto un bug dove from_chord sceglieva sempre l'arco minore.
"""

import math
import unittest

from forge.core.primitives.segments import LineSeg, ArcSeg, CircleSeg


def _arc_len(seg, tol=0.01):
    pts = seg.discretize(tol)
    return sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
               for i in range(len(pts) - 1))


class TestReversed(unittest.TestCase):

    def test_line_reversed(self):
        s = LineSeg(start=(1, 2), end=(4, 6))
        r = s.reversed()
        self.assertEqual((r.start, r.end), ((4, 6), (1, 2)))

    def test_arc_reversed_same_locus_opposite_orientation(self):
        s = ArcSeg(center=(3, -2), radius=7.5,
                   start_angle=math.radians(20), end_angle=math.radians(140), ccw=True)
        r = s.reversed()
        self.assertFalse(r.ccw)
        fwd = s.discretize(0.01)
        rev = r.discretize(0.01)
        self.assertEqual(len(fwd), len(rev))
        for (xf, yf), (xr, yr) in zip(fwd, reversed(rev)):
            self.assertAlmostEqual(xf, xr, places=6)
            self.assertAlmostEqual(yf, yr, places=6)

    def test_circle_reversed_is_equal(self):
        s = CircleSeg(center=(0, 0), radius=5)
        r = s.reversed()
        self.assertEqual((r.center, r.radius), (s.center, s.radius))


class TestFromChordMajorArc(unittest.TestCase):

    def test_minor_arc_bulge_below_one(self):
        arc = ArcSeg.from_chord((0, 0), (10, 0), bulge=0.5)
        # sweep = 4*atan(0.5) ≈ 106°, r = 6.25
        self.assertAlmostEqual(arc.radius, 6.25, places=6)
        self.assertAlmostEqual(_arc_len(arc), 6.25 * 4 * math.atan(0.5), places=2)

    def test_major_arc_bulge_above_one(self):
        # bulge=2 → sweep = 4*atan(2) ≈ 254° — arco MAGGIORE.
        arc = ArcSeg.from_chord((0, 0), (10, 0), bulge=2.0)
        self.assertAlmostEqual(arc.radius, 6.25, places=6)
        # il centro deve stare SOTTO la corda (y < 0), non sopra
        self.assertLess(arc.center[1], 0)
        # lunghezza = arco maggiore, non minore
        expected = 6.25 * 4 * math.atan(2.0)
        self.assertAlmostEqual(_arc_len(arc), expected, delta=0.05)

    def test_major_arc_negative_bulge(self):
        arc = ArcSeg.from_chord((0, 0), (10, 0), bulge=-2.0)
        self.assertGreater(arc.center[1], 0)
        self.assertFalse(arc.ccw)

    def test_semicircle_bulge_one(self):
        arc = ArcSeg.from_chord((0, 0), (10, 0), bulge=1.0)
        self.assertAlmostEqual(arc.radius, 5.0, places=6)
        self.assertAlmostEqual(_arc_len(arc), math.pi * 5.0, delta=0.05)


if __name__ == "__main__":
    unittest.main()
