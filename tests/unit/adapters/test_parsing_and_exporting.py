"""
test_parsing_and_exporting.py
-------------------
Test unitari per adapters/dxf/parser.py e adapters/dxf/exporter.py.

Testa il parsing di entità ezdxf mock → primitive pure,
l'esportazione primitive → DXF, e il routing parse_loop.
"""

import unittest
from unittest.mock import MagicMock, patch
import math

from forge.core.primitives import LineSeg, ArcSeg, SplineSeg
from forge.adapters.bridge.edge import Edge
from forge.adapters.dxf.parser import (
    DxfEntityDispatcher,
    parse_loop,
)
from forge.adapters.dxf.exporter import (
    arc_seg_to_bulge,
    segments_to_pts_with_bulge,
    write_contour_to_msp,
)
from forge.model.role import ContourRole

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


def make_lwpolyline(points_with_bulge, layer="0", is_closed=True):
    """
    Crea una LWPOLYLINE mock.
    points_with_bulge: lista di tuple (x, y, bulge)
    """
    e = MagicMock()
    e.dxftype.return_value = 'LWPOLYLINE'
    e.get_points.return_value = points_with_bulge
    e.dxf.layer = layer
    e.closed = is_closed
    e.is_closed = is_closed
    return e


def make_polyline(vertices, layer="0", is_closed=True):
    """Crea una POLYLINE mock (3D)."""
    e = MagicMock()
    e.dxftype.return_value = 'POLYLINE'
    e.dxf.layer = layer
    e.closed = is_closed
    e.is_closed = is_closed
    
    mock_vertices = []
    for x, y, bulge in vertices:
        v = MagicMock()
        v.dxf.location.x = x
        v.dxf.location.y = y
        getattr(v.dxf, "bulge", 0.0)  # per mockare l'attributo
        v.dxf.bulge = bulge
        mock_vertices.append(v)
    e.vertices = mock_vertices
    return e


def make_spline_entity(points, layer="0"):
    e = MagicMock()
    e.dxftype.return_value = 'SPLINE'
    e._mock_points = points
    e.dxf.layer = layer
    
    def mock_flattening(tolerance):
        return [(p[0], p[1], 0.0) for p in points]
    e.flattening = mock_flattening
    return e


def make_circle(cx, cy, radius, layer="0"):
    e = MagicMock()
    e.dxftype.return_value = 'CIRCLE'
    e.dxf.center.x = cx
    e.dxf.center.y = cy
    e.dxf.radius = radius
    e.dxf.layer = layer
    return e


def make_edge(entity, layer="0"):
    """Crea un Edge con segmento LineSeg di default."""
    return Edge(
        source_ref=entity,
        role=ContourRole.UNKNOWN,
        start=(0.0, 0.0),
        end=(0.0, 0.0),
        segment=LineSeg(start=(0.0, 0.0), end=(0.0, 0.0)),
    )


def make_square_loop(side=100.0):
    s = side
    return [
        (make_edge(make_line(0, 0, s, 0)), False),
        (make_edge(make_line(s, 0, s, s)), False),
        (make_edge(make_line(s, s, 0, s)), False),
        (make_edge(make_line(0, s, 0, 0)), False),
    ]


class MockMSP:
    """Mock per ezdxf ModelSpace."""
    def __init__(self):
        self.doc = MagicMock()
        self.doc.dxfversion = "AC1015"
        self.entities = []
    
    def add_lwpolyline(self, pts, format="xyseb", dxfattribs=None, close=True):
        self.entities.append({
            'type': 'LWPOLYLINE',
            'points': pts,
            'format': format,
            'dxfattribs': dxfattribs,
            'close': close
        })
        return MagicMock()
    
    def add_polyline2d(self, pts, dxfattribs=None):
        self.entities.append({
            'type': 'POLYLINE2D',
            'points': pts,
            'dxfattribs': dxfattribs
        })
        return MagicMock()


# ===========================================================================
# TESTS: DxfEntityDispatcher
# ===========================================================================

