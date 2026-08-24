# tests/unit/core/test_graph.py

import unittest
from shapely.geometry import LineString
from forge.core.topology.graph import Graph, build_node_graph
from forge.adapters.bridge.edge import Edge


def _make_edge(p1, p2):
    return Edge(
        source_ref=None,
        layer="",
        start=p1,
        end=p2,
        geometry=LineString([p1, p2]),
    )

def _triangle_edges():
    a, b, c = (0.0, 0.0), (1.0, 0.0), (0.5, 1.0)
    return [_make_edge(a, b), _make_edge(b, c), _make_edge(c, a)]


class TestGraphDegree(unittest.TestCase):

    def test_degree_triangolo(self):
        g = build_node_graph(_triangle_edges())
        for node in g.nodes:
            self.assertEqual(g.degree(node), 2)


class TestGraphBranchingNodes(unittest.TestCase):

    def test_nodo_con_tre_connessioni(self):
        edges = _triangle_edges()
        edges.append(_make_edge((0.0, 0.0), (1.0, 1.0)))
        g = build_node_graph(edges)
        self.assertIn((0.0, 0.0), g.branching_nodes())


class TestGraphPruned(unittest.TestCase):

    def test_catena_aperta_rimossa(self):
        a, b, c = (0.0, 0.0), (1.0, 0.0), (2.0, 0.0)
        edges = [_make_edge(a, b), _make_edge(b, c)]
        g = build_node_graph(edges)
        self.assertEqual(len(g.pruned().nodes), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)