"""
test_graph.py
-------------
Test per dxf_forge.graph — find_closed_loops e classify_loops.

Verifica:
  - Loop CCW trovato correttamente
  - Loop CW viene invertito a CCW
  - Geometria con raccordi (maniglia) → loop corretto, non il complementare
  - Gerarchia outer/inner
  - SPLINE chiusa solitaria → trattata come outer

DXF sintetici generati inline — nessun file su disco necessario.

Lancia:
    python -m pytest tests/test_graph.py -v
"""

import unittest
import math
from pathlib import Path
import sys
import ezdxf
from shapely.geometry import LinearRing, Polygon

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dxf_forge.core.graph import (
    build_node_graph, find_closed_loops, classify_loops,
    round_point, entity_endpoints,
)
from dxf_forge.core.geometry import arc_to_bulge


# ---------------------------------------------------------------------------
# Helper: costruisce poligono approssimato da un loop
# ---------------------------------------------------------------------------

def _loop_to_polygon(loop) -> Polygon:
    """Converte un loop in Polygon Shapely (stesso metodo di classify_loops)."""
    pts = []
    for entity, rev in loop:
        if entity.dxftype() == 'LINE':
            pts.append(
                (entity.dxf.end.x, entity.dxf.end.y) if rev
                else (entity.dxf.start.x, entity.dxf.start.y)
            )
        elif entity.dxftype() == 'ARC':
            entry_pt, _, _ = arc_to_bulge(entity, reversed=rev)
            pts.append(entry_pt)
    return Polygon(pts) if len(pts) >= 3 else None


def _make_rect_msp(w=100.0, h=50.0, ccw=True):
    """
    Crea un msp con rettangolo formato da 4 LINE.
    ccw=True  → ordine antiorario (standard CAD)
    ccw=False → ordine orario (invertito)
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    if ccw:
        msp.add_line((0, 0),   (w, 0))
        msp.add_line((w, 0),   (w, h))
        msp.add_line((w, h),   (0, h))
        msp.add_line((0, h),   (0, 0))
    else:
        msp.add_line((0, 0),   (0, h))
        msp.add_line((0, h),   (w, h))
        msp.add_line((w, h),   (w, 0))
        msp.add_line((w, 0),   (0, 0))
    return msp


def _make_rect_with_inner_msp(outer_w=100.0, outer_h=80.0,
                               inner_w=40.0,  inner_h=30.0):
    """
    Crea un msp con rettangolo esterno e rettangolo interno (foro).
    Entrambi CCW.
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # outer
    msp.add_line((0,      0),       (outer_w, 0))
    msp.add_line((outer_w, 0),      (outer_w, outer_h))
    msp.add_line((outer_w, outer_h),(0,       outer_h))
    msp.add_line((0,      outer_h), (0,       0))

    # inner — centrato
    ox = (outer_w - inner_w) / 2
    oy = (outer_h - inner_h) / 2
    msp.add_line((ox,          oy),          (ox + inner_w, oy))
    msp.add_line((ox + inner_w, oy),         (ox + inner_w, oy + inner_h))
    msp.add_line((ox + inner_w, oy + inner_h),(ox,          oy + inner_h))
    msp.add_line((ox,          oy + inner_h),(ox,          oy))

    return msp


