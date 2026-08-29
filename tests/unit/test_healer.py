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


def load(name):
    return EXAMPLES_DIR / name


def load_msp(name):
    return ezdxf.readfile(str(EXAMPLES_DIR / name)).modelspace()

# ---------------------------------------------------------------------------
# Rettangolo 4 LINE
# ---------------------------------------------------------------------------

class TestHealerRectLines(unittest.TestCase):

    def setUp(self):
        doc = forge.load_dxf(load("rect_lines.dxf"))
        self.result = forge.heal(doc)

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
        doc = forge.load_dxf(load("rect_with_hole_lines.dxf"))
        self.result = forge.heal(doc)

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
        doc = forge.load_dxf(load("pline_with_hole.dxf"))
        result = forge.heal(doc)
        self.assertIsNotNone(result)

    def test_002_finds_one_part(self):
        doc = forge.load_dxf(load("pline_with_hole.dxf"))
        result = forge.heal(doc)
        self.assertEqual(result.part_count, 1)

    def test_003_has_one_inner(self):
        doc = forge.load_dxf(load("pline_with_hole.dxf"))
        result = forge.heal(doc)
        self.assertEqual(len(result.parts[0].inners), 1)


# ---------------------------------------------------------------------------
# CIRCLE outer (flangia tonda)
# ---------------------------------------------------------------------------

class TestHealerCircleOuter(unittest.TestCase):

    def setUp(self):
        doc = forge.load_dxf(load("circle_outer_with_hole.dxf"))
        self.result = forge.heal(doc)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_inner_classified(self):
        self.assertGreaterEqual(len(self.result.parts[0].holes) + len(self.result.parts[0].inners), 1)


# ---------------------------------------------------------------------------
# CIRCLE piccolo → HOLE (dopo detect — D15: heal non promuove più i fori)
# ---------------------------------------------------------------------------

class TestHealerCircleHole(unittest.TestCase):

    def setUp(self):
        doc = forge.load_dxf(load("rect_with_circle_hole.dxf"))
        self.result = forge.heal(doc)
        # heal() consegna solo il contorno interno; la promozione a foro è di
        # detect(features="holes").
        self.assertEqual(len(self.result.parts[0].holes), 0)
        self.assertEqual(len(self.result.parts[0].inners), 1)
        forge.detect(self.result, features="all")

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_has_hole(self):
        self.assertGreaterEqual(len(self.result.parts[0].holes), 1)

    def test_003_hole_role(self):
        from forge.model.role import ContourRole
        for hole in self.result.parts[0].holes:
            self.assertEqual(hole.role, ContourRole.HOLE)

    def test_004_exact_hole_count(self):
        self.assertEqual(len(self.result.parts[0].holes), 1)


# ---------------------------------------------------------------------------
# CIRCLE grande → INNER (resta contorno interno anche dopo detect)
# ---------------------------------------------------------------------------

class TestHealerCircleInner(unittest.TestCase):

    def setUp(self):
        doc = forge.load_dxf(load("rect_with_circle_inner.dxf"))
        self.result = forge.heal(doc)

    def test_001_inner_present_and_role(self):
        from forge.model.role import ContourRole
        inners = self.result.parts[0].inners
        self.assertEqual(len(inners), 1)
        self.assertEqual(inners[0].role, ContourRole.INNER)
        self.assertEqual(len(self.result.parts[0].holes), 0)


# ---------------------------------------------------------------------------
# Coppia concentrica → countersink
# heal() vede entrambi i CIRCLE come inners; detect(features="holes") li
# riconosce come countersink (piccolo → Hole, anello grande assorbito).
# ---------------------------------------------------------------------------

class TestHealerCountersink(unittest.TestCase):

    def setUp(self):
        doc = forge.load_dxf(load("rect_with_countersink.dxf"))
        self.result = forge.heal(doc)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_sees_both_circles_as_inners(self):
        # heal() non distingue countersink — li vede entrambi come inners
        self.assertEqual(len(self.result.parts[0].holes), 0)
        self.assertGreaterEqual(len(self.result.parts[0].inners), 2)


# ---------------------------------------------------------------------------
# LWPOLYLINE outer + loop LINE interno
# ---------------------------------------------------------------------------

class TestHealerInnerLoopInsideLwpolyline(unittest.TestCase):

    def setUp(self):
        doc = forge.load_dxf(load("rect_with_inner_mark.dxf"))
        self.result = forge.heal(doc)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_inner_loop_classified_as_inner(self):
        self.assertEqual(len(self.result.parts[0].inners), 1)


# ---------------------------------------------------------------------------
# Deduplicazione entità duplicate
# ---------------------------------------------------------------------------

class TestHealerDeduplication(unittest.TestCase):

    def setUp(self):
        doc = forge.load_dxf(load("rect_lines_duplicated.dxf"), explode_inserts=True)
        self.result = forge.heal(doc)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_correct_area(self):
        self.assertAlmostEqual(self.result.parts[0].area, 5000, delta=50)


# ---------------------------------------------------------------------------
# Validate input (ForgeDocument)
# ---------------------------------------------------------------------------

class TestValidateInput(unittest.TestCase):

    def test_001_detects_open_lines(self):
        check = forge.validate(forge.load_dxf(load("rect_lines.dxf")))
        self.assertGreater(len(check.warnings), 0)
        self.assertTrue(check.is_valid)

    def test_002_clean_file_no_errors(self):
        check = forge.validate(forge.load_dxf(load("pline_with_hole.dxf")))
        self.assertEqual(len(check.errors), 0)
        self.assertTrue(check.is_valid)


if __name__ == "__main__":
    unittest.main(verbosity=2)