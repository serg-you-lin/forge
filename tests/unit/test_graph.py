
# """
# test_graph.py
# -------------
# Test per dxf_forge.graph — find_closed_loops e classify_loops.
# """

# import unittest
# import math
# from pathlib import Path
# import sys
# import ezdxf
# from shapely.geometry import LinearRing, Polygon

# project_root = Path(__file__).resolve().parent.parent
# sys.path.insert(0, str(project_root))

# # from dxf_forge.core.graph import (
# #     build_node_graph, find_closed_loops, classify_loops,
# #     round_point, entity_endpoints,
# # )

# from dxf_forge.core.geometry import arc_to_bulge

# from dxf_forge.core.graph import (
#     build_node_graph, find_closed_loops, classify_loops,
#     round_point,
# )
# from dxf_forge.adapters.dxf.graph_adapter import entity_endpoints

# # ---------------------------------------------------------------------------
# # Helper: costruisce poligono approssimato da un loop
# # ---------------------------------------------------------------------------

# def _loop_to_polygon(loop) -> Polygon:
#     """Converte un loop in Polygon Shapely (stesso metodo di classify_loops)."""
#     pts = []
#     for edge, rev in loop:
#         entity = edge.entity
#         if entity.dxftype() == 'LINE':
#             pts.append(
#                 (entity.dxf.end.x, entity.dxf.end.y) if rev
#                 else (entity.dxf.start.x, entity.dxf.start.y)
#             )
#         elif entity.dxftype() == 'ARC':
#             entry_pt, _, _ = arc_to_bulge(entity, reversed=rev)
#             pts.append(entry_pt)
#     return Polygon(pts) if len(pts) >= 3 else None


# def _make_rect_msp(w=100.0, h=50.0, ccw=True):
#     doc = ezdxf.new('R2010')
#     msp = doc.modelspace()
#     if ccw:
#         msp.add_line((0, 0),   (w, 0))
#         msp.add_line((w, 0),   (w, h))
#         msp.add_line((w, h),   (0, h))
#         msp.add_line((0, h),   (0, 0))
#     else:
#         msp.add_line((0, 0),   (0, h))
#         msp.add_line((0, h),   (w, h))
#         msp.add_line((w, h),   (w, 0))
#         msp.add_line((w, 0),   (0, 0))
#     return msp


# def _make_rect_with_inner_msp(outer_w=100.0, outer_h=80.0,
#                                inner_w=40.0,  inner_h=30.0):
#     doc = ezdxf.new('R2010')
#     msp = doc.modelspace()

#     msp.add_line((0,      0),       (outer_w, 0))
#     msp.add_line((outer_w, 0),      (outer_w, outer_h))
#     msp.add_line((outer_w, outer_h),(0,       outer_h))
#     msp.add_line((0,      outer_h), (0,       0))

#     ox = (outer_w - inner_w) / 2
#     oy = (outer_h - inner_h) / 2
#     msp.add_line((ox,          oy),          (ox + inner_w, oy))
#     msp.add_line((ox + inner_w, oy),         (ox + inner_w, oy + inner_h))
#     msp.add_line((ox + inner_w, oy + inner_h),(ox,          oy + inner_h))
#     msp.add_line((ox,          oy + inner_h),(ox,          oy))

#     return msp


# def _make_arc_rect_msp():
#     doc = ezdxf.new('R2010')
#     msp = doc.modelspace()

#     msp.add_line((10, 60), (90, 60))
#     msp.add_line((90, 60), (90, 10))
#     msp.add_arc( (80, 10), 10, 270, 360)
#     msp.add_line((80, 0),  (20, 0))
#     msp.add_arc( (20, 10), 10, 180, 270)
#     msp.add_line((10, 10), (10, 60))

#     return msp


# def _make_rounded_rect_msp():
#     doc = ezdxf.new('R2010')
#     msp = doc.modelspace()

#     msp.add_line((47, 50), (64, 50))
#     msp.add_line((74, 40), (74, 30))
#     msp.add_line((74, 30), (37, 30))
#     msp.add_line((37, 30), (37, 40))
#     msp.add_arc( (47, 40), 10,  90, 180)
#     msp.add_arc( (64, 40), 10,   0,  90)
#     msp.add_line((37, 40), (37, 50))
#     msp.add_line((37, 50), (47, 50))
#     msp.add_line((64, 50), (74, 50))
#     msp.add_line((74, 50), (74, 40))

#     return msp


# def _make_stub_in_loop_msp():
#     doc = ezdxf.new('R2010')
#     msp = doc.modelspace()

