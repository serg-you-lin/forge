# tests/unit/core/test_island_regressions.py

"""
Regressioni isolate su `read_island()`, trovate l'11 ottobre aprendo
`anch_02.dxf` (golden_islands) in un viewer e viste sbagliate a occhio da
Federico — non intercettate da nessun golden esistente (vedi TODO.md).
Ogni fixture è un ritaglio minimo del foglio reale, salvato con l'API di
topo stessa (mai ezdxf diretto): `tests/data/regressions/*.dxf`.
"""

import unittest
from pathlib import Path

import topo
from topo.core.island import read_island

FIXTURES = Path(__file__).resolve().parent.parent.parent / "data" / "regressions"
TOLERANCE = 0.05
MAX_GAP = 0.5


class TestGhostLoop(unittest.TestCase):
    """15 edge (2 ArcSeg + 13 SplineSeg) di un solo foro della vista
    isometrica di anch_02: un'ellisse proiettata pulita (2 spline che si
    chiudono da estremo a estremo). Preesistente, non introdotto dal lavoro
    PDF né da D98-D101 (bisecato su 1b5b02e, D99: identico)."""

    def test_un_foro_non_ha_un_giro_fantasma_annidato(self):
        doc = topo.load_dxf(str(FIXTURES / "island_ghost_loop.dxf"), tolerance=TOLERANCE)
        reading = read_island(doc.edges, tolerance=TOLERANCE, max_gap=MAX_GAP)
        self.assertIsNotNone(reading.outer)
        self.assertAlmostEqual(reading.outer.polygon.area, 16.247, places=2)
        # oggi: 1 giro fantasma (~11 mm^2, 2 ArcSeg + spline seghettate) annidato
        # nello stesso punto — non un buco vero, un artefatto del noding
        self.assertEqual(len(reading.inner_loops), 0,
                          "giro fantasma annidato nello stesso foro: non e' una feature reale")


class TestTangentSpike(unittest.TestCase):
    """71 edge di una sola asola della stessa vista isometrica. Pulita su
    1b5b02e (D99, punta a x=1506.30), rotta già su 091970a (D100, "the outer
    face is the boundary of the union of the closed faces") — D101 e' innocente
    su questo caso."""

    def test_la_punta_arrotondata_non_ha_una_spike(self):
        doc = topo.load_dxf(str(FIXTURES / "island_tangent_spike.dxf"), tolerance=TOLERANCE)
        reading = read_island(doc.edges, tolerance=TOLERANCE, max_gap=MAX_GAP)
        self.assertIsNotNone(reading.outer)
        self.assertAlmostEqual(reading.outer.polygon.area, 1011.27, places=1)
        max_x = max(x for x, _ in reading.outer.polygon.exterior.coords)
        # pulito (D99) = 1506.30; rotto (D100, oggi) = 1506.63 (spike di 0.33mm)
        self.assertLess(max_x, 1506.4,
                         "vertice spurio sulla punta arrotondata, oltre la curva liscia")


if __name__ == "__main__":
    unittest.main(verbosity=2)
