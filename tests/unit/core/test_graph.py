# tests/unit/core/test_graph.py

import unittest
from forge.core.topology.graph import Graph, build_node_graph, cluster_points
from forge.core.topology.edge import Edge
from forge.core.primitives.segments import LineSeg
from forge.model.role import ContourRole


def _make_edge(p1, p2):
    return Edge(
        role=ContourRole.UNKNOWN,
        start=p1,
        end=p2,
        segment=LineSeg(start=p1, end=p2),
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


class TestClusterPoints(unittest.TestCase):

    def test_epsilon_zero_is_identity(self):
        pts = [(0.0, 0.0), (0.02, 0.0), (5.0, 5.0)]
        m = cluster_points(pts, 0.0)
        self.assertEqual(m, {p: p for p in pts})

    def test_merges_points_within_epsilon(self):
        pts = [(0.0, 0.0), (0.02, 0.0), (5.0, 5.0)]
        m = cluster_points(pts, 0.1)
        self.assertEqual(m[(0.0, 0.0)], m[(0.02, 0.0)])
        self.assertNotEqual(m[(0.0, 0.0)], m[(5.0, 5.0)])

    def test_representative_is_lexicographic_min(self):
        pts = [(1.0, 0.0), (0.98, 0.0), (1.02, 0.0)]
        m = cluster_points(pts, 0.1)
        self.assertEqual(set(m.values()), {(0.98, 0.0)})

    def test_transitive_chaining(self):
        # caveat documentato: punti a catena entro epsilon collassano tutti
        pts = [(0.0, 0.0), (0.08, 0.0), (0.16, 0.0)]
        m = cluster_points(pts, 0.1)
        self.assertEqual(len(set(m.values())), 1)


class TestBuildNodeGraphClustering(unittest.TestCase):

    def _open_square_split_corner(self):
        # quadrato chiuso, ma un angolo è spezzato in due nodi a 0.06 di
        # distanza — come un arrotondamento al confine di cella
        a, b = (0.0, 0.0), (10.0, 0.0)
        c1, c2 = (10.0, 10.0), (10.06, 10.0)
        d = (0.0, 10.0)
        return [
            _make_edge(a, b),
            _make_edge(b, c1),
            _make_edge(c2, d),
            _make_edge(d, a),
        ]

    def test_exact_graph_leaves_corner_open(self):
        g = build_node_graph(self._open_square_split_corner())
        self.assertEqual(len(g.open_nodes()), 2)
        self.assertEqual(len(g.pruned().nodes), 0)

    def test_clustered_graph_closes_corner(self):
        g = build_node_graph(self._open_square_split_corner(), epsilon=0.1)
        self.assertEqual(g.open_nodes(), [])
        for node in g.pruned().nodes:
            self.assertEqual(g.degree(node), 2)

    def test_clustering_preserves_edge_objects(self):
        edges = self._open_square_split_corner()
        g = build_node_graph(edges, epsilon=0.1)
        seen = {id(e) for conn in g.nodes.values() for e, _ in conn}
        self.assertEqual(seen, {id(e) for e in edges})


if __name__ == "__main__":
    unittest.main(verbosity=2)