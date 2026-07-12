
"""
test_contour.py
--------------------
Test unitari per core/primitives/contour.py.

Zero dipendenze da ezdxf — tutto in termini di primitive pure.
"""

import unittest
from forge.core.primitives import LineSeg, ArcSeg, SplineSeg, DiscretizedArcSeg
from forge.core.primitives.contour import Contour, _build_polygon


# ---------------------------------------------------------------------------
# _build_polygon
# ---------------------------------------------------------------------------

class TestBuildPolygon(unittest.TestCase):

    def test_quadrato_valido(self):
        pts = [(0,0),(100,0),(100,100),(0,100)]
        poly = _build_polygon(pts)
        self.assertIsNotNone(poly)
        self.assertAlmostEqual(poly.area, 10000.0, delta=1.0)

    def test_meno_di_3_punti_restituisce_none(self):
        self.assertIsNone(_build_polygon([(0,0),(1,1)]))

    def test_lista_vuota_restituisce_none(self):
        self.assertIsNone(_build_polygon([]))


# ---------------------------------------------------------------------------
# Contour.from_primitives — loop di sole LINE
# ---------------------------------------------------------------------------

class TestFromPrimitivesLines(unittest.TestCase):

    def _square_primitives(self, side=100.0):
        s = side
        return [
            LineSeg(start=(0, 0), end=(s, 0)),
            LineSeg(start=(s, 0), end=(s, s)),
            LineSeg(start=(s, s), end=(0, s)),
            LineSeg(start=(0, s), end=(0, 0)),
        ]

    def setUp(self):
        self.contour = Contour.from_primitives(
            primitives=self._square_primitives(100.0),
            source_layer='outer',
        )

    def test_001_restituisce_contour(self):
        self.assertIsNotNone(self.contour)
        self.assertIsInstance(self.contour, Contour)

    def test_002_has_spline_false(self):
        self.assertFalse(self.contour.has_spline)

    def test_003_polygon_valido(self):
        self.assertTrue(self.contour.polygon.is_valid)

    def test_004_area_corretta(self):
        self.assertAlmostEqual(self.contour.polygon.area, 10000.0, delta=1.0)

    def test_005_source_layer(self):
        self.assertEqual(self.contour.source_layer, 'outer')

    def test_006_segments_popolati(self):
        self.assertEqual(len(self.contour.segments), 4)

    def test_007_source_ref_none_se_non_passato(self):
        self.assertIsNone(self.contour.source_ref)

    def test_008_no_layer_su_contour(self):
        self.assertFalse(hasattr(self.contour, 'layer'))

    def test_009_no_color_su_contour(self):
        self.assertFalse(hasattr(self.contour, 'color'))


# ---------------------------------------------------------------------------
# Contour.from_primitives — loop con SplineSeg
# ---------------------------------------------------------------------------

class TestFromPrimitivesSpline(unittest.TestCase):

    def _spline_loop_primitives(self):
        return [
            SplineSeg(points=[(0,0),(0,25),(0,50),(0,75),(0,100)]),
            LineSeg(start=(0,100),   end=(100,100)),
            LineSeg(start=(100,100), end=(100,0)),
            LineSeg(start=(100,0),   end=(0,0)),
        ]

    def setUp(self):
        self.contour = Contour.from_primitives(
            primitives=self._spline_loop_primitives(),
            source_layer='outer',
        )

    def test_001_restituisce_contour(self):
        self.assertIsNotNone(self.contour)

    def test_002_has_spline_true(self):
        self.assertTrue(self.contour.has_spline)

    def test_003_polygon_valido(self):
        self.assertTrue(self.contour.polygon.is_valid)

    def test_004_area_positiva(self):
        self.assertGreater(self.contour.polygon.area, 0.0)

    def test_005_segments_popolati(self):
        self.assertEqual(len(self.contour.segments), 4)


# ---------------------------------------------------------------------------
# Contour.from_primitives — loop con DiscretizedArcSeg
# ---------------------------------------------------------------------------

class TestFromPrimitivesDiscretizedArc(unittest.TestCase):

    def setUp(self):
        arc_pts = [(0.0, 100.0), (50.0, 110.0), (100.0, 100.0)]
        primitives = [
            SplineSeg(points=[(0, 0), (0, 50), (0, 100)]),
            DiscretizedArcSeg(points=arc_pts),
            LineSeg(start=(100.0, 100.0), end=(100.0, 0.0)),
            LineSeg(start=(100.0, 0.0),   end=(0.0, 0.0)),
        ]
        self.contour = Contour.from_primitives(
            primitives=primitives,
            source_layer='inner',
        )

    def test_001_has_spline_true(self):
        self.assertTrue(self.contour.has_spline)

    def test_002_polygon_valido(self):
        if self.contour is not None:
            self.assertTrue(self.contour.polygon.is_valid)


# ---------------------------------------------------------------------------
# source_ref — opaco, passato dal chiamante
# ---------------------------------------------------------------------------

class TestSourceRef(unittest.TestCase):

    def test_001_source_ref_passato_viene_conservato(self):
        primitives = [
            LineSeg(start=(0, 0),   end=(100, 0)),
            LineSeg(start=(100, 0), end=(100, 100)),
            LineSeg(start=(100, 100), end=(0, 100)),
            LineSeg(start=(0, 100), end=(0, 0)),
        ]
        ref = {"loop": [], "pts_with_bulge": [(0,0,0,0,0)]}
        contour = Contour.from_primitives(primitives=primitives, source_ref=ref)
        self.assertEqual(contour.source_ref, ref)

    def test_002_source_ref_default_none(self):
        primitives = [
            LineSeg(start=(0, 0),   end=(100, 0)),
            LineSeg(start=(100, 0), end=(100, 100)),
            LineSeg(start=(100, 100), end=(0, 100)),
            LineSeg(start=(0, 100), end=(0, 0)),
        ]
        contour = Contour.from_primitives(primitives=primitives)
        self.assertIsNone(contour.source_ref)


# ---------------------------------------------------------------------------
# Casi degeneri
# ---------------------------------------------------------------------------

class TestFromPrimitivesDegeneri(unittest.TestCase):

    def test_001_lista_vuota_restituisce_none(self):
        contour = Contour.from_primitives(primitives=[])
        self.assertIsNone(contour)

    def test_002_una_sola_line_restituisce_none(self):
        contour = Contour.from_primitives(
            primitives=[LineSeg(start=(0,0), end=(10,0))]
        )
        self.assertIsNone(contour)


if __name__ == "__main__":
    unittest.main(verbosity=2)