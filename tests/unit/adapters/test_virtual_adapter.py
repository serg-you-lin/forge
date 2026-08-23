"""
test_virtual_adapter.py
-----------------------
Test unitari per adapters/dxf/virtual_adapter.py.

Testa il parsing di entità ezdxf mock → primitive pure,
e il routing _loop_to_contour → DxfWriteContext.
"""

import unittest
from unittest.mock import MagicMock, patch
import math

from forge.core.primitives import LineSeg, ArcSeg, SplineSeg
from forge.model import Edge
from forge.adapters.dxf.virtual_adapter import (
    DxfEntityDispatcher, 
    parse_loop, 
    _loop_to_contour, 
    DxfWriteContext,
    _BulgeSeg,
)


# ---------------------------------------------------------------------------
# Helper — entità DXF mock
# ---------------------------------------------------------------------------

def make_line(x1, y1, x2, y2, layer="0"):
    e = MagicMock()
    e.dxftype.return_value = 'LINE'
    e.dxf.start.x = x1
    e.dxf.start.y = y1
    e.dxf.end.x = x2
    e.dxf.end.y = y2
    e.dxf.layer = layer
    return e


def make_arc(cx, cy, radius, start_angle, end_angle, layer="0"):
    e = MagicMock()
    e.dxftype.return_value = 'ARC'
    e.dxf.center.x = cx
    e.dxf.center.y = cy
    e.dxf.radius = radius
    e.dxf.start_angle = start_angle
    e.dxf.end_angle = end_angle
    e.dxf.layer = layer
    return e


def make_lwpolyline(points_with_bulge, layer="0"):
    """
    Crea una LWPOLYLINE mock.
    points_with_bulge: lista di tuple (x, y, bulge)
    """
    e = MagicMock()
    e.dxftype.return_value = 'LWPOLYLINE'
    e.get_points.return_value = points_with_bulge
    e.dxf.layer = layer
    return e


def make_spline_entity(points, layer="0"):
    e = MagicMock()
    e.dxftype.return_value = 'SPLINE'
    e._mock_points = points
    e.dxf.layer = layer
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
# DxfEntityDispatcher — dispatch centralizzato per tipo entità DXF
# ---------------------------------------------------------------------------

class TestDxfEntityDispatcher(unittest.TestCase):

    def test_001_dispatches_known_types(self):
        self.assertEqual(DxfEntityDispatcher(make_line(0, 0, 10, 0)).kind, 'LINE')
        self.assertEqual(DxfEntityDispatcher(make_arc(0, 0, 10, 0, 180)).kind, 'ARC')
        self.assertEqual(
            DxfEntityDispatcher(make_spline_entity([(0, 0), (10, 10), (20, 0)])).kind,
            'SPLINE'
        )
        self.assertEqual(
            DxfEntityDispatcher(make_lwpolyline([(0, 0, 0), (10, 0, 0)])).kind,
            'LWPOLYLINE'
        )

    def test_002_dispatch_to_parse_line(self):
        parsed = DxfEntityDispatcher(make_line(0, 0, 10, 0)).parse(rev=False)
        self.assertIsInstance(parsed, LineSeg)
        self.assertEqual(parsed.start, (0.0, 0.0))
        self.assertEqual(parsed.end, (10.0, 0.0))

    def test_003_dispatch_to_parse_arc(self):
        parsed = DxfEntityDispatcher(
            make_arc(0, 0, 10, 0, 180)
        ).parse(rev=False)
        self.assertIsInstance(parsed, ArcSeg)
        self.assertEqual(parsed.center, (0.0, 0.0))
        self.assertEqual(parsed.radius, 10.0)
        self.assertAlmostEqual(parsed.start_angle, 0.0)
        self.assertAlmostEqual(parsed.end_angle, math.pi)

    def test_004_dispatch_to_parse_circle(self):
        e = MagicMock()
        e.dxftype.return_value = 'CIRCLE'
        e.dxf.center.x = 0.0
        e.dxf.center.y = 0.0
        e.dxf.radius = 10.0
        parsed = DxfEntityDispatcher(e).parse(rev=False)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)
        self.assertIsInstance(parsed[0], ArcSeg)
        self.assertIsInstance(parsed[1], ArcSeg)

    def test_005_dispatch_to_parse_lwpolyline(self):
        parsed = DxfEntityDispatcher(
            make_lwpolyline([(0, 0, 0), (10, 0, 0), (10, 10, 0)])
        ).parse(rev=False)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 3)
        self.assertIsInstance(parsed[0], LineSeg)
        self.assertEqual(parsed[0].start, (0.0, 0.0))
        self.assertEqual(parsed[0].end, (10.0, 0.0))

    def test_006_dispatch_unknown_type_returns_none(self):
        e = MagicMock()
        e.dxftype.return_value = 'UNKNOWN'
        parsed = DxfEntityDispatcher(e).parse(rev=False)
        self.assertIsNone(parsed)

    def test_007_line_reversed(self):
        parsed = DxfEntityDispatcher(make_line(0, 0, 10, 0)).parse(rev=True)
        self.assertIsInstance(parsed, LineSeg)
        self.assertEqual(parsed.start, (10.0, 0.0))
        self.assertEqual(parsed.end, (0.0, 0.0))


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
        self.assertEqual(self.primitives[0].end, (100.0, 0.0))

    def test_004_line_reversed(self):
        entity = make_line(0, 0, 100, 0)
        loop = [
            (make_edge(entity), True),
            (make_edge(make_line(0, 0, 0, 100)), False),
            (make_edge(make_line(0, 100, 100, 100)), False),
            (make_edge(make_line(100, 100, 100, 0)), False),
        ]
        prims = parse_loop(loop)
        self.assertEqual(prims[0].start, (100.0, 0.0))
        self.assertEqual(prims[0].end, (0.0, 0.0))


