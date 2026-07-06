"""
test_layers.py
--------------
Verifica che dopo write() ogni layer forge abbia il colore canonico
nella tabella layer del documento, e che ogni entità abbia color=256 (BYLAYER).

File di test: tests/examples/Multifeature.dxf
"""

import unittest
import sys
from pathlib import Path

import ezdxf

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.rules.layers import ALL_FORGE_LAYERS, TRASH_LAYER

EXAMPLES_DIR   = project_root / "tests" / "examples"
MULTIFEATURE   = EXAMPLES_DIR / "Multifeature.dxf"

SPECIAL_LAYERS = {
    "MARK":      "engrave",
    "Filettati": "threaded_hole",
    "Svasati":   "countersink",
    "Piega":     "bending",
}


def _run_pipeline(dxf_path: Path):
    """Esegue heal → detect → write e restituisce (doc, msp, result)."""
    doc = ezdxf.readfile(dxf_path)
    if doc.dxfversion < "AC1015":
        doc = forge.upgrade_to_r2010(doc)
    msp = doc.modelspace()

    result = forge.heal(
        msp,
        tolerance=1,
        explode_inserts=True,
        special_layers=SPECIAL_LAYERS,
        label=dxf_path.stem,
        source_file=dxf_path.name,
    )
    forge.detect(result, msp, bending_tolerance=0.2)
    forge.write(msp, result)

    return doc, msp, result


class TestLayerTable(unittest.TestCase):
    """Il colore canonico vive nella tabella layer del documento."""

    @classmethod
    def setUpClass(cls):
        if not MULTIFEATURE.exists():
            raise unittest.SkipTest(f"File non trovato: {MULTIFEATURE}")
        cls.doc, cls.msp, cls.result = _run_pipeline(MULTIFEATURE)

    def test_tutti_i_layer_forge_presenti(self):
        """Ogni layer forge deve esistere nella tabella layer del doc."""
        for name in ALL_FORGE_LAYERS:
            with self.subTest(layer=name):
                self.assertIn(
                    name,
                    self.doc.layers,
                    msg=f"Layer '{name}' assente dalla tabella layer",
                )

    def test_colori_canonici_nella_tabella(self):
        """Il colore di ogni layer forge nella tabella deve corrispondere ad ALL_FORGE_LAYERS."""
        for name, expected_color in ALL_FORGE_LAYERS.items():
            with self.subTest(layer=name):
                if name not in self.doc.layers:
                    self.skipTest(f"Layer '{name}' assente — coperto da test_tutti_i_layer_forge_presenti")
                actual_color = self.doc.layers.get(name).color
                self.assertEqual(
                    actual_color,
                    expected_color,
                    msg=f"Layer '{name}': colore atteso {expected_color}, trovato {actual_color}",
                )


class TestEntitaBylayer(unittest.TestCase):
    """Ogni entità forge deve avere color=256 (BYLAYER)."""

    @classmethod
    def setUpClass(cls):
        if not MULTIFEATURE.exists():
            raise unittest.SkipTest(f"File non trovato: {MULTIFEATURE}")
        cls.doc, cls.msp, cls.result = _run_pipeline(MULTIFEATURE)
        cls.forge_layer_names = {name.upper() for name in ALL_FORGE_LAYERS}

    def test_entita_su_layer_forge_hanno_bylayer(self):
        """
        Tutte le entità posizionate su un layer forge devono avere color=256.
        Le entità su layer non-forge (layer originali del file) vengono ignorate.
        """
        violazioni = []
        for entity in self.msp:
            if not entity.dxf.hasattr("layer"):
                continue
            if entity.dxf.layer.upper() not in self.forge_layer_names:
                continue
            color = entity.dxf.color if entity.dxf.hasattr("color") else 256
            if color != 256:
                violazioni.append(
                    f"{entity.dxftype()} su '{entity.dxf.layer}' ha color={color}"
                )

        self.assertEqual(
            violazioni,
            [],
            msg="Entità con colore esplicito (non BYLAYER):\n" + "\n".join(violazioni),
        )

    def test_outer_contour_su_layer_corretto(self):
        """Il contorno esterno di ogni part deve essere su OuterContour."""
        from forge.rules.layers import LAYER_OUTER
        for i, part in enumerate(self.result.parts):
            with self.subTest(part=i):
                self.assertEqual(
                    part.outer.layer,
                    LAYER_OUTER,
                    msg=f"Part {i}: outer.layer atteso '{LAYER_OUTER}', trovato '{part.outer.layer}'",
                )

    def test_holes_su_layer_corretto(self):
        """I fori devono essere su Hole o InnerContour (mai su layer non-forge)."""
        from forge.rules.layers import LAYER_HOLE, LAYER_INNER
        layer_fori_validi = {LAYER_HOLE, LAYER_INNER}
        for i, part in enumerate(self.result.parts):
            for j, hole in enumerate(part.holes):
                with self.subTest(part=i, hole=j):
                    self.assertIn(
                        hole.layer,
                        layer_fori_validi,
                        msg=f"Part {i} hole {j}: layer '{hole.layer}' non valido per un foro",
                    )


