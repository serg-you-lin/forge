"""
test_geometry.py
----------------
Test unitari per le funzioni pure di forge.core.geometry e
forge.core.classification.hole_detector.

Copre:
  - is_threaded_hole      : riconosce fori filettati (cerchio + arco a 270°)
  - is_countersink_outer  : riconosce il cerchio esterno di un countersink
  - are_collinear         : verifica collinearità di due LineString
  - group_collinear_lines : raggruppa LineString collineari
"""

import unittest
import math
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from shapely.geometry import LineString

from forge.core.primitives.segments import ArcSeg
from forge.core.classification.hole_detector import is_threaded_hole, is_countersink_outer
from forge.core.geometry import are_collinear, group_collinear_lines


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_arc(cx, cy, radius, start_angle, end_angle):
    """Crea un ArcSeg con angoli in gradi."""
    return ArcSeg(
        center=(cx, cy),
        radius=radius,
        start_angle=math.radians(start_angle),
        end_angle=math.radians(end_angle),
        ccw=True
    )


def make_line(x1, y1, x2, y2) -> LineString:
    """Crea una LineString shapely."""
    return LineString([(x1, y1), (x2, y2)])


# ---------------------------------------------------------------------------
# is_threaded_hole
# ---------------------------------------------------------------------------

class TestIsThreadedHole(unittest.TestCase):

    def test_001_arco_270_gradi_e_filettato(self):
        arc = make_arc(0, 0, 6, 0, 270)
        self.assertTrue(is_threaded_hole((0, 0), 5, [arc]))

    def test_002_arco_260_gradi_entro_tolleranza(self):
        arc = make_arc(0, 0, 6, 0, 260)
        self.assertTrue(is_threaded_hole((0, 0), 5, [arc]))

    def test_003_arco_180_gradi_non_filettato(self):
        arc = make_arc(0, 0, 6, 0, 180)
        self.assertFalse(is_threaded_hole((0, 0), 5, [arc]))

    def test_004_arco_360_non_filettato(self):
        arc = make_arc(0, 0, 6, 0, 360)
        self.assertFalse(is_threaded_hole((0, 0), 5, [arc]))

    def test_005_tolleranza_custom_stretta(self):
        arc = make_arc(0, 0, 6, 0, 260)
        self.assertFalse(is_threaded_hole((0, 0), 5, [arc], angle_tolerance=1.0))

    def test_006_arco_ruotato_stesso_risultato(self):
        arc = make_arc(0, 0, 6, 45, 315)  # 270 gradi, ruotato
        self.assertTrue(is_threaded_hole((0, 0), 5, [arc]))

    def test_007_nessun_arco(self):
        self.assertFalse(is_threaded_hole((0, 0), 5, []))

    def test_008_arco_non_concentrico(self):
        arc = make_arc(100, 100, 6, 0, 270)
        self.assertFalse(is_threaded_hole((0, 0), 5, [arc]))

    def test_009_arco_piu_piccolo_del_cerchio(self):
        arc = make_arc(0, 0, 4, 0, 270)
        self.assertFalse(is_threaded_hole((0, 0), 5, [arc]))

    def test_010_piu_archi_uno_solo_valido(self):
        arc_bad = make_arc(0, 0, 6, 0, 180)   # non filettato
        arc_ok  = make_arc(0, 0, 6, 0, 270)   # filettato
        self.assertTrue(is_threaded_hole((0, 0), 5, [arc_bad, arc_ok]))

    def test_011_tolleranza_centro(self):
        # Centro leggermente spostato, entro tolleranza
        arc = make_arc(0.5, 0.5, 6, 0, 270)
        self.assertTrue(is_threaded_hole((0, 0), 5, [arc], tolerance_center=1.0))

    def test_012_centro_fuori_tolleranza(self):
        arc = make_arc(2.0, 0, 6, 0, 270)
        self.assertFalse(is_threaded_hole((0, 0), 5, [arc], tolerance_center=1.0))


# ---------------------------------------------------------------------------
# is_countersink_outer
# ---------------------------------------------------------------------------

class TestIsCountersinkOuter(unittest.TestCase):

    def test_001_cerchio_grande_con_piccolo_concentrico(self):
        """Il cerchio esterno ha un cerchio più piccolo concentrico."""
        self.assertTrue(is_countersink_outer((0, 0), 10, [((0, 0), 5)]))

    def test_002_cerchio_senza_figli(self):
        self.assertFalse(is_countersink_outer((0, 0), 10, []))

    def test_003_cerchio_con_figlio_non_concentrico(self):
        self.assertFalse(is_countersink_outer((0, 0), 10, [((50, 50), 5)]))

    def test_004_cerchio_con_figlio_stesso_raggio(self):
        self.assertFalse(is_countersink_outer((0, 0), 10, [((0, 0), 10)]))

    def test_005_cerchio_con_figlio_piu_grande(self):
        self.assertFalse(is_countersink_outer((0, 0), 10, [((0, 0), 15)]))

    def test_006_piu_figli_uno_solo_concentrico(self):
        siblings = [((50, 50), 3), ((0, 0), 4)]
        self.assertTrue(is_countersink_outer((0, 0), 10, siblings))

    def test_007_tolleranza_centro(self):
        # Centro leggermente spostato, entro tolleranza
        self.assertTrue(is_countersink_outer((0, 0), 10, [((0.5, 0.5), 5)], tolerance=1.0))

    def test_008_centro_fuori_tolleranza(self):
        self.assertFalse(is_countersink_outer((0, 0), 10, [((2.0, 0), 5)], tolerance=1.0))