# ---------------------------------------------------------------------------
# parse_loop — loop con ARC
# ---------------------------------------------------------------------------

class TestParseLoopArc(unittest.TestCase):

    def _make_arc_loop(self):
        arc = make_arc(
            cx=50, cy=0, radius=50,
            start_angle=0, end_angle=180
        )
        return [
            (make_edge(arc), False),
            (make_edge(make_line(0, 0, 100, 0)), False),
        ]

    def test_001_arco_produce_arcseg(self):
        prims = parse_loop(self._make_arc_loop())
        arc_prims = [p for p in prims if isinstance(p, ArcSeg)]
        self.assertEqual(len(arc_prims), 1)
        self.assertEqual(arc_prims[0].center, (50.0, 0.0))
        self.assertEqual(arc_prims[0].radius, 50.0)

    def test_002_arco_reversed(self):
        arc = make_arc(
            cx=50, cy=0, radius=50,
            start_angle=0, end_angle=180
        )
        loop = [
            (make_edge(arc), True),
            (make_edge(make_line(0, 0, 100, 0)), False),
        ]
        prims = parse_loop(loop)
        arc_prims = [p for p in prims if isinstance(p, ArcSeg)]
        self.assertEqual(len(arc_prims), 1)
        # Verifica che gli angoli siano scambiati
        self.assertAlmostEqual(arc_prims[0].start_angle, math.pi)
        self.assertAlmostEqual(arc_prims[0].end_angle, 0.0)


# ---------------------------------------------------------------------------
# parse_loop — loop con LWPOLYLINE (bulge)
# ---------------------------------------------------------------------------

