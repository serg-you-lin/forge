

"""
test_virtual_adapter.py
-----------------------
Test unitari per adapters/dxf/virtual_adapter.py.

Testa il parsing di entità ezdxf mock → primitive pure,
e il routing _loop_to_virtual_shape → DxfWriteContext.
"""

import unittest
from unittest.mock import MagicMock, patch

from forge.core.primitives import LineSeg, ArcSeg, SplineSeg, DiscretizedArcSeg
from forge.core.primitives.contour import Contour
from forge.model import Edge
from forge.adapters.dxf.virtual_adapter import (
    parse_loop, _loop_to_contour, DxfWriteContext,
)


# ---------------------------------------------------------------------------
# Helper — entità DXF mock
# ---------------------------------------------------------------------------

def make_line(x1, y1, x2, y2, layer="0"):
    e = MagicMock()
    e.dxftype.return_value = 'LINE'
    e.dxf.start.x = x1; e.dxf.start.y = y1
    e.dxf.end.x   = x2; e.dxf.end.y   = y2
    e.dxf.layer   = layer
    return e


def make_arc(cx, cy, radius, start_angle, end_angle, layer="0"):
    e = MagicMock()
    e.dxftype.return_value = 'ARC'
    e.dxf.center.x    = cx;     e.dxf.center.y    = cy
    e.dxf.radius      = radius
    e.dxf.start_angle = start_angle
    e.dxf.end_angle   = end_angle
    e.dxf.layer       = layer
    return e


def make_spline_entity(points, layer="0"):
    e = MagicMock()
    e.dxftype.return_value = 'SPLINE'
    e._mock_points = points
    e.dxf.layer    = layer
    return e


def make_edge(entity, layer="0"):
    return Edge(source_ref=entity, layer=layer, start=(0.0, 0.0), end=(0.0, 0.0))


def make_square_loop(side=100.0):
    s = side
    return [
        (make_edge(make_line(0, 0, s, 0)), False),
        (make_edge(make_line(s, 0, s, s)), False),
        (make_edge(make_line(s, s, 0, s)), False),
        (make_edge(make_line(0, s, 0, 0)), False),
    ]


# ---------------------------------------------------------------------------
# parse_loop — loop di sole LINE
# ---------------------------------------------------------------------------

class TestParseLoopLines(unittest.TestCase):

    def setUp(self):
        self.primitives = parse_loop(make_square_loop(100.0))

    def test_001_numero_primitive(self):
        self.assertEqual(len(self.primitives), 4)

    def test_002_tutte_lineseg(self):
        for p in self.primitives:
            self.assertIsInstance(p, LineSeg)

    def test_003_coordinate_corrette(self):
        self.assertEqual(self.primitives[0].start, (0.0, 0.0))
        self.assertEqual(self.primitives[0].end,   (100.0, 0.0))

    def test_004_line_reversed(self):
        entity = make_line(0, 0, 100, 0)
        loop = [(make_edge(entity), True),
                (make_edge(make_line(0, 0, 0, 100)), False),
                (make_edge(make_line(0, 100, 100, 100)), False),
                (make_edge(make_line(100, 100, 100, 0)), False)]
        prims = parse_loop(loop)
        self.assertEqual(prims[0].start, (100.0, 0.0))
        self.assertEqual(prims[0].end,   (0.0, 0.0))


# ---------------------------------------------------------------------------
# parse_loop — loop con ARC (senza spline → ArcSeg)
# ---------------------------------------------------------------------------

class TestParseLoopArc(unittest.TestCase):

    def _make_arc_loop(self):
        arc = make_arc(cx=50, cy=0, radius=50,
                       start_angle=0, end_angle=180)
        arc.start_point.x = 100.0; arc.start_point.y = 0.0
        arc.end_point.x   = 0.0;   arc.end_point.y   = 0.0
        return [
            (make_edge(arc),                          False),
            (make_edge(make_line(0, 0, 100, 0)),      False),
        ]

    def test_001_arco_senza_spline_produce_arcseg(self):
        with patch('forge.adapters.dxf.virtual_adapter.arc_to_bulge',
                   return_value=(None, None, 1.0)):
            prims = parse_loop(self._make_arc_loop())
        arc_prims = [p for p in prims if isinstance(p, ArcSeg)]
        self.assertEqual(len(arc_prims), 1)

    def test_002_arco_senza_spline_non_produce_discretized(self):
        with patch('forge.adapters.dxf.virtual_adapter.arc_to_bulge',
                   return_value=(None, None, 1.0)):
            prims = parse_loop(self._make_arc_loop())
        self.assertFalse(any(isinstance(p, DiscretizedArcSeg) for p in prims))


# ---------------------------------------------------------------------------
# parse_loop — loop con SPLINE (ARC → DiscretizedArcSeg)
# ---------------------------------------------------------------------------

