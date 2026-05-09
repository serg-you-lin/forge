"""
generate_golden.py
------------------
Genera i golden file per il test di regressione.

Runna UNA VOLTA quando sei soddisfatto dell'output corrente.
I golden file vengono salvati in tests/examples/golden/.

Per ogni DXF è possibile affiancare un file di configurazione opzionale:
    tests/examples/la_104.json   ← config per la_104.DXF

Formato config (tutti i campi sono opzionali):
    {
        "special_layers": {"MARK": "engrave", "Bend": "bending"},
        "tolerance": 0.5
    }

Se il config non esiste, si usano i default:
    tolerance=0.5, nessun special_layers.

Lancia:
    python generate_golden.py
    python generate_golden.py --force   # sovrascrive golden esistenti
"""

import json
import sys
import argparse
from pathlib import Path
import ezdxf

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import dxf_forge as forge

EXAMPLES_DIR = project_root / "tests" / "examples"
GOLDEN_DIR   = project_root / "tests" / "examples" / "golden"

DEFAULT_TOLERANCE = 0.5


def _load_config(dxf_path: Path) -> dict:
    """
    Carica il file di configurazione opzionale affiancato al DXF.
    Es: la_104.DXF → la_104.json (nella stessa cartella del DXF).
    Restituisce un dict vuoto se il config non esiste.
    """
    config_path = EXAMPLES_DIR / "config" / f"{dxf_path.stem}.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding='utf-8'))
    return {}


def generate(force: bool = False):
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    dxf_files = [
        f for f in EXAMPLES_DIR.glob("*")
        if f.is_file()
        and f.suffix.lower() == ".dxf"
        and not f.stem.endswith("_healed")
    ]

    print(f"Trovati {len(dxf_files)} DXF in {EXAMPLES_DIR}\n")

    generated = 0
    skipped   = 0
    failed    = 0

    for dxf_path in sorted(dxf_files):
        golden_path = GOLDEN_DIR / f"{dxf_path.stem}.json"

        if golden_path.exists() and not force:
            print(f"  SKIP (golden esiste): {dxf_path.name}")
            skipped += 1
            continue

        try:
            config         = _load_config(dxf_path)
            tolerance      = config.get("tolerance", DEFAULT_TOLERANCE)
            special_layers = config.get("special_layers", None)

            doc = ezdxf.readfile(dxf_path)
            if doc.dxfversion < 'AC1015':
                doc = forge.upgrade_to_r2010(doc)
            msp = doc.modelspace()

            result = forge.heal(
                msp,
                tolerance=tolerance,
                write_to_msp=True,
                special_layers=special_layers,
            )

            if special_layers:
                forge.inject(msp, result)

            if not result.is_valid:
                print(f"  SKIP (non valido): {dxf_path.name} — {result.errors}")
                skipped += 1
                continue

            golden = {
                "source_file"   : dxf_path.name,
                "part_count"    : result.part_count,
                "parts"         : [],
            }

            for part in result.parts:
                part_golden = {
                    "area_mm2"           : round(part.outer.area - sum(i.area for i in part.inners), 4),
                    "holes_count"        : len(part.inners),
                    "outer_perimeter_mm" : round(part.outer.polygon.exterior.length, 4),
                    "inner_perimeter_mm" : round(sum(i.polygon.exterior.length for i in part.inners), 4),
                    "total_perimeter_mm" : round(
                        part.outer.polygon.exterior.length +
                        sum(i.polygon.exterior.length for i in part.inners), 4
                    ),
                    "outer_wkt"    : part.outer.polygon.wkt,
                    "inners_wkt"   : [i.polygon.wkt for i in part.inners],
                    "outer_layer"  : part.outer.layer,
                    "inners_layers": [i.layer for i in part.inners],
                    "custom"       : dict(part.custom),
                }
                golden["parts"].append(part_golden)

            golden_path.write_text(
                json.dumps(golden, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )

            config_note = f" [config: {list(config.keys())}]" if config else ""
            print(f"  OK: {dxf_path.name} → {golden_path.name} "
                  f"({result.part_count} parti){config_note}")
            generated += 1

        except Exception as ex:
            print(f"  ERRORE: {dxf_path.name} — {ex}")
            failed += 1

    print(f"\nGenerati: {generated}  Skippati: {skipped}  Errori: {failed}")
    print(f"Golden salvati in: {GOLDEN_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Sovrascrive golden esistenti")
    args = parser.parse_args()
    generate(force=args.force)