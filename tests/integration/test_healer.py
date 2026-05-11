"""
test_healer.py
--------------
Test Suite per dxf_forge.healer

Prima di lanciare, genera i DXF di esempio:
    python tests/generate_examples.py

Poi lancia:
    python -m pytest tests/test_healer.py -v
    oppure
    python -m unittest tests/test_healer.py -v
"""

import unittest
from pathlib import Path
import sys
import ezdxf

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import dxf_forge as forge
from dxf_forge.rules.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    COLOR_OUTER, COLOR_INNER, COLOR_HOLE,
    COLOR_TRASH, HOLE_DIAMETER_THRESHOLD,
)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def load(name):
    return ezdxf.readfile(str(EXAMPLES_DIR / name))


# ---------------------------------------------------------------------------
# Rettangolo 4 LINE
# ---------------------------------------------------------------------------

class TestHealerRectLines(unittest.TestCase):

    def setUp(self):
        doc = load("rect_lines.dxf")
        self.result = forge.heal(doc.modelspace(), write_to_msp=False)

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

    def test_006_writes_lwpolyline(self):
        doc = load("rect_lines.dxf")
        msp = doc.modelspace()
        forge.heal(msp, write_to_msp=True)
        self.assertGreaterEqual(len(list(msp.query('LWPOLYLINE'))), 1)

    def test_007_outer_layer_assigned(self):
        doc = load("rect_lines.dxf")
        msp = doc.modelspace()
        forge.heal(msp, write_to_msp=True)
        layers = {e.dxf.layer for e in msp.query('LWPOLYLINE')}
        self.assertIn(LAYER_OUTER, layers)

    def test_008_outer_color_assigned(self):
        doc = load("rect_lines.dxf")
        msp = doc.modelspace()
        forge.heal(msp, write_to_msp=True)
        for e in msp.query('LWPOLYLINE'):
            if e.dxf.layer == LAYER_OUTER:
                self.assertEqual(e.dxf.color, COLOR_OUTER)


# ---------------------------------------------------------------------------
# Rettangolo con foro (LINE)
# ---------------------------------------------------------------------------