# ---------------------------------------------------------------------------
# are_collinear
# ---------------------------------------------------------------------------

class TestAreCollinear(unittest.TestCase):

    def test_001_stessa_linea_orizzontale(self):
        a = make_line(0, 10, 45, 10)
        b = make_line(125, 10, 170, 10)
        self.assertTrue(are_collinear(a, b))

    def test_002_stessa_linea_verticale(self):
        a = make_line(50, 0, 50, 30)
        b = make_line(50, 80, 50, 120)
        self.assertTrue(are_collinear(a, b))

    def test_003_parallele_non_collineari(self):
        a = make_line(0, 10, 100, 10)
        b = make_line(0, 20, 100, 20)
        self.assertFalse(are_collinear(a, b))

    def test_004_perpendicolari(self):
        a = make_line(0, 0, 100, 0)
        b = make_line(50, -50, 50, 50)
        self.assertFalse(are_collinear(a, b))

    def test_005_stessa_retta_obliqua(self):
        a = make_line(0, 0, 10, 10)
        b = make_line(20, 20, 30, 30)
        self.assertTrue(are_collinear(a, b))

    def test_006_direzioni_opposte_stessa_retta(self):
        a = make_line(0, 5, 45, 5)
        b = make_line(170, 5, 125, 5)
        self.assertTrue(are_collinear(a, b))

    def test_007_entro_tolleranza(self):
        a = make_line(0, 10.00, 100, 10.00)
        b = make_line(0, 10.05, 100, 10.05)
        self.assertTrue(are_collinear(a, b, tolerance=0.1))

    def test_008_fuori_tolleranza(self):
        a = make_line(0, 10.00, 100, 10.00)
        b = make_line(0, 10.20, 100, 10.20)
        self.assertFalse(are_collinear(a, b, tolerance=0.1))

    def test_009_linea_degenere(self):
        a = make_line(0, 0, 0, 0)
        b = make_line(10, 10, 10, 10)
        self.assertFalse(are_collinear(a, b))


# ---------------------------------------------------------------------------
# group_collinear_lines
# ---------------------------------------------------------------------------

class TestGroupCollinearLines(unittest.TestCase):

    def test_001_caso_reale_tre_pieghe(self):
        lines = [
            make_line(125.0, -39.628, 170.0, -39.628),
            make_line(0.0,   -39.628,  45.0, -39.628),
            make_line(125.0,  21.114, 130.2,  21.114),
            make_line(164.8,  21.114, 170.0,  21.114),
            make_line(0.0,    21.114,   5.2,  21.114),
            make_line(39.8,   21.114,  45.0,  21.114),
        ]

        groups = group_collinear_lines(lines)
        self.assertEqual(len(groups), 2)

    def test_002_gruppi_con_dimensione_corretta(self):
        lines = [
            make_line(125.0, -39.628, 170.0, -39.628),
            make_line(0.0,   -39.628,  45.0, -39.628),
            make_line(125.0,  21.114, 130.2,  21.114),
            make_line(164.8,  21.114, 170.0,  21.114),
            make_line(0.0,    21.114,   5.2,  21.114),
            make_line(39.8,   21.114,  45.0,  21.114),
        ]

        groups = group_collinear_lines(lines)
        sizes = sorted(len(g) for g in groups)
        self.assertEqual(sizes, [2, 4])

    def test_003_segmento_singolo(self):
        lines = [make_line(0, 0, 100, 0)]
        groups = group_collinear_lines(lines)

        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 1)

    def test_004_lista_vuota(self):
        groups = group_collinear_lines([])
        self.assertEqual(groups, [])

    def test_005_tre_segmenti_stessa_retta(self):
        lines = [
            make_line(0, 0, 10, 0),
            make_line(20, 0, 30, 0),
            make_line(40, 0, 50, 0),
        ]

        groups = group_collinear_lines(lines)

        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 3)

    def test_006_parallele_separate(self):
        lines = [
            make_line(0, 0, 100, 0),
            make_line(0, 10, 100, 10),
            make_line(0, 20, 100, 20),
        ]

        groups = group_collinear_lines(lines)

        self.assertEqual(len(groups), 3)

    def test_007_linee_oblique_collineari(self):
        lines = [
            make_line(0, 0, 10, 10),
            make_line(20, 20, 30, 30),
            make_line(40, 40, 50, 50),
        ]

        groups = group_collinear_lines(lines)

        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 3)

    def test_008_linee_miste(self):
        lines = [
            make_line(0, 0, 10, 0),    # orizzontale y=0
            make_line(20, 0, 30, 0),   # orizzontale y=0
            make_line(0, 10, 10, 10),  # orizzontale y=10
            make_line(0, 0, 0, 10),    # verticale x=0
        ]

        groups = group_collinear_lines(lines)

        self.assertEqual(len(groups), 3)
        sizes = sorted(len(g) for g in groups)
        self.assertEqual(sizes, [1, 1, 2])


if __name__ == "__main__":
    unittest.main(verbosity=2)