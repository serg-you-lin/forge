"""
tests/unit/core/test_segment_rotation.py
------------------------------------------
`.rotated(angle, origin)` su ogni primitiva nativa (core/primitives/segments.py)
— stesso pattern di `.reversed()`: stessa geometria, trasformata. Verifica la
matematica pura di forge, zero ezdxf.
"""

import math
import unittest

from forge.core.primitives.segments import (
    LineSeg, ArcSeg, SplineSeg, CircleSeg, EllipseSeg, segment_endpoints,
)


class TestLineSegRotated(unittest.TestCase):

    def test_90_degrees_around_origin(self):
        seg = LineSeg(start=(1, 0), end=(2, 0))
        rotated = seg.rotated(math.pi / 2, origin=(0, 0))
        self.assertAlmostEqual(rotated.start[0], 0.0, places=9)
        self.assertAlmostEqual(rotated.start[1], 1.0, places=9)
        self.assertAlmostEqual(rotated.end[0], 0.0, places=9)
        self.assertAlmostEqual(rotated.end[1], 2.0, places=9)

    def test_around_non_zero_origin_keeps_length(self):
        seg = LineSeg(start=(10, 5), end=(20, 5))
        rotated = seg.rotated(math.radians(37), origin=(10, 5))
        # l'origine coincide con lo start: quel punto resta fermo
        self.assertAlmostEqual(rotated.start[0], 10.0, places=9)
        self.assertAlmostEqual(rotated.start[1], 5.0, places=9)
        length = math.hypot(rotated.end[0] - rotated.start[0], rotated.end[1] - rotated.start[1])
        self.assertAlmostEqual(length, 10.0, places=9)


class TestArcSegRotated(unittest.TestCase):

    def test_center_and_angles_shift(self):
        seg = ArcSeg(center=(5, 0), radius=3, start_angle=0.0, end_angle=math.pi / 2, ccw=True)
        rotated = seg.rotated(math.pi / 2, origin=(0, 0))
        self.assertAlmostEqual(rotated.center[0], 0.0, places=9)
        self.assertAlmostEqual(rotated.center[1], 5.0, places=9)
        self.assertAlmostEqual(rotated.radius, 3.0, places=9)
        self.assertAlmostEqual(rotated.start_angle, math.pi / 2, places=9)
        self.assertAlmostEqual(rotated.end_angle, math.pi, places=9)
        self.assertEqual(rotated.ccw, seg.ccw)

    def test_discretized_points_match_manual_rotation(self):
        seg = ArcSeg(center=(0, 0), radius=4, start_angle=0.0, end_angle=math.pi, ccw=True)
        angle = math.radians(30)
        rotated = seg.rotated(angle, origin=(0, 0))
        for (x, y), (rx, ry) in zip(seg.discretize(0.01), rotated.discretize(0.01)):
            ex = x * math.cos(angle) - y * math.sin(angle)
            ey = x * math.sin(angle) + y * math.cos(angle)
            self.assertAlmostEqual(rx, ex, places=6)
            self.assertAlmostEqual(ry, ey, places=6)


class TestCircleSegRotated(unittest.TestCase):

    def test_only_center_moves(self):
        seg = CircleSeg(center=(5, 0), radius=2)
        rotated = seg.rotated(math.pi / 2, origin=(0, 0))
        self.assertAlmostEqual(rotated.center[0], 0.0, places=9)
        self.assertAlmostEqual(rotated.center[1], 5.0, places=9)
        self.assertEqual(rotated.radius, seg.radius)


class TestSplineSegRotated(unittest.TestCase):

    def test_control_points_rotate_and_back_restores_original(self):
        seg = SplineSeg(
            degree=2,
            control_points=[(0, 0), (5, 10), (10, 0)],
            knots=[0, 0, 0, 1, 1, 1],
        )
        angle = math.radians(53)
        rotated = seg.rotated(angle, origin=(2, 3))
        back = rotated.rotated(-angle, origin=(2, 3))
        for (x, y), (bx, by) in zip(seg.control_points, back.control_points):
            self.assertAlmostEqual(x, bx, places=6)
            self.assertAlmostEqual(y, by, places=6)

    def test_tangent_vector_rotates_but_not_translated_by_origin(self):
        seg = SplineSeg(
            degree=1,
            control_points=[(0, 0), (10, 0)],
            knots=[0, 0, 1, 1],
            start_tangent=(1.0, 0.0, 0.0),
        )
        rotated = seg.rotated(math.pi / 2, origin=(100, 100))
        # vettore direzione: ruota solo, mai traslato dall'origine di rotazione
        self.assertAlmostEqual(rotated.start_tangent[0], 0.0, places=9)
        self.assertAlmostEqual(rotated.start_tangent[1], 1.0, places=9)
        self.assertAlmostEqual(rotated.start_tangent[2], 0.0, places=9)


class TestEllipseSegRotated(unittest.TestCase):

    def test_center_and_major_axis_rotate(self):
        seg = EllipseSeg(center=(5, 0), major_axis=(2, 0), ratio=0.5,
                          start_param=0.0, end_param=2 * math.pi)
        rotated = seg.rotated(math.pi / 2, origin=(0, 0))
        self.assertAlmostEqual(rotated.center[0], 0.0, places=9)
        self.assertAlmostEqual(rotated.center[1], 5.0, places=9)
        self.assertAlmostEqual(rotated.major_axis[0], 0.0, places=9)
        self.assertAlmostEqual(rotated.major_axis[1], 2.0, places=9)
        self.assertEqual(rotated.ratio, seg.ratio)
        self.assertEqual(rotated.start_param, seg.start_param)
        self.assertEqual(rotated.end_param, seg.end_param)

    def test_endpoints_match_manual_rotation(self):
        seg = EllipseSeg(center=(1, 1), major_axis=(4, 0), ratio=0.5,
                          start_param=0.0, end_param=math.pi / 2)
        angle = math.radians(45)
        rotated = seg.rotated(angle, origin=(1, 1))
        start, end = segment_endpoints(seg)
        rstart, rend = segment_endpoints(rotated)

        def _rot(pt, origin):
            ox, oy = origin
            x, y = pt[0] - ox, pt[1] - oy
            return (ox + x * math.cos(angle) - y * math.sin(angle),
                    oy + x * math.sin(angle) + y * math.cos(angle))

        ex, ey = _rot(start, (1, 1))
        self.assertAlmostEqual(rstart[0], ex, places=6)
        self.assertAlmostEqual(rstart[1], ey, places=6)


if __name__ == "__main__":
    unittest.main()
