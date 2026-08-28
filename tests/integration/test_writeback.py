"""
test_writeback.py
-----------------
Test di integrazione per forge.to_dxf().

Dopo il refactoring `write` non modifica più il modelspace sorgente: produce
un Drawing NUOVO. Questi test verificano il routing dei layer forge sul
documento materializzato (doc_out), non più sul msp di partenza.

Il vecchio comportamento "sposta le entità sul msp / entità su layer Trash /
keep_trash" non esiste più — i test relativi sono stati riscritti per
ispezionare il modello (`result.trash_entities`) o l'output di to_dxf().

Prima di lanciare, genera i DXF di esempio:
    python tests/generate_examples.py

Poi lancia:
    python -m pytest tests/integration/test_writeback.py -v
"""

import unittest
from collections import Counter
from pathlib import Path
import sys
import ezdxf

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.adapters.dxf.geometry_adapter import entity_to_polygon
from forge.adapters.dxf.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    LAYER_COUNTERSINK, LAYER_BENDING, LAYER_ENGRAVE,
)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def _pipeline(name, *, detect=False, label_map=None):
    """heal (+ detect) → to_dxf. Ritorna (result, msp_out)."""
    doc = forge.load_dxf(EXAMPLES_DIR / name, label_map=label_map or {})
    result = forge.heal(doc)
    if detect:
        forge.detect(result)
    doc_out = forge.to_dxf(result, doc)
    return result, doc_out.modelspace()


def _layers_of(msp, dxftype):
    return {e.dxf.layer for e in msp.query(dxftype)}


# ---------------------------------------------------------------------------
# Rettangolo 4 LINE — routing outer
# ---------------------------------------------------------------------------

class TestWritebackRectLines(unittest.TestCase):

    def setUp(self):
        self.result, self.msp = _pipeline("rect_lines.dxf")

    def test_001_writes_lwpolyline(self):
        self.assertGreaterEqual(len(list(self.msp.query("LWPOLYLINE"))), 1)

    def test_002_outer_layer_assigned(self):
        self.assertIn(LAYER_OUTER, _layers_of(self.msp, "LWPOLYLINE"))

    def test_003_outer_color_bylayer(self):
        for e in self.msp.query("LWPOLYLINE"):
            if e.dxf.layer == LAYER_OUTER:
                self.assertEqual(e.dxf.color, 256)


# ---------------------------------------------------------------------------
# CIRCLE outer (flangia tonda)
# ---------------------------------------------------------------------------

class TestWritebackCircleOuter(unittest.TestCase):

    def setUp(self):
        self.result, self.msp = _pipeline("circle_outer_with_hole.dxf")

    def test_001_outer_layer(self):
        self.assertIn(LAYER_OUTER, _layers_of(self.msp, "CIRCLE"))


# ---------------------------------------------------------------------------
# CIRCLE piccolo → LAYER_HOLE
# ---------------------------------------------------------------------------

class TestWritebackCircleHole(unittest.TestCase):

    def setUp(self):
        self.result, self.msp = _pipeline("rect_with_circle_hole.dxf")

    def test_001_circle_on_hole_layer(self):
        self.assertIn(LAYER_HOLE, _layers_of(self.msp, "CIRCLE"))

    def test_002_circle_color_bylayer(self):
        for e in self.msp.query("CIRCLE"):
            if e.dxf.layer == LAYER_HOLE:
                self.assertEqual(e.dxf.color, 256)


# ---------------------------------------------------------------------------
# CIRCLE grande → LAYER_INNER
# ---------------------------------------------------------------------------

class TestWritebackCircleInner(unittest.TestCase):

    def setUp(self):
        self.result, self.msp = _pipeline("rect_with_circle_inner.dxf")

    def test_001_circle_on_inner_layer(self):
        self.assertIn(LAYER_INNER, _layers_of(self.msp, "CIRCLE"))


# ---------------------------------------------------------------------------
# Countersink — routing dopo detect()
# ---------------------------------------------------------------------------

