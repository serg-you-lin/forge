# tests/unit/core/test_trim.py

"""
`sub_segment`: il tratto di una primitiva fra due suoi punti è la stessa
curva accorciata — stessi capi, ogni punto sulla curva originale.
"""

import math
import unittest

from topo.core.primitives.segments import (
    ArcSeg, CircleSeg, EllipseSeg, LineSeg, SplineSeg, segment_endpoints,
)
from topo.core.primitives.trim import sub_segment


def _close(p, q, tol=1e-6):
    return math.dist(p, q) <= tol


class TestSubSegment(unittest.TestCase):

    def _assert_on(self, piece, curve_distance, tol=1e-6):
        # ogni punto del tratto sta sulla curva originale
        for pt in piece.discretize(0.001):
            self.assertLess(curve_distance(pt), tol)

    def test_retta(self):
        piece = sub_segment(LineSeg(start=(0, 0), end=(10, 0)), (2, 0), (7, 0), (4, 0))
        self.assertEqual(segment_endpoints(piece), ((2, 0), (7, 0)))

    def test_retta_al_contrario(self):
        piece = sub_segment(LineSeg(start=(0, 0), end=(10, 0)), (7, 0), (2, 0), (4, 0))
        self.assertEqual(segment_endpoints(piece), ((7, 0), (2, 0)))

    def test_arco_nei_due_versi(self):
        arc = ArcSeg(center=(0, 0), radius=5, start_angle=0, end_angle=math.pi, ccw=True)
        a, b = (5 * math.cos(0.5), 5 * math.sin(0.5)), (5 * math.cos(2.0), 5 * math.sin(2.0))
        for x, y in ((a, b), (b, a)):
            piece = sub_segment(arc, x, y, (0, 5))
            s, e = segment_endpoints(piece)
            self.assertTrue(_close(s, x) and _close(e, y))
            self.assertAlmostEqual(piece._sweep(), 1.5)
            self._assert_on(piece, lambda p: abs(math.dist(p, (0, 0)) - 5))

    def test_capo_appena_oltre_la_fine_dell_arco_sta_sulla_fine(self):
        arc = ArcSeg(center=(0, 0), radius=5, start_angle=0, end_angle=math.pi / 2, ccw=True)
        beyond = (5 * math.cos(math.pi / 2 + 1e-4), 5 * math.sin(math.pi / 2 + 1e-4))
        piece = sub_segment(arc, (5, 0), beyond, (0, 5))
        self.assertAlmostEqual(piece._sweep(), math.pi / 2)

    def test_cerchio_gira_dalla_parte_di_via(self):
        circle = CircleSeg(center=(0, 0), radius=5)
        top, bottom = (0, 5), (0, -5)
        left = sub_segment(circle, top, bottom, (-5, 0))
        right = sub_segment(circle, top, bottom, (5, 0))
        self.assertAlmostEqual(left._sweep(), math.pi)
        self.assertAlmostEqual(right._sweep(), math.pi)
        self.assertLess(min(p[0] for p in left.discretize(0.01)), -4.9)
        self.assertGreater(max(p[0] for p in right.discretize(0.01)), 4.9)

    def test_ellisse(self):
        ellipse = EllipseSeg(center=(0, 0), major_axis=(10, 0), ratio=0.5,
                             start_param=0, end_param=2 * math.pi)
        a, b = ellipse._point_at(0.3), ellipse._point_at(1.2)
        piece = sub_segment(ellipse, a, b, ellipse._point_at(0.7))
        s, e = segment_endpoints(piece)
        self.assertTrue(_close(s, a) and _close(e, b))
        self._assert_on(piece, lambda p: abs((p[0] / 10) ** 2 + (p[1] / 5) ** 2 - 1), tol=1e-6)

    def test_spline_tratto_esatto_nei_due_versi(self):
        spline = SplineSeg(degree=3,
                           control_points=[(0, 0), (2, 4), (5, -1), (8, 3), (10, 0), (13, 2)],
                           knots=[0, 0, 0, 0, 0.3, 0.6, 1, 1, 1, 1])
        a, b = spline._evaluate(0.2), spline._evaluate(0.75)
        for x, y in ((a, b), (b, a)):
            piece = sub_segment(spline, x, y, None)
            s, e = segment_endpoints(piece)
            self.assertTrue(_close(s, x, 1e-6) and _close(e, y, 1e-6))
        # stessa curva: ogni punto del tratto coincide con la spline originale
        piece = sub_segment(spline, a, b, None)
        lo, hi = piece.knots[0], piece.knots[-1]
        for k in range(11):
            t = lo + (hi - lo) * k / 10
            self.assertTrue(_close(piece._evaluate(t), spline._evaluate(t), 1e-9))

    def test_spline_razionale(self):
        spline = SplineSeg(degree=2, control_points=[(0, 0), (5, 5), (10, 0)],
                           knots=[0, 0, 0, 1, 1, 1], weights=[1.0, 0.5, 1.0])
        a, b = spline._evaluate(0.25), spline._evaluate(0.8)
        piece = sub_segment(spline, a, b, None)
        for k in range(11):
            t = 0.25 + 0.55 * k / 10
            self.assertTrue(_close(piece._evaluate(t), spline._evaluate(t), 1e-9))

    def test_spline_periodica_non_si_taglia(self):
        spline = SplineSeg(degree=3, control_points=[(0, 0), (1, 1), (2, 0), (3, 1)],
                           knots=[0, 1, 2, 3, 4, 5, 6, 7], periodic=True)
        self.assertIsNone(sub_segment(spline, (0, 0), (3, 1), None))


if __name__ == "__main__":
    unittest.main()
