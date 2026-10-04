"""
test_role_style.py
-------------------
Test per RoleStyle (MAP.md D37): override esplicito di colore/linetype/
lineweight per ruolo in to_dxf()/split(), noto a forge o assegnato da un
consumatore (role_rules). L'override agisce sul layer, non sull'entità —
tutto ciò che forge scrive è BYLAYER.
"""

import unittest
from pathlib import Path
import sys

import ezdxf

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge import RoleStyle, register_role_style
from forge.adapters.dxf.layers import TRASH_LAYER


def _rect_with_hole_and_frame():
    """
    Rettangolo 100x50 con un cerchio dentro + una LINE su layer STAMP dentro
    (ruolo 'stamp_d90', registrato dai test) + una LINE su layer FRAME fuori
    (ruolo consumatore 'frame', mai registrato — D31).
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    msp.add_line((0, 0), (100, 0))
    msp.add_line((100, 0), (100, 50))
    msp.add_line((100, 50), (0, 50))
    msp.add_line((0, 50), (0, 0))
    msp.add_circle((50, 25), 5)

    msp.add_line((10, 10), (30, 10), dxfattribs={'layer': 'STAMP'})
    msp.add_line((200, 200), (220, 200), dxfattribs={'layer': 'FRAME'})

    doc_in = forge.document_from_msp(
        msp, role_rules=forge.name_rules({'FRAME': 'frame', 'STAMP': 'stamp_d90'}))
    result = forge.heal(doc_in, tolerance=0.05)
    return result, doc_in


class TestRoleStyleRegisteredRole(unittest.TestCase):
    """
    Un ruolo di consumatore registrato con `register_role_style` ha il suo
    colore sul layer col nome registrato; uno mai registrato (`frame`) prende
    il grigio consumatore, senza `true_color` (D31, D37).
    """

    def setUp(self):
        register_role_style("stamp_d90", RoleStyle(color=(255, 0, 255), layer_name="StampD90"))
        self.result, self.doc_in = _rect_with_hole_and_frame()
        self.doc_out = forge.to_dxf(self.result, self.doc_in)

    def test_001_registered_layer_has_true_color(self):
        layer = self.doc_out.layers.get("StampD90")
        self.assertTrue(layer.dxf.hasattr("true_color"))
        self.assertEqual(layer.rgb, (255, 0, 255))

    def test_002_frame_layer_created_with_consumer_color(self):
        # Layer creato al volo col nome dello slug (D31), colore di default
        # (grigio consumatore), nessun override richiesto.
        self.assertIn('frame', self.doc_out.layers)
        layer = self.doc_out.layers.get('frame')
        self.assertFalse(layer.dxf.hasattr("true_color"))


class TestRoleStyleColorOverride(unittest.TestCase):
    """role_styles fa override del colore di un ruolo registrato."""

    def setUp(self):
        register_role_style("stamp_d90", RoleStyle(color=(255, 0, 255), layer_name="StampD90"))
        self.result, self.doc_in = _rect_with_hole_and_frame()
        self.doc_out = forge.to_dxf(
            self.result, self.doc_in,
            role_styles={"stamp_d90": RoleStyle(color=(0, 0, 0))},
        )

    def test_001_registered_layer_true_color_is_black(self):
        layer = self.doc_out.layers.get("StampD90")
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


class TestRoleStyleUnknownLinetypeRaises(unittest.TestCase):
    """
    Un linetype che né il documento né la tabella standard sanno definire è
    un errore di configurazione del consumatore: solleva, mai un DXF con un
    riferimento pendente (MAP.md D85).
    """

    def test_001_unknown_name_raises(self):
        result, doc_in = _rect_with_hole_and_frame()
        with self.assertRaises(ValueError):
            forge.to_dxf(result, doc_in, role_styles={"unknown": RoleStyle(linetype="DASHHED")})


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
