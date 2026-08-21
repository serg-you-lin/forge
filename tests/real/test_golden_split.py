

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

import atexit
import json
import shutil
import sys
import tempfile
from collections import Counter
import unittest
from functools import lru_cache
from pathlib import Path

import ezdxf
from shapely import wkt as shapely_wkt

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.adapters.dxf.layers import (
    ROLE_TO_LAYER,
    LAYER_INNER,
    LAYER_OUTER,
    LAYER_HOLE,
)


MULTIPLI_DIR = project_root / "tests" / "examples" / "golden_multipli"
GOLDEN_DIR   = MULTIPLI_DIR / "golden"

TOL_AREA      = 0.1
TOL_PERIMETER = 0.5
TOL_SHAPE     = 1.0
DEFAULT_TOLERANCE = 0.5

_PARENT_PIPELINE_CACHE: dict[tuple[Path, float], dict] = {}


def _match_inner_polygons(actual_wkts: list[str], expected_wkts: list[str]) -> list[tuple[int, int, float]]:
    """
    Restituisce un matching one-to-one (greedy) tra inner attuali/attesi
    minimizzando il diff geometrico (area symmetric_difference).
    """
    if len(actual_wkts) != len(expected_wkts):
        raise ValueError(
            f"inner count mismatch: actual={len(actual_wkts)} expected={len(expected_wkts)}"
        )

    actual_polys = [shapely_wkt.loads(w) for w in actual_wkts]
    expected_polys = [shapely_wkt.loads(w) for w in expected_wkts]

    candidates = []
    for ai, a_poly in enumerate(actual_polys):
        for ei, e_poly in enumerate(expected_polys):
            diff = a_poly.symmetric_difference(e_poly).area
            candidates.append((diff, ai, ei))

    candidates.sort(key=lambda t: t[0])

    matched_actual = set()
    matched_expected = set()
    matches: list[tuple[int, int, float]] = []
    for diff, ai, ei in candidates:
        if ai in matched_actual or ei in matched_expected:
            continue
        matched_actual.add(ai)
        matched_expected.add(ei)
        matches.append((ai, ei, diff))
        if len(matches) == len(actual_wkts):
            break

    if len(matches) != len(actual_wkts):
        raise ValueError("impossibile costruire un matching completo tra inner")

    return matches


@lru_cache(maxsize=None)
def _load_golden_entries() -> tuple[tuple[tuple[str, dict], ...], ...]:
    if not GOLDEN_DIR.exists():
        return ()
    entries = []
    for golden_path in sorted(GOLDEN_DIR.glob("*.json")):
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        entries.append((golden_path.stem, golden))
    return tuple(entries)


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


def _get_parent_split_cache(parent_path: Path, tolerance: float) -> dict:
    cache_key = (parent_path.resolve(), float(tolerance))
    cached = _PARENT_PIPELINE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    output_folder = Path(tempfile.mkdtemp(prefix=f"golden_split_{parent_path.stem}_"))
    atexit.register(shutil.rmtree, output_folder, ignore_errors=True)

    doc, msp = forge.load_dxf(parent_path, explode_inserts=True)
    result = forge.heal(msp, tolerance=tolerance)

    if result.is_valid and result.parts:
        forge.detect(result)
        forge.write(msp, result)
        forge.split(
            msp,
            result,
            output_folder=str(output_folder),
            namer=lambda i, part: f"{part.label}_P{i + 1:03d}",
        )

    part_payloads = []
    for part in result.parts if result.is_valid and result.parts else []:
        part_payloads.append({
            "area": part.area,
            "holes_count": len(part.holes + part.inners),
            "outer_perimeter": part.outer.polygon.exterior.length,
            "inner_perimeter": sum(h.polygon.exterior.length for h in part.holes + part.inners),
            "outer_wkt": part.outer.polygon.wkt,
            "inners_wkt": [h.polygon.wkt for h in sorted(part.holes + part.inners, key=lambda x: x.area, reverse=True)],
            "outer_role": part.outer.role,
            "inner_roles": [h.role for h in sorted(part.holes + part.inners, key=lambda x: x.area, reverse=True)],
            "custom": dict(part.custom),
        })

    cached_entry = {
        "output_folder": output_folder,
        "children": sorted(output_folder.glob("*.dxf")),
        "parts": part_payloads,
    }
    _PARENT_PIPELINE_CACHE[cache_key] = cached_entry
    return cached_entry


