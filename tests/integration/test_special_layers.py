
"""
test_special_layers.py
----------------------
Test per la gestione dei layer speciali (MARK, MARCATURA, ecc.).

Verifica che:
  - Le entità su special_layers non entrino nel grafo
  - Non finiscano su OuterContour/InnerContour
  - Non finiscano in trash
  - I metadati siano corretti

DXF sintetici generati inline.

Lancia:
    python -m pytest tests/test_special_layers.py -v
"""

import unittest
from pathlib import Path
import sys

import ezdxf

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.adapters.dxf.layers import TRASH_LAYER, LAYER_ENGRAVE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_pipeline(
    msp,
    special_layers,
    tolerance=0.05,
    inject=False,
):
    result = forge.heal(
        msp,
        tolerance=tolerance,
        label_map=special_layers,
    )

    forge.detect(
        result,     
    )

    forge.write(msp, result)

    if inject:
        forge.inject(result)

    return result


def _rect_with_mark(
    mark_layer='MARK',
    mark_type='engrave',
):
    """
    Rettangolo 100x50 +
    LINE da 20mm su MARK.
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # rettangolo
    msp.add_line((0, 0), (100, 0))
    msp.add_line((100, 0), (100, 50))
    msp.add_line((100, 50), (0, 50))
    msp.add_line((0, 50), (0, 0))

    # marcatura
    msp.add_line(
        (10, 25),
        (30, 25),
        dxfattribs={'layer': mark_layer},
    )

    special_layers = {
        mark_layer: mark_type,
    }

    return msp, special_layers


def _rect_with_bending(
    bend_layer='MARCATURA',
):
    """
    Rettangolo 100x50 +
    3 LINE di piega.
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    msp.add_line((0, 0), (100, 0))
    msp.add_line((100, 0), (100, 50))
    msp.add_line((100, 50), (0, 50))
    msp.add_line((0, 50), (0, 0))

    for y in [15, 25, 35]:
        msp.add_line(
            (0, y),
            (100, y),
            dxfattribs={'layer': bend_layer},
        )

    special_layers = {
        bend_layer: 'bending',
    }

    return msp, special_layers