class TestDxfEntityDispatcher(unittest.TestCase):
    """Test del dispatcher per tipo entità DXF."""

    def test_001_riconosce_tipi_noti(self):
        """Il dispatcher riconosce correttamente i tipi DXF."""
        self.assertEqual(DxfEntityDispatcher(make_line(0, 0, 10, 0)).kind, 'LINE')
        self.assertEqual(DxfEntityDispatcher(make_arc(0, 0, 10, 0, 180)).kind, 'ARC')
        self.assertEqual(
            DxfEntityDispatcher(make_spline_entity([(0, 0), (10, 10)])).kind,
            'SPLINE'
        )
        self.assertEqual(
            DxfEntityDispatcher(make_lwpolyline([(0, 0, 0), (10, 0, 0)])).kind,
            'LWPOLYLINE'
        )
        self.assertEqual(
            DxfEntityDispatcher(make_circle(0, 0, 10)).kind,
            'CIRCLE'
        )

    def test_002_parse_line(self):
        """Parsing di una LINE → LineSeg."""
        parsed = DxfEntityDispatcher(make_line(0, 0, 10, 0)).parse(rev=False)
        self.assertIsInstance(parsed, LineSeg)
        self.assertEqual(parsed.start, (0.0, 0.0))
        self.assertEqual(parsed.end, (10.0, 0.0))

    def test_003_parse_line_reversed(self):
        """Parsing di una LINE con rev=True inverte start/end."""
        parsed = DxfEntityDispatcher(make_line(0, 0, 10, 0)).parse(rev=True)
        self.assertIsInstance(parsed, LineSeg)
        self.assertEqual(parsed.start, (10.0, 0.0))
        self.assertEqual(parsed.end, (0.0, 0.0))

    def test_004_parse_arc(self):
        """Parsing di un ARC → ArcSeg."""
        parsed = DxfEntityDispatcher(
            make_arc(0, 0, 10, 0, 180)
        ).parse(rev=False)
        self.assertIsInstance(parsed, ArcSeg)
        self.assertEqual(parsed.center, (0.0, 0.0))
        self.assertEqual(parsed.radius, 10.0)
        self.assertAlmostEqual(parsed.start_angle, 0.0)
        self.assertAlmostEqual(parsed.end_angle, math.pi)
        self.assertTrue(parsed.ccw)

    def test_005_parse_arc_reversed(self):
        """Parsing di un ARC con rev=True inverte ccw e angoli."""
        parsed = DxfEntityDispatcher(
            make_arc(0, 0, 10, 0, 180)
        ).parse(rev=True)
        self.assertIsInstance(parsed, ArcSeg)
        self.assertAlmostEqual(parsed.start_angle, math.pi)
        self.assertAlmostEqual(parsed.end_angle, 0.0)
        self.assertFalse(parsed.ccw)

    def test_006_parse_circle(self):
        """Parsing di un CIRCLE → CircleSeg (primitiva geometrica pura)."""
        parsed = DxfEntityDispatcher(make_circle(0, 0, 10)).parse(rev=False)
        from forge.core.primitives import CircleSeg
        self.assertIsInstance(parsed, CircleSeg)
        self.assertEqual(parsed.center, (0.0, 0.0))
        self.assertEqual(parsed.radius, 10.0)

    def test_007_parse_lwpolyline_senza_bulge(self):
        """LWPOLYLINE senza bulge → LineSeg."""
        parsed = DxfEntityDispatcher(
            make_lwpolyline([(0, 0, 0), (10, 0, 0), (10, 10, 0)], is_closed=False)
        ).parse(rev=False)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)  # N-1 segmenti
        self.assertIsInstance(parsed[0], LineSeg)

    def test_008_parse_lwpolyline_con_bulge(self):
        """LWPOLYLINE con bulge → ArcSeg."""
        parsed = DxfEntityDispatcher(
            make_lwpolyline([
                (0, 0, 0),
                (10, 0, 1.0),  # bulge=1 → arco 180°
                (10, 10, 0),
            ], is_closed=False)
        ).parse(rev=False)
        
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)
        self.assertIsInstance(parsed[0], LineSeg)
        self.assertIsInstance(parsed[1], ArcSeg)
        
        # bulge=1, start=(10,0), end=(10,10) 
        # sweep = 4*atan(1) = π (180°)
        # half_chord = 5, radius = 5, d = 0
        # centro = (10, 5)
        self.assertAlmostEqual(parsed[1].center[0], 10.0)
        self.assertAlmostEqual(parsed[1].center[1], 5.0)
        self.assertAlmostEqual(parsed[1].radius, 5.0)

    def test_009_parse_lwpolyline_chiusa(self):
        """LWPOLYLINE chiusa: N punti → N segmenti."""
        parsed = DxfEntityDispatcher(
            make_lwpolyline([
                (0, 0, 0),
                (10, 0, 0),
                (10, 10, 0),
            ], is_closed=True)
        ).parse(rev=False)
        
        self.assertEqual(len(parsed), 3)  # N segmenti (chiusa)

    def test_010_parse_polyline_3d(self):
        """Parsing di POLYLINE 3D con bulge."""
        parsed = DxfEntityDispatcher(
            make_polyline([
                (0, 0, 0),
                (10, 0, 1.0),
                (10, 10, 0),
            ], is_closed=False)
        ).parse(rev=False)
        
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)
        self.assertIsInstance(parsed[0], LineSeg)
        self.assertIsInstance(parsed[1], ArcSeg)

    def test_011_parse_tipo_sconosciuto_restituisce_none(self):
        """Tipo DXF sconosciuto → None."""
        e = MagicMock()
        e.dxftype.return_value = 'UNKNOWN'
        parsed = DxfEntityDispatcher(e).parse(rev=False)
        self.assertIsNone(parsed)


