"""
test_special_layers.py
----------------------
Test per la gestione dei layer speciali (MARK, MARCATURA, ecc.).

Verifica che:
  - Le entità su special_layers non entrino nel grafo (no loop spuri)
  - Non finiscano su OuterContour/InnerContour
  - Non finiscano in trash
  - I metadati (total_engrave_length, bending_lines) siano corretti

DXF sintetici generati inline — nessun file su disco necessario.

Lancia:
    python -m pytest tests/test_special_layers.py -v
"""

import unittest
import math
from pathlib import Path
import sys
import ezdxf

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import dxf_forge as forge
from dxf_forge.layers import LAYER_OUTER, LAYER_INNER, TRASH_LAYER, LAYER_ENGRAVE, LAYER_BENDING


def _rect_with_mark(mark_layer='MARK', mark_type='engrave'):
    """
    Crea un DXF con:
      - rettangolo 100x50 su layer '0' (geometria pezzo)
      - una LINE orizzontale 20mm su layer MARK (marcatura)

    Restituisce (msp, special_layers).
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # rettangolo
    msp.add_line((0,   0),   (100, 0))
    msp.add_line((100, 0),   (100, 50))
    msp.add_line((100, 50),  (0,   50))
    msp.add_line((0,   50),  (0,   0))

    # marcatura — una LINE da 20mm sul layer speciale
    msp.add_line((10, 25), (30, 25), dxfattribs={'layer': mark_layer})

    special_layers = {mark_layer: mark_type}
    return msp, special_layers


def _rect_with_bending(bend_layer='MARCATURA'):
    """
    Crea un DXF con:
      - rettangolo 100x50 su layer '0'
      - 3 LINE di piega su layer MARCATURA
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    msp.add_line((0,   0),   (100, 0))
    msp.add_line((100, 0),   (100, 50))
    msp.add_line((100, 50),  (0,   50))
    msp.add_line((0,   50),  (0,   0))

    for y in [15, 25, 35]:
        msp.add_line((0, y), (100, y), dxfattribs={'layer': bend_layer})

    special_layers = {bend_layer: 'bending'}
    return msp, special_layers


def _rect_with_mark_loop(mark_layer='MARK'):
    """
    Crea un DXF con:
      - rettangolo 100x50 su layer '0'
      - un loop chiuso (quadrato 10x10) su layer MARK
        che senza filtro verrebbe healato come OuterContour
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    msp.add_line((0,   0),   (100, 0))
    msp.add_line((100, 0),   (100, 50))
    msp.add_line((100, 50),  (0,   50))
    msp.add_line((0,   50),  (0,   0))

    # loop chiuso su layer MARK
    msp.add_line((20, 10), (30, 10), dxfattribs={'layer': mark_layer})
    msp.add_line((30, 10), (30, 20), dxfattribs={'layer': mark_layer})
    msp.add_line((30, 20), (20, 20), dxfattribs={'layer': mark_layer})
    msp.add_line((20, 20), (20, 10), dxfattribs={'layer': mark_layer})

    special_layers = {mark_layer: 'engrave'}
    return msp, special_layers


# ---------------------------------------------------------------------------
# Test: entità speciale non diventa OuterContour
# ---------------------------------------------------------------------------

class TestSpecialLayerNotOuter(unittest.TestCase):
    """
    Una LINE su MARK non deve diventare OuterContour,
    anche se forma un loop chiuso.
    """

    def setUp(self):
        msp, special_layers = _rect_with_mark_loop()
        self.result = forge.heal(msp, tolerance=0.05,
                                 write_to_msp=False,
                                 special_layers=special_layers)

    def test_001_finds_one_part(self):
        """Deve trovare solo 1 parte — il rettangolo."""
        self.assertEqual(self.result.part_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_area_is_rectangle(self):
        """L'area deve essere quella del rettangolo, non del loop MARK."""
        area = self.result.parts[0].area
        self.assertAlmostEqual(area, 100 * 50, delta=1.0)

    def test_004_no_holes(self):
        """Il loop MARK non deve diventare un foro."""
        self.assertEqual(len(self.result.parts[0].inners), 0)


# ---------------------------------------------------------------------------
# Test: entità speciale non finisce in trash
# ---------------------------------------------------------------------------