class TestWritebackCountersink(unittest.TestCase):

    def setUp(self):
        self.result, self.msp = _pipeline("rect_with_countersink.dxf", detect=True)

    def test_001_countersink_on_correct_layer(self):
        circles = [e for e in self.msp.query("CIRCLE")
                   if e.dxf.layer == LAYER_COUNTERSINK]
        self.assertEqual(len(circles), 1)

    def test_002_countersink_collapsed_to_single_hole(self):
        # La coppia concentrica è un solo Hole nel modello → un solo CIRCLE,
        # sul layer Countersink (non più uno su Hole + uno su Countersink).
        self.assertEqual(len(list(self.msp.query("CIRCLE"))), 1)


# ---------------------------------------------------------------------------
# Special layers (BEND + MARK) — routing dopo detect()
# ---------------------------------------------------------------------------

class TestWritebackSpecialLayers(unittest.TestCase):

    def setUp(self):
        self.result, self.msp = _pipeline(
            "rect_with_special_layers.dxf",
            detect=True,
            label_map={"BEND": "bending", "MARK": "engrave"},
        )

    def test_001_no_source_layer_survives(self):
        # I layer originali "BEND"/"MARK" non compaiono mai nel doc_out.
        present = {e.dxf.layer for e in self.msp if e.dxf.hasattr("layer")}
        self.assertNotIn("BEND", present)
        self.assertNotIn("MARK", present)

    def test_002_bending_on_correct_layer(self):
        bending = [e for e in self.msp
                   if e.dxf.hasattr("layer") and e.dxf.layer == LAYER_BENDING]
        self.assertGreater(len(bending), 0)

    def test_003_engrave_geometry_materialized(self):
        # Regressione: to_dxf() deve scrivere la geometria delle engrave line,
        # non solo contarle nel modello.
        engrave = [e for e in self.msp
                   if e.dxf.hasattr("layer") and e.dxf.layer == LAYER_ENGRAVE]
        self.assertGreater(len(engrave), 0,
                           "Nessuna geometria engrave sul layer Engrave del doc_out")


# ---------------------------------------------------------------------------
# LWPOLYLINE outer + loop LINE interno
# ---------------------------------------------------------------------------

class TestWritebackInnerLoop(unittest.TestCase):

    def setUp(self):
        self.result, self.msp = _pipeline("rect_with_inner_mark.dxf")

    def test_001_inner_layer_present(self):
        self.assertIn(LAYER_INNER, _layers_of(self.msp, "LWPOLYLINE"))

    def test_002_single_outer(self):
        outer = [e for e in self.msp.query("LWPOLYLINE")
                 if e.dxf.layer == LAYER_OUTER]
        self.assertEqual(len(outer), 1)


# ---------------------------------------------------------------------------
# Deduplicazione
# ---------------------------------------------------------------------------

class TestWritebackDeduplication(unittest.TestCase):

    def setUp(self):
        self.result, self.msp = _pipeline("rect_lines_duplicated.dxf")

    def test_001_single_outer_lwpolyline(self):
        outer = [e for e in self.msp.query("LWPOLYLINE")
                 if e.dxf.layer == LAYER_OUTER]
        self.assertEqual(len(outer), 1)

    def test_002_no_duplicate_lines_in_output(self):
        from forge.adapters.dxf.sanitize import deduplicate as _dedup
        self.assertEqual(_dedup(self.msp), 0)


# ---------------------------------------------------------------------------
# Trash — vive nel modello E viene materializzato sul layer Trash del doc_out
# ---------------------------------------------------------------------------

from forge.adapters.dxf.layers import TRASH_LAYER


