# tests/unit/core/test_island_segments_consistency.py

"""
Per ogni contorno letto da `island()`, `.polygon` (la forma geometrica finita,
quella che SVG/view_model disegnano) e `.segments` (i pezzi grezzi che `to_dxf`
scrive) devono descrivere la stessa forma: sono due rappresentazioni dello
stesso contorno, non due letture indipendenti. Trovato il 12 ottobre: su
`regr_04.dxf`, un contorno esterno di vista isometrica (l'unione di più facce,
D100) aveva `.segments` scollegati (26 giunzioni rotte su 84) che coprivano un
terzo dell'area vera — invisibile sia a `test_golden_islands.py` (confronta
solo bbox+conteggio) sia a SVG/view_model (leggono solo `.polygon`).
Non è un golden: non confronta contro un valore congelato, è un'invariante
sempre vera per definizione — non va mai rigenerato, va solo fatto passare.
"""

import unittest
from pathlib import Path

import topo
from topo.core.island import GRAPH_EPSILON
from topo.core.primitives.polygon_builder import build_polygon
from topo.core.primitives.segments import DEFAULT_TOLERANCE

SOURCE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "golden_islands"
MAX_GAP = 0.5
# di quanto può spostarsi il bordo della stessa forma fra le due letture: la
# freccia della discretizzazione più la griglia dei nodi dell'unione di facce
# (D106) — lungo tutto il perimetro, è l'area di una fascia così larga
OUTLINE_BAND = DEFAULT_TOLERANCE + GRAPH_EPSILON


class TestIslandSegmentsConsistency(unittest.TestCase):

    def _assert_same_shape(self, contour, where):
        poly = contour.polygon
        rebuilt = build_polygon(contour.segments)
        self.assertIsNotNone(rebuilt, f"{where}: .segments non formano un poligono valido")
        sym = poly.symmetric_difference(rebuilt).area
        tol = max(poly.area * 0.01, poly.length * OUTLINE_BAND)
        self.assertLess(sym, tol,
                         f"{where}: .polygon (area={poly.area:.4f}) e .segments "
                         f"(area={rebuilt.area:.4f}) descrivono forme diverse "
                         f"(differenza simmetrica={sym:.4f})")


def _make_test(dxf: Path):
    def test(self):
        result = topo.island(topo.load_dxf(str(dxf)), max_gap=MAX_GAP)
        for ci, cluster in enumerate(result.clusters):
            self._assert_same_shape(cluster.outer, f"{dxf.stem}.cluster[{ci}].outer")
            for ii, inner in enumerate(cluster.inners):
                self._assert_same_shape(inner, f"{dxf.stem}.cluster[{ci}].inner[{ii}]")
    return test


for _dxf in sorted(SOURCE_DIR.glob("*.dxf")):
    setattr(TestIslandSegmentsConsistency, f"test_{_dxf.stem}", _make_test(_dxf))


if __name__ == "__main__":
    unittest.main()
