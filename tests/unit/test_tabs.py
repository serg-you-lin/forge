"""
test_tabs.py
------------
Test unitari per forge.tools.tabs (MAP.md D40): `bridge_tabs` (una coppia,
una posizione) e `bridge_nested_tabs` (cammina la gerarchia, N linguette per
coppia, a qualunque profondità).
"""

import math
import unittest
from pathlib import Path
import sys

from shapely.geometry import Polygon

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.core.primitives.segments import CircleSeg
from forge.model.contour import ForgeContour
from forge.tools.tabs import bridge_tabs, bridge_nested_tabs


def _circle_points(center, radius, n=200):
    cx, cy = center
    return [
        (cx + radius * math.cos(2 * math.pi * i / n), cy + radius * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


class TestBridgeTabs(unittest.TestCase):
    """Una coppia genitore/figlio, una sola posizione — la meccanica di base."""

    def setUp(self):
        self.center = (0.0, 0.0)
        self.parent_points = _circle_points(self.center, radius=9.0)
        self.child_points = _circle_points(self.center, radius=4.0)

    def test_001_tab_edges_span_the_radial_gap(self):
        # linguetta a destra (angolo 0): anchor esatti sui due cerchi
        anchor_child = (4.0, 0.0)
        anchor_parent = (9.0, 0.0)
        bridge = bridge_tabs(self.parent_points, self.child_points, anchor_parent, anchor_child, tab_width=1.0)
        self.assertEqual(len(bridge.tab_edges), 2)
        for edge in bridge.tab_edges:
            length = math.hypot(edge.end[0] - edge.start[0], edge.end[1] - edge.start[1])
            # il fianco e' leggermente piu' lungo del gap radiale puro (9-4=5)
            # perche' e' offsettato di tab_width/2 dal centro esatto — ma non di molto.
            self.assertAlmostEqual(length, 5.0, delta=0.05)

    def test_002_cuts_land_close_to_the_anchor(self):
        anchor_child = (4.0, 0.0)
        anchor_parent = (9.0, 0.0)
        bridge = bridge_tabs(self.parent_points, self.child_points, anchor_parent, anchor_child, tab_width=1.0)
        for cut_pt, _ in (bridge.child_cut_a, bridge.child_cut_b):
            self.assertAlmostEqual(math.hypot(*cut_pt), 4.0, delta=0.05)
        for cut_pt, _ in (bridge.parent_cut_a, bridge.parent_cut_b):
            self.assertAlmostEqual(math.hypot(*cut_pt), 9.0, delta=0.05)

    def test_003_too_wide_tab_raises(self):
        anchor_child = (4.0, 0.0)
        anchor_parent = (9.0, 0.0)
        with self.assertRaises(ValueError):
            bridge_tabs(self.parent_points, self.child_points, anchor_parent, anchor_child, tab_width=100.0)


def _make_contour(radius, depth, parent=None, center=(0.0, 0.0)):
    poly = Polygon(_circle_points(center, radius, n=64))
    return ForgeContour(role="unknown", polygon=poly, segments=[CircleSeg(center=center, radius=radius)],
                         depth=depth, parent=parent)


class _FakeCluster:
    def __init__(self, outer, inners):
        self.outer = outer
        self.inners = inners


class TestBridgeNestedTabs(unittest.TestCase):
    """Cammina la gerarchia — a qualunque profondita', mai un livello saltato."""

    def test_001_single_pair_on_real_fixture(self):
        doc = forge.load_dxf(str(project_root / "tests/examples/cerchi_concentrici_detect_is_counter_tabs_join.dxf"))
        result = forge.heal(doc)
        cluster = result.clusters[0]

        bridges = bridge_nested_tabs(cluster, tab_width=2.0, tab_count=4, discretize_tolerance=0.05)

        self.assertEqual(len(bridges), 1)
        bridge = bridges[0]
        self.assertEqual(bridge.child_contour.depth, 2)
        self.assertEqual(bridge.parent_contour.depth, 1)
        self.assertEqual(len(bridge.child_stretches), 4)
        self.assertEqual(len(bridge.parent_stretches), 4)
        self.assertEqual(len(bridge.tab_edges), 8)  # 2 fianchi x 4 linguette

    def test_002_four_level_chain_pairs_by_immediate_parent(self):
        # outer (depth0) -> figlio depth1 (vuoto) -> nipote depth2 (isola)
        # -> pronipote depth3 (vuoto) -> pro-pronipote depth4 (isola)
        outer = _make_contour(radius=20.0, depth=0)
        figlio = _make_contour(radius=15.0, depth=1, parent=outer)
        nipote = _make_contour(radius=10.0, depth=2, parent=figlio)
        pronipote = _make_contour(radius=6.0, depth=3, parent=nipote)
        pro_pronipote = _make_contour(radius=3.0, depth=4, parent=pronipote)

        cluster = _FakeCluster(outer=outer, inners=[figlio, nipote, pronipote, pro_pronipote])
        bridges = bridge_nested_tabs(cluster, tab_width=0.5, tab_count=4, discretize_tolerance=0.05)

        # solo le profondita' pari >= 2 generano un ponte, ognuna col SUO genitore diretto
        self.assertEqual(len(bridges), 2)
        pairs = {(b.child_contour.depth, b.parent_contour.depth) for b in bridges}
        self.assertEqual(pairs, {(2, 1), (4, 3)})


if __name__ == "__main__":
    unittest.main(verbosity=2)
