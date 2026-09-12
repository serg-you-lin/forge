"""
test_simplify_points.py
------------------------
Test unitari per forge.tools.simplify_points.

Semantica di `detect_corners` (ereditata da smoother_5.py::classifica_punti):
l'angolo interno ai due lati adiacenti è VICINO A 180 gradi su un tratto
liscio/dritto (i lati puntano quasi in direzioni opposte) e VICINO A 0 su una
punta acuta (i lati ripiegano quasi su se stessi). Un angolo retto (90 gradi,
il vertice di un rettangolo) sta in mezzo. "spigolo" = angolo SOTTO soglia:
una soglia bassa cattura solo le punte acute, una soglia sopra 90 cattura
anche i vertici retti.

Copre:
  - detect_corners  : punte acute sotto soglia, punti lisci ignorati,
                       estremi mai spigoli su polilinea aperta
  - fit_primitives   : tratti corti -> LineSeg, tratti lunghi -> SplineSeg,
                        loop senza spigoli -> un solo SplineSeg chiuso
  - simplify_points  : le due funzioni in sequenza, soglie del chiamante
"""

import math
import unittest
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from forge.core.primitives.segments import LineSeg, SplineSeg
from forge.tools.simplify_points import (
    detect_corners,
    fit_primitives,
    simplify_points,
)


def densify_edge(p1, p2, n_extra):
    """Punti intermedi collineari fra p1 e p2 (esclusi gli estremi)."""
    return [
        (p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t)
        for t in (i / (n_extra + 1) for i in range(1, n_extra + 1))
    ]


# ---------------------------------------------------------------------------
# detect_corners
# ---------------------------------------------------------------------------

class TestDetectCorners(unittest.TestCase):

    def test_001_punta_acuta_sotto_soglia_e_spigolo(self):
        # Punta a ~22.6 gradi: sotto una soglia di 50 e' spigolo.
        spike = [(0, 0), (2, 10), (4, 0)]
        corners = detect_corners(spike, angle_threshold_deg=50.0, closed=False)
        self.assertEqual(corners, [False, True, False])

    def test_002_vertice_retto_serve_soglia_sopra_90(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        # Soglia bassa (tipica per punte acute): il vertice a 90 gradi non e' spigolo.
        self.assertEqual(
            detect_corners(square, angle_threshold_deg=50.0, closed=True),
            [False, False, False, False],
        )
        # Soglia sopra 90: il vertice retto ora e' spigolo.
        self.assertEqual(
            detect_corners(square, angle_threshold_deg=100.0, closed=True),
            [True, True, True, True],
        )

    def test_003_punti_su_lato_dritto_non_sono_mai_spigoli(self):
        # Punto a meta' di un lato: angolo ~180 gradi, non scende sotto
        # nessuna soglia ragionevole, a differenza dei vertici veri.
        corners_pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
        square = []
        for i in range(4):
            square.append(corners_pts[i])
            square.extend(densify_edge(corners_pts[i], corners_pts[(i + 1) % 4], 1))
        corners = detect_corners(square, angle_threshold_deg=100.0, closed=True)
        # indici pari = vertici (True), indici dispari = punti medi (False)
        self.assertEqual(corners, [True, False] * 4)

    def test_004_polilinea_aperta_estremi_mai_spigoli(self):
        # Stessa punta acuta di test_001, ma come polilinea aperta: se fosse
        # chiusa il primo e l'ultimo punto sarebbero spigoli fra loro fra
        # loro; aperta, non lo sono mai.
        zigzag = [(0, 0), (2, 10), (4, 0)]
        corners = detect_corners(zigzag, angle_threshold_deg=170.0, closed=False)
        self.assertEqual(corners, [False, True, False])

    def test_005_meno_di_tre_punti_nessuno_spigolo(self):
        self.assertEqual(detect_corners([(0, 0), (1, 1)]), [False, False])


# ---------------------------------------------------------------------------
# fit_primitives
# ---------------------------------------------------------------------------

class TestFitPrimitives(unittest.TestCase):

    def test_010_quadrato_diventa_quattro_lineseg(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        corners = detect_corners(square, angle_threshold_deg=100.0, closed=True)
        primitives = fit_primitives(square, corners, closed=True)
        self.assertEqual(len(primitives), 4)
        self.assertTrue(all(isinstance(p, LineSeg) for p in primitives))
        # Il loop si richiude: ultimo end coincide col primo start.
        self.assertEqual(primitives[-1].end, primitives[0].start)

    def test_011_tratto_curvo_denso_diventa_una_spline(self):
        # Semicerchio discretizzato densamente, nessun punto sotto soglia
        # (angoli vicini a 180): un solo tratto -> un solo SplineSeg.
        arc_points = [
            (10 * math.cos(t), 10 * math.sin(t))
            for t in (i * math.pi / 20 for i in range(20))
        ]
        primitives = simplify_points(arc_points, closed=True, angle_threshold_deg=50.0)
        self.assertEqual(len(primitives), 1)
        self.assertIsInstance(primitives[0], SplineSeg)

    def test_012_tratto_sotto_soglia_min_punti_resta_lineseg(self):
        # 3 punti + punto di chiusura del loop = 4: sotto min_points_for_spline=5
        # anche senza alcuno spigolo marcato -> resta una sequenza di LineSeg.
        pts = [(0, 0), (5, 5), (10, 0)]
        corners = [False, False, False]
        primitives = fit_primitives(pts, corners, closed=True, min_points_for_spline=5)
        self.assertTrue(all(isinstance(p, LineSeg) for p in primitives))

    def test_013_punti_duplicati_consecutivi_rimossi(self):
        square = [(0, 0), (0, 0), (10, 0), (10, 10), (10, 10), (0, 10)]
        # Spigoli passati esplicitamente (i duplicati confonderebbero il calcolo
        # angolare, non e' quello sotto test qui): solo i 4 vertici veri.
        corners = [True, False, True, True, False, True]
        primitives = fit_primitives(square, corners, closed=True)
        self.assertTrue(all(isinstance(p, LineSeg) for p in primitives))
        # nessun segmento degenere (start == end) rimasto dai duplicati
        self.assertTrue(all(p.start != p.end for p in primitives))


# ---------------------------------------------------------------------------
# simplify_points
# ---------------------------------------------------------------------------

class TestSimplifyPoints(unittest.TestCase):

    def test_020_soglie_sono_parametri_del_chiamante(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        # Soglia bassa: il vertice retto non e' uno spigolo -> un solo SplineSeg.
        primitives = simplify_points(square, angle_threshold_deg=10.0)
        self.assertEqual(len(primitives), 1)
        self.assertIsInstance(primitives[0], SplineSeg)

        # Soglia sopra 90: i 4 vertici sono spigoli -> 4 LineSeg.
        primitives = simplify_points(square, angle_threshold_deg=100.0)
        self.assertEqual(len(primitives), 4)
        self.assertTrue(all(isinstance(p, LineSeg) for p in primitives))


if __name__ == "__main__":
    unittest.main()
