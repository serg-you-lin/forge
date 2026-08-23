"""
test_gap.py
-----------
Test TDD per la gestione dei gap e overlap negli angoli.

Lancia:
    python -m pytest tests/test_gap.py -v
"""

import unittest
from pathlib import Path
import sys
import ezdxf
import math

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import forge

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

W, H  = 100.0, 50.0
AREA  = W * H       # 5000.0
GAP   = 0.1
DELTA = 1.0         # tolleranza area mm²


def load(name):
    return ezdxf.readfile(str(EXAMPLES_DIR / name))


# ---------------------------------------------------------------------------
# GAP — LINE troppo corte
# ---------------------------------------------------------------------------

class TestGapClose(unittest.TestCase):
    """tolerance > gap → profilo chiuso, area corretta."""

    def setUp(self):
        doc = load("rect_gap.dxf")
        self.result = forge.heal(doc.modelspace(),
                                 tolerance=0.2)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_area_correct(self):
        area = self.result.parts[0].area
        self.assertAlmostEqual(area, AREA, delta=DELTA,
                               msg=f"Area {area:.4f} != attesa {AREA}")

    def test_004_no_holes(self):
        self.assertEqual(len(self.result.parts[0].inners), 0)


class TestGapNoClose(unittest.TestCase):
    """tolerance < gap → profilo non chiuso."""

    def setUp(self):
        doc = load("rect_gap.dxf")
        self.result = forge.heal(doc.modelspace(),
                                 tolerance=0.05)

    def test_001_no_parts(self):
        self.assertEqual(self.result.part_count, 0)


# ---------------------------------------------------------------------------
# OVERLAP — LINE troppo lunghe
# ---------------------------------------------------------------------------

class TestOverlapClose(unittest.TestCase):
    """tolerance > overlap → trim agli angoli, area corretta."""

    def setUp(self):
        doc = load("rect_overlap.dxf")
        self.result = forge.heal(doc.modelspace(),
                                 tolerance=0.2)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_area_correct(self):
        area = self.result.parts[0].area
        self.assertAlmostEqual(area, AREA, delta=DELTA,
                               msg=f"Area {area:.4f} != attesa {AREA}")

    def test_004_no_holes(self):
        self.assertEqual(len(self.result.parts[0].inners), 0)


class TestOverlapNoClose(unittest.TestCase):
    """tolerance < overlap → comportamento invariato."""

    def setUp(self):
        doc = load("rect_overlap.dxf")
        self.result = forge.heal(doc.modelspace(),
                                 tolerance=0.05)

    def test_001_one_part_or_warning(self):
        if self.result.part_count == 1:
            area = self.result.parts[0].area
            self.assertAlmostEqual(area, AREA, delta=DELTA)


# ---------------------------------------------------------------------------
# LINE parallele — lato mancante
# ---------------------------------------------------------------------------

class TestParallelClose(unittest.TestCase):
    """
    Profilo a C (7 LINE) con gap tra due linee verticali parallele.
    tolerance > gap → aggiunge LINE di chiusura, profilo chiuso.
    """

    def setUp(self):
        doc = load("gap_parallelo.dxf")
        self.result = forge.heal(doc.modelspace(),
                                 tolerance=0.3)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_no_errors(self):
        print("ERRORS:", self.result.errors)
        self.assertEqual(len(self.result.errors), 0)

    def test_003_no_holes(self):
        self.assertEqual(len(self.result.parts[0].inners), 0)


class TestParallelNoClose(unittest.TestCase):
    """tolerance < gap → profilo non chiuso."""

    def setUp(self):
        doc = load("gap_parallelo.dxf")
        self.result = forge.heal(doc.modelspace(),
                                 tolerance=0.05)

    def test_001_no_parts(self):
        self.assertEqual(self.result.part_count, 0)


# ---------------------------------------------------------------------------
# ARC + LINE — gap tra arco e segmento
# ---------------------------------------------------------------------------

class TestArcLineGapClose(unittest.TestCase):
    """
    Rettangolo con angolo arrotondato (ARC).
    Gap di 0.1mm tra endpoint ARC e LINE adiacente.
    tolerance > gap → profilo chiuso, 1 parte senza fori.
    """

    def setUp(self):
        doc = load("arc_line_gap.dxf")
        self.result = forge.heal(doc.modelspace(),
                                 tolerance=0.2)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_no_holes(self):
        self.assertEqual(len(self.result.parts[0].inners), 0)

    def test_004_area_plausible(self):
        """Area deve essere inferiore al rettangolo pieno W*H."""
        area = self.result.parts[0].area
        self.assertLess(area, W * H)
        self.assertGreater(area, W * H * 0.8)

