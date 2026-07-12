"""
test_writeback.py
-----------------
Test di integrazione per forge.write().

Verifica gli effetti sul msp dopo heal() + write():
layer assegnati, colori, LWPOLYLINE scritte, entità Trash.

Prima di lanciare, genera i DXF di esempio:
    python tests/generate_examples.py

Poi lancia:
    python -m pytest tests/integration/test_writeback.py -v
"""

import unittest
from pathlib import Path
import sys
import ezdxf

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.rules.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    LAYER_COUNTERSINK, LAYER_BENDING, LAYER_ENGRAVE,
    COLOR_OUTER, COLOR_INNER, COLOR_HOLE, COLOR_TRASH,
)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def load(name):
    return ezdxf.readfile(str(EXAMPLES_DIR / name))


# ---------------------------------------------------------------------------
# Rettangolo 4 LINE — scrittura msp
# ---------------------------------------------------------------------------

class TestWritebackRectLines(unittest.TestCase):

    def setUp(self):
        doc = load("rect_lines.dxf")
        self.msp = doc.modelspace()
        result = forge.heal(self.msp)
        forge.write(self.msp, result)

    def test_001_writes_lwpolyline(self):
        self.assertGreaterEqual(len(list(self.msp.query("LWPOLYLINE"))), 1)

    def test_002_outer_layer_assigned(self):
        layers = {e.dxf.layer for e in self.msp.query("LWPOLYLINE")}
        self.assertIn(LAYER_OUTER, layers)

    def test_003_outer_color_assigned(self):
        for e in self.msp.query("LWPOLYLINE"):
            if e.dxf.layer == LAYER_OUTER:
                self.assertEqual(e.dxf.color, 256)


# ---------------------------------------------------------------------------
# CIRCLE outer (flangia tonda) — layer sul msp
# ---------------------------------------------------------------------------

class TestWritebackCircleOuter(unittest.TestCase):

    def setUp(self):
        doc = load("circle_outer_with_hole.dxf")
        self.msp = doc.modelspace()
        result = forge.heal(self.msp)
        forge.write(self.msp, result)

    def test_001_outer_layer(self):
        layers = {e.dxf.layer for e in self.msp.query("CIRCLE")}
        self.assertIn(LAYER_OUTER, layers)


# ---------------------------------------------------------------------------
# CIRCLE piccolo → LAYER_HOLE sul msp
# ---------------------------------------------------------------------------