def _rect_with_mark_loop(
    mark_layer='MARK',
):
    """
    Rettangolo 100x50 +
    loop chiuso su MARK.
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # rettangolo
    msp.add_line((0, 0), (100, 0))
    msp.add_line((100, 0), (100, 50))
    msp.add_line((100, 50), (0, 50))
    msp.add_line((0, 50), (0, 0))

    # loop MARK
    msp.add_line((20, 10), (30, 10), dxfattribs={'layer': mark_layer})
    msp.add_line((30, 10), (30, 20), dxfattribs={'layer': mark_layer})
    msp.add_line((30, 20), (20, 20), dxfattribs={'layer': mark_layer})
    msp.add_line((20, 20), (20, 10), dxfattribs={'layer': mark_layer})

    special_layers = {
        mark_layer: 'engrave',
    }

    return msp, special_layers


# ---------------------------------------------------------------------------
# Test: special layer non diventa contour
# ---------------------------------------------------------------------------

class TestSpecialLayerNotOuter(unittest.TestCase):

    def setUp(self):
        msp, special_layers = _rect_with_mark_loop()

        self.result = _run_pipeline(
            msp=msp,
            special_layers=special_layers,
        )

    def test_001_finds_one_part(self):
        self.assertEqual(
            self.result.part_count,
            1,
        )

    def test_002_no_errors(self):
        self.assertEqual(
            len(self.result.errors),
            0,
        )

    def test_003_area_is_rectangle(self):
        area = self.result.parts[0].area

        self.assertAlmostEqual(
            area,
            100 * 50,
            delta=1.0,
        )

    def test_004_no_holes(self):
        self.assertEqual(
            len(self.result.parts[0].inners),
            0,
        )


# ---------------------------------------------------------------------------
# Test: special layer non finisce in trash
# ---------------------------------------------------------------------------

class TestSpecialLayerNotTrash(unittest.TestCase):

    def setUp(self):
        doc = ezdxf.new('R2010')
        self.msp = doc.modelspace()

        # rettangolo
        self.msp.add_line((0, 0), (100, 0))
        self.msp.add_line((100, 0), (100, 50))
        self.msp.add_line((100, 50), (0, 50))
        self.msp.add_line((0, 50), (0, 0))

        # MARK
        self.msp.add_line(
            (10, 25),
            (30, 25),
            dxfattribs={'layer': 'MARK'},
        )

        self.result = _run_pipeline(
            msp=self.msp,
            special_layers={'MARK': 'engrave'},
            inject=True,
        )

    def test_001_mark_not_in_trash(self):

        for entity in self.msp:

            layer = (
                entity.dxf.layer
                if entity.dxf.hasattr("layer")
                else ""
            )

            if layer == TRASH_LAYER:

                if entity.dxftype() == 'LINE':

                    s = (
                        entity.dxf.start.x,
                        entity.dxf.start.y,
                    )

                    self.assertNotEqual(
                        s,
                        (10, 25),
                        "La LINE su MARK è finita in trash",
                    )

    def test_002_mark_layer_preserved(self):

        found = any(
            entity.dxf.layer == LAYER_ENGRAVE
            for entity in self.msp
        )

        self.assertTrue(
            found,
            "Nessuna entità ENGRAVE trovata",
        )


# ---------------------------------------------------------------------------
# Test: total_engrave_length
# ---------------------------------------------------------------------------

class TestEngraveLength(unittest.TestCase):

    def setUp(self):

        msp, special_layers = _rect_with_mark()

        self.result = _run_pipeline(
            msp=msp,
            special_layers=special_layers,
            inject=True,
        )

    def test_001_has_custom(self):

        self.assertIsNotNone(
            self.result.parts[0].custom,
        )

    def test_002_engrave_length_present(self):

        custom = self.result.parts[0].custom

        self.assertIn(
            'total_engrave_length',
            custom,
        )

    def test_003_engrave_length_correct(self):

        length = self.result.parts[0].custom[
            'total_engrave_length'
        ]

        self.assertAlmostEqual(
            length,
            20.0,
            delta=0.01,
        )

    def test_004_no_bending_lines(self):

        custom = self.result.parts[0].custom

        self.assertNotIn(
            'bending_lines',
            custom,
        )


# ---------------------------------------------------------------------------
# Test: bending_lines
# ---------------------------------------------------------------------------

class TestBendingLines(unittest.TestCase):

    def setUp(self):

        msp, special_layers = _rect_with_bending()

        self.result = _run_pipeline(
            msp=msp,
            special_layers=special_layers,
            inject=True,
        )

    def test_001_has_custom(self):

        self.assertIsNotNone(
            self.result.parts[0].custom,
        )

    def test_002_bending_lines_present(self):

        custom = self.result.parts[0].custom

        self.assertIn(
            'bending_lines',
            custom,
        )

    def test_003_bending_lines_correct(self):

        count = self.result.parts[0].custom[
            'bending_lines'
        ]

        self.assertEqual(
            count,
            3,
        )


# ---------------------------------------------------------------------------
# Test: mix engrave + bending
# ---------------------------------------------------------------------------

class TestMixedSpecialLayers(unittest.TestCase):

    def setUp(self):

        doc = ezdxf.new('R2010')
        msp = doc.modelspace()

        # rettangolo
        msp.add_line((0, 0), (100, 0))
        msp.add_line((100, 0), (100, 50))
        msp.add_line((100, 50), (0, 50))
        msp.add_line((0, 50), (0, 0))

        # engrave
        msp.add_line(
            (10, 25),
            (30, 25),
            dxfattribs={'layer': 'MARK'},
        )

        # bending
        msp.add_line(
            (0, 15),
            (100, 15),
            dxfattribs={'layer': 'MARCATURA'},
        )

        msp.add_line(
            (0, 35),
            (100, 35),
            dxfattribs={'layer': 'MARCATURA'},
        )

        self.result = _run_pipeline(
            msp=msp,
            special_layers={
                'MARK': 'engrave',
                'MARCATURA': 'bending',
            },
            inject=True,
        )

    def test_001_one_part(self):

        self.assertEqual(
            self.result.part_count,
            1,
        )

    def test_002_bending_lines(self):

        self.assertEqual(
            self.result.parts[0].custom.get(
                'bending_lines'
            ),
            2,
        )

    def test_003_total_engrave_length(self):

        length = self.result.parts[0].custom.get(
            'total_engrave_length',
            0,
        )

        self.assertAlmostEqual(
            length,
            20.0,
            delta=0.1,
        )

    def test_004_bending_lines(self):

        count = self.result.parts[0].custom.get(
            'bending_lines',
            0,
        )

        self.assertEqual(
            count,
            2,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)