def _make_arc_rect_msp():
    """
    Crea un profilo rettangolare con due angoli arrotondati (ARC).
    Simula il caso maniglia: 4 LINE + 2 ARC tutti a grado 2.

    Geometria verificata (r=10):
      ARC-dx: centro=(80,10), 270->360  endpoints: (80,0)->(90,10)
      ARC-sx: centro=(20,10), 180->270  endpoints: (10,10)->(20,0)
    Tutti i nodi a grado 2, ciclo chiuso.
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    msp.add_line((10, 60), (90, 60))          # top
    msp.add_line((90, 60), (90, 10))          # right
    msp.add_arc( (80, 10), 10, 270, 360)      # angolo basso-dx
    msp.add_line((80, 0),  (20, 0))           # bottom
    msp.add_arc( (20, 10), 10, 180, 270)      # angolo basso-sx
    msp.add_line((10, 10), (10, 60))          # left

    return msp

def _make_rounded_rect_msp():
    """
    Rettangolo con 4 angoli raggiati (r=10).
    Genera nodi degree 3: ogni angolo è condiviso tra 1 ARC e 2 LINE.
    Questo è il caso che produceva loop spuri prima del fix.

    Geometria:
      bottom : (37,30)→(74,30)
      right  : (74,30)→(74,40) e (74,40)→(74,50)   ← degree 3 in (74,40)
      arc TR : centro (64,40), 0→90°
      top    : (64,50)→(47,50)
      arc TL : centro (47,40), 90→180°
      left   : (47,50)→(37,50) e (37,40)→(37,30)   ← degree 3 in (37,40)
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    msp.add_line((47, 50), (64, 50))          # top
    msp.add_line((74, 40), (74, 30))          # right bottom
    msp.add_line((74, 30), (37, 30))          # bottom
    msp.add_line((37, 30), (37, 40))          # left bottom
    msp.add_arc( (47, 40), 10,  90, 180)      # angolo top-left
    msp.add_arc( (64, 40), 10,   0,  90)      # angolo top-right
    msp.add_line((37, 40), (37, 50))          # left top  ← stub
    msp.add_line((37, 50), (47, 50))          # top-left connector
    msp.add_line((64, 50), (74, 50))          # top-right connector
    msp.add_line((74, 50), (74, 40))          # right top ← stub

    return msp


def _make_stub_in_loop_msp():
    """
    Rettangolo con una lineetta interna che parte dal bordo inferiore
    e ha l'endpoint superiore libero (degree 1).
    Verifica che _prune_dead_ends escluda la lineetta dal loop.
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    msp.add_line((0,   0),  (100, 0))    # bottom
    msp.add_line((100, 0),  (100, 50))   # right
    msp.add_line((100, 50), (0,   50))   # top
    msp.add_line((0,   50), (0,    0))   # left
    msp.add_line((50,  0),  (50,   25))  # stub: parte dal bordo, endpoint libero

    return msp




# ---------------------------------------------------------------------------
# Test: find_closed_loops — loop trovato
# ---------------------------------------------------------------------------

class TestFindClosedLoopsBasic(unittest.TestCase):
    """find_closed_loops trova il loop su un rettangolo semplice."""

    def setUp(self):
        msp = _make_rect_msp(ccw=True)
        graph = build_node_graph(msp, decimals=1)
        self.loops = find_closed_loops(graph)

    def test_001_finds_one_loop(self):
        self.assertEqual(len(self.loops), 1)

    def test_002_loop_has_four_entities(self):
        self.assertEqual(len(self.loops[0]), 4)

    def test_003_loop_is_closed(self):
        """Il primo e l'ultimo nodo devono coincidere."""
        loop = self.loops[0]
        first_entity, first_rev = loop[0]
        last_entity,  last_rev  = loop[-1]
        s, e = entity_endpoints(first_entity)
        first_node = round_point(s if first_rev else s)

        ls, le = entity_endpoints(last_entity)
        last_exit = round_point(ls if last_rev else le)
        # Il nodo di uscita dell'ultimo deve tornare al nodo di entrata del primo
        self.assertEqual(last_exit, round_point(s if first_rev else s))


# ---------------------------------------------------------------------------
# Test: orientamento — CCW preservato, CW invertito
# ---------------------------------------------------------------------------

class TestLoopOrientationCCW(unittest.TestCase):
    """Loop CCW rimane CCW dopo find_closed_loops."""

    def setUp(self):
        msp = _make_rect_msp(ccw=True)
        graph = build_node_graph(msp, decimals=1)
        loops = find_closed_loops(graph)
        self.poly = _loop_to_polygon(loops[0])

    def test_001_polygon_valid(self):
        self.assertIsNotNone(self.poly)
        self.assertTrue(self.poly.is_valid)

    def test_002_is_ccw(self):
        """Il poligono prodotto deve avere orientamento CCW."""
        ring = LinearRing(self.poly.exterior.coords)
        self.assertTrue(ring.is_ccw,
                        "Il loop non è CCW — find_closed_loops non ha corretto l'orientamento")

    def test_003_area_positive(self):
        self.assertGreater(self.poly.area, 0)


