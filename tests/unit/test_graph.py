
"""
test_graph.py
-------------
Test per dxf_forge.core.graph — find_closed_loops e classify_loops.

Nessuna dipendenza da ezdxf o dal modelspace.
Gli Edge sono costruiti direttamente con geometria Shapely.
entity=None — il core non ne ha bisogno.
"""

import unittest
import math
from pathlib import Path
import sys
from shapely.geometry import LinearRing, Polygon, LineString

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from forge.core.topology.graph import (
    build_node_graph
)
from forge.core.topology.loops import (
    find_closed_loops, classify_loops,
)

from forge.model import Edge


# ---------------------------------------------------------------------------
# Helper: Edge puri senza ezdxf
# ---------------------------------------------------------------------------

def _edge(start, end):
    """Crea un Edge lineare puro — niente ezdxf."""
    return Edge(
        source_ref=None,
        layer="0",
        start=start,
        end=end,
        geometry=LineString([start, end]),
    )


def _arc_edge(start, end, arc_pts):
    """
    Crea un Edge che approssima un arco.
    arc_pts: lista di (x,y) che discretizzano l'arco da start a end.
    """
    return Edge(
        source_ref=None,
        layer="0",
        start=start,
        end=end,
        geometry=LineString(arc_pts),
    )


# ---------------------------------------------------------------------------
# Factory: geometrie di test
# ---------------------------------------------------------------------------

def _make_rect_edges(w=100.0, h=50.0, ccw=True):
    if ccw:
        return [
            _edge((0, 0),  (w, 0)),
            _edge((w, 0),  (w, h)),
            _edge((w, h),  (0, h)),
            _edge((0, h),  (0, 0)),
        ]
    else:
        return [
            _edge((0, 0),  (0, h)),
            _edge((0, h),  (w, h)),
            _edge((w, h),  (w, 0)),
            _edge((w, 0),  (0, 0)),
        ]


def _make_rect_with_inner_edges(outer_w=100.0, outer_h=80.0,
                                 inner_w=40.0,  inner_h=30.0):
    ox = (outer_w - inner_w) / 2
    oy = (outer_h - inner_h) / 2
    return [
        # outer
        _edge((0,       0),       (outer_w, 0)),
        _edge((outer_w, 0),       (outer_w, outer_h)),
        _edge((outer_w, outer_h), (0,       outer_h)),
        _edge((0,       outer_h), (0,       0)),
        # inner
        _edge((ox,          oy),           (ox + inner_w, oy)),
        _edge((ox + inner_w, oy),          (ox + inner_w, oy + inner_h)),
        _edge((ox + inner_w, oy + inner_h),(ox,           oy + inner_h)),
        _edge((ox,          oy + inner_h), (ox,           oy)),
    ]


def _make_arc_rect_edges():
    """
    Rettangolo con due raccordi circolari agli angoli inferiori.
    Archi approssimati con punti campionati.
    """
    def _arc_pts(cx, cy, r, start_deg, end_deg, n=16):
        import numpy as np
        start = math.radians(start_deg)
        end   = math.radians(end_deg)
        if start > end:
            end += 2 * math.pi
        angles = [start + (end - start) * i / n for i in range(n + 1)]
        return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in angles]

    arc1 = _arc_pts(80, 10, 10, 270, 360)
    arc2 = _arc_pts(20, 10, 10, 180, 270)

    return [
        _edge((10, 60), (90, 60)),
        _edge((90, 60), (90, 10)),
        _arc_edge((90, 10), (80, 0),  arc1),
        _edge((80, 0),  (20, 0)),
        _arc_edge((20, 0),  (10, 10), arc2),
        _edge((10, 10), (10, 60)),
    ]


def _make_separate_rects_edges():
    return [
        _edge((0,  0),  (40, 0)),
        _edge((40, 0),  (40, 30)),
        _edge((40, 30), (0,  30)),
        _edge((0,  30), (0,  0)),

        _edge((60, 0),  (100, 0)),
        _edge((100, 0), (100, 30)),
        _edge((100, 30),(60,  30)),
        _edge((60,  30),(60,  0)),
    ]


def _make_stub_in_loop_edges():
    return [
        _edge((0,   0),  (100, 0)),
        _edge((100, 0),  (100, 50)),
        _edge((100, 50), (0,   50)),
        _edge((0,   50), (0,   0)),
        _edge((50,  0),  (50,  25)),  # stub — dead end
    ]


