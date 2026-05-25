

"""
test_golden_split.py
--------------------
Test di regressione geometrica per i file prodotti dallo splitting.

Per ogni golden in tests/examples/multipli_golden/golden/:
  1. Riprocessa il DXF padre con la pipeline completa (heal → detect → write → split)
     in una cartella temporanea.
  2. Riprocessa il figlio corrispondente (heal → detect → write).
  3. Confronta area, perimetri e geometria WKT contro il golden salvato.

Tolleranze:
    TOL_AREA      = 0.1  mm²
    TOL_PERIMETER = 0.5  mm
    TOL_SHAPE     = 1.0  mm²  (symmetric difference Shapely)

Genera prima i golden con:
    python generate_golden_split.py

Lancia i test con:
    python -m pytest tests/test_golden_split.py -v
    oppure
    python tests/test_golden_split.py
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import ezdxf
from shapely import wkt as shapely_wkt

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import dxf_forge as forge

MULTIPLI_DIR = project_root / "tests" / "examples" / "golden_multipli"
GOLDEN_DIR   = MULTIPLI_DIR / "golden"

TOL_AREA      = 0.1
TOL_PERIMETER = 0.5
TOL_SHAPE     = 1.0
DEFAULT_TOLERANCE = 0.5


def _load_config(dxf_path: Path) -> dict:
    config_path = MULTIPLI_DIR / "config" / f"{dxf_path.stem}.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def _run_pipeline_and_get_child(parent_path: Path, tolerance: float, child_stem: str) -> Path | None:
    """
    Esegue la pipeline completa sul padre in una cartella temporanea e
    restituisce il Path del figlio con lo stem cercato (o None se non trovato).

    La cartella temporanea è gestita dal chiamante tramite il context manager
    che viene passato indirettamente: qui creiamo una tmp locale perché il
    test deve poter leggere il file figlio prima che la cartella venga rimossa.
    Usiamo quindi una tmp che sopravvive per tutta la durata del test method.
    """
    raise NotImplementedError(
        "_run_pipeline_and_get_child non deve essere chiamata direttamente: "
        "usa _SplitContext come context manager nel test."
    )


class _SplitContext:
    """
    Context manager che esegue la pipeline sul padre e mette a disposizione
    la cartella di output per tutta la durata del blocco `with`.

    Esempio:
        with _SplitContext(parent_path, tolerance) as output_folder:
            child_path = output_folder / "la_104_1.dxf"
    """

    def __init__(self, parent_path: Path, tolerance: float):
        self._parent_path = parent_path
        self._tolerance   = tolerance
        self._tmpdir      = None

    def __enter__(self) -> Path:
        self._tmpdir = tempfile.TemporaryDirectory()
        output_folder = Path(self._tmpdir.name)

        doc = ezdxf.readfile(self._parent_path)
        if doc.dxfversion < "AC1015":
            doc = forge.upgrade_to_r2010(doc)
        msp = doc.modelspace()

        result = forge.heal(msp, tolerance=self._tolerance, explode_inserts=True)

        if result.is_valid and result.parts:
            forge.detect(result, msp)
            forge.write(msp, result)
            forge.split(msp, result, output_folder=str(output_folder), namer=lambda i, part: f"{part.label}_P{i + 1:03d}",)

        for child in sorted(output_folder.glob("*.dxf")):
            child_doc = ezdxf.readfile(child)
            for e in child_doc.modelspace():
                print(f"  [CHILD entities] {child.name}: {e.dxftype()} layer={e.dxf.layer}")

        return output_folder

    def __exit__(self, *_):
        if self._tmpdir:
            self._tmpdir.cleanup()


def _process_child(child_path: Path, tolerance: float):
    """
    Riprocessa un DXF figlio (singola parte attesa) con heal → detect → write.
    Restituisce il result, oppure None se non valido.
    """
    doc = ezdxf.readfile(child_path)
    if doc.dxfversion < "AC1015":
        doc = forge.upgrade_to_r2010(doc)
    msp = doc.modelspace()

    result = forge.heal(msp, tolerance=tolerance, explode_inserts=True)

    for idx, p in enumerate(result.parts):
        print(f"  [CHILD] part{idx} outer.entity={type(p.outer.entity).__name__} area={p.area:.4f}")

    if not result.is_valid or not result.parts:
        return None

    forge.detect(result, msp)
    forge.write(msp, result)

    for idx, p in enumerate(result.parts):
        print(f"  [CHILD2] part{idx}: outer={p.outer.polygon.area:.4f} holes={sum(h.area for h in p.holes):.4f} inners={sum(i.area for i in p.inners):.4f} net={p.area:.4f}")
    return result


def _load_golden_files():
    if not GOLDEN_DIR.exists():
        return []
    return sorted(GOLDEN_DIR.glob("*.json"))


class TestGoldenSplit(unittest.TestCase):
    pass


def _make_split_test(golden_path: Path):
    def test_method(self):
        golden      = json.loads(golden_path.read_text(encoding="utf-8"))
        child_name = golden.get("source_file", f"{golden['parent_file']}__part{golden['part_index']}")
        parent_name = golden["parent_file"]
        parent_path = MULTIPLI_DIR / parent_name

        if not parent_path.exists():
            self.skipTest(f"DXF padre non trovato: {parent_path}")

        config    = _load_config(parent_path)
        tolerance = config.get("tolerance", DEFAULT_TOLERANCE)

        part_index = golden["part_index"]

        # Trova il figlio per indice, non per nome: padri diversi producono
        # figli con nomi identici (000_.dxf, 001_.dxf...), quindi il nome
        # non è una chiave affidabile. L'indice è la fonte di verità.
        with _SplitContext(parent_path, tolerance) as output_folder:
            children = sorted(output_folder.glob("*.dxf"))

            if part_index >= len(children):
                self.fail(
                    f"part_index={part_index} fuori range: "
                    f"lo split ha prodotto solo {len(children)} figli.\n"
                    f"Figli generati: {[f.name for f in children]}"
                )

            child_path = children[part_index]
            result = _process_child(child_path, tolerance)

        # Dopo il context manager la cartella tmp è rimossa, ma result è già in memoria.
        self.assertIsNotNone(
            result,
            f"{child_name}: heal sul figlio ha restituito None (file non valido?)"
        )

        self.assertEqual(
            len(result.parts), 1,
            f"{child_name}: attesa 1 parte nel figlio, trovate {len(result.parts)}"
        )

        part  = result.parts[0]
        label = child_name

        all_inners = sorted(
            part.holes + part.inners,
            key=lambda x: x.area,
            reverse=True,
        )

        # --- Area ---
        actual_area = round(part.area, 4)
        self.assertAlmostEqual(
            actual_area,
            golden["area_mm2"],
            delta=TOL_AREA,
            msg=f"{label}: area {actual_area} != attesa {golden['area_mm2']} (tol={TOL_AREA})",
        )

        # --- Holes count ---
        self.assertEqual(
            len(all_inners),
            golden["holes_count"],
            msg=f"{label}: holes_count {len(all_inners)} != atteso {golden['holes_count']}",
        )

        # --- Perimetro esterno ---
        actual_outer_p = round(part.outer.polygon.exterior.length, 4)
        self.assertAlmostEqual(
            actual_outer_p,
            golden["outer_perimeter_mm"],
            delta=TOL_PERIMETER,
            msg=f"{label}: outer_perimeter {actual_outer_p} != atteso {golden['outer_perimeter_mm']}",
        )

        # --- Perimetro interno ---
        actual_inner_p = round(
            sum(h.polygon.exterior.length for h in all_inners),
            4,
        )
        self.assertAlmostEqual(
            actual_inner_p,
            golden["inner_perimeter_mm"],
            delta=TOL_PERIMETER,
            msg=f"{label}: inner_perimeter {actual_inner_p} != atteso {golden['inner_perimeter_mm']}",
        )

        # --- Geometria outer (WKT) ---
        expected_outer = shapely_wkt.loads(golden["outer_wkt"])
        diff = part.outer.polygon.symmetric_difference(expected_outer).area
        self.assertLess(
            diff, TOL_SHAPE,
            msg=f"{label}: geometria outer cambiata (diff={diff:.4f} mm², tol={TOL_SHAPE})",
        )

        # --- Geometria inners (WKT) ---
        for j, (inner, exp_wkt) in enumerate(zip(all_inners, golden["inners_wkt"])):
            expected_inner = shapely_wkt.loads(exp_wkt)
            diff = inner.polygon.symmetric_difference(expected_inner).area
            self.assertLess(
                diff, TOL_SHAPE,
                msg=f"{label} inner[{j}]: geometria cambiata (diff={diff:.4f} mm², tol={TOL_SHAPE})",
            )

        # --- Layer ---
        if "outer_layer" in golden:
            self.assertEqual(
                part.outer.layer,
                golden["outer_layer"],
                msg=f"{label}: outer_layer '{part.outer.layer}' != atteso '{golden['outer_layer']}'",
            )

        if "inners_layers" in golden:
            self.assertEqual(
                [h.layer for h in all_inners],
                golden["inners_layers"],
                msg=f"{label}: inners_layers {[h.layer for h in all_inners]} != attesi {golden['inners_layers']}",
            )

        # --- Custom ---
        if "custom" in golden:
            for key, expected_val in golden["custom"].items():
                actual_val = part.custom.get(key)
                if isinstance(expected_val, float):
                    self.assertAlmostEqual(
                        actual_val, expected_val, delta=TOL_PERIMETER,
                        msg=f"{label}: custom['{key}'] {actual_val} != atteso {expected_val}",
                    )
                else:
                    self.assertEqual(
                        actual_val, expected_val,
                        msg=f"{label}: custom['{key}'] {actual_val} != atteso {expected_val}",
                    )

    test_method.__name__ = f"test_{golden_path.stem}"
    test_method.__doc__  = f"Split golden: {golden_path.name}"
    return test_method


# Genera dinamicamente un test per ogni golden file
for _golden_path in _load_golden_files():
    setattr(TestGoldenSplit, f"test_{_golden_path.stem}", _make_split_test(_golden_path))


class TestGoldenSplitSetup(unittest.TestCase):

    def test_001_golden_dir_exists(self):
        """La cartella multipli_golden/golden/ esiste."""
        self.assertTrue(
            GOLDEN_DIR.exists(),
            f"Cartella golden non trovata: {GOLDEN_DIR}\n"
            f"Genera i golden file con: python generate_golden_split.py"
        )

    def test_002_golden_not_empty(self):
        """La cartella multipli_golden/golden/ contiene almeno 1 golden file."""
        files = list(GOLDEN_DIR.glob("*.json")) if GOLDEN_DIR.exists() else []
        self.assertGreater(
            len(files), 0,
            f"Nessun golden file trovato in {GOLDEN_DIR}\n"
            f"Genera i golden file con: python generate_golden_split.py"
        )
        print(f"\n  Golden split trovati: {len(files)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)