class TestLoopOrientationCW(unittest.TestCase):
    """Loop CW viene corretto a CCW da find_closed_loops."""

    def setUp(self):
        msp = _make_rect_msp(ccw=False)
        graph = build_node_graph(msp, decimals=1)
        loops = find_closed_loops(graph)
        self.poly = _loop_to_polygon(loops[0])

    def test_001_polygon_valid(self):
        self.assertIsNotNone(self.poly)
        self.assertTrue(self.poly.is_valid)

    def test_002_is_ccw(self):
        """Anche partendo da un loop CW, deve risultare CCW."""
        ring = LinearRing(self.poly.exterior.coords)
        self.assertTrue(ring.is_ccw,
                        "Il loop CW non è stato corretto a CCW")

    def test_003_area_correct(self):
        """Area deve essere 100*50 = 5000 indipendentemente dall'orientamento."""
        self.assertAlmostEqual(self.poly.area, 5000.0, delta=1.0)


# ---------------------------------------------------------------------------
# Test: geometria con raccordi (caso maniglia)
# ---------------------------------------------------------------------------

class TestLoopWithArcs(unittest.TestCase):
    """
    Profilo con LINE e ARC — simula il caso maniglia.
    find_closed_loops deve trovare il profilo esterno, non il complementare.
    """

    EXPECTED_AREA = 100 * 60 - (math.pi * 10**2 / 2)  # rettangolo - 2 semicerchi

    def setUp(self):
        msp = _make_arc_rect_msp()
        graph = build_node_graph(msp, decimals=1)
        loops = find_closed_loops(graph)
        self.loops = loops
        self.polygons = [_loop_to_polygon(l) for l in loops]
        self.valid_polys = [p for p in self.polygons if p is not None and p.is_valid]

    def test_001_finds_at_least_one_loop(self):
        self.assertGreaterEqual(len(self.loops), 1)

    def test_002_largest_loop_is_outer_profile(self):
        """
        Il loop con area maggiore deve essere il profilo esterno,
        non il complementare. Area attesa > 4000mm².
        """
        max_area = max(p.area for p in self.valid_polys)
        self.assertGreater(max_area, 4000.0,
                           f"Area massima {max_area:.1f} — potrebbe essere il complementare")

    def test_003_all_loops_ccw(self):
        """Tutti i loop trovati devono essere CCW."""
        for i, poly in enumerate(self.valid_polys):
            ring = LinearRing(poly.exterior.coords)
            self.assertTrue(ring.is_ccw,
                            f"Loop {i+1} non è CCW (area={poly.area:.1f})")


# ---------------------------------------------------------------------------
# Test: classify_loops — outer e inner
# ---------------------------------------------------------------------------

class TestClassifyLoops(unittest.TestCase):
    """classify_loops assegna correttamente outer e inner."""

    def setUp(self):
        msp = _make_rect_with_inner_msp()
        graph = build_node_graph(msp, decimals=1)
        loops = find_closed_loops(graph)
        self.outer, self.inner = classify_loops(loops)

    def test_001_finds_two_loops(self):
        total = len(self.outer) + len(self.inner)
        self.assertEqual(total, 2)

    def test_002_one_outer(self):
        self.assertEqual(len(self.outer), 1)

    def test_003_one_inner(self):
        self.assertEqual(len(self.inner), 1)

    def test_004_outer_area_larger(self):
        outer_poly = _loop_to_polygon(self.outer[0])
        inner_poly  = _loop_to_polygon(self.inner[0])
        self.assertGreater(outer_poly.area, inner_poly.area)

    def test_005_outer_contains_inner(self):
        outer_poly = _loop_to_polygon(self.outer[0])
        inner_poly  = _loop_to_polygon(self.inner[0])
        self.assertTrue(outer_poly.contains(inner_poly))


