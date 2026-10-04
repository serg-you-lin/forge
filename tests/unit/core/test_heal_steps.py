"""
tests/unit/core/test_heal_steps.py
----------------------------------
I passi di heal() usati da soli, come li usa un consumatore che compone la
sua ricetta (D62) — e la composizione nell'ordine di heal() che dà lo stesso
risultato di heal().
"""

import sys
import unittest
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

import forge
from forge.model.document import ForgeDocument
from forge.model.feature import ClosedFeature, OpenFeature
from forge.model.role import ContourRole
from forge.core.topology.edge import Edge
from forge.core.primitives.segments import LineSeg, CircleSeg, SplineSeg

EXAMPLES = project_root / "tests" / "data"


def _line(p1, p2, role=ContourRole.UNKNOWN, decimals=3):
    r = lambda p: (round(p[0], decimals), round(p[1], decimals))
    return Edge(role=role, start=r(p1), end=r(p2), segment=LineSeg(start=p1, end=p2))


def _square(x0, y0, side, role=ContourRole.UNKNOWN):
    pts = [(x0, y0), (x0 + side, y0), (x0 + side, y0 + side), (x0, y0 + side)]
    return [_line(pts[i], pts[(i + 1) % 4], role) for i in range(4)]


def _circle(center, radius, role=ContourRole.UNKNOWN):
    pt = (center[0] + radius, center[1])
    return Edge(role=role, start=pt, end=pt, segment=CircleSeg(center=center, radius=radius))


def _broken_square(spur=False):
    # Angolo in basso a destra rotto: 10.03 vs 10.14, nodi a 1 decimale
    # 10.0 vs 10.1 — lo chiude solo la riparazione via clustering (D57).
    edges = [_line((0.0, 0.0), (10.03, 0.0), decimals=1),
             _line((10.14, 0.0), (10.14, 10.0), decimals=1),
             _line((10.14, 10.0), (0.0, 10.0), decimals=1),
             _line((0.0, 10.0), (0.0, 0.0), decimals=1)]
    if spur:
        # terzo estremo nello stesso cluster: riparazione a due non definita
        edges.append(_line((10.06, 0.0), (10.06, -5.0), decimals=1))
    return edges


class TestSplitLabeled(unittest.TestCase):

    def test_001_ruolo_non_strutturale_messo_da_parte(self):
        mark = _line((2, 2), (5, 5), role="engrave")
        kept, labeled = forge.split_labeled(_square(0, 0, 10) + [mark])
        self.assertEqual(len(kept), 4)
        self.assertEqual(labeled, [mark])

    def test_002_hole_resta_col_predicato_del_chiamante(self):
        # D30: senza predicato un "hole" non è strutturale, con il predicato
        # del chiamante che lo riconosce sì
        hole = _circle((5, 5), 1, role="hole")
        _, labeled = forge.split_labeled(_square(0, 0, 10) + [hole])
        self.assertEqual(labeled, [hole])
        is_structural = lambda role: forge.is_structural_role(role) or role == "hole"
        kept, labeled = forge.split_labeled(_square(0, 0, 10) + [hole], is_structural)
        self.assertEqual(labeled, [])
        self.assertIn(hole, kept)


class TestCloseFreeGaps(unittest.TestCase):

    def test_001_gap_sotto_tolleranza_chiuso(self):
        edges = _square(0, 0, 10)
        edges[0] = _line((0, 0), (9.95, 0))
        # prima serve un gradino oltre il grafo esatto, dopo basta quello
        self.assertNotEqual(forge.find_loops(edges, set(), 0.1).method, "exact")
        search = forge.find_loops(forge.close_free_gaps(edges, 0.1), set(), 0.1)
        self.assertEqual(search.method, "exact")
        self.assertEqual(len(search.loops), 1)

    def test_002_gap_sopra_tolleranza_intatto(self):
        edges = _square(0, 0, 10)
        edges[0] = _line((0, 0), (9, 0))
        self.assertEqual(forge.close_free_gaps(edges, 0.1), edges)


class TestDanglingSplines(unittest.TestCase):

    def test_001_spline_con_estremo_libero(self):
        spline = Edge(role=ContourRole.UNKNOWN, start=(0.0, 0.0), end=(5.0, 5.0),
                      segment=SplineSeg(degree=1, control_points=[(0.0, 0.0), (5.0, 5.0)],
                                        knots=[0, 0, 1, 1]))
        self.assertEqual(forge.dangling_splines([spline]), [spline])
        self.assertEqual(forge.dangling_splines(_square(0, 0, 10)), [])


class TestFindNonContourEdges(unittest.TestCase):

    def test_001_diagonale_interna_esclusa(self):
        diagonal = _line((0.0, 0.0), (1.0, 2.0))
        edges = [_line((0.0, 0.0), (1.0, 0.0)), _line((1.0, 0.0), (1.0, 2.0)),
                 _line((1.0, 2.0), (0.0, 2.0)), _line((0.0, 2.0), (0.0, 0.0)), diagonal]
        self.assertEqual(forge.find_non_contour_edges(edges, 0.01), {id(diagonal)})