def _make_rect_with_split_arcs_and_stubs(
    w=1000.0, h=500.0, r=3.0, stub_len=5.0
):
    """
    Rettangolo con 4 angoli raccordati da archi concavi spezzati in 2 metà.
    Ogni punto di spezzatura ha una LINE stub verso l'interno.
    
    Riproduce il bug: leaf attaccate a nodi di grado 3 (2 semiarchi + LINE).
    """
    import numpy as np

    def arc_pts(cx, cy, r, start_deg, end_deg, n=8):
        angles = np.linspace(math.radians(start_deg), math.radians(end_deg), n)
        return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in angles]

    edges = []

    # lati rettilinei
    edges.append(_edge((r, 0),       (w - r, 0)))
    edges.append(_edge((w, r),       (w, h - r)))
    edges.append(_edge((w - r, h),   (r, h)))
    edges.append(_edge((0, h - r),   (0, r)))

    # angolo in basso a sinistra — arco concavo spezzato in 2 metà
    # il punto di spezzatura è a 225° (verso l'interno)
    split_bl = (r - r * math.cos(math.radians(45)),
                r - r * math.sin(math.radians(45)))
    pts_bl_1 = arc_pts(r, r, r, 180, 225, n=5)
    pts_bl_2 = arc_pts(r, r, r, 225, 270, n=5)
    edges.append(_arc_edge(pts_bl_1[0],  pts_bl_1[-1],  pts_bl_1))
    edges.append(_arc_edge(pts_bl_2[0],  pts_bl_2[-1],  pts_bl_2))
    # stub verso l'interno
    stub_end_bl = (split_bl[0] + stub_len * math.cos(math.radians(45)),
                   split_bl[1] + stub_len * math.sin(math.radians(45)))
    edges.append(_edge(split_bl, stub_end_bl))

    # angolo in basso a destra
    split_br = (w - r + r * math.cos(math.radians(45)),
                r - r * math.sin(math.radians(45)))
    pts_br_1 = arc_pts(w - r, r, r, 270, 315, n=5)
    pts_br_2 = arc_pts(w - r, r, r, 315, 360, n=5)
    edges.append(_arc_edge(pts_br_1[0], pts_br_1[-1], pts_br_1))
    edges.append(_arc_edge(pts_br_2[0], pts_br_2[-1], pts_br_2))
    split_br = pts_br_1[-1]
    stub_end_br = (split_br[0] - stub_len * math.cos(math.radians(45)),
                   split_br[1] + stub_len * math.sin(math.radians(45)))
    edges.append(_edge(split_br, stub_end_br))

    # angolo in alto a destra
    split_tr = (w - r + r * math.cos(math.radians(45)),
                h - r + r * math.sin(math.radians(45)))
    pts_tr_1 = arc_pts(w - r, h - r, r, 0, 45, n=5)
    pts_tr_2 = arc_pts(w - r, h - r, r, 45, 90, n=5)
    edges.append(_arc_edge(pts_tr_1[0], pts_tr_1[-1], pts_tr_1))
    edges.append(_arc_edge(pts_tr_2[0], pts_tr_2[-1], pts_tr_2))
    split_tr = pts_tr_1[-1]
    stub_end_tr = (split_tr[0] - stub_len * math.cos(math.radians(45)),
                   split_tr[1] - stub_len * math.sin(math.radians(45)))
    edges.append(_edge(split_tr, stub_end_tr))

    # angolo in alto a sinistra
    pts_tl_1 = arc_pts(r, h - r, r, 90, 135, n=5)
    pts_tl_2 = arc_pts(r, h - r, r, 135, 180, n=5)
    edges.append(_arc_edge(pts_tl_1[0], pts_tl_1[-1], pts_tl_1))
    edges.append(_arc_edge(pts_tl_2[0], pts_tl_2[-1], pts_tl_2))
    split_tl = pts_tl_1[-1]
    stub_end_tl = (split_tl[0] + stub_len * math.cos(math.radians(45)),
                   split_tl[1] - stub_len * math.sin(math.radians(45)))
    edges.append(_edge(split_tl, stub_end_tl))

    return edges



# ---------------------------------------------------------------------------
# Helper: loop → Polygon
# ---------------------------------------------------------------------------

def _loop_to_polygon(loop) -> Polygon:
    pts = []
    for edge, rev in loop:
        coords = list(edge.geometry.coords)
        if rev:
            coords = list(reversed(coords))
        pts.append(coords[0])
    return Polygon(pts) if len(pts) >= 3 else None


# ---------------------------------------------------------------------------
# Test: find_closed_loops — rettangolo base
# ---------------------------------------------------------------------------

class TestFindClosedLoopsBasic(unittest.TestCase):

    def setUp(self):
        edges = _make_rect_edges(ccw=True)
        graph = build_node_graph(edges)
        self.loops = find_closed_loops(graph)

    def test_001_finds_one_loop(self):
        self.assertEqual(len(self.loops), 1)

    def test_002_loop_has_four_edges(self):
        self.assertEqual(len(self.loops[0]), 4)

    def test_003_loop_is_closed(self):
        loop = self.loops[0]
        first_edge, first_rev = loop[0]
        last_edge,  last_rev  = loop[-1]

        first_coords = list(first_edge.geometry.coords)
        first_start = first_coords[0] if not first_rev else first_coords[-1]

        last_coords = list(last_edge.geometry.coords)
        last_exit = last_coords[-1] if not last_rev else last_coords[0]

        self.assertAlmostEqual(first_start[0], last_exit[0], places=1)
        self.assertAlmostEqual(first_start[1], last_exit[1], places=1)


# ---------------------------------------------------------------------------
# Test: orientamento CCW
# ---------------------------------------------------------------------------

