"""
test_collinear.py
-----------------
Test per are_collinear() e group_collinear_lines()
in core/geometry.py

Versione MOCK (senza ezdxf), coerente con test_virtual.py.

Lancia:
    python -m pytest tests/test_collinear.py -v
"""

import unittest
from pathlib import Path
import sys
from unittest.mock import MagicMock

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dxf_forge.core.geometry import are_collinear, group_collinear_lines


# ---------------------------------------------------------------------------
# Helper — LINE mock ezdxf-like
# ---------------------------------------------------------------------------

def make_line(x1, y1, x2, y2):
    """
    Crea una LINE mock compatibile con geometry.py
    (stesso pattern usato nei test virtuali)
    """
    entity = MagicMock()
    entity.dxftype.return_value = "LINE"

    entity.dxf.start.x = x1
    entity.dxf.start.y = y1
    entity.dxf.end.x   = x2
    entity.dxf.end.y   = y2

    return entity


# ---------------------------------------------------------------------------
# Test are_collinear
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


# ---------------------------------------------------------------------------
# Test group_collinear_lines
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

    def test_002_ogni_gruppo_ha_due_segmenti(self):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)