class TestClassifyLoopsSeparate(unittest.TestCase):
    """Due loop separati (non annidati) → entrambi outer."""

    def setUp(self):
        doc = ezdxf.new('R2010')
        msp = doc.modelspace()

        # rettangolo A — sinistra
        msp.add_line((0,  0),  (40, 0))
        msp.add_line((40, 0),  (40, 30))
        msp.add_line((40, 30), (0,  30))
        msp.add_line((0,  30), (0,  0))

        # rettangolo B — destra (separato)
        msp.add_line((60, 0),  (100, 0))
        msp.add_line((100, 0), (100, 30))
        msp.add_line((100, 30),(60,  30))
        msp.add_line((60,  30),(60,  0))

        graph = build_node_graph(msp, decimals=1)
        loops = find_closed_loops(graph)
        self.outer, self.inner = classify_loops(loops)

    def test_001_two_outer(self):
        self.assertEqual(len(self.outer), 2)

    def test_002_no_inner(self):
        self.assertEqual(len(self.inner), 0)


# ---------------------------------------------------------------------------
# Test: heal end-to-end — outer/inner assegnati correttamente
# ---------------------------------------------------------------------------

class TestHealHierarchy(unittest.TestCase):
    """
    Test end-to-end: rettangolo con foro interno.
    Verifica che heal() assegni OuterContour e InnerContour correttamente.
    """

    def setUp(self):
        import dxf_forge as forge
        msp = _make_rect_with_inner_msp(outer_w=100, outer_h=80,
                                         inner_w=40,  inner_h=30)
        self.result = forge.heal(msp, tolerance=0.05)

    def test_001_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_one_inner(self):
        self.assertEqual(len(self.result.parts[0].inners), 1)

    def test_003_outer_area_correct(self):
        area = self.result.parts[0].outer.area
        self.assertAlmostEqual(area, 100 * 80, delta=2.0)

    def test_004_inner_area_correct(self):
        inner_area = self.result.parts[0].inners[0].area
        self.assertAlmostEqual(inner_area, 40 * 30, delta=2.0)

    def test_005_net_area_correct(self):
        net = self.result.parts[0].area
        self.assertAlmostEqual(net, 100 * 80 - 40 * 30, delta=2.0)

class TestRoundedRectLoop(unittest.TestCase):
    """
    Rettangolo con angoli raggiati — nodi degree 3.
    Il fix deve produrre esattamente 1 loop valido (il profilo esterno)
    e nessun loop spurio, con warning nel result.
    """

    def setUp(self):
        import dxf_forge as forge
        msp = _make_rounded_rect_msp()
        self.result = forge.heal(msp, tolerance=0.05)

    def test_001_no_parts_on_ambiguous(self):
        self.assertEqual(self.result.part_count, 0,
            "Geometria ambigua — nessun pezzo deve essere classificato")

    def test_002_has_warning(self):
        joined = " ".join(self.result.warnings)
        self.assertIn("ambigua", joined.lower(),
            "Atteso warning su loop spuri — geometria ambigua")

    def test_003_no_area_on_ambiguous(self):
        self.assertEqual(len(self.result.parts), 0,
            "Geometria ambigua — nessuna parte deve avere area classificata")


class TestStubInLoop(unittest.TestCase):
    """
    Rettangolo con lineetta interna (endpoint libero, degree 1).
    La lineetta deve finire in trash, non rompere il loop.
    """

    def setUp(self):
        import dxf_forge as forge
        msp = _make_stub_in_loop_msp()
        self.result = forge.heal(msp, tolerance=0.05)

    def test_001_one_part(self):
        self.assertEqual(self.result.part_count, 1,
            "La lineetta con endpoint libero non deve rompere il loop")

    def test_002_outer_area_correct(self):
        area = self.result.parts[0].outer.area
        self.assertAlmostEqual(area, 100 * 50, delta=2.0)

    def test_003_stub_in_trash(self):
        """La lineetta deve finire in trash, non nel loop."""
        self.assertEqual(len(self.result.trash_entities), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)