class TestParseLoopSpline(unittest.TestCase):

    def _make_spline_loop(self):
        spline = make_spline_entity([(0,0),(0,50),(0,100)])
        arc = make_arc(cx=50, cy=100, radius=50,
                       start_angle=180, end_angle=0)
        arc.start_point.x = 0.0;   arc.start_point.y = 100.0
        arc.end_point.x   = 100.0; arc.end_point.y   = 100.0
        return [
            (make_edge(spline),                       False),
            (make_edge(arc),                          False),
            (make_edge(make_line(100, 100, 100, 0)),  False),
            (make_edge(make_line(100, 0, 0, 0)),      False),
        ]

    def setUp(self):
        fake_arc_pts = [(0.0, 100.0), (50.0, 150.0), (100.0, 100.0)]
        with patch('forge.adapters.dxf.virtual_adapter.spline_to_points',
                   side_effect=lambda e: e._mock_points), \
             patch('forge.adapters.dxf.virtual_adapter.arc_to_bulge',
                   return_value=(None, None, 1.0)), \
             patch('forge.adapters.dxf.virtual_adapter.arc_to_linestrings',
                   return_value=[MagicMock(coords=fake_arc_pts)]), \
             patch('forge.adapters.dxf.virtual_adapter.num_segments_for_bulge',
                   return_value=3):
            self.primitives = parse_loop(self._make_spline_loop())

    def test_001_spline_produce_splineseg(self):
        self.assertTrue(any(isinstance(p, SplineSeg) for p in self.primitives))

    def test_002_arco_in_loop_spline_produce_discretized(self):
        self.assertTrue(any(isinstance(p, DiscretizedArcSeg) for p in self.primitives))

    def test_003_nessun_arcseg_in_loop_spline(self):
        self.assertFalse(any(isinstance(p, ArcSeg) for p in self.primitives))


# ---------------------------------------------------------------------------
# _loop_to_virtual_shape — restituisce DxfWriteContext
# ---------------------------------------------------------------------------

class TestLoopToVirtualShape(unittest.TestCase):

    def test_001_loop_line_restituisce_dxf_write_context(self):
        ctx = _loop_to_contour(make_square_loop(100.0), 'outer', 1)
        self.assertIsInstance(ctx, DxfWriteContext)

    def test_002_ctx_ha_vs_virtual_shape(self):
        ctx = _loop_to_contour(make_square_loop(100.0), 'outer', 1)
        self.assertIsInstance(ctx.contour, Contour)

    def test_003_loop_line_has_spline_false(self):
        ctx = _loop_to_contour(make_square_loop(100.0), 'outer', 1)
        self.assertFalse(ctx.contour.has_spline)

    def test_004_ctx_ha_pts_with_bulge(self):
        ctx = _loop_to_contour(make_square_loop(100.0), 'outer', 1)
        self.assertGreater(len(ctx.pts_with_bulge), 0)

    def test_005_ctx_ha_loop(self):
        loop = make_square_loop(100.0)
        ctx = _loop_to_contour(loop, 'outer', 1)
        self.assertEqual(ctx.loop, loop)

    def test_006_loop_spline_ha_has_spline_true(self):
        spline = make_spline_entity([(0,0),(0,50),(0,100)])
        loop = [
            (make_edge(spline),                          False),
            (make_edge(make_line(0, 100, 100, 100)),     False),
            (make_edge(make_line(100, 100, 100, 0)),     False),
            (make_edge(make_line(100, 0, 0, 0)),         False),
        ]
        with patch('forge.adapters.dxf.virtual_adapter.spline_to_points',
                   side_effect=lambda e: e._mock_points):
            ctx = _loop_to_contour(loop, 'outer', 1)
        self.assertTrue(ctx.contour.has_spline)

    def test_007_loop_spline_pts_with_bulge_vuoto(self):
        spline = make_spline_entity([(0,0),(0,50),(0,100)])
        loop = [
            (make_edge(spline),                          False),
            (make_edge(make_line(0, 100, 100, 100)),     False),
            (make_edge(make_line(100, 100, 100, 0)),     False),
            (make_edge(make_line(100, 0, 0, 0)),         False),
        ]
        with patch('forge.adapters.dxf.virtual_adapter.spline_to_points',
                   side_effect=lambda e: e._mock_points):
            ctx = _loop_to_contour(loop, 'outer', 1)
        self.assertEqual(ctx.pts_with_bulge, [])

    def test_008_loop_vuoto_restituisce_none(self):
        ctx = _loop_to_contour([], 'outer', 1)
        self.assertIsNone(ctx)

    def test_009_loop_una_line_restituisce_none(self):
        loop = [(make_edge(make_line(0, 0, 10, 0)), False)]
        ctx = _loop_to_contour(loop, 'outer', 1)
        self.assertIsNone(ctx)


if __name__ == "__main__":
    unittest.main(verbosity=2)