class TestArcLineGapNoClose(unittest.TestCase):
    """tolerance < gap → profilo non chiuso."""

    def setUp(self):
        doc = load("arc_line_gap.dxf")
        self.result = forge.heal(doc.modelspace(),
                                 tolerance=0.05)

    def test_001_no_parts(self):
        self.assertEqual(self.result.part_count, 0)


# ---------------------------------------------------------------------------
# ARC + ARC stesso cerchio — due semicerchi con gap
# ---------------------------------------------------------------------------

class TestArcArcSameCircleClose(unittest.TestCase):
    """
    Due semicerchi dello stesso cerchio (r=50) con gap angolare di ~0.11°.
    tolerance > gap → profilo chiuso, area ≈ π*r².
    """

    RADIUS_C = 50.0
    AREA_C = math.pi * (RADIUS_C ** 2)
    # Tolleranza numerica: include discretizzazione arco + gap-fix.
    DELTA_C = 5.0

    def setUp(self):
        doc = load("arc_arc_gap.dxf")
        self.result = forge.heal(doc.modelspace(),
                                 tolerance=0.2)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_area_correct(self):
        area = self.result.parts[0].area
        self.assertAlmostEqual(area, self.AREA_C, delta=self.DELTA_C,
                               msg=f"Area {area:.2f} != attesa {self.AREA_C:.2f}")

    def test_004_no_holes(self):
        self.assertEqual(len(self.result.parts[0].inners), 0)


class TestArcArcSameCircleNoClose(unittest.TestCase):
    """tolerance < gap → profilo non chiuso."""

    def setUp(self):
        doc = load("arc_arc_gap.dxf")
        self.result = forge.heal(doc.modelspace(),
                                 tolerance=0.05)

    def test_001_no_parts(self):
        self.assertEqual(self.result.part_count, 0)


# ---------------------------------------------------------------------------
# ARC + ARC cerchi diversi — due archi con centri distinti
# ---------------------------------------------------------------------------

class TestArcArcDifferentCircleClose(unittest.TestCase):
    """
    Due archi di cerchi diversi con gap di ~0.2mm agli endpoint.
    tolerance > gap → profilo chiuso, 1 parte senza fori.
    """

    def setUp(self):
        doc = load("arc_open.dxf")
        self.result = forge.heal(doc.modelspace(),
                                 tolerance=0.5)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_no_holes(self):
        self.assertEqual(len(self.result.parts[0].inners), 0)

    def test_004_area_plausible(self):
        area = self.result.parts[0].area
        self.assertGreater(area, 100.0)


class TestArcArcDifferentCircleNoClose(unittest.TestCase):
    """tolerance < gap → profilo non chiuso."""

    def setUp(self):
        doc = load("arc_open.dxf")
        self.result = forge.heal(doc.modelspace(),
                                 tolerance=0.05)

    def test_001_no_parts(self):
        self.assertEqual(self.result.part_count, 0)


# ---------------------------------------------------------------------------
# SPLINE + LINE — gap con chiusura tramite LINE aggiuntiva
# ---------------------------------------------------------------------------

class TestSplineLineGapClose(unittest.TestCase):
    """
    Rettangolo con lato sinistro SPLINE che termina 0.2mm prima dell'angolo.
    tolerance > gap → aggiunge LINE di chiusura, profilo chiuso.
    Area attesa: circa W*H (piccola differenza per la curvatura della spline).
    """

    def setUp(self):
        doc = load("spline_line_gap.dxf")
        self.result = forge.heal(doc.modelspace(),
                                 tolerance=0.3)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_no_holes(self):
        self.assertEqual(len(self.result.parts[0].inners), 0)

    def test_004_area_plausible(self):
        """Area deve essere vicina a W*H — la spline è quasi verticale."""
        area = self.result.parts[0].area
        self.assertAlmostEqual(area, W * H, delta=50.0,
                               msg=f"Area {area:.2f} lontana da attesa {W*H}")


class TestSplineLineGapNoClose(unittest.TestCase):
    """tolerance < gap → profilo non chiuso."""

    def setUp(self):
        doc = load("spline_line_gap.dxf")
        self.result = forge.heal(doc.modelspace(),
                                 tolerance=0.05)

    def test_001_no_parts(self):
        self.assertEqual(self.result.part_count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)