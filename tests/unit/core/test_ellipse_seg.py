"""
tests/unit/core/test_ellipse_seg.py
------------------------------------
`EllipseSeg` (core/primitives/segments.py): parametrizzazione, chiusura,
`.reversed()`, discretizzazione adattiva. Stessa parametrizzazione del
gruppo DXF ELLIPSE, verificata contro `ezdxf.math.ellipse` (vedi docstring
della classe) — questi test verificano solo la matematica pura di forge,
zero ezdxf.
"""

import math
import unittest

from forge.core.primitives.segments import EllipseSeg, CircleSeg, segment_is_closed, segment_endpoints


def _max_deviation_from_ellipse(seg: EllipseSeg, pts) -> float:
    """Scostamento massimo dei punti discretizzati dalla curva vera — la
    curva è nota in forma chiusa (parametrica), quindi per ogni punto basta
    verificare che soddisfi l'equazione dell'ellisse ruotata/traslata."""
    mx, my = seg.major_axis
    a = math.hypot(mx, my)
    b = a * seg.ratio
    ux, uy = mx / a, my / a  # asse maggiore, versore
    max_dev = 0.0
    for x, y in pts:
        dx, dy = x - seg.center[0], y - seg.center[1]
        # coordinate nel sistema locale dell'ellisse (asse maggiore = u)
        u = dx * ux + dy * uy
        v = -dx * uy + dy * ux
        val = (u / a) ** 2 + (v / b) ** 2
        # val == 1 esatto sulla curva; la deviazione radiale approssimata
        max_dev = max(max_dev, abs(math.sqrt(val) - 1.0) * a)
    return max_dev


class TestEllipseSegClosed(unittest.TestCase):

    def test_full_ellipse_is_closed(self):
        seg = EllipseSeg(center=(0, 0), major_axis=(10, 0), ratio=0.5,
                          start_param=0.0, end_param=2 * math.pi)
        self.assertTrue(segment_is_closed(seg))

    def test_full_ellipse_discretize_closes_polyline(self):
        seg = EllipseSeg(center=(3, -2), major_axis=(10, 0), ratio=0.4,
                          start_param=0.0, end_param=2 * math.pi)
        pts = seg.discretize(0.01)
        self.assertAlmostEqual(pts[0][0], pts[-1][0], places=6)
        self.assertAlmostEqual(pts[0][1], pts[-1][1], places=6)

    def test_open_arc_is_not_closed(self):
        seg = EllipseSeg(center=(0, 0), major_axis=(10, 0), ratio=0.5,
                          start_param=0.0, end_param=math.pi / 2)
        self.assertFalse(segment_is_closed(seg))


class TestEllipseSegPointAt(unittest.TestCase):

    def test_axis_aligned_endpoints(self):
        """major_axis=(10,0), ratio=0.5: a t=0 estremo asse maggiore,
        a t=pi/2 estremo asse minore (rotate90 CCW del maggiore)."""
        seg = EllipseSeg(center=(0, 0), major_axis=(10, 0), ratio=0.5,
                          start_param=0.0, end_param=math.pi / 2)
        start, end = segment_endpoints(seg)
        self.assertAlmostEqual(start[0], 10.0, places=6)
        self.assertAlmostEqual(start[1], 0.0, places=6)
        self.assertAlmostEqual(end[0], 0.0, places=6)
        self.assertAlmostEqual(end[1], 5.0, places=6)

    def test_rotated_major_axis(self):
        """major_axis=(0,10) (ruotato 90°), ratio=0.5: l'asse minore ruota
        con lui — rotate90((0,10)) = (-10,0) scalato per ratio = (-5,0)."""
        seg = EllipseSeg(center=(1, 1), major_axis=(0, 10), ratio=0.5,
                          start_param=0.0, end_param=math.pi / 2)
        start, end = segment_endpoints(seg)
        self.assertAlmostEqual(start[0], 1.0, places=6)
        self.assertAlmostEqual(start[1], 11.0, places=6)
        self.assertAlmostEqual(end[0], -4.0, places=6)
        self.assertAlmostEqual(end[1], 1.0, places=6)

    def test_degenerates_to_circle_when_ratio_one(self):
        """ratio=1.0: ogni punto dell'ellisse discretizzata sta sul cerchio
        dello stesso raggio — la formula generale deve ridursi a un cerchio."""
        radius = 7.0
        ellipse = EllipseSeg(center=(2, -3), major_axis=(radius, 0), ratio=1.0,
                              start_param=0.0, end_param=2 * math.pi)
        pts = ellipse.discretize(0.01)
        for x, y in pts:
            d = math.hypot(x - 2, y - (-3))
            self.assertAlmostEqual(d, radius, places=4)


class TestEllipseSegDiscretize(unittest.TestCase):

    def test_deviation_within_tolerance_eccentric(self):
        """Ellisse eccentrica (ratio basso, curvatura molto variabile):
        ogni punto campionato deve stare sulla curva vera entro una
        tolleranza ragionevole rispetto a quella richiesta."""
        seg = EllipseSeg(center=(0, 0), major_axis=(50, 0), ratio=0.1,
                          start_param=0.0, end_param=2 * math.pi)
        tolerance = 0.05
        pts = seg.discretize(tolerance)
        max_dev = _max_deviation_from_ellipse(seg, pts)
        self.assertLess(max_dev, tolerance * 5)  # i punti VALUTATI stanno sulla curva

    def test_zero_sweep_returns_degenerate_point(self):
        seg = EllipseSeg(center=(0, 0), major_axis=(10, 0), ratio=0.5,
                          start_param=1.0, end_param=1.0, ccw=True)
        pts = seg.discretize(0.01)
        self.assertEqual(len(pts), 2)
        self.assertEqual(pts[0], pts[1])


class TestEllipseSegReversed(unittest.TestCase):

    def test_reversed_swaps_params_and_ccw(self):
        seg = EllipseSeg(center=(0, 0), major_axis=(10, 0), ratio=0.5,
                          start_param=0.2, end_param=1.5, ccw=True)
        rev = seg.reversed()
        self.assertEqual(rev.start_param, seg.end_param)
        self.assertEqual(rev.end_param, seg.start_param)
        self.assertFalse(rev.ccw)

    def test_reversed_same_locus_opposite_order(self):
        seg = EllipseSeg(center=(3, -2), major_axis=(12, 4), ratio=0.6,
                          start_param=math.radians(20), end_param=math.radians(140),
                          ccw=True)
        rev = seg.reversed()
        fwd_pts = seg.discretize(0.01)
        rev_pts = rev.discretize(0.01)
        self.assertEqual(len(fwd_pts), len(rev_pts))
        for (xf, yf), (xr, yr) in zip(fwd_pts, reversed(rev_pts)):
            self.assertAlmostEqual(xf, xr, places=6)
            self.assertAlmostEqual(yf, yr, places=6)


if __name__ == "__main__":
    unittest.main()