class TestWritebackTrash(unittest.TestCase):

    def test_001_trash_entities_in_model(self):
        result, _ = _pipeline("rect_with_trash.dxf")
        self.assertGreater(len(result.trash_entities), 0)

    def test_002_trash_materialized_on_trash_layer(self):
        # Regressione: to_dxf() DEVE riportare ogni entità non classificata sul
        # layer Trash — un operatore CAM deve vedere tutto il disegno di
        # partenza, non solo le parti pulite.
        result, msp = _pipeline("rect_with_trash.dxf")
        trash = [e for e in msp
                 if e.dxf.hasattr("layer") and e.dxf.layer == TRASH_LAYER]
        self.assertEqual(len(trash), len(result.trash_entities))

    def test_003_include_trash_false_omits_trash(self):
        doc = forge.load_dxf(EXAMPLES_DIR / "rect_with_trash.dxf", label_map={})
        result = forge.heal(doc)
        msp = forge.to_dxf(result, doc, include_trash=False).modelspace()
        trash = [e for e in msp
                 if e.dxf.hasattr("layer") and e.dxf.layer == TRASH_LAYER]
        self.assertEqual(len(trash), 0)

    def test_004_open_trash_not_closed(self):
        # Le tracce aperte non devono essere chiuse: una LWPOLYLINE trash
        # con flag closed falserebbe la forma.
        result, msp = _pipeline("arc_open.dxf")
        self.assertGreater(len(result.trash_entities), 0)
        for e in msp.query("LWPOLYLINE"):
            if e.dxf.layer == TRASH_LAYER:
                self.assertFalse(e.closed)


# ---------------------------------------------------------------------------
# Annotazioni — testi e quote mai scartati, routing su layer dedicato
# ---------------------------------------------------------------------------

from forge.adapters.dxf.layers import LAYER_ANNOTATION


class TestWritebackAnnotations(unittest.TestCase):

    def _texts(self, msp):
        return list(msp.query("TEXT")) + list(msp.query("MTEXT"))

    def test_001_dimensions_and_text_materialized(self):
        # gamba_tavolo: 7 DIMENSION + 1 MTEXT nella sorgente. Nessuna parte le
        # copre → prima sparivano tutte. Ora ognuna è un TEXT/MTEXT scritto.
        result, msp = _pipeline("gamba_tavolo.dxf")
        texts = self._texts(msp)
        self.assertEqual(len(texts), 8)

    def test_002_annotations_on_dedicated_layer_by_default(self):
        result, msp = _pipeline("gamba_tavolo.dxf")
        for e in self._texts(msp):
            self.assertEqual(e.dxf.layer, LAYER_ANNOTATION)

    def test_003_dimension_carries_measured_value(self):
        # La quota non porta geometria nel modello: ne materializziamo il valore.
        result, msp = _pipeline("gamba_tavolo.dxf")
        values = {e.dxf.text for e in msp.query("TEXT")}
        self.assertIn("50", values)

    def test_003b_dimension_geometry_rendered_not_just_number(self):
        # Regressione: la quota deve uscire con le sue linee (direttrici, linea
        # di misura, frecce), non solo un numero piazzato a caso.
        result, msp = _pipeline("gamba_tavolo.dxf")
        dim_geom = [e for e in msp.query("LWPOLYLINE")
                    if e.dxf.layer == LAYER_ANNOTATION]
        # 7 quote → parecchie polilinee (≈ 2 direttrici + linea misura + frecce)
        self.assertGreater(len(dim_geom), 7 * 3)

    def test_004_text_covered_by_part_also_routed_to_annotation(self):
        # rect_with_trash: il TEXT è dentro l'outer, prima restava sul layer
        # sorgente "TESTO". Col default va comunque sul layer Annotation.
        result, msp = _pipeline("rect_with_trash.dxf")
        texts = self._texts(msp)
        self.assertEqual(len(texts), 1)
        self.assertEqual(texts[0].dxf.layer, LAYER_ANNOTATION)

    def test_005_annotation_layer_none_keeps_source_layer(self):
        doc = forge.load_dxf(EXAMPLES_DIR / "rect_with_trash.dxf")
        result = forge.heal(doc)
        msp = forge.to_dxf(result, doc, annotation_layer=None).modelspace()
        texts = list(msp.query("TEXT"))
        self.assertEqual(len(texts), 1)
        self.assertEqual(texts[0].dxf.layer, "TESTO")

    def test_006_annotation_layer_custom_routes_there(self):
        doc = forge.load_dxf(EXAMPLES_DIR / "rect_with_trash.dxf")
        result = forge.heal(doc)
        msp = forge.to_dxf(result, doc, annotation_layer=TRASH_LAYER).modelspace()
        texts = list(msp.query("TEXT"))
        self.assertEqual(texts[0].dxf.layer, TRASH_LAYER)

    def test_007_dims_and_leaders_survive_audit(self):
        # Multifeature: 16 DIMENSION (senza blocco geometria → l'auditor di
        # ezdxf le cancellava) + 4 LEADER (frecce di sezione, senza repr point).
        # Devono arrivare tutte in output.
        name = "Multifeature.dxf"
        if not (EXAMPLES_DIR / name).exists():
            self.skipTest(name)
        doc = forge.load_dxf(EXAMPLES_DIR / name)
        kinds = Counter(a.kind for a in doc.annotations)
        self.assertEqual(kinds["DIMENSION"], 16)
        self.assertEqual(kinds["LEADER"], 4)
        result = forge.heal(doc)
        forge.detect(result)
        msp = forge.to_dxf(result, doc).modelspace()
        ann_geom = [e for e in msp.query("LWPOLYLINE")
                    if e.dxf.layer == LAYER_ANNOTATION]
        # direttrici delle quote lineari + frecce dei leader
        self.assertGreater(len(ann_geom), 20)

    def test_008_annotation_layer_ignored_on_reload(self):
        # La geometria che forge scrive sul layer Annotation non deve essere
        # riletta come geometria di parte in un round-trip.
        from forge.adapters.dxf.adapter import _NON_STRUCTURAL_LAYERS
        self.assertIn(LAYER_ANNOTATION.lower(), _NON_STRUCTURAL_LAYERS)
        self.assertIn(TRASH_LAYER.lower(), _NON_STRUCTURAL_LAYERS)


