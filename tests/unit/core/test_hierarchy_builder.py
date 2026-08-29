"""
tests/unit/core/test_hierarchy_builder.py

Test per HierarchyBuilder.

D15: HierarchyBuilder costruisce SOLO l'albero di contenimento —
`ForgePart(outer, inners=[ForgeContour...])`, zero `Hole`. La classificazione
hole / countersink è di `detect()` (vedi tests/unit/test_detect.py).

I proxy ClosedFeature/OpenFeature vengono costruiti direttamente con Polygon
shapely e primitive native — nessun adapter DXF, nessun file reale.
"""

import math
import unittest
from shapely.geometry import Polygon

from forge.core.primitives.segments import LineSeg
from forge.model.feature import ClosedFeature, OpenFeature
from forge.model.role import ContourRole
from forge.core.healing.hierarchy import HierarchyBuilder


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_proxy(polygon, *, role=ContourRole.UNKNOWN):
    return ClosedFeature(role=role, polygon=polygon)


def _make_open_proxy(pts, *, role=ContourRole.UNKNOWN):
    segments = [
        LineSeg(start=pts[i], end=pts[i + 1])
        for i in range(len(pts) - 1)
    ]
    return OpenFeature(role=role, segments=segments)


def _circle_proxy(cx, cy, r):
    poly = Polygon(
        [(cx + r * math.cos(a * math.pi / 180),
          cy + r * math.sin(a * math.pi / 180))
         for a in range(0, 360, 5)]
    )
    return _make_proxy(poly)


def _rect_proxy(x0, y0, x1, y1):
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return _make_proxy(poly)


def _make_builder():
    return HierarchyBuilder(
        label="",
        source_file="",
        label_map={},
        entities_in_loops=set(),
    )


class TestVirtualModelRemoved(unittest.TestCase):
    def test_closed_shape_has_no_virtual_flag(self):
        proxy = _make_proxy(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]))
        self.assertFalse(hasattr(proxy, "is_virtual"))
        self.assertFalse(hasattr(proxy, "vs_id"))


# ---------------------------------------------------------------------------
# Test 1 — outer + contorno interno
# ---------------------------------------------------------------------------

class TestOuterConInner(unittest.TestCase):
    """
    - 1 proxy grande (100×100) → OUTER
    - 1 proxy circolare d=5 contenuto → inner (heal NON lo promuove a foro)

    Atteso: 1 ForgePart, 0 holes, 1 inner, trash vuoto.
    """

    def setUp(self):
        self.outer = _rect_proxy(0, 0, 100, 100)
        self.inner = _circle_proxy(50, 50, 2.5)
        self.parts, self.trash = _make_builder().build([self.outer, self.inner])

    def test_produce_una_part(self):
        self.assertEqual(len(self.parts), 1)

    def test_outer_area(self):
        self.assertAlmostEqual(self.parts[0].outer.polygon.area, 10000.0, delta=1.0)

    def test_zero_holes(self):
        self.assertEqual(len(self.parts[0].holes), 0)

    def test_un_inner(self):
        self.assertEqual(len(self.parts[0].inners), 1)
        self.assertEqual(self.parts[0].inners[0].role, ContourRole.INNER)

    def test_trash_vuoto(self):
        self.assertEqual(len(self.trash), 0)


# ---------------------------------------------------------------------------
# Test 2 — nesting a tre livelli (countersink): heal appiattisce tutto in inners
# ---------------------------------------------------------------------------

class TestNestingFlattened(unittest.TestCase):
    """
    - outer   : rettangolo 100×100
    - medio   : cerchio d=20 dentro outer
    - piccolo : cerchio d=8  dentro medio

    heal() non riconosce più il countersink dal nesting (D15): consegna
    entrambi i cerchi come inners piatti. Il riconoscimento è di detect().
    """

    def setUp(self):
        outer   = _rect_proxy(0, 0, 100, 100)
        medio   = _circle_proxy(50, 50, 10)   # d=20
        piccolo = _circle_proxy(50, 50, 4)    # d=8
        self.parts, self.trash = _make_builder().build([outer, medio, piccolo])

    def test_produce_una_part(self):
        self.assertEqual(len(self.parts), 1)

    def test_zero_holes(self):
        self.assertEqual(len(self.parts[0].holes), 0)

    def test_due_inners(self):
        self.assertEqual(len(self.parts[0].inners), 2)


# ---------------------------------------------------------------------------
# Test 3 — trash
# ---------------------------------------------------------------------------

class TestTrash(unittest.TestCase):
    """
    - 1 proxy outer (100×100)
    - 1 OpenFeature role=UNKNOWN fuori dall'outer

    Atteso: il proxy aperto flottante finisce in trash, l'outer produce 1 ForgePart.
    """

    def setUp(self):
        self.outer    = _rect_proxy(0, 0, 100, 100)
        self.floating = _make_open_proxy([(200, 200), (210, 200)], role=ContourRole.UNKNOWN)
        self.parts, self.trash = _make_builder().build([self.outer, self.floating])

    def test_una_part_prodotta(self):
        self.assertGreaterEqual(len(self.parts), 1)

    def test_floating_in_trash(self):
        self.assertIn(self.floating, self.trash)

    def test_outer_non_in_trash(self):
        self.assertFalse(
            any(
                getattr(t, "polygon", None) is not None
                and t.polygon.equals(self.outer.polygon)
                for t in self.trash
            )
        )


# ---------------------------------------------------------------------------
# Test 4 — segments copiati dal proxy al model
# ---------------------------------------------------------------------------

class TestSegmentsCopiati(unittest.TestCase):
    """
    HierarchyBuilder copia proxy.segments su outer e inner.

    I segments sono stub — l'importante è che arrivino intatti.
    """

    def setUp(self):
        from forge.core.primitives import LineSeg, ArcSeg

        self.seg_outer = [
            LineSeg(start=(0, 0),   end=(100, 0)),
            LineSeg(start=(100, 0), end=(100, 100)),
            LineSeg(start=(100, 100), end=(0, 100)),
            LineSeg(start=(0, 100), end=(0, 0)),
        ]
        self.seg_inner = [
            ArcSeg(center=(50, 50), radius=2.5,
                   start_angle=0.0, end_angle=6.2831, ccw=True),
        ]

        outer = _rect_proxy(0, 0, 100, 100)
        outer.segments = list(self.seg_outer)

        inner = _circle_proxy(50, 50, 2.5)
        inner.segments = list(self.seg_inner)

        self.parts, _ = _make_builder().build([outer, inner])

    def test_outer_segments_copiati(self):
        self.assertEqual(self.parts[0].outer.segments, self.seg_outer)

    def test_inner_segments_copiati(self):
        self.assertEqual(self.parts[0].inners[0].segments, self.seg_inner)


if __name__ == "__main__":
    unittest.main(verbosity=2)
