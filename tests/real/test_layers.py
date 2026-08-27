
"""
test_layers.py
--------------
Verifica che dopo write() ogni layer forge abbia il colore canonico
nella tabella layer del documento, e che ogni entità abbia color=256 (BYLAYER).

File di test: tests/examples/Multifeature.dxf
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

import ezdxf

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.adapters.dxf.layers import ALL_FORGE_LAYERS, TRASH_LAYER
from forge.adapters.dxf.layers import LAYER_OUTER, ROLE_TO_LAYER, LAYER_BENDING
from forge.model.role import ContourRole

EXAMPLES_DIR = project_root / "tests" / "examples"
MULTIFEATURE = EXAMPLES_DIR / "Multifeature.dxf"

SPECIAL_LAYERS = {
    "MARK":      "engrave",
    "Filettati": "threaded_hole",
    "Svasati":   "countersink",
    "Piega":     "bending",
}


def _run_pipeline(dxf_path: Path) -> tuple:
    """Esegue heal → detect → to_dxf e restituisce (source_doc, doc_out, result).

    `doc_out` è il documento materializzato da to_dxf(): è lì che vivono i
    layer forge e le entità routate. `source_doc` serve solo a split().
    """
    source_doc = forge.load_dxf(
        dxf_path, explode_inserts=True, label_map=SPECIAL_LAYERS,
    )
    result = forge.heal(
        source_doc,
        tolerance=1,
        label=dxf_path.stem,
        source_file=dxf_path.name,
    )
    forge.detect(result, bending_tolerance=0.2)
    doc_out = forge.to_dxf(result, source_doc)

    return source_doc, doc_out, result


class TestLayerTable(unittest.TestCase):
    """Il colore canonico vive nella tabella layer del documento."""

    @classmethod
    def setUpClass(cls):
        if not MULTIFEATURE.exists():
            raise unittest.SkipTest(f"File non trovato: {MULTIFEATURE}")
        cls.src_doc, cls.doc, cls.result = _run_pipeline(MULTIFEATURE)
        cls.msp = cls.doc.modelspace()

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
        cls.src_doc, cls.doc, cls.result = _run_pipeline(MULTIFEATURE)
        cls.msp = cls.doc.modelspace()
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
                violazioni.append(f"{entity.dxftype()} su '{entity.dxf.layer}' ha color={color}")

        self.assertEqual(
            violazioni,
            [],
            msg="Entità con colore esplicito (non BYLAYER):\n" + "\n".join(violazioni),
        )

    def test_outer_contour_su_layer_corretto(self):
        """Il contorno esterno di ogni part deve essere su OuterContour."""
        for i, part in enumerate(self.result.parts):
            with self.subTest(part=i):
                self.assertEqual(
                    ROLE_TO_LAYER.get(part.outer.role),
                    LAYER_OUTER,
                    msg=f"Part {i}: outer.role atteso 'outer', trovato '{part.outer.role}'",
                )

    def test_holes_su_layer_corretto(self):
        """I fori devono avere un role foro-compatibile (hole, inner, threaded_hole, countersink)."""
        role_fori_validi = {ContourRole.HOLE, ContourRole.INNER, ContourRole.THREADED_HOLE, ContourRole.COUNTERSINK}
        for i, part in enumerate(self.result.parts):
            for j, hole in enumerate(part.holes):
                with self.subTest(part=i, hole=j):
                    self.assertIn(
                        hole.role,
                        role_fori_validi,
                        msg=f"Part {i} hole {j}: role '{hole.role}' non valido per un foro",
                    )


class TestLayerSplit(unittest.TestCase):
    """Dopo split() i file figli devono avere la stessa struttura layer."""

    @classmethod
    def setUpClass(cls):
        if not MULTIFEATURE.exists():
            raise unittest.SkipTest(f"File non trovato: {MULTIFEATURE}")
        
        cls.src_doc, cls.doc, cls.result = _run_pipeline(MULTIFEATURE)
        cls.msp = cls.doc.modelspace()
        cls.output_dir = tempfile.mkdtemp()
        drawings = forge.split(cls.result, cls.src_doc)
        cls.generated = []
        for i, drawing in enumerate(drawings):
            path = str(Path(cls.output_dir) / f"child_{i:03d}.dxf")
            drawing.saveas(path)
            cls.generated.append(path)

    def test_file_figli_generati(self):
        self.assertGreater(len(self.generated), 0, "split() non ha generato file")

    def test_layer_forge_nei_figli(self):
        """Ogni file figlio deve avere i layer forge con i colori canonici."""
        for path in self.generated:
            doc_out = ezdxf.readfile(path)
            for name, expected_color in ALL_FORGE_LAYERS.items():
                # Un figlio potrebbe non avere tutti i layer se quella feature non c'è
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
            msp_out = ezdxf.readfile(path).modelspace()
            violazioni = []

            for entity in msp_out:
                if not entity.dxf.hasattr("layer"):
                    continue
                if entity.dxf.layer.upper() not in forge_layer_names:
                    continue
                
                color = entity.dxf.color if entity.dxf.hasattr("color") else 256
                if color != 256:
                    violazioni.append(f"{entity.dxftype()} su '{entity.dxf.layer}' ha color={color}")
            
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

        src_doc = forge.load_dxf(cls.dxf_path, explode_inserts=True)
        cls.result = forge.heal(
            src_doc,
            tolerance=1,
            label=cls.dxf_path.stem,
            source_file=cls.dxf_path.name,
        )
        forge.detect(cls.result)
        cls.msp = forge.to_dxf(cls.result, src_doc).modelspace()

    def test_un_solo_part(self):
        self.assertEqual(self.result.part_count, 1, "Atteso 1 part")

    def test_outer_su_layer_corretto(self):
        part = self.result.parts[0]
        self.assertEqual(ROLE_TO_LAYER.get(part.outer.role), LAYER_OUTER)

    def test_due_entita_su_bending(self):
        bending = [e for e in self.msp if e.dxf.hasattr("layer") and e.dxf.layer == LAYER_BENDING]
        self.assertEqual(len(bending), 2, f"Attese 2 entità su Bending, trovate {len(bending)}")

    def test_linee_spurie_in_trash(self):
        """Le LINE non riconosciute come piega non vengono perse: restano nel
        modello come trash_entities (non più spostate su un layer 'Trash').
        Con 2 sole pieghe reali riconosciute, il resto finisce in trash."""
        self.assertEqual(len(self.result.parts[0].bending_lines), 2)
        self.assertGreaterEqual(
            len(self.result.trash_entities), 4,
            f"trash_entities inatteso: {len(self.result.trash_entities)}",
        )

    def test_nessuna_line_spuria_su_bending(self):
        """Ogni LINE materializzata su Bending deve corrispondere, per coordinate,
        a una bending line del modello — nessuna LINE bastarda."""
        part = self.result.parts[0]

        def _key(a, b):
            pa, pb = sorted([(round(a[0], 3), round(a[1], 3)),
                             (round(b[0], 3), round(b[1], 3))])
            return (pa, pb)

        model_keys = set()
        for bl in part.bending_lines:
            if bl.geometry is None:
                continue
            coords = list(bl.geometry.coords)
            model_keys.add(_key(coords[0], coords[-1]))

        spurie = []
        for e in self.msp:
            if e.dxftype() != "LINE":
                continue
            if not e.dxf.hasattr("layer") or e.dxf.layer != LAYER_BENDING:
                continue
            k = _key((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y))
            if k not in model_keys:
                spurie.append(k)

        self.assertEqual(spurie, [], msg=f"LINE su Bending non nel modello: {spurie}")


class TestGambaTavoloSplit(unittest.TestCase):
    """
    gamba_tavolo.dxf
    Dopo split_to_files() tutti i figli devono avere l'outer su OuterContour.
    """

    @classmethod
    def setUpClass(cls):
        cls.dxf_path = EXAMPLES_DIR / "gamba_tavolo.dxf"
        if not cls.dxf_path.exists():
            raise unittest.SkipTest(f"File non trovato: {cls.dxf_path}")
        
        src_doc = forge.load_dxf(cls.dxf_path, explode_inserts=True)
        cls.output_dir = tempfile.mkdtemp()
        cls.result = forge.split_to_files(
            src_doc,
            output_folder=cls.output_dir,
            label=cls.dxf_path.stem,
            source_file=cls.dxf_path.name,
            include_annotations=True,
        )
        cls.generated = [str(p) for p in Path(cls.output_dir).glob("*.dxf")]

    def test_quattro_figli_generati(self):
        self.assertEqual(len(self.generated), 4, f"Attesi 4 file figli, trovati {len(self.generated)}")

    def test_tutti_i_figli_hanno_outer_su_layer_corretto(self):
        """Ogni figlio deve avere almeno una LWPOLYLINE su OuterContour."""
        for path in self.generated:
            msp_out = ezdxf.readfile(path).modelspace()
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
            msp_out = ezdxf.readfile(path).modelspace()
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
                    msg=f"{Path(path).name}: LWPOLYLINE su layer non-forge: " + ", ".join(e.dxf.layer for e in spuri),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)