# ---------------------------------------------------------------------------
# INSERT — esplosi di default: un blocco non deve far sparire la geometria
# ---------------------------------------------------------------------------

class TestWritebackInsertExplodedByDefault(unittest.TestCase):

    def test_001_block_geometry_survives_without_flag(self):
        # scritta.dxf è un solo INSERT che avvolge 93 LINE + 23 SPLINE (lettere).
        # Senza esplodere, load_dxf scartava tutto. Ora è il default.
        doc = forge.load_dxf(EXAMPLES_DIR / "scritta.dxf")
        self.assertGreater(len(doc.edges), 50)
        result = forge.heal(doc)
        self.assertEqual(result.part_count, 1)
        self.assertGreater(len(result.parts[0].inners), 6)


# ---------------------------------------------------------------------------
# Round-trip geometrico — la geometria SCRITTA deve coincidere col modello
# ---------------------------------------------------------------------------

class TestWritebackArcRoundTrip(unittest.TestCase):
    """
    Regressione archi: to_dxf() deve materializzare l'outer con la stessa
    area del modello. Prima del fix a arc_seg_to_bulge gli archi invertiti
    (loop orientato CCW → ccw=False) venivano scritti con il bulge dell'arco
    complementare, cioè "alla rovescia", falsando l'area di migliaia di mm².
    """

    ARC_EXAMPLES = [
        "archi_bastardi.dxf",
        "arco convesso.dxf",
        "maniglia.dxf",
        "flangia_scantonata.dxf",
        "rettangolo_raggiato.dxf",
    ]

    def _written_outer_area(self, msp):
        area = 0.0
        for e in msp:
            if not e.dxf.hasattr("layer") or e.dxf.layer != LAYER_OUTER:
                continue
            if e.dxftype() not in ("LWPOLYLINE", "POLYLINE", "CIRCLE"):
                continue
            poly = entity_to_polygon(e)
            if poly is not None:
                area += poly.area
        return area

    def test_outer_area_matches_model(self):
        for name in self.ARC_EXAMPLES:
            path = EXAMPLES_DIR / name
            if not path.exists():
                continue
            with self.subTest(example=name):
                result, msp = _pipeline(name, detect=True)
                model_area = sum(p.outer.polygon.area for p in result.parts)
                written_area = self._written_outer_area(msp)
                self.assertAlmostEqual(
                    written_area, model_area, delta=max(1.0, model_area * 1e-4),
                    msg=f"{name}: outer scritto {written_area:.3f} vs "
                        f"modello {model_area:.3f}",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
