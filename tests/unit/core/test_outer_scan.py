# tests/unit/core/test_outer_scan.py

import math
import unittest
from forge.core.healing.outer_scan import outer_candidate_edges, AXIS_X, AXIS_Y
from forge.core.topology.edge import Edge
from forge.core.primitives.segments import LineSeg, ArcSeg, CircleSeg


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _poly(*pts):
    return [_line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


class TestOuterCandidateEdges(unittest.TestCase):

    def test_quadrato_tutti_i_lati(self):
        # i lati orizzontali li vede solo il raggio verticale: servono entrambi gli assi
        edges = _poly((0, 0), (10, 0), (10, 10), (0, 10))
        oc = outer_candidate_edges(edges)
        self.assertEqual(oc.ids, {id(e) for e in edges})
        top = edges[2]
        self.assertTrue(all(h.axis == AXIS_X for h in oc.hits_of(top)))

    def test_foro_non_e_candidato(self):
        outer = _poly((0, 0), (10, 0), (10, 10), (0, 10))
        hole = Edge(role="unknown", start=(6, 5), end=(6, 5),
                    segment=CircleSeg(center=(5, 5), radius=1))
        oc = outer_candidate_edges(outer + [hole])
        self.assertNotIn(id(hole), oc.ids)
        self.assertEqual(len(oc.edges), 4)

    def test_rientro_a_l_tutti_i_lati(self):
        # L: i due lati del rientro sono esterni, visti da uno dei due assi
        edges = _poly((0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10))
        oc = outer_candidate_edges(edges)
        self.assertEqual(oc.ids, {id(e) for e in edges})

    def test_binario_interno_parallelo_scartato(self):
        # proiezione quasi coincidente, ma dentro: mai all'estremo
        outer = _poly((0, 0), (10, 0), (10, 10), (0, 10))
        ghost = _line((9.9, 1), (9.9, 9))
        oc = outer_candidate_edges(outer + [ghost])
        self.assertNotIn(id(ghost), oc.ids)

    def test_arco_esterno(self):
        # semicerchio in cima a un rettangolo: l'arco è il bordo superiore
        base = [_line((10, 5), (10, 0)), _line((10, 0), (0, 0)), _line((0, 0), (0, 5))]
        arc = Edge(role="unknown", start=(10, 5), end=(0, 5),
                   segment=ArcSeg(center=(5, 5), radius=5, start_angle=0.0,
                                  end_angle=math.pi, ccw=True))
        oc = outer_candidate_edges(base + [arc])
        self.assertIn(id(arc), oc.ids)
        self.assertTrue(any(h.axis == AXIS_Y for h in oc.hits_of(arc)))

    def test_lista_vuota(self):
        oc = outer_candidate_edges([])
        self.assertEqual(oc.edges, [])
        self.assertEqual(oc.n_rays, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