# ===========================================================================
# TESTS: parse_loop
# ===========================================================================

class TestParseLoop(unittest.TestCase):
    """Test del routing parse_loop su loop di Edge."""

    def test_001_loop_vuoto(self):
        """Loop vuoto → lista vuota."""
        self.assertEqual(parse_loop([]), [])

    def test_002_loop_line_singola(self):
        """Loop con una LINE → un LineSeg."""
        loop = [(make_edge(make_line(0, 0, 10, 0)), False)]
        result = parse_loop(loop)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], LineSeg)

    def test_003_loop_quadrato(self):
        """Loop quadrato → 4 LineSeg."""
        primitives = parse_loop(make_square_loop(100.0))
        self.assertEqual(len(primitives), 4)
        for p in primitives:
            self.assertIsInstance(p, LineSeg)
        self.assertEqual(primitives[0].start, (0.0, 0.0))
        self.assertEqual(primitives[0].end, (100.0, 0.0))

    def test_004_loop_con_arco(self):
        """Loop con ARC → ArcSeg."""
        arc = make_arc(50, 0, 50, 0, 180)
        loop = [
            (make_edge(arc), False),
            (make_edge(make_line(0, 0, 100, 0)), False),
        ]
        result = parse_loop(loop)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], ArcSeg)
        self.assertIsInstance(result[1], LineSeg)

    def test_005_loop_con_lwpolyline(self):
        """Loop con LWPOLYLINE → segmenti."""
        polyline = make_lwpolyline([
            (0, 0, 0),
            (10, 0, 0.5),
            (10, 10, 0),
            (0, 10, 0),
        ], is_closed=False)
        loop = [(make_edge(polyline), False)]
        result = parse_loop(loop)
        
        self.assertEqual(len(result), 3)  # N-1 segmenti
        self.assertIsInstance(result[0], LineSeg)
        self.assertIsInstance(result[1], ArcSeg)  # bulge convertito
        self.assertIsInstance(result[2], LineSeg)

    def test_006_loop_con_lwpolyline_reversed(self):
        """Loop con LWPOLYLINE reversed → bulge negato e punti invertiti."""
        polyline = make_lwpolyline([
            (0, 0, 0),
            (10, 0, 0.5),
            (10, 10, 0),
        ], is_closed=False)
        loop = [(make_edge(polyline), True)]
        result = parse_loop(loop)
        
        self.assertEqual(len(result), 2)
        
        # Con reversal, l'ordine dei punti è invertito:
        # original: (0,0) → (10,0) → (10,10)
        # reversed: (10,10) → (10,0) → (0,0)
        # Il bulge rimane sullo stesso segmento ma invertito: (10,0)→(0,0) con bulge=0.5
        
        # Primo segmento: da (10,10) a (10,0) con bulge=0 → LineSeg
        self.assertIsInstance(result[0], LineSeg)
        self.assertEqual(result[0].start, (10.0, 10.0))
        self.assertEqual(result[0].end, (10.0, 0.0))
        
        # Secondo segmento: da (10,0) a (0,0) con bulge=0.5 → ArcSeg
        self.assertIsInstance(result[1], ArcSeg)
        start1 = (
            result[1].center[0] + result[1].radius * math.cos(result[1].start_angle),
            result[1].center[1] + result[1].radius * math.sin(result[1].start_angle)
        )
        end1 = (
            result[1].center[0] + result[1].radius * math.cos(result[1].end_angle),
            result[1].center[1] + result[1].radius * math.sin(result[1].end_angle)
        )
        self.assertAlmostEqual(start1[0], 10.0)
        self.assertAlmostEqual(start1[1], 0.0)
        self.assertAlmostEqual(end1[0], 0.0)
        self.assertAlmostEqual(end1[1], 0.0)

    def test_007_loop_con_spline(self):
        """Loop con SPLINE → SplineSeg."""
        spline = make_spline_entity([(0, 0), (0, 50), (0, 100)])
        loop = [
            (make_edge(spline), False),
            (make_edge(make_line(0, 100, 100, 100)), False),
        ]
        result = parse_loop(loop)
        spline_prims = [p for p in result if isinstance(p, SplineSeg)]
        self.assertEqual(len(spline_prims), 1)

    def test_008_loop_ottimizzazione_polyline_singola(self):
        """Loop con singola LWPOLYLINE viene ottimizzato."""
        polyline = make_lwpolyline([
            (0, 0, 0),
            (10, 0, 0),
            (10, 10, 0),
            (0, 10, 0),
        ], is_closed=True)
        loop = [(make_edge(polyline), False)]
        result = parse_loop(loop)
        self.assertEqual(len(result), 4)  # N segmenti (chiusa)