class TestLayerSplit(unittest.TestCase):
    """Dopo split() i file figli devono avere la stessa struttura layer."""

    @classmethod
    def setUpClass(cls):
        if not MULTIFEATURE.exists():
            raise unittest.SkipTest(f"File non trovato: {MULTIFEATURE}")
        import tempfile, os
        cls.doc, cls.msp, cls.result = _run_pipeline(MULTIFEATURE)
        cls.output_dir = tempfile.mkdtemp()
        cls.generated = forge.split(cls.msp, cls.result, cls.output_dir)

    def test_file_figli_generati(self):
        self.assertGreater(len(self.generated), 0, "split() non ha generato file")

    def test_layer_forge_nei_figli(self):
        """Ogni file figlio deve avere i layer forge con i colori canonici."""
        for path in self.generated:
            doc_out = ezdxf.readfile(path)
            for name, expected_color in ALL_FORGE_LAYERS.items():
                # un figlio potrebbe non avere tutti i layer se quella feature non c'è
                if name not in doc_out.layers:
                    continue
                with self.subTest(file=Path(path).name, layer=name):
                    actual_color = doc_out.layers.get(name).color
                    self.assertEqual(
                        actual_color,
                        expected_color,
                        msg=f"{Path(path).name} — layer '{name}': atteso {expected_color}, trovato {actual_color}",
                    )

    def test_entita_bylayer_nei_figli(self):
        """Nei file figli le entità forge devono avere color=256."""
        forge_layer_names = {name.upper() for name in ALL_FORGE_LAYERS}
        for path in self.generated:
            doc_out  = ezdxf.readfile(path)
            msp_out  = doc_out.modelspace()
            violazioni = []
            for entity in msp_out:
                if not entity.dxf.hasattr("layer"):
                    continue
                if entity.dxf.layer.upper() not in forge_layer_names:
                    continue
                color = entity.dxf.color if entity.dxf.hasattr("color") else 256
                if color != 256:
                    violazioni.append(
                        f"{entity.dxftype()} su '{entity.dxf.layer}' ha color={color}"
                    )
            with self.subTest(file=Path(path).name):
                self.assertEqual(
                    violazioni,
                    [],
                    msg="Entità non BYLAYER in " + Path(path).name + ":\n" + "\n".join(violazioni),
                )


