# """
# test_core_virtual.py
# --------------------
# Test unitari per core/virtual.py.

# Zero dipendenze da ezdxf — tutto in termini di primitive pure.
# """

# import unittest
# import math
# from forge.core.virtual import (
#     LineSeg, ArcSeg, SplineSeg, DiscretizedArcSeg,
#     VirtualShape, _build_polygon,
# )


# # ---------------------------------------------------------------------------
# # Primitive — dataclass base
# # ---------------------------------------------------------------------------

# class TestPrimitives(unittest.TestCase):

#     def test_lineseg(self):
#         s = LineSeg(start=(0.0, 0.0), end=(10.0, 0.0))
#         self.assertEqual(s.start, (0.0, 0.0))
#         self.assertEqual(s.end,   (10.0, 0.0))

#     def test_arcseg(self):
#         a = ArcSeg(start=(1.0, 0.0), end=(0.0, 1.0), bulge=0.5)
#         self.assertEqual(a.bulge, 0.5)

#     def test_splineseg(self):
#         pts = [(0, 0), (1, 1), (2, 0)]
#         s = SplineSeg(points=pts)
#         self.assertEqual(s.points, pts)

#     def test_discretized_arcseg(self):
#         pts = [(1.0, 0.0), (0.707, 0.707), (0.0, 1.0)]
#         d = DiscretizedArcSeg(points=pts)
#         self.assertEqual(len(d.points), 3)


# # ---------------------------------------------------------------------------
# # _build_polygon
# # ---------------------------------------------------------------------------

# class TestBuildPolygon(unittest.TestCase):

#     def test_quadrato_valido(self):
#         pts = [(0,0),(100,0),(100,100),(0,100)]
#         poly = _build_polygon(pts)
#         self.assertIsNotNone(poly)
#         self.assertAlmostEqual(poly.area, 10000.0, delta=1.0)

#     def test_meno_di_3_punti_restituisce_none(self):
#         self.assertIsNone(_build_polygon([(0,0),(1,1)]))

#     def test_lista_vuota_restituisce_none(self):
#         self.assertIsNone(_build_polygon([]))


# # ---------------------------------------------------------------------------
# # VirtualShape.from_primitives — loop di sole LINE
# # ---------------------------------------------------------------------------

# class TestFromPrimitivesLines(unittest.TestCase):

#     def _square_primitives(self, side=100.0):
#         s = side
#         return [
#             LineSeg(start=(0, 0),   end=(s, 0)),
#             LineSeg(start=(s, 0),   end=(s, s)),
#             LineSeg(start=(s, s),   end=(0, s)),
#             LineSeg(start=(0, s),   end=(0, 0)),
#         ]

#     def setUp(self):
#         self.vs = VirtualShape.from_primitives(
#             self._square_primitives(100.0), layer='outer', color=1
#         )

#     def test_001_restituisce_virtual_shape(self):
#         self.assertIsNotNone(self.vs)
#         self.assertIsInstance(self.vs, VirtualShape)

#     def test_002_has_spline_false(self):
#         self.assertFalse(self.vs.has_spline)

#     def test_003_pts_with_bulge_popolato(self):
#         self.assertEqual(len(self.vs.pts_with_bulge), 4)

#     def test_004_bulge_zero(self):
#         for pt in self.vs.pts_with_bulge:
#             self.assertEqual(pt[4], 0.0)

#     def test_005_polygon_valido(self):
#         self.assertTrue(self.vs.polygon.is_valid)

#     def test_006_area_corretta(self):
#         self.assertAlmostEqual(self.vs.polygon.area, 10000.0, delta=1.0)

#     def test_007_layer(self):
#         self.assertEqual(self.vs.layer, 'outer')

#     def test_008_color(self):
#         self.assertEqual(self.vs.color, 1)

#     def test_009_entity_none(self):
#         self.assertIsNone(self.vs.entity)


# # ---------------------------------------------------------------------------
# # VirtualShape.from_primitives — loop con SplineSeg
# # ---------------------------------------------------------------------------

# class TestFromPrimitivesSpline(unittest.TestCase):

