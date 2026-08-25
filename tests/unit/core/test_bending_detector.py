# tests/unit/core/test_bending_detector.py

import unittest
from forge.core.topology.graph import build_node_graph
from forge.core.topology.bending_detector import BendingDetector
from forge.adapters.bridge.edge import Edge
from forge.core.primitives.segments import LineSeg
from forge.model.role import ContourRole


def _make_edge(p1, p2):
    return Edge(
        source_ref=object(),
        role=ContourRole.BEND,
        start=p1,
        end=p2,
        segment=LineSeg(start=p1, end=p2),
    )


class TestBendingDetector(unittest.TestCase):

    def test_linea_interna_confermata(self):
        # rettangolo con diagonale interna
        #
        #  (0,2)-----(1,2)
        #    |    /    |
        #  (0,0)-----(1,0)
        #
        # la diagonale (0,0)-(1,2) ha entrambi gli endpoint su nodi branching
        # e il centroide è interno al convex hull → confermata come bending

        edges = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (1.0, 2.0)),
            _make_edge((1.0, 2.0), (0.0, 2.0)),
            _make_edge((0.0, 2.0), (0.0, 0.0)),
            _make_edge((0.0, 0.0), (1.0, 2.0)),  # bending
        ]
        g = build_node_graph(edges)
        result = BendingDetector(tolerance=0.01).detect(g, edges)
        bending_edge = edges[-1]
        self.assertIn(id(bending_edge.source_ref), result)

    def test_linea_sul_bordo_ignorata(self):
        # triangolo semplice — nessun nodo branching → nessun bending
        edges = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (0.5, 1.0)),
            _make_edge((0.5, 1.0), (0.0, 0.0)),
        ]
        g = build_node_graph(edges)
        result = BendingDetector(tolerance=0.01).detect(g, edges)
        self.assertEqual(len(result), 0)

    def test_nessun_branching_nessun_bending(self):
        # catena aperta — nessun nodo branching
        edges = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (2.0, 0.0)),
        ]
        g = build_node_graph(edges)
        result = BendingDetector(tolerance=0.01).detect(g, edges)
        self.assertEqual(len(result), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)