# ===========================================================================
# TESTS: arc_seg_to_bulge
# ===========================================================================

class TestArcSegToBulge(unittest.TestCase):
    """Test conversione ArcSeg → bulge DXF."""

    def test_001_bulge_90_ccw(self):
        """Arco 90° CCW → bulge = tan(π/8)."""
        arc = ArcSeg(center=(0, 0), radius=10, start_angle=0, end_angle=math.pi/2, ccw=True)
        bulge = arc_seg_to_bulge(arc)
        self.assertAlmostEqual(bulge, math.tan(math.pi/8), places=6)

    def test_002_bulge_90_cw(self):
        """Arco 90° CW → bulge = -tan(π/8)."""
        arc = ArcSeg(center=(0, 0), radius=10, start_angle=0, end_angle=math.pi/2, ccw=False)
        bulge = arc_seg_to_bulge(arc)
        self.assertAlmostEqual(bulge, -math.tan(math.pi/8), places=6)

    def test_003_bulge_180_ccw(self):
        """Arco 180° CCW → bulge = tan(π/4)."""
        arc = ArcSeg(center=(0, 0), radius=10, start_angle=0, end_angle=math.pi, ccw=True)
        bulge = arc_seg_to_bulge(arc)
        self.assertAlmostEqual(bulge, math.tan(math.pi/4), places=6)

    def test_004_bulge_negativo_per_cw(self):
        """Arco CW produce bulge negativo."""
        arc = ArcSeg(center=(0, 0), radius=10, start_angle=math.pi, end_angle=0, ccw=False)
        bulge = arc_seg_to_bulge(arc)
        self.assertLess(bulge, 0)


# ===========================================================================
# TESTS: segments_to_pts_with_bulge
# ===========================================================================

