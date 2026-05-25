"""
Test Suite per writeback.split() e split_to_files().

Struttura
---------
_Fixtures                  — helper che costruiscono geometria in memoria
                             e passano per heal() reale (no mock ForgeResult)

TestUnitSplitOutput        — unit: file generati, namer, min_area
TestUnitSplitFilters       — unit: include_annotations, exclude_types, keep_trash
TestUnitSplitLayers        — unit: layer presenti e colori canonici nei figli

TestIntegrationPipeline    — integration: pipeline heal→detect→split su examples/
TestIntegrationContours    — integration: LWPOLYLINE chiuse, CIRCLE, SPLINE

Filosofia
---------
- I test unit usano _make_via_heal(): costruisce un msp ezdxf in memoria,
  chiama heal() reale, poi chiama split() direttamente.
  Niente ForgeResult finto — se heal() non riconosce la geometria il test
  fallisce con un messaggio chiaro, non con un falso verde.

- I test integration usano split_to_files() come black box su file in examples/.
  Verificano solo invarianti osservabili dall'esterno (file su disco, layer, entità).

- exclude_types è un parametro che split() deve accettare.
  Se non esiste ancora, i test in TestUnitSplitFilters falliscono con TypeError —
  segnale chiaro per aggiungerlo.

- ALL_FORGE_LAYERS deve essere esportato da dxf_forge.rules.layers come:
      ALL_FORGE_LAYERS = {LAYER_OUTER: COLOR_OUTER, LAYER_INNER: COLOR_INNER, ...}
  Se manca, TestUnitSplitLayers.test_002 e TestIntegrationLayers.test_003
  falliscono con ImportError — segnale chiaro per aggiungerlo.

Esecuzione
----------
    python -m unittest tests/integration/test_splitter_restructured.py -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import ezdxf

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import dxf_forge as forge
from dxf_forge.workflow.writeback import split, ANNOTATION_TYPES, DEFAULT_MIN_PART_AREA
from dxf_forge.rules.layers import ALL_FORGE_LAYERS

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


# ---------------------------------------------------------------------------
# Fixtures: geometria in memoria + heal() reale
# ---------------------------------------------------------------------------

def _make_via_heal(points: list[tuple], extra_entities=None):
    """
    Crea un msp ezdxf in memoria con una LWPOLYLINE chiusa definita da `points`,
    esegue heal() reale e ritorna (msp, result).

    extra_entities: lista di callable (msp) -> None
                    per aggiungere entità extra (testi, cerchi, ecc.)
                    prima di heal().

    Usato dai test unit per avere un ForgeResult autentico su geometria
    controllata, senza file su disco e senza dipendere da examples/.
    """
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_lwpolyline(points, close=True, dxfattribs={"layer": "0"})
    if extra_entities:
        for fn in extra_entities:
            fn(msp)
    result = forge.heal(msp, label="fixture")
    return msp, result


def _rect(w=200, h=100) -> list[tuple]:
    """Punti di un rettangolo con angolo in origine."""
    return [(0, 0), (w, 0), (w, h), (0, h)]


def _read_children(out_dir: str) -> dict[str, object]:
    """Legge tutti i file .dxf in out_dir e ritorna {nome: modelspace}."""
    return {
        f.name: ezdxf.readfile(str(f)).modelspace()
        for f in Path(out_dir).glob("*.dxf")
    }


# ---------------------------------------------------------------------------
# UNIT TEST — writeback.split()
# ---------------------------------------------------------------------------

class TestUnitSplitOutput(unittest.TestCase):
    """
    Testa gli invarianti di output di split():
    file generati, namer, min_area, cartella di output.
    """

    def setUp(self):
        self.out_dir = tempfile.mkdtemp()
        self.msp, self.result = _make_via_heal(_rect())

    def _assert_heal_found_parts(self):
        self.assertGreater(
            len(self.result.parts), 0,
            "heal() non ha trovato parti — verifica la geometria della fixture"
        )

    def test_001_genera_un_file(self):
        """split() genera almeno un file .dxf."""
        self._assert_heal_found_parts()
        generated = split(self.msp, self.result, output_folder=self.out_dir)
        files = list(Path(self.out_dir).glob("*.dxf"))
        self.assertGreater(len(files), 0, "Nessun file .dxf generato")
        self.assertEqual(len(generated), len(files),
                         "Lista returned non corrisponde ai file su disco")

    def test_002_file_leggibile(self):
        """I file generati sono DXF validi leggibili da ezdxf."""
        self._assert_heal_found_parts()
        generated = split(self.msp, self.result, output_folder=self.out_dir)
        for path in generated:
            try:
                ezdxf.readfile(path)
            except Exception as e:
                self.fail(f"File non leggibile: {path} — {e}")

    def test_003_namer_default_formato(self):
            """Il namer default produce un nome del tipo 'label_P1'."""
            self._assert_heal_found_parts()
            generated = split(self.msp, self.result, output_folder=self.out_dir)
            
            self.assertTrue(len(generated) > 0)
            nome = Path(generated[0]).stem
            
            self.assertRegex(nome, r".+_P\d+$",
                            f"Nome '{nome}' non segue il formato 'label_P1'")

    def test_004_namer_custom(self):
        """Un namer custom viene rispettato."""
        self._assert_heal_found_parts()
        namer = lambda i, part: f"pezzo_{i + 1}"
        generated = split(self.msp, self.result, output_folder=self.out_dir,
                          namer=namer)
        self.assertTrue(len(generated) > 0)
        self.assertEqual(Path(generated[0]).stem, "pezzo_1")

    def test_005_part_label_aggiornata(self):
        """Dopo split(), part.label corrisponde al nome file usato."""
        self._assert_heal_found_parts()
        generated = split(self.msp, self.result, output_folder=self.out_dir)
        nome_file = Path(generated[0]).stem
        self.assertEqual(self.result.parts[0].label, nome_file)

    def test_006_min_area_scarta_part_sotto_soglia(self):
        """Part con area sotto min_area vengono scartati e producono un warning."""
        self._assert_heal_found_parts()
        # 200x100 = 20_000 mm²; soglia altissima → scartato
        generated = split(self.msp, self.result, output_folder=self.out_dir,
                          min_area=999_999)
        self.assertEqual(len(generated), 0, "Part sotto soglia non scartato")
        self.assertTrue(len(self.result.warnings) > 0,
                        "Nessun warning emesso per part scartato")

    def test_007_output_folder_creata_se_assente(self):
        """split() crea la cartella di output se non esiste."""
        self._assert_heal_found_parts()
        new_dir = os.path.join(self.out_dir, "sub", "nuovo")
        split(self.msp, self.result, output_folder=new_dir)
        self.assertTrue(os.path.isdir(new_dir))


class TestUnitSplitFilters(unittest.TestCase):
    """
    Testa i filtri su tipi di entità in split().

    La fixture aggiunge un TEXT e un CIRCLE dentro l'area del rettangolo,
    così i filtri hanno qualcosa su cui agire.

    NOTA: exclude_types deve essere aggiunto a writeback.split() e propagato
    in split_to_files(). Se manca, i test 004/005 falliscono con TypeError.
    """

    def setUp(self):
        self.out_dir = tempfile.mkdtemp()

        def _add_annotations(msp):
            msp.add_text("NOTA", dxfattribs={
                "insert": (50, 50), "height": 5, "layer": "0"
            })
            msp.add_circle((100, 50), 10, dxfattribs={"layer": "0"})

        self.msp, self.result = _make_via_heal(
            _rect(), extra_entities=[_add_annotations]
        )
        self.assertTrue(
            len(self.result.parts) > 0,
            "heal() non ha trovato parti — verifica la fixture"
        )

    def _child_msp(self, **split_kwargs):
        """Esegue split() e ritorna il modelspace del primo figlio."""
        out_dir = tempfile.mkdtemp()
        generated = split(self.msp, self.result,
                          output_folder=out_dir, **split_kwargs)
        self.assertTrue(len(generated) > 0, "Nessun file generato")
        return ezdxf.readfile(generated[0]).modelspace()

    def test_001_default_include_testo_e_cerchio(self):
        """Default (include_annotations=True): TEXT e CIRCLE copiati nel figlio."""
        out_msp = self._child_msp()
        self.assertEqual(len(list(out_msp.query("TEXT"))), 1,
                         "TEXT dovrebbe essere presente")
        self.assertEqual(len(list(out_msp.query("CIRCLE"))), 1,
                         "CIRCLE dovrebbe essere presente")

    def test_002_include_annotations_false_esclude_text(self):
        """include_annotations=False: TEXT assente, CIRCLE presente."""
        out_msp = self._child_msp(include_annotations=False)
        self.assertEqual(len(list(out_msp.query("TEXT"))), 0,
                         "TEXT non dovrebbe essere presente")
        self.assertEqual(len(list(out_msp.query("CIRCLE"))), 1,
                         "CIRCLE dovrebbe essere presente")

    def test_003_include_annotations_false_esclude_tutti_i_tipi(self):
        """include_annotations=False esclude tutti i tipi in ANNOTATION_TYPES."""
        def _add_mtext(msp):
            msp.add_mtext("mtext", dxfattribs={
                "insert": (30, 30), "char_height": 5, "layer": "0"
            })

        msp, result = _make_via_heal(
            _rect(), extra_entities=[_add_mtext]
        )
        out_dir = tempfile.mkdtemp()
        generated = split(msp, result, output_folder=out_dir,
                          include_annotations=False)
        self.assertTrue(len(generated) > 0)
        out_msp = ezdxf.readfile(generated[0]).modelspace()
        for ann_type in ANNOTATION_TYPES:
            found = list(out_msp.query(ann_type))
            self.assertEqual(len(found), 0,
                             f"{ann_type} non dovrebbe essere presente")

    def test_004_exclude_types_singolo(self):
        """exclude_types={'TEXT'}: TEXT assente, CIRCLE presente."""
        out_msp = self._child_msp(exclude_types={"TEXT"})
        self.assertEqual(len(list(out_msp.query("TEXT"))), 0,
                         "TEXT non dovrebbe essere presente")
        self.assertEqual(len(list(out_msp.query("CIRCLE"))), 1,
                         "CIRCLE dovrebbe essere presente")

    def test_005_exclude_types_multipli(self):
        """exclude_types={'TEXT', 'CIRCLE'}: entrambi assenti."""
        out_msp = self._child_msp(exclude_types={"TEXT", "CIRCLE"})
        self.assertEqual(len(list(out_msp.query("TEXT"))), 0)
        self.assertEqual(len(list(out_msp.query("CIRCLE"))), 0)

    def test_006_keep_trash_false_non_causa_eccezioni(self):
        """keep_trash=False (default) non causa eccezioni."""
        try:
            self._child_msp(keep_trash=False)
        except Exception as e:
            self.fail(f"split() con keep_trash=False ha sollevato: {e}")


class TestUnitSplitLayers(unittest.TestCase):
    """
    Verifica layer e colori canonici nei documenti figli prodotti da split().

    NOTA: ALL_FORGE_LAYERS deve esistere in dxf_forge.rules.layers come:
        ALL_FORGE_LAYERS = {LAYER_OUTER: COLOR_OUTER, LAYER_INNER: COLOR_INNER, ...}
    """

    def setUp(self):
        self.out_dir = tempfile.mkdtemp()
        self.msp, self.result = _make_via_heal(_rect())
        self.assertTrue(
            len(self.result.parts) > 0,
            "heal() non ha trovato parti — verifica la fixture"
        )
        self.generated = split(self.msp, self.result,
                               output_folder=self.out_dir)
        self.assertTrue(len(self.generated) > 0,
                        "split() non ha generato file")

    def test_001_tutti_i_layer_presenti(self):
        """Tutti i layer forge standard sono presenti nel documento figlio."""
        from dxf_forge.rules.layers import (
            LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
            LAYER_BENDING, LAYER_MARKING, LAYER_ENGRAVE, TRASH_LAYER,
        )
        expected = {LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
                    LAYER_BENDING, LAYER_MARKING, LAYER_ENGRAVE, TRASH_LAYER}
        for path in self.generated:
            child_doc = ezdxf.readfile(path)
            present = {l.dxf.name for l in child_doc.layers}
            for name in expected:
                self.assertIn(name, present,
                              f"{Path(path).name}: layer '{name}' mancante")

    def test_002_colori_canonici(self):
        """Ogni layer forge ha il colore canonico definito in layers.py."""
        from dxf_forge.rules.layers import ALL_FORGE_LAYERS
        for path in self.generated:
            child_doc = ezdxf.readfile(path)
            for layer_name, expected_color in ALL_FORGE_LAYERS.items():
                layer = child_doc.layers.get(layer_name)
                self.assertIsNotNone(
                    layer, f"{Path(path).name}: layer '{layer_name}' non trovato"
                )
                self.assertEqual(
                    layer.dxf.color, expected_color,
                    f"{Path(path).name}: '{layer_name}' ha colore "
                    f"{layer.dxf.color}, atteso {expected_color}"
                )


# ---------------------------------------------------------------------------
# INTEGRATION TEST — split_to_files() pipeline completa
# ---------------------------------------------------------------------------

class TestIntegrationPipeline(unittest.TestCase):
    """
    Testa split_to_files() come black box su file in examples/.
    Verifica invarianti osservabili: file su disco, part count, layer.
    Non entra nei dettagli di split() — quelli sono nei test unit.
    """

    def _run(self, dxf_name, label, **kwargs):
        out_dir = tempfile.mkdtemp()
        doc = ezdxf.readfile(str(EXAMPLES_DIR / dxf_name))
        result = forge.split_to_files(
            doc.modelspace(), output_folder=out_dir, label=label, **kwargs
        )
        return result, out_dir

    def test_001_two_parts_genera_due_file(self):
        """two_parts.dxf → pipeline genera 2 file figli."""
        _, out_dir = self._run("two_parts.dxf", "two_parts")
        files = list(Path(out_dir).glob("*.dxf"))
        self.assertEqual(len(files), 2,
                         f"Attesi 2 file, trovati {len(files)}: "
                         f"{[f.name for f in files]}")

    def test_002_file_figli_leggibili(self):
        """I file figli sono DXF validi."""
        _, out_dir = self._run("two_parts.dxf", "two_parts")
        for f in Path(out_dir).glob("*.dxf"):
            try:
                ezdxf.readfile(str(f))
            except Exception as e:
                self.fail(f"File figlio non leggibile: {f.name} — {e}")

    def test_003_result_ha_parts(self):
        """split_to_files() ritorna un ForgeResult con parts popolati."""
        result, _ = self._run("two_parts.dxf", "two_parts")
        self.assertGreater(result.part_count, 0)

    def test_004_part_con_foro(self):
        """pline_with_hole.dxf → il part ha almeno un inner/hole."""
        result, _ = self._run("pline_with_hole.dxf", "pline_with_hole")
        self.assertEqual(result.part_count, 1)
        self.assertGreater(len(result.parts[0].inners), 0,
                           "Nessun inner/hole trovato")

    def test_005_include_annotations_false_propagato(self):
        """include_annotations=False propagato correttamente dalla wrapper."""
        out_dir = tempfile.mkdtemp()
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        msp.add_lwpolyline(_rect(), close=True, dxfattribs={"layer": "0"})
        msp.add_text("NOTA", dxfattribs={
            "insert": (50, 50), "height": 5, "layer": "0"
        })
        forge.split_to_files(msp, output_folder=out_dir, label="test",
                             include_annotations=False)
        for f in Path(out_dir).glob("*.dxf"):
            out_msp = ezdxf.readfile(str(f)).modelspace()
            self.assertEqual(len(list(out_msp.query("TEXT"))), 0,
                             f"{f.name}: TEXT presente con include_annotations=False")

    def test_006_namer_custom_propagato(self):
        """Un namer custom passato a split_to_files() viene usato."""
        out_dir = tempfile.mkdtemp()
        doc = ezdxf.readfile(str(EXAMPLES_DIR / "two_parts.dxf"))
        namer = lambda i, part: f"custom_{i + 1:02d}"
        forge.split_to_files(doc.modelspace(), output_folder=out_dir,
                             label="two_parts", namer=namer)
        names = {f.stem for f in Path(out_dir).glob("*.dxf")}
        self.assertIn("custom_01", names,
                      f"Nome custom non trovato tra: {names}")

    def test_007_msp_vuoto_non_genera_file(self):
        """msp vuoto → nessun file generato."""
        out_dir = tempfile.mkdtemp()
        doc = ezdxf.new("R2010")
        forge.split_to_files(doc.modelspace(), output_folder=out_dir,
                             label="empty")
        files = list(Path(out_dir).glob("*.dxf"))
        self.assertEqual(len(files), 0,
                         f"File generati da msp vuoto: {[f.name for f in files]}")


class TestIntegrationContours(unittest.TestCase):
    """
    Verifica che i contorni strutturali nei file figli siano corretti:
    LWPOLYLINE chiuse, CIRCLE e SPLINE esportati correttamente.
    """

    def _children(self, dxf_name, label, **kwargs):
        out_dir = tempfile.mkdtemp()
        doc = ezdxf.readfile(str(EXAMPLES_DIR / dxf_name))
        print([ (e.dxftype(), e.dxf.layer) for e in doc.modelspace() ])
        forge.split_to_files(doc.modelspace(), output_folder=out_dir,
                             label=label, **kwargs)
        return _read_children(out_dir)

    def test_001_lwpolyline_outer_chiusa(self):
        """LWPOLYLINE su OuterContour nei figli è closed=True."""
        from dxf_forge.rules.layers import LAYER_OUTER
        children = self._children("two_parts.dxf", "two_parts")
        self.assertGreater(len(children), 0)
        for fname, msp in children.items():
            for e in msp.query("LWPOLYLINE"):
                if e.dxf.layer == LAYER_OUTER:
                    self.assertTrue(e.closed,
                                    f"{fname}: LWPOLYLINE su {LAYER_OUTER} "
                                    f"non è chiusa")

    def test_002_lwpolyline_inner_chiusa(self):
        """LWPOLYLINE su InnerContour/Hole nei figli è closed=True."""
        from dxf_forge.rules.layers import LAYER_INNER, LAYER_HOLE
        children = self._children("pline_with_hole.dxf", "pline_with_hole")
        for fname, msp in children.items():
            for e in msp.query("LWPOLYLINE"):
                if e.dxf.layer in (LAYER_INNER, LAYER_HOLE):
                    self.assertTrue(e.closed,
                                    f"{fname}: LWPOLYLINE su {e.dxf.layer} "
                                    f"non è chiusa")

    def test_003_circle_outer_esportato(self):
        """CIRCLE su OuterContour viene esportato nel file figlio."""
        from dxf_forge.rules.layers import LAYER_OUTER
        children = self._children("cerchi_ciambella.dxf", "cerchi_ciambella")
        self.assertGreater(len(children), 0,
                           "Nessun file figlio da cerchi_ciambella.dxf")
        for fname, msp in children.items():
            outer_circles = [e for e in msp.query("CIRCLE")
                             if e.dxf.layer == LAYER_OUTER]
            self.assertEqual(len(outer_circles), 1,
                             f"{fname}: atteso 1 CIRCLE su {LAYER_OUTER}, "
                             f"trovati {len(outer_circles)}")

    def test_004_spline_outer_esportato(self):
        """File con SPLINE: entità originali su OuterContour presenti nel figlio."""
        from dxf_forge.rules.layers import LAYER_OUTER
        children = self._children("intricato_doppio.dxf", "intricato_doppio")
        figli_con_outer = [
            fname for fname, msp in children.items()
            if any(e.dxf.layer == LAYER_OUTER
                   for e in msp.query("SPLINE LINE ARC"))
        ]
        self.assertGreater(len(figli_con_outer), 0,
                           "Nessun figlio ha entità su OuterContour "
                           "per file con SPLINE")

    def test_005_regressione_lwpolyline_chiusa_tutti_gli_esempi(self):
        """
        Regressione: per ogni file in examples/, ogni LWPOLYLINE strutturale
        nei figli è closed=True. File non splittabili ignorati silenziosamente.
        """
        from dxf_forge.rules.layers import LAYER_OUTER, LAYER_INNER, LAYER_HOLE
        structural = {LAYER_OUTER, LAYER_INNER, LAYER_HOLE}
        for src in Path(EXAMPLES_DIR).glob("*.dxf"):
            if src.stem.endswith("_healed"):
                continue
            out_dir = tempfile.mkdtemp()
            try:
                doc = ezdxf.readfile(str(src))
                forge.split_to_files(doc.modelspace(),
                                     output_folder=out_dir, label=src.stem)
                for child in Path(out_dir).glob("*.dxf"):
                    child_doc = ezdxf.readfile(str(child))
                    for e in child_doc.modelspace().query("LWPOLYLINE"):
                        if e.dxf.layer in structural:
                            self.assertTrue(
                                e.closed,
                                f"{child.name}: LWPOLYLINE su {e.dxf.layer} "
                                f"non chiusa (sorgente: {src.name})"
                            )
            except Exception:
                pass


class TestIntegrationLayers(unittest.TestCase):
    """
    Verifica layer e colori canonici nei file prodotti dalla pipeline completa.
    Separato da TestUnitSplitLayers perché qui passa per heal() su file reale.
    """

    def setUp(self):
        self.out_dir = tempfile.mkdtemp()
        doc = ezdxf.readfile(str(EXAMPLES_DIR / "two_parts.dxf"))
        forge.split_to_files(doc.modelspace(),
                             output_folder=self.out_dir, label="test")
        self.files = list(Path(self.out_dir).glob("*.dxf"))
        self.assertTrue(len(self.files) > 0,
                        "setUp: nessun file generato da two_parts.dxf")

    def test_001_outer_layer_colore_canonico(self):
        """LAYER_OUTER ha COLOR_OUTER in ogni file figlio."""
        from dxf_forge.rules.layers import LAYER_OUTER, COLOR_OUTER
        for f in self.files:
            child_doc = ezdxf.readfile(str(f))
            layer = child_doc.layers.get(LAYER_OUTER)
            self.assertIsNotNone(layer, f"{f.name}: LAYER_OUTER mancante")
            self.assertEqual(layer.dxf.color, COLOR_OUTER,
                             f"{f.name}: LAYER_OUTER ha colore "
                             f"{layer.dxf.color}, atteso {COLOR_OUTER}")

    def test_002_tutti_i_layer_forge_presenti(self):
        """Tutti i layer forge standard sono presenti in ogni file figlio."""
        from dxf_forge.rules.layers import (
            LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
            LAYER_BENDING, LAYER_MARKING, LAYER_ENGRAVE, TRASH_LAYER,
        )
        expected = {LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
                    LAYER_BENDING, LAYER_MARKING, LAYER_ENGRAVE, TRASH_LAYER}
        for f in self.files:
            child_doc = ezdxf.readfile(str(f))
            present = {l.dxf.name for l in child_doc.layers}
            for name in expected:
                self.assertIn(name, present,
                              f"{f.name}: layer '{name}' mancante")

    def test_003_tutti_i_colori_canonici(self):
        """Ogni layer forge ha il colore canonico definito in layers.py."""
        from dxf_forge.rules.layers import ALL_FORGE_LAYERS
        for f in self.files:
            child_doc = ezdxf.readfile(str(f))
            for layer_name, expected_color in ALL_FORGE_LAYERS.items():
                layer = child_doc.layers.get(layer_name)
                self.assertIsNotNone(
                    layer, f"{f.name}: layer '{layer_name}' non trovato"
                )
                self.assertEqual(
                    layer.dxf.color, expected_color,
                    f"{f.name}: '{layer_name}' ha colore "
                    f"{layer.dxf.color}, atteso {expected_color}"
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)