class TestFindLoops(unittest.TestCase):
    """Un caso per gradino della scala: LoopSearch.method dice quale ha chiuso."""

    def test_001_grafo_esatto(self):
        search = forge.find_loops(_square(0, 0, 10), set(), 0.1)
        self.assertEqual(search.method, "exact")
        self.assertEqual(len(search.loops), 1)

    def test_002_riparazione_angoli(self):
        search = forge.find_loops(_broken_square(), set(), 0.1)
        self.assertEqual(search.method, "corner_repair")
        self.assertEqual(search.repaired, 1)
        self.assertEqual(len(search.loops), 1)

    def test_003_riparazione_anche_con_un_loop_chiuso_altrove(self):
        # D57: il cerchio chiuso non blinda l'angolo rotto dalla riparazione
        search = forge.find_loops(_broken_square() + [_circle((50, 5), 2)], set(), 0.1)
        self.assertEqual(search.repaired, 1)
        self.assertEqual(len(search.loops), 2)

    def test_004_grafo_tollerante(self):
        search = forge.find_loops(_broken_square(spur=True), set(), 0.1)
        self.assertEqual(search.method, "tolerant")
        self.assertEqual(search.repaired, 0)
        self.assertEqual(len(search.skipped_corners), 1)
        self.assertEqual(len(search.unrepaired_corners), 1)

    def test_005_nessun_gradino_chiude(self):
        edges = [_line((0, 0), (10, 0)), _line((20, 0), (20, 10))]
        search = forge.find_loops(edges, set(), 0.1)
        self.assertEqual(search.method, "none")
        self.assertEqual(search.loops, [])
        self.assertEqual(len(search.open_nodes), 4)

    def test_006_riparazione_non_tocca_gli_edge_in_ingresso(self):
        edges = _broken_square()
        before = [e.segment for e in edges]
        forge.find_loops(edges, set(), 0.1)
        self.assertEqual([e.segment for e in edges], before)


class TestLoopsToFeatures(unittest.TestCase):

    def test_001_loop_con_un_edge_non_strutturale_scartato(self):
        engraved = _square(20, 0, 5, role="engrave")
        loops = forge.find_loops(_square(0, 0, 10) + engraved, set(), 0.1).loops
        self.assertEqual(len(loops), 2)
        kept = forge.structural_loops(loops)
        self.assertEqual(len(kept), 1)
        features = forge.loops_to_features(kept)
        self.assertEqual([round(f.polygon.area) for f in features], [100])


class TestPolygonize(unittest.TestCase):

    def test_001_bordo_esterno_e_buco(self):
        polygons = forge.polygonize_edges(_square(0, 0, 10) + _square(3, 3, 4), 0.1)
        features = forge.polygons_to_features(polygons)
        roles = sorted((f.role, round(f.polygon.area)) for f in features)
        self.assertIn((ContourRole.OUTER, 84), roles)
        self.assertIn((ContourRole.INNER, 16), roles)


class TestLabeledAndHierarchy(unittest.TestCase):

    def test_001_labeled_features_chiuso_e_aperto(self):
        features = forge.labeled_features([_circle((5, 5), 1, role="engrave"),
                                           _line((0, 0), (3, 0), role="engrave")])
        self.assertIsInstance(features[0], ClosedFeature)
        self.assertIsInstance(features[1], OpenFeature)
        self.assertTrue(all(f.role == "engrave" for f in features))

    def test_002_quadrato_dentro_quadrato(self):
        loops = forge.find_loops(_square(0, 0, 10) + _square(3, 3, 4), set(), 0.1).loops
        clusters, trash = forge.build_hierarchy(forge.loops_to_features(loops), label="p")
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].inners), 1)
        self.assertEqual(clusters[0].inners[0].depth, 1)
        self.assertEqual(clusters[0].label, "p")
        self.assertEqual(trash, [])


class TestComposition(unittest.TestCase):
    """I passi composti a mano nell'ordine di heal() danno i cluster di heal()."""

    def _compose(self, doc, tol):
        edges = forge.weld_degenerate_linesegs(forge.merge_cocircular_overlaps(
            forge.merge_collinear_overlaps(list(doc.edges))))
        edges, labeled = forge.split_labeled(edges)
        edges = forge.close_free_gaps(edges, tol)
        search = forge.find_loops(edges, forge.find_non_contour_edges(edges, tol), tol)
        kept = forge.structural_loops(search.loops)
        in_loops = {id(e) for loop in kept for e, _ in loop}
        features = forge.loops_to_features(kept) + forge.edges_to_open_features(
            search.edges, exclude_ids=in_loops)
        clusters, _ = forge.build_hierarchy(features)
        return clusters

    def test_001_stessi_cluster_di_heal(self):
        for name in ("rect_with_circle_hole.dxf", "flangia con fori.DXF", "two_parts.dxf"):
            with self.subTest(name=name):
                doc = forge.load_dxf(str(EXAMPLES / name))
                expected = forge.heal(doc).clusters
                got = self._compose(doc, doc.source_meta.get("tolerance", 0.05))
                self.assertEqual([c.outer.polygon.wkt for c in got],
                                 [c.outer.polygon.wkt for c in expected])
                self.assertEqual([len(c.inners) for c in got], [len(c.inners) for c in expected])


if __name__ == "__main__":
    unittest.main(verbosity=2)