class TestParseLoopPolyline(unittest.TestCase):

    def test_001_lwpolyline_singola_produce_primitives(self):
        polyline = make_lwpolyline([
            (0, 0, 0),
            (10, 0, 0.5),  # bulge positivo
            (10, 10, 0),
            (0, 10, 0),
        ])
        loop = [(make_edge(polyline), False)]
        primitives = parse_loop(loop)
        
        self.assertEqual(len(primitives), 4)
        self.assertIsInstance(primitives[0], LineSeg)
        self.assertIsInstance(primitives[1], _BulgeSeg)
        self.assertIsInstance(primitives[2], LineSeg)
        self.assertIsInstance(primitives[3], LineSeg)
        
        # Verifica bulge
        self.assertEqual(primitives[1].start, (10.0, 0.0))
        self.assertEqual(primitives[1].end, (10.0, 10.0))
        self.assertAlmostEqual(primitives[1].bulge, 0.5)

    def test_002_lwpolyline_reversed(self):
        polyline = make_lwpolyline([
            (0, 0, 0),
            (10, 0, 0.5),
            (10, 10, 0),
        ])
        loop = [(make_edge(polyline), True)]
        primitives = parse_loop(loop)
        
        self.assertEqual(len(primitives), 3)
        # Bulge dovrebbe essere negato e spostato
        self.assertIsInstance(primitives[0], LineSeg)
        self.assertIsInstance(primitives[1], _BulgeSeg)
        self.assertAlmostEqual(primitives[1].bulge, -0.5)


# ---------------------------------------------------------------------------
# parse_loop — loop con SPLINE (solo parsing, senza build_polygon)
# ---------------------------------------------------------------------------

class TestParseLoopSpline(unittest.TestCase):

    def _make_spline_loop(self):
        spline = make_spline_entity([(0,0), (0,50), (0,100)])
        return [
            (make_edge(spline), False),
            (make_edge(make_line(0, 100, 100, 100)), False),
            (make_edge(make_line(100, 100, 100, 0)), False),
            (make_edge(make_line(100, 0, 0, 0)), False),
        ]

    def test_001_spline_produce_splineseg(self):
        with patch('forge.adapters.dxf.virtual_adapter._parse_spline',
           side_effect=lambda entity, rev: SplineSeg(
               degree=0,
               control_points=entity._mock_points if not rev else list(reversed(entity._mock_points)),
               knots=[],
               weights=None
           )):
            primitives = parse_loop(self._make_spline_loop())
        spline_prims = [p for p in primitives if isinstance(p, SplineSeg)]
        self.assertEqual(len(spline_prims), 1)
        self.assertEqual(spline_prims[0].control_points, [(0,0), (0,50), (0,100)])


# ---------------------------------------------------------------------------
# _loop_to_contour — restituisce DxfWriteContext
# ---------------------------------------------------------------------------