class TestLineetteBastarde(unittest.TestCase):
    """
    6200012964_lineette_bastarde.dxf
    Dopo heal() le 4 LINE spurie devono finire su Trash, non su Bending.
    Attesi: 1 outer, 2 entità su Bending, 4 entità su Trash.
    """

    @classmethod
    def setUpClass(cls):
        cls.dxf_path = EXAMPLES_DIR / "6200012964_lineette_bastarde.dxf"
        if not cls.dxf_path.exists():
            raise unittest.SkipTest(f"File non trovato: {cls.dxf_path}")
        doc = ezdxf.readfile(cls.dxf_path)
        if doc.dxfversion < "AC1015":
            doc = forge.upgrade_to_r2010(doc)
        cls.msp = doc.modelspace()
        cls.result = forge.heal(
            cls.msp,
            tolerance=1,
            explode_inserts=True,
            label=cls.dxf_path.stem,
            source_file=cls.dxf_path.name,
        )
        forge.detect(cls.result, cls.msp)
        forge.write(cls.msp, cls.result)

    def test_un_solo_part(self):
        self.assertEqual(self.result.part_count, 1, "Atteso 1 part")

    def test_outer_su_layer_corretto(self):
        from forge.rules.layers import LAYER_OUTER
        part = self.result.parts[0]
        self.assertEqual(part.outer.layer, LAYER_OUTER)

    def test_due_entita_su_bending(self):
        from forge.rules.layers import LAYER_BENDING
        bending = [e for e in self.msp if e.dxf.hasattr("layer") and e.dxf.layer == LAYER_BENDING]
        self.assertEqual(len(bending), 2, f"Attese 2 entità su Bending, trovate {len(bending)}")

    def test_quattro_entita_su_trash(self):
        from forge.rules.layers import TRASH_LAYER
        trash = [e for e in self.msp if e.dxf.hasattr("layer") and e.dxf.layer == TRASH_LAYER]
        self.assertEqual(len(trash), 4, f"Attese 4 entità su Trash, trovate {len(trash)}")

    def test_nessuna_line_su_bending(self):
        """Nessuna LINE deve finire su Bending se non è in bend_line_ids."""
        from forge.rules.layers import LAYER_BENDING
        part = self.result.parts[0]
        bend_ids = part.geometry_hints.bend_line_ids
        linee_bastarde = [
            e for e in self.msp
            if e.dxftype() == "LINE"
            and e.dxf.hasattr("layer")
            and e.dxf.layer == LAYER_BENDING
            and id(e) not in bend_ids
        ]
        self.assertEqual(
            linee_bastarde,
            [],
            msg=f"{len(linee_bastarde)} LINE su Bending non presenti in bend_line_ids",
        )


class TestGambaTavoloSplit(unittest.TestCase):
    """
    gamba_tavolo.dxf
    Dopo split_to_files() tutti i figli devono avere l'outer su OuterContour.
    """

    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.dxf_path = EXAMPLES_DIR / "gamba_tavolo.dxf"
        if not cls.dxf_path.exists():
            raise unittest.SkipTest(f"File non trovato: {cls.dxf_path}")
        doc = ezdxf.readfile(cls.dxf_path)
        if doc.dxfversion < "AC1015":
            doc = forge.upgrade_to_r2010(doc)
        cls.msp = doc.modelspace()
        cls.output_dir = tempfile.mkdtemp()
        cls.result = forge.split_to_files(
            cls.msp,
            output_folder=cls.output_dir,
            explode_inserts=True,
            label=cls.dxf_path.stem,
            source_file=cls.dxf_path.name,
            include_annotations=True,
        )
        cls.generated = [
            str(p) for p in Path(cls.output_dir).glob("*.dxf")
        ]

    def test_quattro_figli_generati(self):
        self.assertEqual(len(self.generated), 4, f"Attesi 4 file figli, trovati {len(self.generated)}")

    def test_tutti_i_figli_hanno_outer_su_layer_corretto(self):
        """Ogni figlio deve avere almeno una LWPOLYLINE su OuterContour."""
        from forge.rules.layers import LAYER_OUTER
        for path in self.generated:
            doc_out = ezdxf.readfile(path)
            msp_out = doc_out.modelspace()
            outer_entities = [
                e for e in msp_out
                if e.dxf.hasattr("layer") and e.dxf.layer == LAYER_OUTER
            ]
            with self.subTest(file=Path(path).name):
                self.assertGreater(
                    len(outer_entities),
                    0,
                    msg=f"{Path(path).name}: nessuna entità su '{LAYER_OUTER}'",
                )

    def test_nessun_outer_su_layer_originale(self):
        """Nessun figlio deve avere LWPOLYLINE su layer non-forge come contorno esterno."""
        forge_layer_names = {name.upper() for name in ALL_FORGE_LAYERS}
        for path in self.generated:
            doc_out = ezdxf.readfile(path)
            msp_out = doc_out.modelspace()
            spuri = [
                e for e in msp_out
                if e.dxftype() == "LWPOLYLINE"
                and e.dxf.hasattr("layer")
                and e.dxf.layer.upper() not in forge_layer_names
            ]
            with self.subTest(file=Path(path).name):
                self.assertEqual(
                    spuri,
                    [],
                    msg=f"{Path(path).name}: LWPOLYLINE su layer non-forge: "
                        + ", ".join(e.dxf.layer for e in spuri),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)