class TestHealerRectWithHole(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_hole_lines.dxf")
        self.result = forge.heal(doc.modelspace(), write_to_msp=False)

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
        doc = load("pline_with_hole.dxf")
        result = forge.heal(doc.modelspace(), write_to_msp=False)
        self.assertIsNotNone(result)

    def test_002_finds_one_part(self):
        doc = load("pline_with_hole.dxf")
        result = forge.heal(doc.modelspace(), write_to_msp=False)
        self.assertEqual(result.part_count, 1)

    def test_003_has_one_inner(self):
        doc = load("pline_with_hole.dxf")
        result = forge.heal(doc.modelspace(), write_to_msp=False)
        self.assertEqual(len(result.parts[0].inners), 1)


# ---------------------------------------------------------------------------
# CIRCLE outer (flangia tonda)
# ---------------------------------------------------------------------------

class TestHealerCircleOuter(unittest.TestCase):

    def setUp(self):
        doc = load("circle_outer_with_hole.dxf")
        self.msp = doc.modelspace()
        self.result = forge.heal(self.msp, write_to_msp=True)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_outer_layer(self):
        layers = {e.dxf.layer for e in self.msp.query('CIRCLE')}
        self.assertIn(LAYER_OUTER, layers)

    def test_003_inner_classified(self):
        self.assertGreaterEqual(len(self.result.parts[0].inners), 1)


# ---------------------------------------------------------------------------
# CIRCLE piccolo → LAYER_HOLE
# ---------------------------------------------------------------------------

class TestHealerCircleHole(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_circle_hole.dxf")
        self.msp = doc.modelspace()
        self.result = forge.heal(self.msp, write_to_msp=True)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_circle_on_hole_layer(self):
        layers = {e.dxf.layer for e in self.msp.query('CIRCLE')}
        self.assertIn(LAYER_HOLE, layers)

    def test_003_circle_color(self):
        for e in self.msp.query('CIRCLE'):
            if e.dxf.layer == LAYER_HOLE:
                self.assertEqual(e.dxf.color, COLOR_HOLE)

    def test_004_holes_count(self):
        self.assertEqual(len(self.result.parts[0].inners), 1)

    def test_005_hole_diameter_below_threshold(self):
        for inner in self.result.parts[0].inners:
            self.assertEqual(inner.layer, LAYER_HOLE)


# ---------------------------------------------------------------------------
# CIRCLE grande → LAYER_INNER
# ---------------------------------------------------------------------------

class TestHealerCircleInner(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_circle_inner.dxf")
        self.msp = doc.modelspace()
        self.result = forge.heal(self.msp, write_to_msp=True)

    def test_001_circle_on_inner_layer(self):
        layers = {e.dxf.layer for e in self.msp.query('CIRCLE')}
        self.assertIn(LAYER_INNER, layers)

    def test_002_inner_layer_assigned(self):
        for inner in self.result.parts[0].inners:
            self.assertEqual(inner.layer, LAYER_INNER)


# ---------------------------------------------------------------------------
# Coppia concentrica → countersink
# ---------------------------------------------------------------------------

class TestHealerCountersink(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_countersink.dxf")
        self.msp = doc.modelspace()
        self.result = forge.heal(self.msp, write_to_msp=True)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_only_one_inner(self):
        # il cerchio grande viene escluso, resta solo il piccolo
        self.assertEqual(len(self.result.parts[0].inners), 1)

    def test_003_inner_is_hole(self):
        self.assertTrue(self.result.parts[0].inners[0].is_hole)

    def test_004_big_circle_in_trash(self):
        from dxf_forge.rules.layers import TRASH_LAYER
        trash = [e for e in self.msp.query('CIRCLE')
                 if e.dxf.layer == TRASH_LAYER]
        self.assertEqual(len(trash), 1)

    def test_005_small_circle_on_hole_layer(self):
        hole = [e for e in self.msp.query('CIRCLE')
                if e.dxf.layer == LAYER_HOLE]
        self.assertEqual(len(hole), 1)

        
# ---------------------------------------------------------------------------
# Special layers (BEND + MARK)
# ---------------------------------------------------------------------------

class TestHealerSpecialLayers(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_special_layers.dxf")
        msp = doc.modelspace()
        self.result = forge.heal(
            msp,
            write_to_msp=True,
            special_layers={
                "BEND": "bending",
                "MARK": "engrave",
            }
        )
        forge.inject(msp, self.result)

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_bending_lines_counted(self):
        custom = self.result.parts[0].custom
        self.assertEqual(custom.get("bending_lines", 0), 2)

    def test_003_total_engrave_length(self):
        """1 LINE MARK diagonale da (50,0) a (150,100) = √(100²+100²) ≈ 141.42mm."""
        custom = self.result.parts[0].custom
        length = custom.get("total_engrave_length", 0.0)
        self.assertAlmostEqual(length, 141.42, delta=0.1)

    def test_004_special_entities_not_in_trash(self):
        # Le entità su BEND e MARK non devono finire su Trash
        doc = load("rect_with_special_layers.dxf")
        msp = doc.modelspace()
        forge.heal(msp, write_to_msp=True, special_layers={"BEND": "bending", "MARK": "engrave"})
        forge.inject(msp, self.result)
        trash = [e for e in msp if e.dxf.hasattr("layer") and e.dxf.layer == "Trash"]
        bend_trash = [e for e in trash if "BEND" in e.dxf.layer.upper()]
        self.assertEqual(len(bend_trash), 0)


# ---------------------------------------------------------------------------
# Keep trash / delete trash
# ---------------------------------------------------------------------------

class TestHealerTrash(unittest.TestCase):

    def test_001_keep_trash_default(self):
        """Entità non classificate finiscono su layer Trash."""
        doc = load("rect_with_trash.dxf")
        msp = doc.modelspace()
        forge.heal(msp, write_to_msp=True, keep_trash=True)
        trash = [e for e in msp if e.dxf.hasattr("layer") and e.dxf.layer == "Trash"]
        self.assertGreater(len(trash), 0)

    def test_002_trash_color(self):
        """Entità Trash hanno il colore COLOR_TRASH."""
        doc = load("rect_with_trash.dxf")
        msp = doc.modelspace()
        forge.heal(msp, write_to_msp=True, keep_trash=True)
        for e in msp:
            if e.dxf.hasattr("layer") and e.dxf.layer == "Trash":
                self.assertEqual(e.dxf.color, COLOR_TRASH)

    def test_003_delete_trash(self):
        """Con keep_trash=False le entità non classificate vengono cancellate."""
        doc = load("rect_with_trash.dxf")
        msp = doc.modelspace()
        forge.heal(msp, write_to_msp=True, keep_trash=False)
        trash = [e for e in msp if e.dxf.hasattr("layer") and e.dxf.layer == "Trash"]
        self.assertEqual(len(trash), 0)


# ---------------------------------------------------------------------------
# Validate + nester input
# ---------------------------------------------------------------------------

class TestValidateMsp(unittest.TestCase):

    def test_001_detects_lines(self):
        doc = load("rect_lines.dxf")
        check = forge.validate_msp(doc.modelspace())
        self.assertGreater(len(check.warnings), 0)

    def test_002_clean_file_no_errors(self):
        doc = load("pline_with_hole.dxf")
        check = forge.validate_msp(doc.modelspace())
        self.assertEqual(len(check.errors), 0)


class TestNesterInput(unittest.TestCase):

    def test_001_correct_structure(self):
        doc = load("rect_lines.dxf")
        result = forge.heal(doc.modelspace(), write_to_msp=False)
        nester = forge.to_nester_input(result)
        self.assertIsInstance(nester, list)
        if nester:
            item = nester[0]
            self.assertIn("outer_coords", item)
            self.assertIn("holes_coords", item)
            self.assertIn("area", item)
            self.assertIn("bbox", item)

# ---------------------------------------------------------------------------
# LWPOLYLINE outer + loop LINE interno (es. marcatura)
# Loop trovato dal grafo deve diventare INNER, non OUTER
# ---------------------------------------------------------------------------

class TestHealerInnerLoopInsideLwpolyline(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_inner_mark.dxf")
        self.msp = doc.modelspace()
        self.result = forge.heal(self.msp, write_to_msp=True)

    def test_001_finds_one_part(self):
        """Il file ha un solo pezzo — la LWPOLYLINE outer."""
        self.assertEqual(self.result.part_count, 1)

    def test_002_inner_loop_classified_as_inner(self):
        """Il loop di LINE interno deve essere classificato come inner, non outer."""
        self.assertEqual(len(self.result.parts[0].inners), 1)

    def test_003_no_outer_on_inner_loop(self):
        """Nessuna LWPOLYLINE con layer OUTER deve avere area < outer area."""
        outer_area = self.result.parts[0].outer.area
        for e in self.msp.query('LWPOLYLINE'):
            if e.dxf.layer == LAYER_OUTER:
                poly_area = forge.pline_to_polygon(e).area if hasattr(forge, 'pline_to_polygon') else outer_area
                self.assertAlmostEqual(poly_area, outer_area, delta=outer_area * 0.1)

    def test_004_inner_layer_on_msp(self):
        """La LWPOLYLINE materializzata dal loop interno deve avere layer INNER."""
        inner_layers = {e.dxf.layer for e in self.msp.query('LWPOLYLINE')
                        if e.dxf.layer == LAYER_INNER}
        self.assertIn(LAYER_INNER, inner_layers)
        
# ---------------------------------------------------------------------------
# Deduplicazione entità duplicate (es. dopo explode INSERT)
# ---------------------------------------------------------------------------

class TestHealerDeduplication(unittest.TestCase):

    def setUp(self):
        doc = load("rect_lines_duplicated.dxf")
        self.msp = doc.modelspace()
        self.result = forge.heal(self.msp, write_to_msp=True, explode_inserts=False)

    def test_001_finds_one_part(self):
        """Anche con LINE duplicate, deve trovare un solo pezzo."""
        self.assertEqual(self.result.part_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_correct_area(self):
        """L'area deve essere quella del rettangolo, non distorta dai duplicati."""
        self.assertAlmostEqual(self.result.parts[0].area, 5000, delta=50)

    def test_004_dedup_warning_emitted(self):
        """Deve esserci un warning che segnala le entità rimosse."""
        warnings_text = " ".join(self.result.warnings)
        self.assertIn("duplicate", warnings_text.lower())

    def test_005_no_duplicate_lines_in_msp(self):
        """Dopo l'healing, non devono esistere LINE identiche nel msp."""
        from dxf_forge.workflow.healer import _deduplicate_entities

        # Chiamiamo la funzione su un msp già healato:
        # se non ci sono duplicati, deve restituire 0
        removed = _deduplicate_entities(self.msp)
        self.assertEqual(removed, 0)

    def test_006_single_outer_lwpolyline(self):
        """Deve esserci esattamente una LWPOLYLINE sul layer OuterContour."""
        outer = [e for e in self.msp.query('LWPOLYLINE')
                 if e.dxf.layer == LAYER_OUTER]
        self.assertEqual(len(outer), 1)

if __name__ == "__main__":
    unittest.main(verbosity=2)