#     def _spline_loop_primitives(self):
#         return [
#             SplineSeg(points=[(0,0),(0,25),(0,50),(0,75),(0,100)]),
#             LineSeg(start=(0,100),   end=(100,100)),
#             LineSeg(start=(100,100), end=(100,0)),
#             LineSeg(start=(100,0),   end=(0,0)),
#         ]

#     def setUp(self):
#         self.vs = VirtualShape.from_primitives(
#             self._spline_loop_primitives(), layer='outer', color=1
#         )

#     def test_001_restituisce_virtual_shape(self):
#         self.assertIsNotNone(self.vs)

#     def test_002_has_spline_true(self):
#         self.assertTrue(self.vs.has_spline)

#     def test_003_pts_with_bulge_vuoto(self):
#         self.assertEqual(self.vs.pts_with_bulge, [])

#     def test_004_polygon_valido(self):
#         self.assertTrue(self.vs.polygon.is_valid)

#     def test_005_area_positiva(self):
#         self.assertGreater(self.vs.polygon.area, 0.0)


# # ---------------------------------------------------------------------------
# # VirtualShape.from_primitives — loop con DiscretizedArcSeg
# # ---------------------------------------------------------------------------

# class TestFromPrimitivesDiscretizedArc(unittest.TestCase):

#     def setUp(self):
#         # rettangolo con un lato sostituito da un DiscretizedArcSeg
#         # geometria coerente: tutti i giunti connessi
#         # lato sinistro: SplineSeg (forza has_spline=True)
#         # lato superiore: DiscretizedArcSeg
#         # lati destro e inferiore: LineSeg
#         arc_pts = [(0.0, 100.0), (50.0, 110.0), (100.0, 100.0)]  # arco da (0,100) a (100,100)
#         primitives = [
#             SplineSeg(points=[(0, 0), (0, 50), (0, 100)]),
#             DiscretizedArcSeg(points=arc_pts),
#             LineSeg(start=(100.0, 100.0), end=(100.0, 0.0)),
#             LineSeg(start=(100.0, 0.0),   end=(0.0, 0.0)),
#         ]
#         self.vs = VirtualShape.from_primitives(primitives, layer='inner', color=2)

#     def test_001_has_spline_true(self):
#         self.assertTrue(self.vs.has_spline)

#     def test_002_polygon_valido(self):
#         if self.vs is not None:
#             self.assertTrue(self.vs.polygon.is_valid)





# # ---------------------------------------------------------------------------
# # Casi degeneri
# # ---------------------------------------------------------------------------

# class TestFromPrimitivesDegeneri(unittest.TestCase):

#     def test_001_lista_vuota_restituisce_none(self):
#         vs = VirtualShape.from_primitives([], layer='outer', color=1)
#         self.assertIsNone(vs)

#     def test_002_una_sola_line_restituisce_none(self):
#         vs = VirtualShape.from_primitives(
#             [LineSeg(start=(0,0), end=(10,0))], layer='outer', color=1
#         )
#         self.assertIsNone(vs)


# if __name__ == "__main__":
#     unittest.main(verbosity=2)

"""
test_core_virtual.py
--------------------
Test unitari per core/virtual.py.

Zero dipendenze da ezdxf — tutto in termini di primitive pure.
"""

import unittest
from forge.core.primitives import LineSeg, ArcSeg, SplineSeg, DiscretizedArcSeg
from forge.core.primitives.virtual import VirtualShape, _build_polygon


# ---------------------------------------------------------------------------
# Primitive — dataclass base (ora in core/primitives)
# ---------------------------------------------------------------------------

class TestPrimitives(unittest.TestCase):

    def test_lineseg(self):
        s = LineSeg(start=(0.0, 0.0), end=(10.0, 0.0))
        self.assertEqual(s.start, (0.0, 0.0))
        self.assertEqual(s.end,   (10.0, 0.0))

    def test_arcseg(self):
        a = ArcSeg(start=(1.0, 0.0), end=(0.0, 1.0), bulge=0.5)
        self.assertEqual(a.bulge, 0.5)

    def test_splineseg(self):
        pts = [(0, 0), (1, 1), (2, 0)]
        s = SplineSeg(points=pts)
        self.assertEqual(s.points, pts)

    def test_discretized_arcseg(self):
        pts = [(1.0, 0.0), (0.707, 0.707), (0.0, 1.0)]
        d = DiscretizedArcSeg(points=pts)
        self.assertEqual(len(d.points), 3)


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
# VirtualShape.from_primitives — loop di sole LINE
# ---------------------------------------------------------------------------

