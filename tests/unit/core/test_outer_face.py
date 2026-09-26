# tests/unit/core/test_outer_face.py

import unittest
from forge.core.topology.outer_face import outer_face
from forge.core.topology.noding import split_at_crossings
from forge.core.topology.edge import Edge
from forge.core.primitives.segments import LineSeg, CircleSeg


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _poly(*pts):
    return [_line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def _face(edges):
    return outer_face(split_at_crossings(edges, tolerance=0.05).pieces, epsilon=0.01)


class TestOuterFace(unittest.TestCase):

    def test_quadrato_con_diagonale(self):
        # la diagonale divide il quadrato in due facce: il contorno esterno è il quadrato
        edges = _poly((0, 0), (10, 0), (10, 10), (0, 10)) + [_line((0, 0), (10, 10))]
        face = _face(edges)
        self.assertAlmostEqual(face.polygon.area, 100.0)
        self.assertEqual(len(face.edges), 4)

    def test_asse_che_sporge_e_una_sporgenza(self):
        # un asse che attraversa il quadrato ed esce dai due lati
        edges = _poly((0, 0), (10, 0), (10, 10), (0, 10)) + [_line((-3, 5), (13, 5))]
        face = _face(edges)
        self.assertAlmostEqual(face.polygon.area, 100.0)
        self.assertEqual(len(face.spurs), 2)

    def test_l_con_rientro(self):
        edges = _poly((0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10))
        self.assertAlmostEqual(_face(edges).polygon.area, 64.0)

    def test_punto_piu_a_sinistra_a_meta_di_un_arco(self):
        # vista stretta dentro un cerchio che la attraversa: il nodo più a
        # sinistra è dentro il cerchio, il punto più a sinistra è sul cerchio
        view = _poly((-1, -3), (1, -3), (1, 20), (-1, 20))
        circle = Edge(role="unknown", start=(8, 0), end=(8, 0),
                      segment=CircleSeg(center=(0, 0), radius=8))
        face = _face(view + [circle])
        self.assertGreater(face.polygon.area, 3.14 * 64)
        # la parte di vista che esce sopra il cerchio è contorno
        self.assertGreater(face.polygon.bounds[3], 19.9)

    def test_nessun_giro(self):
        self.assertIsNone(_face([_line((0, 0), (5, 0))]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