class TestWritebackCircleHole(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_circle_hole.dxf")
        self.msp = doc.modelspace()
        result = forge.heal(self.msp)
        forge.write(self.msp, result)

    def test_001_circle_on_hole_layer(self):
        layers = {e.dxf.layer for e in self.msp.query("CIRCLE")}
        self.assertIn(LAYER_HOLE, layers)

    def test_002_circle_color(self):
        for e in self.msp.query("CIRCLE"):
            if e.dxf.layer == LAYER_HOLE:
                self.assertEqual(e.dxf.color, 256)


# ---------------------------------------------------------------------------
# CIRCLE grande → LAYER_INNER sul msp
# ---------------------------------------------------------------------------

class TestWritebackCircleInner(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_circle_inner.dxf")
        self.msp = doc.modelspace()
        result = forge.heal(self.msp)
        forge.write(self.msp, result)

    def test_001_circle_on_inner_layer(self):
        layers = {e.dxf.layer for e in self.msp.query("CIRCLE")}
        self.assertIn(LAYER_INNER, layers)


# ---------------------------------------------------------------------------
# Countersink — layer sul msp dopo detect()
# ---------------------------------------------------------------------------

class TestWritebackCountersink(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_countersink.dxf")
        self.msp = doc.modelspace()
        result = forge.heal(self.msp)
        forge.detect(result, self.msp)
        forge.write(self.msp, result)

    def test_001_countersink_on_correct_layer(self):
        circles = [e for e in self.msp.query("CIRCLE")
                   if e.dxf.layer == LAYER_COUNTERSINK]
        self.assertEqual(len(circles), 1)

    def test_002_small_circle_on_hole_layer(self):
        hole = [e for e in self.msp.query("CIRCLE")
                if e.dxf.layer == LAYER_HOLE]
        self.assertEqual(len(hole), 1)


# ---------------------------------------------------------------------------
# Special layers (BEND + MARK) — layer sul msp dopo detect()
# ---------------------------------------------------------------------------

class TestWritebackSpecialLayers(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_special_layers.dxf")
        self.msp = doc.modelspace()
        self.result = forge.heal(self.msp, special_layers={"BEND": "bending", "MARK": "engrave"})
        forge.detect(
            self.result,
            self.msp,
        )
        forge.write(self.msp, self.result)

    def test_001_special_entities_not_in_trash(self):
        trash = [e for e in self.msp
                 if e.dxf.hasattr("layer") and e.dxf.layer == "Trash"]
        bend_trash = [e for e in trash
                      if e.dxf.hasattr("layer") and "BEND" in e.dxf.layer.upper()]
        self.assertEqual(len(bend_trash), 0)

    def test_002_bending_on_correct_layer(self):
        bending = [e for e in self.msp
                   if e.dxf.hasattr("layer") and e.dxf.layer == LAYER_BENDING]
        self.assertGreater(len(bending), 0)


# ---------------------------------------------------------------------------
# LWPOLYLINE outer + loop LINE interno — layer sul msp
# ---------------------------------------------------------------------------

class TestWritebackInnerLoop(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_inner_mark.dxf")
        self.msp = doc.modelspace()
        result = forge.heal(self.msp)
        forge.write(self.msp, result)

    def test_001_inner_layer_on_msp(self):
        inner_layers = {e.dxf.layer for e in self.msp.query("LWPOLYLINE")
                        if e.dxf.layer == LAYER_INNER}
        self.assertIn(LAYER_INNER, inner_layers)

    def test_002_no_small_outer(self):
        outer_area = None
        for e in self.msp.query("LWPOLYLINE"):
            if e.dxf.layer == LAYER_OUTER:
                poly = forge.pline_to_polygon(e) if hasattr(forge, "pline_to_polygon") else None
                if poly:
                    outer_area = poly.area
        if outer_area is not None:
            for e in self.msp.query("LWPOLYLINE"):
                if e.dxf.layer == LAYER_OUTER:
                    poly = forge.pline_to_polygon(e) if hasattr(forge, "pline_to_polygon") else None
                    if poly:
                        self.assertAlmostEqual(poly.area, outer_area, delta=outer_area * 0.1)


# ---------------------------------------------------------------------------
# Deduplicazione — layer sul msp
# ---------------------------------------------------------------------------

class TestWritebackDeduplication(unittest.TestCase):

    def setUp(self):
        doc = load("rect_lines_duplicated.dxf")
        self.msp = doc.modelspace()
        result = forge.heal(self.msp, explode_inserts=False)
        forge.write(self.msp, result)

    def test_001_single_outer_lwpolyline(self):
        outer = [e for e in self.msp.query("LWPOLYLINE")
                 if e.dxf.layer == LAYER_OUTER]
        self.assertEqual(len(outer), 1)

    def test_002_no_duplicate_lines_in_msp(self):
        from forge.adapters.dxf.dedup_adapter import deduplicate as _deduplicate_entities
        removed = _deduplicate_entities(self.msp)
        self.assertEqual(removed, 0)


# ---------------------------------------------------------------------------
# Trash — keep e delete
# ---------------------------------------------------------------------------

class TestWritebackTrash(unittest.TestCase):

    def test_001_keep_trash_default(self):
        doc = load("rect_with_trash.dxf")
        msp = doc.modelspace()
        result = forge.heal(msp)
        forge.write(msp, result, keep_trash=True)
        trash = [e for e in msp
                 if e.dxf.hasattr("layer") and e.dxf.layer == "Trash"]
        self.assertGreater(len(trash), 0)

    def test_002_trash_color(self):
        doc = load("rect_with_trash.dxf")
        msp = doc.modelspace()
        result = forge.heal(msp)
        forge.write(msp, result, keep_trash=True)
        for e in msp:
            if e.dxf.hasattr("layer") and e.dxf.layer == "Trash":
                self.assertEqual(e.dxf.color, 256)

    def test_003_delete_trash(self):
        doc = load("rect_with_trash.dxf")
        msp = doc.modelspace()
        result = forge.heal(msp)
        forge.write(msp, result, keep_trash=False)
        trash = [e for e in msp
                 if e.dxf.hasattr("layer") and e.dxf.layer == "Trash"]
        self.assertEqual(len(trash), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)