"""
test_corner_repair.py
---------------------
repair_merged_corners: gli angoli individuati dal clustering degli
endpoint vengono chiusi *davvero*, portando i due segmenti alla loro
intersezione reale — non solo tollerati nel grafo.
"""

import math
import unittest

from forge.model.document import ForgeDocument
from forge.model.role import ContourRole
from forge.core.topology.edge import Edge
from forge.core.primitives.segments import LineSeg, CircleSeg
from forge.core.heal import heal
from forge.core.healing.steps import repair_merged_corners
from forge.core.topology.graph import build_node_graph
from forge.core.topology.loop_finder import LoopFinder


def _edge(seg: LineSeg, decimals: int = 1) -> Edge:
    s = (round(seg.start[0], decimals), round(seg.start[1], decimals))
    e = (round(seg.end[0], decimals), round(seg.end[1], decimals))
    return Edge(role=ContourRole.UNKNOWN, start=s, end=e, segment=seg)


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class TestRepairMergedCorners(unittest.TestCase):

    TOL = 0.1

    def _broken_corner(self):
        # Angolo retto quasi chiuso: la linea orizzontale finisce a x=10.03,
        # la verticale parte da x=10.07. Arrotondati a 1 decimale danno nodi
        # diversi (10.0 vs 10.1) → il grafo esatto non chiude.
        horiz = LineSeg(start=(0.0, 0.0), end=(10.03, 0.0))
        vert = LineSeg(start=(10.07, 0.0), end=(10.07, 10.0))
        return [_edge(horiz), _edge(vert)]

    def test_corner_pulled_to_true_intersection(self):
        edges = self._broken_corner()
        graph_c = build_node_graph(edges, epsilon=self.TOL)
        self.assertEqual(len(graph_c.merged_clusters()), 1)

        edges, n_rep, skipped = repair_merged_corners(edges, self.TOL)

        self.assertEqual(n_rep, 1)
        self.assertEqual(skipped, [])

        segs = [e.segment for e in edges]
        horiz = next(s for s in segs if s.start == (0.0, 0.0))
        vert = next(s for s in segs if s.end == (10.07, 10.0))

        # i due segmenti condividono ora un endpoint esatto...
        self.assertEqual(horiz.end, vert.start)
        # ...ed è l'intersezione reale delle due rette: (10.07, 0.0)
        self.assertAlmostEqual(horiz.end[0], 10.07, places=6)
        self.assertAlmostEqual(horiz.end[1], 0.0, places=6)

    def test_exact_graph_closes_after_repair(self):
        # aggiunge i due lati mancanti: ora è un quadrilatero con un solo
        # angolo rotto, che dopo la riparazione deve chiudersi sul grafo esatto
        edges = self._broken_corner()
        edges.append(_edge(LineSeg(start=(10.07, 10.0), end=(0.0, 10.0))))
        edges.append(_edge(LineSeg(start=(0.0, 10.0), end=(0.0, 0.0))))

        edges, _, _ = repair_merged_corners(edges, self.TOL)

        loops = LoopFinder().find(build_node_graph(edges))
        self.assertEqual(len(loops), 1)
        self.assertEqual(len(loops[0]), 4)

    def test_branching_cluster_is_skipped_not_welded(self):
        # tre estremi nello stesso cluster: intersezione a due non definita,
        # il cluster va saltato senza saldare nulla
        edges = self._broken_corner()
        edges.append(_edge(LineSeg(start=(10.04, 0.0), end=(10.04, -5.0))))

        _, n_rep, skipped = repair_merged_corners(edges, self.TOL)

        self.assertEqual(n_rep, 0)
        self.assertEqual(len(skipped), 1)


class TestRepairWithOtherLoopClosed(unittest.TestCase):

    def test_loop_chiuso_altrove_non_blinda_la_riparazione(self):
        # D57: angolo rotto con distanza reale 0.11 > tolerance 0.1 — _preprocess
        # lo salta, lo chiude solo la riparazione via clustering (nodi 10.0 e
        # 10.1). Un cerchio chiuso da solo altrove non deve impedirla.
        edges = [
            _edge(LineSeg(start=(0.0, 0.0), end=(10.03, 0.0))),
            _edge(LineSeg(start=(10.14, 0.0), end=(10.14, 10.0))),
            _edge(LineSeg(start=(10.14, 10.0), end=(0.0, 10.0))),
            _edge(LineSeg(start=(0.0, 10.0), end=(0.0, 0.0))),
            Edge(role=ContourRole.UNKNOWN, start=(52.0, 5.0), end=(52.0, 5.0),
                 segment=CircleSeg(center=(50.0, 5.0), radius=2.0)),
        ]
        doc = ForgeDocument(edges=edges, annotations=[],
                            source_meta={"tolerance": 0.1}, source_path="")
        result = heal(doc)
        self.assertEqual(len(result.clusters), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