class TestSegmentsToPtsWithBulge(unittest.TestCase):
    """Test conversione segmenti → punti con bulge."""

    def test_001_line_segments(self):
        """LineSeg → bulge=0."""
        segments = [
            LineSeg(start=(0, 0), end=(10, 0)),
            LineSeg(start=(10, 0), end=(10, 10)),
        ]
        result = segments_to_pts_with_bulge(segments)
        self.assertEqual(len(result), 2)
        for pt in result:
            self.assertEqual(pt[4], 0.0)  # bulge=0

    def test_002_arc_segment(self):
        """ArcSeg → punto di partenza + bulge calcolato."""
        arc = ArcSeg(center=(0, 0), radius=10, start_angle=0, end_angle=math.pi/2, ccw=True)
        result = segments_to_pts_with_bulge([arc])
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0][0], 10.0)  # x start
        self.assertAlmostEqual(result[0][1], 0.0)   # y start
        self.assertAlmostEqual(result[0][4], math.tan(math.pi/8), places=6)

    def test_003_arc_con_start_angle_diverso(self):
        """ArcSeg con start_angle ≠ 0."""
        arc = ArcSeg(
            center=(5, 5), radius=10,
            start_angle=math.pi/4,
            end_angle=3*math.pi/4,
            ccw=True
        )
        result = segments_to_pts_with_bulge([arc])
        expected_x = 5 + 10 * math.cos(math.pi/4)
        expected_y = 5 + 10 * math.sin(math.pi/4)
        self.assertAlmostEqual(result[0][0], expected_x)
        self.assertAlmostEqual(result[0][1], expected_y)

    def test_004_segments_misti(self):
        """Segmenti misti LineSeg + ArcSeg."""
        segments = [
            LineSeg(start=(0, 0), end=(10, 0)),
            ArcSeg(center=(10, 0), radius=10, start_angle=-math.pi/2, end_angle=0, ccw=True),
        ]
        result = segments_to_pts_with_bulge(segments)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][4], 0.0)   # line → bulge 0
        self.assertNotEqual(result[1][4], 0.0)  # arc → bulge != 0


# ===========================================================================
# TESTS: write_contour_to_msp
# ===========================================================================

class TestWriteContourToMsp(unittest.TestCase):
    """Test esportazione contour su ModelSpace."""

    def setUp(self):
        self.msp = MockMSP()

    def test_001_segments_vuoti(self):
        """Segments vuoti → None."""
        contour = MagicMock()
        contour.segments = []
        result = write_contour_to_msp(self.msp, contour, "TEST")
        self.assertIsNone(result)

    def test_002_segments_con_spline(self):
        """Spline non esportabile → None."""
        contour = MagicMock()
        contour.segments = [
            SplineSeg(degree=0, control_points=[(0, 0), (10, 0)], knots=[], weights=None)
        ]
        result = write_contour_to_msp(self.msp, contour, "TEST")
        self.assertIsNone(result)

    def test_003_line_segments_soli(self):
        """Solo LineSeg → LWPOLYLINE."""
        contour = MagicMock()
        contour.segments = [
            LineSeg(start=(0, 0), end=(10, 0)),
            LineSeg(start=(10, 0), end=(10, 10)),
            LineSeg(start=(10, 10), end=(0, 10)),
            LineSeg(start=(0, 10), end=(0, 0)),
        ]
        result = write_contour_to_msp(self.msp, contour, "TEST")
        self.assertIsNotNone(result)
        self.assertEqual(len(self.msp.entities), 1)
        entity = self.msp.entities[0]
        self.assertEqual(entity['type'], 'LWPOLYLINE')
        self.assertEqual(len(entity['points']), 4)

    def test_004_con_arc_segments(self):
        """Con ArcSeg → LWPOLYLINE con bulge."""
        contour = MagicMock()
        contour.segments = [
            ArcSeg(center=(10, 0), radius=10, start_angle=0, end_angle=math.pi/2, ccw=True),
            LineSeg(start=(10, 10), end=(0, 10)),
            LineSeg(start=(0, 10), end=(0, 0)),
            LineSeg(start=(0, 0), end=(10, 0)),
        ]
        result = write_contour_to_msp(self.msp, contour, "TEST")
        self.assertIsNotNone(result)
        entity = self.msp.entities[0]
        # Primo punto = inizio arco
        self.assertAlmostEqual(entity['points'][0][0], 20.0)
        self.assertAlmostEqual(entity['points'][0][1], 0.0)
        self.assertNotEqual(entity['points'][0][4], 0.0)  # bulge != 0

    def test_005_r12_compatibility(self):
        """Versione R12 → POLYLINE2D invece di LWPOLYLINE."""
        self.msp.doc.dxfversion = "AC1009"
        contour = MagicMock()
        contour.segments = [
            LineSeg(start=(0, 0), end=(10, 0)),
            LineSeg(start=(10, 0), end=(10, 10)),
        ]
        result = write_contour_to_msp(self.msp, contour, "TEST")
        self.assertIsNotNone(result)
        entity = self.msp.entities[0]
        self.assertEqual(entity['type'], 'POLYLINE2D')


if __name__ == "__main__":
    unittest.main(verbosity=2)