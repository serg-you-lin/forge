"""
tests/unit/test_cluster_area.py
-------------------------------
`ForgeCluster.area` sui contorni annidati (MAP.md D89): depth dispari è vuoto,
depth pari è materiale, i segni alternano col livello.
"""

import math
import unittest

import forge

# i cerchi diventano poligoni: ~1.3 mm² di scarto su r=30
DELTA = 3.0


def _nested_circles(*radii):
    """Quadrato 100x100 con cerchi concentrici al centro, dal più grande."""
    square = [((0, 0), (100, 0)), ((100, 0), (100, 100)),
              ((100, 100), (0, 100)), ((0, 100), (0, 0))]
    entities = [{"type": "line", "start": a, "end": b} for a, b in square]
    entities += [{"type": "circle", "center": (50, 50), "radius": r} for r in radii]
    return forge.heal(forge.load_geometry(entities))


class TestClusterAreaNested(unittest.TestCase):

    def test_001_one_level_is_removed(self):
        # un vuoto solo: l'area è outer meno il vuoto
        cluster = _nested_circles(30).clusters[0]
        self.assertAlmostEqual(cluster.area, 10000 - math.pi * 900, delta=DELTA)

    def test_002_island_in_a_void_is_added_back(self):
        # cerchio dentro cerchio: il più piccolo è materiale nel vuoto, non un
        # secondo vuoto sottratto due volte
        cluster = _nested_circles(30, 10).clusters[0]
        self.assertEqual(sorted(i.depth for i in cluster.inners), [1, 2])
        self.assertAlmostEqual(cluster.area, 10000 - math.pi * (900 - 100), delta=DELTA)

    def test_003_signs_alternate_with_depth(self):
        cluster = _nested_circles(30, 10, 3).clusters[0]
        self.assertEqual(sorted(i.depth for i in cluster.inners), [1, 2, 3])
        self.assertAlmostEqual(cluster.area, 10000 - math.pi * (900 - 100 + 9), delta=DELTA)


if __name__ == "__main__":
    unittest.main()
