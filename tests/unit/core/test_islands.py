# tests/unit/core/test_islands.py

import unittest
from forge.core.healing.islands import spatial_islands
from forge.core.topology.edge import Edge
from forge.core.primitives.segments import LineSeg, CircleSeg


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _square(x, y, size=10):
    pts = [(x, y), (x + size, y), (x + size, y + size), (x, y + size)]
    return [_line(pts[i], pts[(i + 1) % 4]) for i in range(4)]


class TestSpatialIslands(unittest.TestCase):

    def test_due_quadrati_lontani_due_isole(self):
        islands = spatial_islands(_square(0, 0) + _square(100, 0), gap_tolerance=5)
        self.assertEqual(len(islands), 2)
        self.assertEqual([len(i.edges) for i in islands], [4, 4])

    def test_gap_sotto_tolleranza_unisce(self):
        # 3mm di distanza, tolleranza 5: stessa isola anche senza toccarsi
        islands = spatial_islands(_square(0, 0) + _square(13, 0), gap_tolerance=5)
        self.assertEqual(len(islands), 1)
        self.assertEqual(islands[0].bbox, (0.0, 0.0, 23.0, 10.0))

    def test_catena_transitiva(self):
        # A vicino a B, B vicino a C, A lontano da C: una sola isola
        edges = _square(0, 0) + _square(12, 0) + _square(24, 0)
        self.assertEqual(len(spatial_islands(edges, gap_tolerance=3)), 1)

    def test_vicino_in_x_lontano_in_y(self):
        islands = spatial_islands(_square(0, 0) + _square(0, 50), gap_tolerance=5)
        self.assertEqual(len(islands), 2)

    def test_foro_vicino_al_lato_stessa_isola(self):
        hole = Edge(role="unknown", start=(3, 5), end=(3, 5),
                    segment=CircleSeg(center=(2, 5), radius=1))
        islands = spatial_islands(_square(0, 0) + [hole], gap_tolerance=1.5)
        self.assertEqual(len(islands), 1)

    def test_foro_lontano_dai_lati_isola_a_se(self):
        # solo vicinanza: che il foro stia DENTRO lo dice il contorno esterno, dopo
        hole = Edge(role="unknown", start=(52, 50), end=(52, 50),
                    segment=CircleSeg(center=(50, 50), radius=2))
        islands = spatial_islands(_square(0, 0, 100) + [hole], gap_tolerance=5)
        self.assertEqual(len(islands), 2)

    def test_diagonale_lunga_non_unisce_per_bbox(self):
        # la bbox della diagonale copre il quadrato, la distanza vera no
        diag = _line((0, 0), (100, 100))
        islands = spatial_islands([diag] + _square(70, 5), gap_tolerance=2)
        self.assertEqual(len(islands), 2)

    def test_ordinate_per_area(self):
        islands = spatial_islands(_square(0, 0, 5) + _square(100, 0, 20), gap_tolerance=1)
        self.assertEqual(islands[0].width, 20)

    def test_lista_vuota(self):
        self.assertEqual(spatial_islands([], gap_tolerance=1), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
