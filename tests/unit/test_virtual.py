"""
test_virtual.py
---------------
Test unitari per VirtualShape e i suoi costruttori.

Questi test verificano il comportamento interno di VirtualShape
in isolamento — senza heal() né file DXF reali.

Lancia:
    python -m pytest tests/test_virtual.py -v
"""

import unittest
import math
from pathlib import Path
import sys
from unittest.mock import MagicMock

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dxf_forge.core.virtual import VirtualShape, _loop_to_virtual_shape


# ---------------------------------------------------------------------------
# Helper — costruisce entità DXF mock minimali
# ---------------------------------------------------------------------------

def make_line(x1, y1, x2, y2):
    """Crea un mock di entità LINE ezdxf."""
    entity = MagicMock()
    entity.dxftype.return_value = 'LINE'
    entity.dxf.start.x = x1
    entity.dxf.start.y = y1
    entity.dxf.end.x   = x2
    entity.dxf.end.y   = y2
    return entity


def make_arc(cx, cy, radius, start_angle, end_angle):
    """Crea un mock di entità ARC ezdxf."""
    entity = MagicMock()
    entity.dxftype.return_value = 'ARC'
    entity.dxf.center.x     = cx
    entity.dxf.center.y     = cy
    entity.dxf.radius       = radius
    entity.dxf.start_angle  = start_angle
    entity.dxf.end_angle    = end_angle
    return entity


def make_spline_entity(points):
    """
    Crea un mock di entità SPLINE ezdxf.
    spline_to_points() viene patchato a livello di modulo,
    quindi il mock deve solo rispondere a dxftype().
    """
    entity = MagicMock()
    entity.dxftype.return_value = 'SPLINE'
    entity._mock_points = points
    return entity


def make_square_loop(side=100.0):
    """
    Restituisce un loop di 4 LINE che formano un quadrato.
    Loop: (0,0)→(side,0)→(side,side)→(0,side)→(0,0)
    """
    s = side
    return [
        (make_line(0, 0, s, 0),   False),
        (make_line(s, 0, s, s),   False),
        (make_line(s, s, 0, s),   False),
        (make_line(0, s, 0, 0),   False),
    ]


# ---------------------------------------------------------------------------
# from_loop — loop di sole LINE
# ---------------------------------------------------------------------------

class TestFromLoopLines(unittest.TestCase):
    """from_loop con 4 LINE che formano un quadrato 100x100."""

    def setUp(self):
        loop = make_square_loop(100.0)
        self.vs = VirtualShape.from_loop(loop, layer='outer', color=1)

    def test_001_restituisce_virtual_shape(self):
        self.assertIsNotNone(self.vs)
        self.assertIsInstance(self.vs, VirtualShape)

    def test_002_has_spline_false(self):
        self.assertFalse(self.vs.has_spline)

    def test_003_pts_with_bulge_popolato(self):
        self.assertEqual(len(self.vs.pts_with_bulge), 4)

    def test_004_bulge_zero_per_le_line(self):
        for pt in self.vs.pts_with_bulge:
            self.assertEqual(pt[4], 0.0,
                             msg=f"Bulge atteso 0.0, trovato {pt[4]}")

    def test_005_polygon_valido(self):
        self.assertIsNotNone(self.vs.polygon)
        self.assertTrue(self.vs.polygon.is_valid)

    def test_006_area_corretta(self):
        self.assertAlmostEqual(self.vs.polygon.area, 10000.0, delta=1.0)

    def test_007_layer_assegnato(self):
        self.assertEqual(self.vs.layer, 'outer')

    def test_008_color_assegnato(self):
        self.assertEqual(self.vs.color, 1)

    def test_009_entity_none_prima_del_writeback(self):
        self.assertIsNone(self.vs.entity)


# ---------------------------------------------------------------------------
# from_spline_loop — loop con almeno una SPLINE
# ---------------------------------------------------------------------------

