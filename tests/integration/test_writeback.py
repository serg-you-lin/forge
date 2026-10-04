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
from forge.adapters.dxf.adapter import entity_to_polygon
from forge.adapters.dxf.layers import LAYER_OUTER, LAYER_INNER

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "data"


def _pipeline(name, *, name_roles=None):
    """heal → to_dxf. Ritorna (result, msp_out)."""
    doc = forge.load_dxf(EXAMPLES_DIR / name, role_rules=forge.name_rules(name_roles or {}))
    result = forge.heal(doc)
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
# CIRCLE grande → LAYER_INNER
# ---------------------------------------------------------------------------

class TestWritebackCircleInner(unittest.TestCase):

    def setUp(self):
        self.result, self.msp = _pipeline("rect_with_circle_inner.dxf")

    def test_001_circle_on_inner_layer(self):
        self.assertIn(LAYER_INNER, _layers_of(self.msp, "CIRCLE"))


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
        doc = forge.load_dxf(EXAMPLES_DIR / "rect_with_trash.dxf")
        result = forge.heal(doc)
        msp = forge.to_dxf(result, doc, include_trash=False).modelspace()
        trash = [e for e in msp
                 if e.dxf.hasattr("layer") and e.dxf.layer == TRASH_LAYER]
        self.assertEqual(len(trash), 0)

    def test_004_open_trash_not_closed(self):
        # Le tracce aperte non devono essere chiuse: una LWPOLYLINE trash
        # con flag closed falserebbe la forma. two_rects_with_bend ha una
        # bending line interna che il detector non promuove (endpoint a ~10 mm
        # dall'outer) → finisce in trash come traccia aperta.
        result, msp = _pipeline("two_rects_with_bend.dxf")
        trash_pl = [e for e in msp.query("LWPOLYLINE")
                    if e.dxf.layer == TRASH_LAYER]
        self.assertGreater(len(trash_pl), 0)
        for e in trash_pl:
            self.assertFalse(e.closed)

    def test_005_invalid_result_written_unless_refused(self):
        # Nessun contorno esterno chiuso (arc_open a tolleranza default: gap
        # arco/arco di ~0.26 mm > 0.05) → heal() invalida il risultato. Di
        # default to_dxf() lo scrive lo stesso (tutto in trash, D83); con
        # allow_invalid=False si rifiuta, come vuole chi consegna a una macchina.
        doc = forge.load_dxf(EXAMPLES_DIR / "arc_open.dxf")
        result = forge.heal(doc)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.cluster_count, 0)
        self.assertTrue(result.errors)

        msp = forge.to_dxf(result, doc).modelspace()
        trash = [e for e in msp if e.dxf.layer == TRASH_LAYER]
        self.assertEqual(len(trash), len(result.trash_entities))
        self.assertGreater(len(trash), 0)

        with self.assertRaises(ValueError):
            forge.to_dxf(result, doc, allow_invalid=False)
        with self.assertRaises(ValueError):
            forge.to_svg(result, allow_invalid=False)
        self.assertIn("<svg", forge.to_svg(result))


# ---------------------------------------------------------------------------
# Cluster E — linetype della sorgente sempre ripristinato in output. Le linee
# tratteggiate non devono uscire continue. Il colore invece non si tocca mai:
# resta quello del layer forge di destinazione (semantico per ruolo — verde
# outer, rosso trash, ... — rules/palette.py), mai quello della sorgente.
# ---------------------------------------------------------------------------

class TestWritebackStyle(unittest.TestCase):

    def _multifeature(self):
        name = "Multifeature.dxf"
        if not (EXAMPLES_DIR / name).exists():
            self.skipTest(name)
        return _pipeline(name, name_roles={"MARK": "engrave"})

    def test_001_trash_linetype_preserved(self):
        # 64+ LINE su "02___PRT_ALL_AXES" (assi dei fori) sono CENTER nella
        # sorgente e finiscono in trash: devono restare CENTER in output, non
        # ricadere sul BYLAYER continuo del layer Trash.
        _, msp = self._multifeature()
        trash = [e for e in msp
                 if e.dxf.hasattr("layer") and e.dxf.layer == TRASH_LAYER]
        self.assertTrue(any(e.dxf.linetype == "CENTER" for e in trash))

    def test_002_custom_linetype_registered_with_pattern(self):
        _, msp = self._multifeature()
        self.assertIn("CENTER", msp.doc.linetypes)
        lt = msp.doc.linetypes.get("CENTER")
        self.assertGreater(len(lt.simplified_line_pattern()), 1)

    def test_003_trash_color_stays_trash_layer_color(self):
        # Le stesse linee assiali portano un colore esplicito nella sorgente
        # (ACI 4/7/1, alcune anche con true_color): il trash non ripristina
        # mai il colore originale, solo il tratteggio. Il colore resta quello
        # del layer Trash (BYLAYER).
        _, msp = self._multifeature()
        trash = [e for e in msp
                 if e.dxf.hasattr("layer") and e.dxf.layer == TRASH_LAYER]
        self.assertTrue(trash)
        for e in trash:
            self.assertEqual(e.dxf.color, 256)
            self.assertFalse(e.dxf.hasattr("true_color"))

    def test_004_structural_color_stays_bylayer_despite_source_color(self):
        # outer/inner restano BYLAYER anche quando la sorgente aveva un
        # colore esplicito diverso: il colore è una decisione di dominio per
        # ruolo (rules/palette.py), non un attributo da riportare fedele.
        result, msp = _pipeline("rect_with_circle_hole.dxf")
        for e in msp.query("LWPOLYLINE"):
            if e.dxf.layer == LAYER_OUTER:
                self.assertEqual(e.dxf.color, 256)


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
        self.assertEqual(result.cluster_count, 1)
        self.assertGreater(len(result.clusters[0].inners), 6)


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
                result, msp = _pipeline(name)
                model_area = sum(p.outer.polygon.area for p in result.clusters)
                written_area = self._written_outer_area(msp)
                self.assertAlmostEqual(
                    written_area, model_area, delta=max(1.0, model_area * 1e-4),
                    msg=f"{name}: outer scritto {written_area:.3f} vs "
                        f"modello {model_area:.3f}",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