#     msp.add_line((0,   0),  (100, 0))
#     msp.add_line((100, 0),  (100, 50))
#     msp.add_line((100, 50), (0,   50))
#     msp.add_line((0,   50), (0,    0))
#     msp.add_line((50,  0),  (50,   25))

#     return msp


# # ---------------------------------------------------------------------------
# # Test: find_closed_loops — loop trovato
# # ---------------------------------------------------------------------------

# class TestFindClosedLoopsBasic(unittest.TestCase):

#     def setUp(self):
#         msp = _make_rect_msp(ccw=True)
#         graph = build_node_graph(msp, decimals=1)
#         self.loops = find_closed_loops(graph)

#     def test_001_finds_one_loop(self):
#         self.assertEqual(len(self.loops), 1)

#     def test_002_loop_has_four_entities(self):
#         self.assertEqual(len(self.loops[0]), 4)

#     def test_003_loop_is_closed(self):
#         loop = self.loops[0]
#         first_edge, first_rev = loop[0]
#         last_edge,  last_rev  = loop[-1]
#         s, e = entity_endpoints(first_edge.entity)
#         first_start = round_point(s)
#         ls, le = entity_endpoints(last_edge.entity)
#         last_exit = round_point(ls if last_rev else le)
#         self.assertEqual(last_exit, first_start)


# # ---------------------------------------------------------------------------
# # Test: orientamento — CCW preservato, CW invertito
# # ---------------------------------------------------------------------------

# class TestLoopOrientationCCW(unittest.TestCase):

#     def setUp(self):
#         msp = _make_rect_msp(ccw=True)
#         graph = build_node_graph(msp, decimals=1)
#         loops = find_closed_loops(graph)
#         self.poly = _loop_to_polygon(loops[0])

#     def test_001_polygon_valid(self):
#         self.assertIsNotNone(self.poly)
#         self.assertTrue(self.poly.is_valid)

#     def test_002_is_ccw(self):
#         ring = LinearRing(self.poly.exterior.coords)
#         self.assertTrue(ring.is_ccw)

#     def test_003_area_positive(self):
#         self.assertGreater(self.poly.area, 0)


# class TestLoopOrientationCW(unittest.TestCase):

#     def setUp(self):
#         msp = _make_rect_msp(ccw=False)
#         graph = build_node_graph(msp, decimals=1)
#         loops = find_closed_loops(graph)
#         self.poly = _loop_to_polygon(loops[0])

#     def test_001_polygon_valid(self):
#         self.assertIsNotNone(self.poly)
#         self.assertTrue(self.poly.is_valid)

#     def test_002_is_ccw(self):
#         ring = LinearRing(self.poly.exterior.coords)
#         self.assertTrue(ring.is_ccw)

#     def test_003_area_correct(self):
#         self.assertAlmostEqual(self.poly.area, 5000.0, delta=1.0)


# # ---------------------------------------------------------------------------
# # Test: geometria con raccordi (caso maniglia)
# # ---------------------------------------------------------------------------

# class TestLoopWithArcs(unittest.TestCase):

#     EXPECTED_AREA = 100 * 60 - (math.pi * 10**2 / 2)

#     def setUp(self):
#         msp = _make_arc_rect_msp()
#         graph = build_node_graph(msp, decimals=1)
#         loops = find_closed_loops(graph)
#         self.loops = loops
#         self.polygons = [_loop_to_polygon(l) for l in loops]
#         self.valid_polys = [p for p in self.polygons if p is not None and p.is_valid]

#     def test_001_finds_at_least_one_loop(self):
#         self.assertGreaterEqual(len(self.loops), 1)

#     def test_002_largest_loop_is_outer_profile(self):
#         max_area = max(p.area for p in self.valid_polys)
#         self.assertGreater(max_area, 4000.0)

#     def test_003_all_loops_ccw(self):
#         for i, poly in enumerate(self.valid_polys):
#             ring = LinearRing(poly.exterior.coords)
#             self.assertTrue(ring.is_ccw,
#                             f"Loop {i+1} non è CCW (area={poly.area:.1f})")


# # ---------------------------------------------------------------------------
# # Test: classify_loops — outer e inner
# # ---------------------------------------------------------------------------

# class TestClassifyLoops(unittest.TestCase):

#     def setUp(self):
#         msp = _make_rect_with_inner_msp()
#         graph = build_node_graph(msp, decimals=1)
#         loops = find_closed_loops(graph)
#         self.outer, self.inner = classify_loops(loops)

#     def test_001_finds_two_loops(self):
#         total = len(self.outer) + len(self.inner)
#         self.assertEqual(total, 2)