class TestFromSplineLoop(unittest.TestCase):
    """
    from_spline_loop con un loop che contiene una SPLINE.
    La SPLINE viene discretizzata solo per il polygon (gerarchia),
    mai per pts_with_bulge.
    """

    def setUp(self):
        # Patch spline_to_points nel modulo virtual
        import dxf_forge.core.virtual as vmod
        self._orig = vmod.spline_to_points

        spline_pts = [(0, 0), (0, 25), (0, 50), (0, 75), (0, 100)]
        vmod.spline_to_points = lambda e: e._mock_points

        spline = make_spline_entity(spline_pts)
        loop = [
            (spline,                          False),
            (make_line(0, 100, 100, 100),     False),
            (make_line(100, 100, 100, 0),     False),
            (make_line(100, 0, 0, 0),         False),
        ]
        self.vs = VirtualShape.from_spline_loop(loop, layer='outer', color=1)

    def tearDown(self):
        import dxf_forge.core.virtual as vmod
        vmod.spline_to_points = self._orig

    def test_001_restituisce_virtual_shape(self):
        self.assertIsNotNone(self.vs)
        self.assertIsInstance(self.vs, VirtualShape)

    def test_002_has_spline_true(self):
        self.assertTrue(self.vs.has_spline)

    def test_003_pts_with_bulge_vuoto(self):
        self.assertEqual(self.vs.pts_with_bulge, [],
                         msg="pts_with_bulge deve essere vuoto per loop con spline")

    def test_004_polygon_valido(self):
        self.assertIsNotNone(self.vs.polygon)
        self.assertTrue(self.vs.polygon.is_valid)

    def test_005_polygon_non_vuoto(self):
        self.assertGreater(self.vs.polygon.area, 0.0)

    def test_006_loop_salvato(self):
        self.assertGreater(len(self.vs.loop), 0,
                           msg="loop deve essere salvato per il writeback")

    def test_007_entity_none(self):
        self.assertIsNone(self.vs.entity)


# ---------------------------------------------------------------------------
# _loop_to_virtual_shape — routing corretto
# ---------------------------------------------------------------------------

class TestLoopToVirtualShapeRouting(unittest.TestCase):
    """
    _loop_to_virtual_shape deve instradare al costruttore corretto
    in base alla presenza di SPLINE nel loop.
    """

    def setUp(self):
        import dxf_forge.core.virtual as vmod
        self._orig = vmod.spline_to_points
        vmod.spline_to_points = lambda e: e._mock_points

    def tearDown(self):
        import dxf_forge.core.virtual as vmod
        vmod.spline_to_points = self._orig

    def test_001_loop_senza_spline_ha_has_spline_false(self):
        loop = make_square_loop(100.0)
        vs = _loop_to_virtual_shape(loop, 'outer', 1)
        self.assertFalse(vs.has_spline)

    def test_002_loop_con_spline_ha_has_spline_true(self):
        spline = make_spline_entity([(0,0),(0,50),(0,100)])
        loop = [
            (spline,                      False),
            (make_line(0, 100, 100, 100), False),
            (make_line(100, 100, 100, 0), False),
            (make_line(100, 0, 0, 0),     False),
        ]
        vs = _loop_to_virtual_shape(loop, 'outer', 1)
        self.assertTrue(vs.has_spline)

    def test_003_loop_senza_spline_ha_pts_with_bulge(self):
        loop = make_square_loop(100.0)
        vs = _loop_to_virtual_shape(loop, 'outer', 1)
        self.assertGreater(len(vs.pts_with_bulge), 0)

    def test_004_loop_con_spline_ha_pts_with_bulge_vuoto(self):
        spline = make_spline_entity([(0,0),(0,50),(0,100)])
        loop = [
            (spline,                      False),
            (make_line(0, 100, 100, 100), False),
            (make_line(100, 100, 100, 0), False),
            (make_line(100, 0, 0, 0),     False),
        ]
        vs = _loop_to_virtual_shape(loop, 'outer', 1)
        self.assertEqual(vs.pts_with_bulge, [])


# ---------------------------------------------------------------------------
# Casi limite — polygon None
# ---------------------------------------------------------------------------

class TestLoopDegenere(unittest.TestCase):
    """Loop con meno di 3 punti → deve restituire None senza eccezioni."""

    def test_001_loop_con_una_sola_line_restituisce_none(self):
        loop = [(make_line(0, 0, 10, 0), False)]
        vs = _loop_to_virtual_shape(loop, 'outer', 1)
        self.assertIsNone(vs)

    def test_002_loop_vuoto_restituisce_none(self):
        vs = _loop_to_virtual_shape([], 'outer', 1)
        self.assertIsNone(vs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