class TestLoopOrientationCCW(unittest.TestCase):

    def setUp(self):
        edges = _make_rect_edges(ccw=True)
        graph = build_node_graph(edges)
        loops = find_closed_loops(graph)
        self.poly = _loop_to_polygon(loops[0])

    def test_001_polygon_valid(self):
        self.assertIsNotNone(self.poly)
        self.assertTrue(self.poly.is_valid)

    def test_002_is_ccw(self):
        ring = LinearRing(self.poly.exterior.coords)
        self.assertTrue(ring.is_ccw)

    def test_003_area_correct(self):
        self.assertAlmostEqual(self.poly.area, 100 * 50, delta=1.0)


class TestLoopOrientationCW(unittest.TestCase):

    def setUp(self):
        edges = _make_rect_edges(ccw=False)
        graph = build_node_graph(edges)
        loops = find_closed_loops(graph)
        self.poly = _loop_to_polygon(loops[0])

    def test_001_polygon_valid(self):
        self.assertIsNotNone(self.poly)
        self.assertTrue(self.poly.is_valid)

    def test_002_is_ccw(self):
        ring = LinearRing(self.poly.exterior.coords)
        self.assertTrue(ring.is_ccw)

    def test_003_area_correct(self):
        self.assertAlmostEqual(self.poly.area, 100 * 50, delta=1.0)


# ---------------------------------------------------------------------------
# Test: geometria con raccordi
# ---------------------------------------------------------------------------

class TestLoopWithArcs(unittest.TestCase):

    def setUp(self):
        edges = _make_arc_rect_edges()
        graph = build_node_graph(edges)
        loops = find_closed_loops(graph)
        self.loops = loops
        self.polygons = [_loop_to_polygon(l) for l in loops]
        self.valid_polys = [p for p in self.polygons if p is not None and p.is_valid]

    def test_001_finds_at_least_one_loop(self):
        self.assertGreaterEqual(len(self.loops), 1)

    def test_002_largest_loop_is_outer_profile(self):
        max_area = max(p.area for p in self.valid_polys)
        self.assertGreater(max_area, 4000.0)

    def test_003_all_loops_ccw(self):
        for i, poly in enumerate(self.valid_polys):
            ring = LinearRing(poly.exterior.coords)
            self.assertTrue(ring.is_ccw,
                            f"Loop {i+1} non è CCW (area={poly.area:.1f})")


# ---------------------------------------------------------------------------
# Test: classify_loops — outer e inner
# ---------------------------------------------------------------------------

class TestClassifyLoops(unittest.TestCase):

    def setUp(self):
        edges = _make_rect_with_inner_edges()
        graph = build_node_graph(edges)
        loops = find_closed_loops(graph)
        self.outer, self.inner = classify_loops(loops)

    def test_001_finds_two_loops(self):
        self.assertEqual(len(self.outer) + len(self.inner), 2)

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

    def setUp(self):
        edges = _make_separate_rects_edges()
        graph = build_node_graph(edges)
        loops = find_closed_loops(graph)
        self.outer, self.inner = classify_loops(loops)

    def test_001_two_outer(self):
        self.assertEqual(len(self.outer), 2)

    def test_002_no_inner(self):
        self.assertEqual(len(self.inner), 0)


# ---------------------------------------------------------------------------
# Test: dead end pruning
# ---------------------------------------------------------------------------

class TestStubInLoop(unittest.TestCase):

    def setUp(self):
        edges = _make_stub_in_loop_edges()
        graph = build_node_graph(edges)
        loops = find_closed_loops(graph)
        self.outer, self.inner = classify_loops(loops)

    def test_001_one_outer(self):
        self.assertEqual(len(self.outer), 1)

    def test_002_no_inner(self):
        self.assertEqual(len(self.inner), 0)

    def test_003_outer_area_correct(self):
        poly = _loop_to_polygon(self.outer[0])
        self.assertAlmostEqual(poly.area, 100 * 50, delta=2.0)

class TestSplitArcStubs(unittest.TestCase):
    """
    BUG NOTO: archi concavi spezzati + LINE stub attaccate al punto di spezzatura.
    Il nodo di spezzatura ha grado 3 (2 semiarchi + 1 stub) — _prune_dead_ends
    non riconosce la stub come leaf e non la elimina.
    """

    def setUp(self):
        edges = _make_rect_with_split_arcs_and_stubs()
        graph = build_node_graph(edges)
        loops = find_closed_loops(graph)
        self.outer, self.inner = classify_loops(loops)

    @unittest.expectedFailure
    def test_un_solo_loop(self):
        """BUG: le stub non vengono potate → loop non chiuso o loop spuri."""
        self.assertEqual(len(self.outer), 1)

    # @unittest.expectedFailure
    # def test_nessun_inner(self):
    #     """BUG: stub verso l'interno possono generare loop interni spuri."""
    #     self.assertEqual(len(self.inner), 0)

    @unittest.expectedFailure
    def test_area_corretta(self):
        """BUG: se il loop viene trovato, l'area deve essere quella del rettangolo."""
        if not self.outer:
            self.fail("Nessun outer loop trovato")
        poly = _loop_to_polygon(self.outer[0])
        self.assertAlmostEqual(poly.area, 1000.0 * 500.0, delta=100.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)