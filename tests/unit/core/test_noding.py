# tests/unit/core/test_noding.py

import math
import unittest
from forge.core.topology.noding import split_at_crossings, renode
from forge.core.topology.edge import Edge
from forge.core.primitives.segments import LineSeg, CircleSeg, ArcSeg


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _circle(center, radius):
    pt = (center[0] + radius, center[1])
    return Edge(role="unknown", start=pt, end=pt, segment=CircleSeg(center=center, radius=radius))


class TestSplitAtCrossings(unittest.TestCase):

    def test_incrocio_a_x_diventa_un_nodo(self):
        a, b = _line((0, 0), (10, 10)), _line((0, 10), (10, 0))
        noded = split_at_crossings([a, b], tolerance=0.05)
        self.assertEqual(len(noded.pieces), 4)
        # tutti e quattro i pezzi si incontrano nello stesso nodo (5, 5)
        ends = [p.end for p in noded.pieces if p.end == (5.0, 5.0)] + \
               [p.start for p in noded.pieces if p.start == (5.0, 5.0)]
        self.assertEqual(len(ends), 4)

    def test_contatto_a_t_spezza_solo_chi_viene_toccato(self):
        base, stem = _line((0, 0), (10, 0)), _line((5, 0), (5, 5))
        noded = split_at_crossings([base, stem], tolerance=0.05)
        self.assertEqual(len(noded.pieces), 3)
        self.assertIs(noded.parent_of(noded.pieces[-1]), stem)

    def test_estremi_originali_restano_i_nodi_dell_edge(self):
        a, b = _line((0, 0), (10, 0)), _line((5, -1), (5, 1))
        noded = split_at_crossings([a, b], tolerance=0.05)
        first = [p for p in noded.pieces if noded.parent_of(p) is a]
        self.assertEqual(first[0].start, a.start)
        self.assertEqual(first[-1].end, a.end)

    def test_cerchio_incrociato_diventa_archi(self):
        # un cerchio attraversato da una retta: due archi fra i due tagli
        noded = split_at_crossings([_circle((0, 0), 5), _line((-10, 0), (10, 0))], tolerance=0.05)
        arcs = [p for p in noded.pieces if isinstance(p.segment, ArcSeg)]
        self.assertEqual(len(arcs), 2)
        total = sum(p.segment.radius * p.segment._sweep() for p in arcs)
        self.assertAlmostEqual(total, 2 * math.pi * 5, places=6)

    def test_cerchio_non_toccato_resta_intero(self):
        c = _circle((0, 0), 1)
        noded = split_at_crossings([c, _line((5, 0), (6, 0))], tolerance=0.05)
        self.assertIn(c, noded.pieces)


class TestRenode(unittest.TestCase):

    def test_nodi_dal_punto_reale(self):
        # nodo arrotondato a 1 decimale, punto reale a 3: il nodo segue il punto reale
        e = Edge(role="unknown", start=(0.0, 0.0), end=(1.0, 0.0),
                 segment=LineSeg(start=(0.0, 0.0), end=(1.034, 0.0)))
        self.assertEqual(renode([e])[0].end, (1.034, 0.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
