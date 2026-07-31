"""
test_healer.py
--------------
Unit test per forge.heal().

Verifica esclusivamente il ForgeResult — parts, inners, holes, trash.
NON verifica effetti sul msp (layer, colori, LWPOLYLINE scritte) → test_writeback.py

Prima di lanciare, genera i DXF di esempio:
    python tests/generate_examples.py

Poi lancia:
    python -m pytest tests/unit/test_healer.py -v
"""

import unittest
from pathlib import Path
import sys
import ezdxf

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.adapters.dxf.layers import LAYER_OUTER, LAYER_INNER, LAYER_HOLE
from forge.rules.palette import COLOR_OUTER, COLOR_INNER, COLOR_HOLE

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


# def load(name):
#     return ezdxf.readfile(str(EXAMPLES_DIR / name))

def load(name):
    return EXAMPLES_DIR / name

# ---------------------------------------------------------------------------
# Rettangolo 4 LINE
# ---------------------------------------------------------------------------

class TestHealerRectLines(unittest.TestCase):

    def setUp(self):
        doc,msp = forge.load_dxf(load("rect_lines.dxf"))
        self.result = forge.heal(msp)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_is_valid(self):
        self.assertTrue(self.result.is_valid)

    def test_004_correct_area(self):
        self.assertAlmostEqual(self.result.parts[0].area, 5000, delta=50)

    def test_005_no_holes(self):
        self.assertEqual(len(self.result.parts[0].inners), 0)

    # helper riutilizzabile
    def assert_entity(self, entity, expected_layer, expected_color):
        self.assertEqual(entity.layer, expected_layer)
        self.assertEqual(entity.color, expected_color)


    


# ---------------------------------------------------------------------------
# Rettangolo con foro (LINE)
# ---------------------------------------------------------------------------

class TestHealerRectWithHole(unittest.TestCase):

    def setUp(self):
        doc, msp = forge.load_dxf(load("rect_with_hole_lines.dxf"))
        self.result = forge.heal(msp)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_has_hole(self):
        self.assertGreaterEqual(len(self.result.parts[0].inners), 1)

    def test_003_outer_area(self):
        self.assertAlmostEqual(self.result.parts[0].outer.area, 20000, delta=200)


# ---------------------------------------------------------------------------
# File già pulito (LWPOLYLINE)
# ---------------------------------------------------------------------------

class TestHealerCleanFile(unittest.TestCase):

    def test_001_does_not_crash(self):
        doc, msp = forge.load_dxf(load("pline_with_hole.dxf"))
        result = forge.heal(msp)
        self.assertIsNotNone(result)

    def test_002_finds_one_part(self):
        doc, msp = forge.load_dxf(load("pline_with_hole.dxf"))
        result = forge.heal(msp)
        self.assertEqual(result.part_count, 1)

    def test_003_has_one_inner(self):
        doc, msp = forge.load_dxf(load("pline_with_hole.dxf"))
        result = forge.heal(msp)
        self.assertEqual(len(result.parts[0].inners), 1)


# ---------------------------------------------------------------------------
# CIRCLE outer (flangia tonda)
# ---------------------------------------------------------------------------

class TestHealerCircleOuter(unittest.TestCase):

    def setUp(self):
        doc, msp = forge.load_dxf(load("circle_outer_with_hole.dxf"))
        self.result = forge.heal(msp)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_inner_classified(self):
        self.assertGreaterEqual(len(self.result.parts[0].holes) + len(self.result.parts[0].inners), 1)


# ---------------------------------------------------------------------------
# CIRCLE piccolo → HOLE
# ---------------------------------------------------------------------------

class TestHealerCircleHole(unittest.TestCase):

    def setUp(self):
        doc, msp = forge.load_dxf(load("rect_with_circle_hole.dxf"))
        self.result = forge.heal(msp)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_has_hole(self):
        self.assertGreaterEqual(len(self.result.parts[0].holes), 1)

    def test_003_hole_layer_and_color(self):
        for inner in self.result.parts[0].inners:
            self.assertEqual(inner.layer, LAYER_HOLE)
            self.assertEqual(inner.color, COLOR_HOLE)

    def test_004_exact_hole_count(self):
        self.assertEqual(len(self.result.parts[0].holes), 1)


# ---------------------------------------------------------------------------
# CIRCLE grande → INNER
# ---------------------------------------------------------------------------

class TestHealerCircleInner(unittest.TestCase):

    def setUp(self):
        doc, msp = forge.load_dxf(load("rect_with_circle_inner.dxf"))
        self.result = forge.heal(msp)

    def test_001_inner_layer_and_color(self):
        for inner in self.result.parts[0].inners:
            self.assertEqual(inner.layer, LAYER_INNER)
            self.assertEqual(inner.color, COLOR_INNER)


# ---------------------------------------------------------------------------
# Coppia concentrica → countersink
# Heal classifica entrambi i CIRCLE come inners.
# detect() li riclassifica come countersink.
# Qui verifichiamo solo che heal() li veda entrambi come inners.
# ---------------------------------------------------------------------------

class TestHealerCountersink(unittest.TestCase):

    def setUp(self):
        doc, msp = forge.load_dxf(load("rect_with_countersink.dxf"))
        self.result = forge.heal(msp)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_sees_both_circles_as_inners(self):
        # heal() non distingue countersink — li vede entrambi come inners
        self.assertGreaterEqual(len(self.result.parts[0].holes) + len(self.result.parts[0].inners), 1)

    def test_003_entity_populated(self):
        # ForgeContour.entity deve essere popolato per detect()
        for inner in self.result.parts[0].inners:
            if inner.is_hole:
                self.assertIsNotNone(inner.entity)


# ---------------------------------------------------------------------------
# LWPOLYLINE outer + loop LINE interno
# ---------------------------------------------------------------------------

class TestHealerInnerLoopInsideLwpolyline(unittest.TestCase):

    def setUp(self):
        doc, msp = forge.load_dxf(load("rect_with_inner_mark.dxf"))
        self.result = forge.heal(msp)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_inner_loop_classified_as_inner(self):
        self.assertEqual(len(self.result.parts[0].inners), 1)


# ---------------------------------------------------------------------------
# Deduplicazione entità duplicate
# ---------------------------------------------------------------------------

class TestHealerDeduplication(unittest.TestCase):

    def setUp(self):
        doc, msp = forge.load_dxf(load("rect_lines_duplicated.dxf"), explode_inserts=True)
        self.result = forge.heal(msp)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_correct_area(self):
        self.assertAlmostEqual(self.result.parts[0].area, 5000, delta=50)


# ---------------------------------------------------------------------------
# Validate msp
# ---------------------------------------------------------------------------

class TestValidateMsp(unittest.TestCase):

    def test_001_detects_lines(self):
        doc, msp = forge.load_dxf(load("rect_lines.dxf"))
        check = forge.validate_msp(msp)
        self.assertGreater(len(check.warnings), 0)

    def test_002_clean_file_no_errors(self):
        doc, msp = forge.load_dxf(load("pline_with_hole.dxf"))
        check = forge.validate_msp(msp)
        self.assertEqual(len(check.errors), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)