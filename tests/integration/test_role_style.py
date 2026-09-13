"""
test_role_style.py
-------------------
Test per RoleStyle (MAP.md D37): override esplicito di colore/linetype/
lineweight per ruolo in to_dxf()/split(), noto a forge o assegnato da un
consumatore (label_map). L'override agisce sul layer, non sull'entità —
tutto ciò che forge scrive è BYLAYER.
"""

import unittest
from pathlib import Path
import sys

import ezdxf

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge import RoleStyle
from forge.adapters.dxf.layers import LAYER_HOLE, TRASH_LAYER


def _rect_with_hole_and_frame():
    """
    Rettangolo 100x50 con un foro (per il ruolo 'hole', noto a forge) + una
    LINE su layer FRAME fuori dal rettangolo (diventa trash col ruolo
    consumatore 'frame', mai visto da forge prima d'ora — D31).
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    msp.add_line((0, 0), (100, 0))
    msp.add_line((100, 0), (100, 50))
    msp.add_line((100, 50), (0, 50))
    msp.add_line((0, 50), (0, 0))
    msp.add_circle((50, 25), 5)

    msp.add_line((200, 200), (220, 200), dxfattribs={'layer': 'FRAME'})

    doc_in = forge.document_from_msp(msp, label_map={'FRAME': 'frame'})
    result = forge.heal(doc_in, tolerance=0.05)
    forge.detect(result, features="all")
    return result, doc_in


class TestRoleStyleDefaultUnchanged(unittest.TestCase):
    """Senza role_styles, il comportamento è identico a prima di D37."""

    def setUp(self):
        self.result, self.doc_in = _rect_with_hole_and_frame()
        self.doc_out = forge.to_dxf(self.result, self.doc_in)

    def test_001_hole_layer_has_no_true_color_override(self):
        layer = self.doc_out.layers.get(LAYER_HOLE)
        self.assertFalse(layer.dxf.hasattr("true_color"))

    def test_002_frame_layer_created_with_consumer_color(self):
        # Layer creato al volo col nome dello slug (D31), colore di default
        # (grigio consumatore), nessun override richiesto.
        self.assertIn('frame', self.doc_out.layers)
        layer = self.doc_out.layers.get('frame')
        self.assertFalse(layer.dxf.hasattr("true_color"))


class TestRoleStyleColorOverride(unittest.TestCase):
    """role_styles fa override del colore di un ruolo noto a forge."""

    def setUp(self):
        self.result, self.doc_in = _rect_with_hole_and_frame()
        self.doc_out = forge.to_dxf(
            self.result, self.doc_in,
            role_styles={"hole": RoleStyle(color=(0, 0, 0))},
        )

    def test_001_hole_layer_true_color_is_black(self):
        layer = self.doc_out.layers.get(LAYER_HOLE)
        self.assertEqual(layer.rgb, (0, 0, 0))

    def test_002_other_layers_untouched(self):
        outer_layer = self.doc_out.layers.get("OuterContour")
        self.assertFalse(outer_layer.dxf.hasattr("true_color"))


class TestRoleStyleConsumerRole(unittest.TestCase):
    """role_styles funziona anche su uno slug di consumatore (frame, D31)."""

    def setUp(self):
        self.result, self.doc_in = _rect_with_hole_and_frame()
        self.doc_out = forge.to_dxf(
            self.result, self.doc_in,
            role_styles={"frame": RoleStyle(color=(0, 0, 0), lineweight=0.05)},
        )

    def test_001_frame_layer_is_black(self):
        layer = self.doc_out.layers.get('frame')
        self.assertEqual(layer.rgb, (0, 0, 0))

    def test_002_frame_layer_lineweight_in_hundredths_mm(self):
        layer = self.doc_out.layers.get('frame')
        self.assertEqual(layer.dxf.lineweight, 5)  # 0.05 mm * 100


class TestRoleStyleLinetypeOverride(unittest.TestCase):
    """role_styles registra e applica un linetype standard ezdxf."""

    def setUp(self):
        self.result, self.doc_in = _rect_with_hole_and_frame()
        self.doc_out = forge.to_dxf(
            self.result, self.doc_in,
            role_styles={"unknown": RoleStyle(linetype="DASHED")},
        )

    def test_001_dashed_linetype_registered(self):
        self.assertIn("DASHED", self.doc_out.linetypes)

    def test_002_trash_layer_uses_dashed(self):
        layer = self.doc_out.layers.get(TRASH_LAYER)
        self.assertEqual(layer.dxf.linetype, "DASHED")


class TestRoleStyleUnknownRoleCreatesLayerEvenWithoutEntities(unittest.TestCase):
    """
    Un override per un ruolo che non compare in nessuna entità di questo
    documento non deve sollevare — il layer viene comunque creato e stilato.
    """

    def setUp(self):
        self.result, self.doc_in = _rect_with_hole_and_frame()
        self.doc_out = forge.to_dxf(
            self.result, self.doc_in,
            role_styles={"title_block": RoleStyle(color=(10, 20, 30))},
        )

    def test_001_layer_exists(self):
        self.assertIn("title_block", self.doc_out.layers)

    def test_002_layer_has_override_color(self):
        layer = self.doc_out.layers.get("title_block")
        self.assertEqual(layer.rgb, (10, 20, 30))


if __name__ == "__main__":
    unittest.main(verbosity=2)