class _SplitContext:
    """
    Context manager che esegue la pipeline sul padre una sola volta per
    parent+tolerance e mette a disposizione la cartella di output per tutta
    la durata del blocco `with`.
    """

    def __init__(self, parent_path: Path, tolerance: float):
        self._parent_path = parent_path
        self._tolerance = tolerance
        self._cache_entry = None

    def __enter__(self) -> Path:
        self._cache_entry = _get_parent_split_cache(self._parent_path, self._tolerance)
        return self._cache_entry["output_folder"]

    def __exit__(self, *_):
        return False


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

            part_payload = _PARENT_PIPELINE_CACHE[(parent_path.resolve(), float(tolerance))]["parts"][part_index]

        self.assertIsNotNone(
            part_payload,
            f"{child_name}: nessuna parte disponibile per il figlio richiesto"
        )

        self.assertEqual(
            len(_PARENT_PIPELINE_CACHE[(parent_path.resolve(), float(tolerance))]["parts"]),
            len(children),
            f"{child_name}: il numero di parti in cache ({len(_PARENT_PIPELINE_CACHE[(parent_path.resolve(), float(tolerance))]['parts'])}) non coincide con i figli generati ({len(children)})"
        )

        label = child_name

        # --- Area ---
        actual_area = round(part_payload["area"], 4)
        self.assertAlmostEqual(
            actual_area,
            golden["area_mm2"],
            delta=TOL_AREA,
            msg=f"{label}: area {actual_area} != attesa {golden['area_mm2']} (tol={TOL_AREA})",
        )

        # --- Holes count ---
        self.assertEqual(
            part_payload["holes_count"],
            golden["holes_count"],
            msg=f"{label}: holes_count {part_payload['holes_count']} != atteso {golden['holes_count']}",
        )

        # --- Perimetro esterno ---
        actual_outer_p = round(part_payload["outer_perimeter"], 4)
        self.assertAlmostEqual(
            actual_outer_p,
            golden["outer_perimeter_mm"],
            delta=TOL_PERIMETER,
            msg=f"{label}: outer_perimeter {actual_outer_p} != atteso {golden['outer_perimeter_mm']}",
        )

        # --- Perimetro interno ---
        actual_inner_p = round(
            part_payload["inner_perimeter"],
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
        diff = shapely_wkt.loads(part_payload["outer_wkt"]).symmetric_difference(expected_outer).area
        self.assertLess(
            diff, TOL_SHAPE,
            msg=f"{label}: geometria outer cambiata (diff={diff:.4f} mm², tol={TOL_SHAPE})",
        )

        # --- Geometria inners (WKT) ---
        self.assertEqual(
            len(part_payload["inners_wkt"]),
            len(golden["inners_wkt"]),
            msg=(
                f"{label}: numero inner diverso "
                f"(actual={len(part_payload['inners_wkt'])}, expected={len(golden['inners_wkt'])})"
            ),
        )

        inner_matches = _match_inner_polygons(part_payload["inners_wkt"], golden["inners_wkt"])
        for actual_idx, expected_idx, diff in inner_matches:
            self.assertLess(
                diff, TOL_SHAPE,
                msg=(
                    f"{label} inner(actual={actual_idx}, expected={expected_idx}): "
                    f"geometria cambiata (diff={diff:.4f} mm², tol={TOL_SHAPE})"
                ),
            )

        # --- Layer ---
        if "outer_layer" in golden:
            self.assertEqual(
                ROLE_TO_LAYER.get(part_payload["outer_role"]),
                golden["outer_layer"],
                msg=f"{label}: outer_layer '{ROLE_TO_LAYER.get(part_payload['outer_role'])}' != atteso '{golden['outer_layer']}'",
            )

        if "inners_layers" in golden:
            actual_layers = [ROLE_TO_LAYER.get(h_role, LAYER_INNER) for h_role in part_payload["inner_roles"]]
            self.assertEqual(
                Counter(actual_layers),
                Counter(golden["inners_layers"]),
                msg=f"{label}: inners_layers multiset {actual_layers} != attesi {golden['inners_layers']}",
            )


        # --- Custom ---
        if "custom" in golden:
            for key, expected_val in golden["custom"].items():
                actual_val = part_payload["custom"].get(key)
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