class TestLoopToContour(unittest.TestCase):

    def test_001_loop_line_restituisce_dxf_write_context(self):
        ctx = _loop_to_contour(make_square_loop(100.0), 'outer', 1)
        self.assertIsInstance(ctx, DxfWriteContext)

    def test_002_ctx_ha_area_corretta(self):
        ctx = _loop_to_contour(make_square_loop(100.0), 'outer', 1)
        self.assertAlmostEqual(ctx.polygon.area, 10000.0, delta=1.0)

    def test_003_loop_line_has_spline_false(self):
        ctx = _loop_to_contour(make_square_loop(100.0), 'outer', 1)
        self.assertFalse(ctx.has_spline)

    def test_004_ctx_ha_pts_with_bulge(self):
        ctx = _loop_to_contour(make_square_loop(100.0), 'outer', 1)
        self.assertGreater(len(ctx.pts_with_bulge), 0)
        # Verifica formato tuple (x, y, start_width, end_width, bulge)
        self.assertEqual(len(ctx.pts_with_bulge[0]), 5)

    def test_005_ctx_ha_loop(self):
        loop = make_square_loop(100.0)
        ctx = _loop_to_contour(loop, 'outer', 1)
        self.assertEqual(ctx.loop, loop)

    def test_006_ctx_ha_layer_e_color(self):
        ctx = _loop_to_contour(make_square_loop(100.0), 'outer', 2)
        self.assertEqual(ctx.layer, 'outer')
        self.assertEqual(ctx.color, 2)

    def test_007_loop_spline_ha_has_spline_true(self):
        """
        Testa che il flag has_spline venga settato correttamente.
        Mocka build_polygon per evitare NotImplementedError.
        """
        spline = make_spline_entity([(0,0), (0,50), (0,100)])
        loop = [
            (make_edge(spline), False),
            (make_edge(make_line(0, 100, 100, 100)), False),
            (make_edge(make_line(100, 100, 100, 0)), False),
            (make_edge(make_line(100, 0, 0, 0)), False),
        ]
        with patch('forge.adapters.dxf.virtual_adapter._parse_spline',
                side_effect=lambda entity, rev: SplineSeg(
                    degree=0,
                    control_points=entity._mock_points if not rev else list(reversed(entity._mock_points)),
                    knots=[],
                    weights=None
                )), \
            patch('forge.adapters.dxf.virtual_adapter.build_polygon',
                return_value=MagicMock()):
            ctx = _loop_to_contour(loop, 'outer', 1)
        self.assertTrue(ctx.has_spline)

    def test_008_loop_spline_pts_with_bulge_vuoto(self):
        """
        Testa che pts_with_bulge sia vuoto quando ci sono spline.
        Mocka build_polygon per evitare NotImplementedError.
        """
        spline = make_spline_entity([(0,0), (0,50), (0,100)])
        loop = [
            (make_edge(spline), False),
            (make_edge(make_line(0, 100, 100, 100)), False),
            (make_edge(make_line(100, 100, 100, 0)), False),
            (make_edge(make_line(100, 0, 0, 0)), False),
        ]
        with patch('forge.adapters.dxf.virtual_adapter._parse_spline',
                side_effect=lambda entity, rev: SplineSeg(
                    degree=0,
                    control_points=entity._mock_points if not rev else list(reversed(entity._mock_points)),
                    knots=[],
                    weights=None
                )), \
            patch('forge.adapters.dxf.virtual_adapter.build_polygon',
                return_value=MagicMock()):
            ctx = _loop_to_contour(loop, 'outer', 1)
        self.assertEqual(ctx.pts_with_bulge, [])

    def test_009_loop_vuoto_restituisce_none(self):
        ctx = _loop_to_contour([], 'outer', 1)
        self.assertIsNone(ctx)

    def test_010_loop_una_line_restituisce_none(self):
        loop = [(make_edge(make_line(0, 0, 10, 0)), False)]
        ctx = _loop_to_contour(loop, 'outer', 1)
        self.assertIsNone(ctx)

    def test_011_ctx_con_bulge_ha_pts_with_bulge_corretti(self):
        polyline = make_lwpolyline([
            (0, 0, 0),
            (10, 0, 0.5),
            (10, 10, 0),
            (0, 10, 0),
        ])
        loop = [(make_edge(polyline), False)]
        ctx = _loop_to_contour(loop, 'outer', 1)
        
        self.assertIsNotNone(ctx)
        self.assertFalse(ctx.has_spline)
        self.assertGreater(len(ctx.pts_with_bulge), 0)
        # Verifica che ci sia almeno un punto con bulge
        bulge_points = [p for p in ctx.pts_with_bulge if p[4] != 0.0]
        self.assertEqual(len(bulge_points), 1)
        self.assertAlmostEqual(bulge_points[0][4], 0.5)

    def test_012_ctx_origin_da_loop(self):
        """
        Testa che origin venga estratto correttamente dal layer delle entità.
        Nota: _extract_origin legge da edge.source_ref.dxf.layer
        """
        loop = make_square_loop(100.0)
        # Modifica il layer delle entità sorgente (non dell'edge)
        for edge, _ in loop:
            edge.source_ref.dxf.layer = 'test_layer'
        ctx = _loop_to_contour(loop, 'outer', 1)
        self.assertEqual(ctx.origin, 'test_layer')

    def test_013_ctx_origin_vuoto_se_layers_diversi(self):
        """
        Testa che origin sia vuoto quando le entità hanno layers diversi.
        """
        loop = make_square_loop(100.0)
        # Imposta layers diversi sulle entità sorgente
        for i, (edge, _) in enumerate(loop):
            edge.source_ref.dxf.layer = f'layer_{i}'
        ctx = _loop_to_contour(loop, 'outer', 1)
        self.assertEqual(ctx.origin, '')


if __name__ == "__main__":
    unittest.main(verbosity=2)