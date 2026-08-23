"""
generate_golden_split.py
------------------------
Genera i golden file per il test di regressione dello splitting.

Struttura attesa:
    tests/examples/golden_multipli/          ← DXF multiparte sorgente
    tests/examples/golden_multipli/config/   ← config opzionali
    tests/examples/golden_multipli/golden/   ← golden JSON generati (uno per parte)

Per ogni DXF padre viene eseguita la pipeline completa:
    heal → detect → write → split

Il golden di ogni parte viene costruito direttamente dal result del padre
(result.parts[i]) — senza riprocessare il figlio.

Lancia:
    python generate_golden_split.py
    python generate_golden_split.py --force
    python generate_golden_split.py --only la_104
    python generate_golden_split.py --force --only la_104
"""

import json
import sys
import argparse
import tempfile
from pathlib import Path
import traceback

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.adapters.dxf.layers import ROLE_TO_LAYER, LAYER_INNER

MULTIPLI_DIR      = project_root / "tests" / "examples" / "golden_multipli"
GOLDEN_DIR        = MULTIPLI_DIR / "golden"
DEFAULT_TOLERANCE = 0.5


def _load_config(dxf_path: Path) -> dict:
    config_path = MULTIPLI_DIR / "config" / f"{dxf_path.stem}.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def generate(force: bool = False, only: str = None):
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    dxf_files = [
        f for f in MULTIPLI_DIR.glob("*")
        if f.is_file() and f.suffix.lower() == ".dxf"
    ]

    if only:
        dxf_files = [f for f in dxf_files if f.stem == only]
        if not dxf_files:
            print(f"Nessun DXF trovato con stem '{only}'")
            return

    print(f"Trovati {len(dxf_files)} DXF padre in {MULTIPLI_DIR}\n")

    generated = 0
    skipped   = 0
    failed    = 0

    for parent_path in sorted(dxf_files):
        config    = _load_config(parent_path)
        tolerance = config.get("tolerance", DEFAULT_TOLERANCE)

        try:
            _, msp = forge.load_dxf(parent_path, upgrade=True, explode_inserts=True)
            result = forge.heal(msp, tolerance=tolerance)

            if not result.is_valid or not result.parts:
                print(f"  SKIP (non valido): {parent_path.name}")
                skipped += 1
                continue

            forge.detect(result)
            forge.write(msp, result)

            with tempfile.TemporaryDirectory() as tmp_dir:
                forge.split(
                    msp,
                    result,
                    output_folder=tmp_dir,
                    namer=lambda i, part: f"{part.label}_P{i + 1:03d}",
                )

            print(f"  {parent_path.name} → {len(result.parts)} parti")

            for part_index, part in enumerate(result.parts):
                golden_stem = f"{parent_path.stem}__{part_index:03d}"
                golden_path = GOLDEN_DIR / f"{golden_stem}.json"

                if golden_path.exists() and not force:
                    print(f"    SKIP (golden esiste): {golden_stem}.json")
                    skipped += 1
                    continue

                all_inners = sorted(
                    part.holes + part.inners,
                    key=lambda x: x.area,
                    reverse=True,
                )

                golden = {
                    "parent_file":         parent_path.name,
                    "part_index":          part_index,
                    "area_mm2":            round(part.area, 4),
                    "holes_count":         len(all_inners),
                    "outer_perimeter_mm":  round(part.outer.polygon.exterior.length, 4),
                    "inner_perimeter_mm":  round(sum(i.polygon.exterior.length for i in all_inners), 4),
                    "total_perimeter_mm":  round(
                        part.outer.polygon.exterior.length +
                        sum(i.polygon.exterior.length for i in all_inners),
                        4,
                    ),
                    "outer_wkt":     part.outer.polygon.wkt,
                    "inners_wkt":    [i.polygon.wkt for i in all_inners],
                    "outer_layer":   ROLE_TO_LAYER.get(part.outer.role),
                    "inners_layers": [ROLE_TO_LAYER.get(i.role, LAYER_INNER) for i in all_inners],
                    "custom":        dict(part.custom),
                }

                golden_path.write_text(
                    json.dumps(golden, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                print(f"    OK: {golden_stem}.json (area={golden['area_mm2']} mm²)")
                generated += 1

        except Exception as ex:
            print(f"  ERRORE: {parent_path.name} — {ex}")
            traceback.print_exc()
            failed += 1

    print(f"\nGenerati: {generated}  Skippati: {skipped}  Errori: {failed}")
    print(f"Golden salvati in: {GOLDEN_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--only",  type=str, default=None)
    args = parser.parse_args()
    generate(force=args.force, only=args.only)