class TestFromPrimitivesLines(unittest.TestCase):

    def _square_primitives(self, side=100.0):
        s = side
        return [
            LineSeg(start=(0, 0),   end=(s, 0)),
            LineSeg(start=(s, 0),   end=(s, s)),
            LineSeg(start=(s, s),   end=(0, s)),
            LineSeg(start=(0, s),   end=(0, 0)),
        ]

    def setUp(self):
        self.vs = VirtualShape.from_primitives(
            self._square_primitives(100.0), layer='outer', color=1
        )

    def test_001_restituisce_virtual_shape(self):
        self.assertIsNotNone(self.vs)
        self.assertIsInstance(self.vs, VirtualShape)

    def test_002_has_spline_false(self):
        self.assertFalse(self.vs.has_spline)

    def test_003_polygon_valido(self):
        self.assertTrue(self.vs.polygon.is_valid)

    def test_004_area_corretta(self):
        self.assertAlmostEqual(self.vs.polygon.area, 10000.0, delta=1.0)

    def test_005_layer(self):
        self.assertEqual(self.vs.layer, 'outer')

    def test_006_color(self):
        self.assertEqual(self.vs.color, 1)

    def test_007_source_ref_non_none(self):
        self.assertIsNotNone(self.vs.source_ref)

    def test_008_source_ref_ha_pts_with_bulge(self):
        self.assertIn('pts_with_bulge', self.vs.source_ref)
        self.assertEqual(len(self.vs.source_ref['pts_with_bulge']), 4)

    def test_009_source_ref_bulge_zero(self):
        for pt in self.vs.source_ref['pts_with_bulge']:
            self.assertEqual(pt[4], 0.0)

    def test_010_source_ref_ha_loop(self):
        self.assertIn('loop', self.vs.source_ref)

    def test_011_no_pts_with_bulge_su_vs(self):
        self.assertFalse(hasattr(self.vs, 'pts_with_bulge'))

    def test_012_no_entity_su_vs(self):
        self.assertFalse(hasattr(self.vs, 'entity'))


# ---------------------------------------------------------------------------
# VirtualShape.from_primitives — loop con SplineSeg
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
        self.vs = VirtualShape.from_primitives(
            self._spline_loop_primitives(), layer='outer', color=1
        )

    def test_001_restituisce_virtual_shape(self):
        self.assertIsNotNone(self.vs)

    def test_002_has_spline_true(self):
        self.assertTrue(self.vs.has_spline)

    def test_003_polygon_valido(self):
        self.assertTrue(self.vs.polygon.is_valid)

    def test_004_area_positiva(self):
        self.assertGreater(self.vs.polygon.area, 0.0)

    def test_005_source_ref_pts_with_bulge_vuoto(self):
        self.assertEqual(self.vs.source_ref['pts_with_bulge'], [])


# ---------------------------------------------------------------------------
# VirtualShape.from_primitives — loop con DiscretizedArcSeg
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
        self.vs = VirtualShape.from_primitives(primitives, layer='inner', color=2)

    def test_001_has_spline_true(self):
        self.assertTrue(self.vs.has_spline)

    def test_002_polygon_valido(self):
        if self.vs is not None:
            self.assertTrue(self.vs.polygon.is_valid)


# ---------------------------------------------------------------------------
# Casi degeneri
# ---------------------------------------------------------------------------

class TestFromPrimitivesDegeneri(unittest.TestCase):

    def test_001_lista_vuota_restituisce_none(self):
        vs = VirtualShape.from_primitives([], layer='outer', color=1)
        self.assertIsNone(vs)

    def test_002_una_sola_line_restituisce_none(self):
        vs = VirtualShape.from_primitives(
            [LineSeg(start=(0,0), end=(10,0))], layer='outer', color=1
        )
        self.assertIsNone(vs)


if __name__ == "__main__":
    unittest.main(verbosity=2)