#     def test_002_one_outer(self):
#         self.assertEqual(len(self.outer), 1)

#     def test_003_one_inner(self):
#         self.assertEqual(len(self.inner), 1)

#     def test_004_outer_area_larger(self):
#         outer_poly = _loop_to_polygon(self.outer[0])
#         inner_poly  = _loop_to_polygon(self.inner[0])
#         self.assertGreater(outer_poly.area, inner_poly.area)

#     def test_005_outer_contains_inner(self):
#         outer_poly = _loop_to_polygon(self.outer[0])
#         inner_poly  = _loop_to_polygon(self.inner[0])
#         self.assertTrue(outer_poly.contains(inner_poly))


# class TestClassifyLoopsSeparate(unittest.TestCase):

#     def setUp(self):
#         doc = ezdxf.new('R2010')
#         msp = doc.modelspace()

#         msp.add_line((0,  0),  (40, 0))
#         msp.add_line((40, 0),  (40, 30))
#         msp.add_line((40, 30), (0,  30))
#         msp.add_line((0,  30), (0,  0))

#         msp.add_line((60, 0),  (100, 0))
#         msp.add_line((100, 0), (100, 30))
#         msp.add_line((100, 30),(60,  30))
#         msp.add_line((60,  30),(60,  0))

#         graph = build_node_graph(msp, decimals=1)
#         loops = find_closed_loops(graph)
#         self.outer, self.inner = classify_loops(loops)

#     def test_001_two_outer(self):
#         self.assertEqual(len(self.outer), 2)

#     def test_002_no_inner(self):
#         self.assertEqual(len(self.inner), 0)


# # ---------------------------------------------------------------------------
# # Test: heal end-to-end
# # ---------------------------------------------------------------------------

# class TestHealHierarchy(unittest.TestCase):

#     def setUp(self):
#         import dxf_forge as forge
#         msp = _make_rect_with_inner_msp(outer_w=100, outer_h=80,
#                                          inner_w=40,  inner_h=30)
#         self.result = forge.heal(msp, tolerance=0.05)

#     def test_001_one_part(self):
#         self.assertEqual(self.result.part_count, 1)

#     def test_002_one_inner(self):
#         self.assertEqual(len(self.result.parts[0].inners), 1)

#     def test_003_outer_area_correct(self):
#         area = self.result.parts[0].outer.area
#         self.assertAlmostEqual(area, 100 * 80, delta=2.0)

#     def test_004_inner_area_correct(self):
#         inner_area = self.result.parts[0].inners[0].area
#         self.assertAlmostEqual(inner_area, 40 * 30, delta=2.0)

#     def test_005_net_area_correct(self):
#         net = self.result.parts[0].area
#         self.assertAlmostEqual(net, 100 * 80 - 40 * 30, delta=2.0)


# class TestRoundedRectLoop(unittest.TestCase):

#     def setUp(self):
#         import dxf_forge as forge
#         msp = _make_rounded_rect_msp()
#         self.result = forge.heal(msp, tolerance=0.05)

#     def test_001_no_parts_on_ambiguous(self):
#         self.assertEqual(self.result.part_count, 0)

#     def test_002_has_warning(self):
#         joined = " ".join(self.result.warnings)
#         self.assertIn("ambigua", joined.lower())

#     def test_003_no_area_on_ambiguous(self):
#         self.assertEqual(len(self.result.parts), 0)


# class TestStubInLoop(unittest.TestCase):

#     def setUp(self):
#         import dxf_forge as forge
#         msp = _make_stub_in_loop_msp()
#         self.result = forge.heal(msp, tolerance=0.05)

#     def test_001_one_part(self):
#         self.assertEqual(self.result.part_count, 1)

#     def test_002_outer_area_correct(self):
#         area = self.result.parts[0].outer.area
#         self.assertAlmostEqual(area, 100 * 50, delta=2.0)

#     def test_003_stub_in_trash(self):
#         self.assertEqual(len(self.result.trash_entities), 1)


# if __name__ == "__main__":
#     unittest.main(verbosity=2)



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

from dxf_forge.core.graph import (
    build_node_graph, find_closed_loops, classify_loops,
)
from dxf_forge.models import Edge


# ---------------------------------------------------------------------------
# Helper: Edge puri senza ezdxf
# ---------------------------------------------------------------------------

def _edge(start, end):
    """Crea un Edge lineare puro — niente ezdxf."""
    return Edge(
        entity=None,
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
        entity=None,
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


if __name__ == "__main__":
    unittest.main(verbosity=2)