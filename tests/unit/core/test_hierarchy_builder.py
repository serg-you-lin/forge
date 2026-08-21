"""
tests/unit/core/test_hierarchy_builder.py

Test per HierarchyBuilder (Step 4 del refactor).

I proxy ClosedShape vengono costruiti direttamente con Polygon shapely —
nessun adapter DXF, nessun file reale.  I source_ref sono stub minimali
perché HierarchyBuilder li passa avanti opachi (traceability) ma non li
interpreta.
"""

import math
import unittest
from shapely.geometry import Polygon

from forge.model.shape import ClosedShape, OpenShape
from forge.model.role import ContourRole
from forge.core.healing.hierarchy import HierarchyBuilder


# ---------------------------------------------------------------------------
# Stub minimo per source_ref
# ---------------------------------------------------------------------------

class _FakeEntity:
    """source_ref fittizio: HierarchyBuilder non ci accede mai direttamente."""

    def __init__(self):
        self.layer = ""
        self.color = 0

    def dxftype(self):
        return "LWPOLYLINE"   # non LINE né ARC → is_durable=True


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_proxy(polygon, *, diameter=None, center=None, role=ContourRole.UNKNOWN):
    return ClosedShape(
        polygon=polygon,
        source_ref=_FakeEntity(),
        role=role,
        shape_type="polyline",
        is_virtual=False,
        diameter=diameter,
        center=center,
    )


def _make_open_proxy(pts, *, role=ContourRole.UNKNOWN):
    length = sum(
        math.dist(pts[i], pts[i + 1])
        for i in range(len(pts) - 1)
    )
    return OpenShape(
        pts=pts,
        length=length,
        source_ref=_FakeEntity(),
        role=role,
        shape_type="line",
    )


def _circle_proxy(cx, cy, r):
    poly = Polygon(
        [(cx + r * math.cos(a * math.pi / 180),
          cy + r * math.sin(a * math.pi / 180))
         for a in range(0, 360, 5)]
    )
    return _make_proxy(poly, diameter=r * 2, center=(cx, cy))


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


# ---------------------------------------------------------------------------
# Test 1 — outer + hole
# ---------------------------------------------------------------------------

class TestOuterConHole(unittest.TestCase):
    """
    Configurazione:
        - 1 proxy grande (100×100) → OUTER
        - 1 proxy circolare d=5 contenuto → HOLE

    Atteso: 1 ForgePart con 1 Hole, 0 inners, trash vuoto.
    """

    def setUp(self):
        self.outer = _rect_proxy(0, 0, 100, 100)
        self.hole  = _circle_proxy(50, 50, 2.5)   # d=5, sotto HOLE_DIAMETER_THRESHOLD
        self.parts, self.trash = _make_builder().build([self.outer, self.hole])

    def test_produce_una_part(self):
        self.assertEqual(len(self.parts), 1)

    def test_outer_area(self):
        self.assertAlmostEqual(self.parts[0].outer.polygon.area, 10000.0, delta=1.0)

    def test_un_hole(self):
        self.assertEqual(len(self.parts[0].holes), 1)

    def test_zero_inners(self):
        self.assertEqual(len(self.parts[0].inners), 0)

    def test_hole_diameter(self):
        self.assertAlmostEqual(self.parts[0].holes[0].diameter, 5.0, places=3)

    def test_trash_vuoto(self):
        self.assertEqual(len(self.trash), 0)


# ---------------------------------------------------------------------------
# Test 2 — countersink
# ---------------------------------------------------------------------------

class TestCountersink(unittest.TestCase):
    """
    Configurazione (tre livelli annidati):
        - outer   : rettangolo 100×100
        - medio   : cerchio d=20 dentro outer   → anello esterno del countersink
        - piccolo : cerchio d=8  dentro medio   → foro del countersink

    Atteso: 1 ForgePart, 1 Hole con geometric_hint="countersink" e
    outer_diameter≈20, 0 inners.
    """

    def setUp(self):
        outer   = _rect_proxy(0, 0, 100, 100)
        medio   = _circle_proxy(50, 50, 10)   # d=20
        piccolo = _circle_proxy(50, 50, 4)    # d=8
        self.parts, self.trash = _make_builder().build([outer, medio, piccolo])

    def test_produce_una_part(self):
        self.assertEqual(len(self.parts), 1)

    def test_un_hole(self):
        self.assertEqual(len(self.parts[0].holes), 1)

    def test_countersink_hint(self):
        self.assertEqual(self.parts[0].holes[0].geometric_hint, "countersink")

    def test_countersink_outer_diameter(self):
        self.assertAlmostEqual(self.parts[0].holes[0].outer_diameter, 20.0, places=3)

    def test_zero_inners(self):
        self.assertEqual(len(self.parts[0].inners), 0)


# ---------------------------------------------------------------------------
# Test 3 — trash
# ---------------------------------------------------------------------------

class TestTrash(unittest.TestCase):
    """
    Configurazione:
        - 1 proxy outer (100×100)
        - 1 OpenShape role=UNKNOWN fuori dall'outer, non in entities_in_loops

    Atteso: il proxy aperto flottante finisce in trash, l'outer produce 1 ForgePart.
    """

    def setUp(self):
        self.outer    = _rect_proxy(0, 0, 100, 100)
        self.floating = _make_open_proxy([(200, 200), (210, 200)], role=ContourRole.UNKNOWN)
        self.parts, self.trash = _make_builder().build([self.outer, self.floating])

    def test_una_part_prodotta(self):
        self.assertGreaterEqual(len(self.parts), 1)

    def test_floating_in_trash(self):
        self.assertTrue(
            any(getattr(t, "source_ref", None) is self.floating.source_ref for t in self.trash)
        )

    def test_outer_non_in_trash(self):
        self.assertFalse(
            any(
                getattr(t, "polygon", None) is not None
                and t.polygon.equals(self.outer.polygon)
                for t in self.trash
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)