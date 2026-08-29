
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
    doc = forge.document_from_msp(msp, label_map=special_layers)

    result = forge.heal(
        doc,
        tolerance=tolerance,
    )

    forge.detect(
        result, features="all",
    )

    doc_out = forge.to_dxf(result, doc)

    if inject:
        forge.inject(result)

    return result, doc_out


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

        self.result, self.doc_out = _run_pipeline(
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

        self.result, self.doc_out = _run_pipeline(
            msp=self.msp,
            special_layers={'MARK': 'engrave'},
            inject=True,
        )

    def test_001_mark_not_in_trash(self):

        for entity in self.doc_out.modelspace():

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
        # La LINE su MARK deve sopravvivere come engrave: nel modello
        # (part.engrave_lines) e materializzata sul layer Engrave del doc_out.
        engrave = [
            eng
            for part in self.result.parts
            for eng in part.engrave_lines
        ]
        self.assertTrue(engrave, "Nessuna engrave line rilevata dal modello")

        on_engrave = [
            e for e in self.doc_out.modelspace()
            if e.dxf.hasattr("layer") and e.dxf.layer == LAYER_ENGRAVE
        ]
        self.assertTrue(
            on_engrave,
            "Engrave line non materializzata sul layer Engrave da to_dxf()",
        )

    def test_003_engrave_materialized_as_native_line_not_point(self):
        # Regressione Cluster D: l'incisione va scritta come geometria nativa
        # (qui una LINE), NON come LWPOLYLINE. Prima usava write_segments (che
        # chiude il contorno) e finiva una LWPOLYLINE con il solo punto di
        # start → in output si vedeva un punto al posto della linea.
        on_engrave = [
            e for e in self.doc_out.modelspace()
            if e.dxf.hasattr("layer") and e.dxf.layer == LAYER_ENGRAVE
        ]
        self.assertEqual(len(on_engrave), 1)
        line = on_engrave[0]
        self.assertEqual(line.dxftype(), "LINE")
        endpoints = {
            (round(line.dxf.start.x, 3), round(line.dxf.start.y, 3)),
            (round(line.dxf.end.x, 3), round(line.dxf.end.y, 3)),
        }
        self.assertEqual(endpoints, {(10.0, 25.0), (30.0, 25.0)})

    def test_004_no_lwpolyline_on_engrave_layer(self):
        pl = [
            e for e in self.doc_out.modelspace()
            if e.dxftype() == "LWPOLYLINE"
            and e.dxf.hasattr("layer") and e.dxf.layer == LAYER_ENGRAVE
        ]
        self.assertEqual(pl, [], "le incisioni non devono uscire come LWPOLYLINE")


# ---------------------------------------------------------------------------
# Test: total_engrave_length
# ---------------------------------------------------------------------------

class TestEngraveLength(unittest.TestCase):

    def setUp(self):

        msp, special_layers = _rect_with_mark()

        self.result, self.doc_out = _run_pipeline(
            msp=msp,
            special_layers=special_layers,
            inject=True,
        )

    def test_001_has_custom(self):

        self.assertIsNotNone(
            self.result.parts[0].custom,
        )

    def test_002_engrave_length_present(self):

        summary = self.result.parts[0].summary

        self.assertIn(
            'total_engrave_length',
            summary,
        )

    def test_003_engrave_length_correct(self):

        length = self.result.parts[0].summary[
            'total_engrave_length'
        ]

        self.assertAlmostEqual(
            length,
            20.0,
            delta=0.01,
        )

    def test_004_no_bending_lines(self):

        self.assertEqual(
            self.result.parts[0].summary['bending_lines'],
            0,
        )


# ---------------------------------------------------------------------------
# Test: bending_lines
# ---------------------------------------------------------------------------

class TestBendingLines(unittest.TestCase):

    def setUp(self):

        msp, special_layers = _rect_with_bending()

        self.result, self.doc_out = _run_pipeline(
            msp=msp,
            special_layers=special_layers,
            inject=True,
        )

    def test_001_has_custom(self):

        self.assertIsNotNone(
            self.result.parts[0].custom,
        )

    def test_002_bending_lines_present(self):

        summary = self.result.parts[0].summary

        self.assertIn(
            'bending_lines',
            summary,
        )

    def test_003_bending_lines_correct(self):

        count = self.result.parts[0].summary[
            'bending_lines'
        ]

        self.assertEqual(
            count,
            3,
        )


# ---------------------------------------------------------------------------
# Test: engrave degenere (CIRCLE su layer mark) — non deve andare perso
# ---------------------------------------------------------------------------

class TestEngraveDegenerateCircle(unittest.TestCase):
    """
    Un CIRCLE su layer engrave è una traccia già chiusa (loop degenere).
    Non passa dalla ricerca loop: l'unico calcolo è il contenimento.
    Dentro il part → Engraving(closed=True), mai un foro. Fuori → trash.
    """

    def setUp(self):
        doc = ezdxf.new('R2010')
        msp = doc.modelspace()

        msp.add_line((0, 0), (100, 0))
        msp.add_line((100, 0), (100, 50))
        msp.add_line((100, 50), (0, 50))
        msp.add_line((0, 50), (0, 0))

        # CIRCLE engrave DENTRO il part
        msp.add_circle((50, 25), 5, dxfattribs={'layer': 'MARK'})
        # LINE engrave FUORI dal part
        msp.add_line((200, 200), (220, 200), dxfattribs={'layer': 'MARK'})

        self.result, self.doc_out = _run_pipeline(
            msp=msp,
            special_layers={'MARK': 'engrave'},
        )

    def test_001_circle_is_not_a_hole(self):
        part = self.result.parts[0]
        self.assertEqual(len(part.holes), 0)
        self.assertEqual(len(part.inners), 0)

    def test_002_circle_becomes_engraving(self):
        part = self.result.parts[0]
        self.assertEqual(len(part.engrave_lines), 1)
        self.assertAlmostEqual(part.engrave_lines[0].length, 2 * 3.14159 * 5, delta=0.5)

    def test_003_circle_materialized_on_engrave_layer(self):
        on_engrave = [
            e for e in self.doc_out.modelspace()
            if e.dxf.hasattr("layer") and e.dxf.layer == LAYER_ENGRAVE
        ]
        self.assertTrue(on_engrave)

    def test_004_orphan_engrave_stays_trash(self):
        # la LINE engrave fuori dal part non è una engrave line del part
        part = self.result.parts[0]
        self.assertEqual(len(part.engrave_lines), 1)
        # ed è rimasta come trash, non promossa a nulla
        roles = [getattr(t, "role", None) for t in self.result.trash_entities]
        self.assertIn("engrave", [getattr(r, "value", r) for r in roles])


# ---------------------------------------------------------------------------
# Test: engrave ad arco → ARC nativo, non LWPOLYLINE
# ---------------------------------------------------------------------------

class TestEngraveArcNative(unittest.TestCase):
    """Cluster D: un'incisione ad arco esce come ARC nativo, geometria esatta."""

    def setUp(self):
        doc = ezdxf.new('R2010')
        msp = doc.modelspace()
        msp.add_line((0, 0), (100, 0))
        msp.add_line((100, 0), (100, 50))
        msp.add_line((100, 50), (0, 50))
        msp.add_line((0, 50), (0, 0))
        msp.add_arc(
            center=(50, 25), radius=8, start_angle=0, end_angle=120,
            dxfattribs={'layer': 'MARK'},
        )
        self.result, self.doc_out = _run_pipeline(
            msp=msp, special_layers={'MARK': 'engrave'},
        )

    def test_001_arc_is_native_arc(self):
        on_engrave = [
            e for e in self.doc_out.modelspace()
            if e.dxf.hasattr("layer") and e.dxf.layer == LAYER_ENGRAVE
        ]
        self.assertEqual(len(on_engrave), 1)
        self.assertEqual(on_engrave[0].dxftype(), "ARC")

    def test_002_arc_geometry_preserved(self):
        arc = next(
            e for e in self.doc_out.modelspace()
            if e.dxftype() == "ARC"
            and e.dxf.hasattr("layer") and e.dxf.layer == LAYER_ENGRAVE
        )
        self.assertAlmostEqual(arc.dxf.center.x, 50.0, places=3)
        self.assertAlmostEqual(arc.dxf.center.y, 25.0, places=3)
        self.assertAlmostEqual(arc.dxf.radius, 8.0, places=3)
        self.assertAlmostEqual(arc.dxf.start_angle % 360, 0.0, places=3)
        self.assertAlmostEqual(arc.dxf.end_angle % 360, 120.0, places=3)


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

        self.result, self.doc_out = _run_pipeline(
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
            self.result.parts[0].summary.get(
                'bending_lines'
            ),
            2,
        )

    def test_003_total_engrave_length(self):

        length = self.result.parts[0].summary.get(
            'total_engrave_length',
            0,
        )

        self.assertAlmostEqual(
            length,
            20.0,
            delta=0.1,
        )

    def test_004_bending_lines(self):

        count = self.result.parts[0].summary.get(
            'bending_lines',
            0,
        )

        self.assertEqual(
            count,
            2,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)