class TestSpecialLayerNotTrash(unittest.TestCase):
    """
    Con write_to_msp=True, le entità su special_layers
    non devono finire su TRASH_LAYER.
    """

    def setUp(self):
        doc = ezdxf.new('R2010')
        self.msp = doc.modelspace()
        self.msp.add_line((0,   0),   (100, 0))
        self.msp.add_line((100, 0),   (100, 50))
        self.msp.add_line((100, 50),  (0,   50))
        self.msp.add_line((0,   50),  (0,   0))
        self.msp.add_line((10, 25), (30, 25),
                          dxfattribs={'layer': 'MARK'})
        forge.heal(self.msp, tolerance=0.05, write_to_msp=True,
                   special_layers={'MARK': 'engrave'})

    def test_001_mark_not_in_trash(self):
        """Nessuna entità su MARK deve essere finita in trash."""
        for entity in self.msp:
            layer = entity.dxf.layer if entity.dxf.hasattr("layer") else ""
            if layer == TRASH_LAYER:
                # verifica che non sia la nostra entità MARK
                if entity.dxftype() == 'LINE':
                    s = (entity.dxf.start.x, entity.dxf.start.y)
                    e = (entity.dxf.end.x,   entity.dxf.end.y)
                    self.assertNotEqual(s, (10, 25),
                                        "La LINE su MARK è finita in trash")

    def test_002_mark_layer_preserved(self):
        """Le entità su MARK devono essere spostate su LAYER_ENGRAVE dopo heal."""
        found = any(
            entity.dxf.layer == LAYER_ENGRAVE
            for entity in self.msp
        )
        self.assertTrue(found, "Nessuna entità su layer Engrave trovata dopo heal")


# ---------------------------------------------------------------------------
# Test: total_engrave_length nei metadati
# ---------------------------------------------------------------------------

class TestEngraveLength(unittest.TestCase):
    """
    Una LINE da 20mm su MARK deve produrre
    total_engrave_length=20.0 nei custom del ForgePart.
    """

    def setUp(self):
        msp, special_layers = _rect_with_mark()
        self.result = forge.heal(msp, tolerance=0.05,
                                 write_to_msp=False,
                                 special_layers=special_layers)

    def test_001_has_custom(self):
        self.assertIsNotNone(self.result.parts[0].custom)

    def test_002_engrave_length_present(self):
        custom = self.result.parts[0].custom
        self.assertIn('total_engrave_length', custom)

    def test_003_engrave_length_correct(self):
        """LINE da (10,25) a (30,25) = 20mm."""
        length = self.result.parts[0].custom['total_engrave_length']
        self.assertAlmostEqual(length, 20.0, delta=0.01)

    def test_004_no_bending_lines(self):
        """Engrave non deve produrre bending_lines."""
        custom = self.result.parts[0].custom
        self.assertNotIn('bending_lines', custom)


# ---------------------------------------------------------------------------
# Test: bending_lines nei metadati
# ---------------------------------------------------------------------------

class TestBendingLines(unittest.TestCase):
    """
    3 LINE su MARCATURA (bending) devono produrre
    bending_lines=3 e total_engrave_length=300mm nei custom.
    """

    def setUp(self):
        msp, special_layers = _rect_with_bending()
        self.result = forge.heal(msp, tolerance=0.05,
                                 write_to_msp=False,
                                 special_layers=special_layers)

    def test_001_has_custom(self):
        self.assertIsNotNone(self.result.parts[0].custom)

    def test_002_bending_lines_present(self):
        custom = self.result.parts[0].custom
        self.assertIn('bending_lines', custom)

    def test_003_bending_lines_correct(self):
        """3 LINE di piega."""
        count = self.result.parts[0].custom['bending_lines']
        self.assertEqual(count, 3)

    def test_004_engrave_length_correct(self):
        """3 LINE da 100mm ciascuna = 300mm totali."""
        length = self.result.parts[0].custom['total_engrave_length']
        self.assertAlmostEqual(length, 300.0, delta=0.1)


# ---------------------------------------------------------------------------
# Test: mix engrave + bending
# ---------------------------------------------------------------------------

class TestMixedSpecialLayers(unittest.TestCase):
    """
    MARK (engrave) + MARCATURA (bending) insieme.
    Verifica che entrambi vengano conteggiati correttamente.
    """

    def setUp(self):
        doc = ezdxf.new('R2010')
        msp = doc.modelspace()

        # rettangolo
        msp.add_line((0,   0),   (100, 0))
        msp.add_line((100, 0),   (100, 50))
        msp.add_line((100, 50),  (0,   50))
        msp.add_line((0,   50),  (0,   0))

        # engrave: LINE da 20mm
        msp.add_line((10, 25), (30, 25), dxfattribs={'layer': 'MARK'})

        # bending: 2 LINE da 100mm
        msp.add_line((0, 15), (100, 15), dxfattribs={'layer': 'MARCATURA'})
        msp.add_line((0, 35), (100, 35), dxfattribs={'layer': 'MARCATURA'})

        self.result = forge.heal(
            msp, tolerance=0.05, write_to_msp=False,
            special_layers={'MARK': 'engrave', 'MARCATURA': 'bending'}
        )

    def test_001_one_part(self):
        self.assertEqual(self.result.part_count, 1)

    def test_002_bending_lines(self):
        self.assertEqual(self.result.parts[0].custom.get('bending_lines'), 2)

    def test_003_total_engrave_length(self):
        """20mm (MARK) + 200mm (MARCATURA) = 220mm."""
        length = self.result.parts[0].custom.get('total_engrave_length', 0)
        self.assertAlmostEqual(length, 220.0, delta=0.1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
