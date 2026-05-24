"""
generate_golden.py
------------------
Genera i golden file per il test di regressione.

Runna UNA VOLTA quando sei soddisfatto dell'output corrente.
I golden file vengono salvati in tests/examples/golden/.

Per ogni DXF è possibile affiancare un file di configurazione opzionale:
    tests/examples/config/la_104.json

Formato config (tutti i campi sono opzionali):
    {
        "special_layers": {"MARK": "engrave", "Bend": "bending"},
        "tolerance": 0.5
    }

Lancia:
    python generate_golden.py                        # genera solo i mancanti
    python generate_golden.py --force                # rigenera tutti
    python generate_golden.py --only la_104          # solo quel file (senza estensione)
    python generate_golden.py --force --only la_104  # forza rigenera solo quel file
"""

import json
import sys
import argparse
from pathlib import Path
import ezdxf

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import dxf_forge as forge

EXAMPLES_DIR      = project_root / "tests" / "examples"
GOLDEN_DIR        = project_root / "tests" / "examples" / "golden"
DEFAULT_TOLERANCE = 0.5

GLOBAL_SPECIAL_LAYERS = {
    "MARK":      "engrave",
    "Signature": "engrave",
}


def _load_config(dxf_path: Path) -> dict:
    config_path = EXAMPLES_DIR / "config" / f"{dxf_path.stem}.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def generate(force: bool = False, only: str = None):
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    dxf_files = [
        f for f in EXAMPLES_DIR.glob("*")
        if f.is_file()
        and f.suffix.lower() == ".dxf"
        and not f.stem.endswith("_healed")
    ]

    if only:
        dxf_files = [f for f in dxf_files if f.stem == only]
        if not dxf_files:
            print(f"Nessun DXF trovato con stem '{only}'")
            return

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
            special_layers = {**GLOBAL_SPECIAL_LAYERS, **config.get("special_layers", {})}

            doc = ezdxf.readfile(dxf_path)
            if doc.dxfversion < "AC1015":
                doc = forge.upgrade_to_r2010(doc)
            msp = doc.modelspace()

            result = forge.heal(
                msp,
                tolerance=tolerance,
            )

            forge.detect(
                result,
                msp,
                special_layers=special_layers,
            )

            forge.inject(msp, result)

            if not result.is_valid:
                print(f"  SKIP (non valido): {dxf_path.name} — {result.errors}")
                skipped += 1
                continue

            golden = {
                "source_file": dxf_path.name,
                "part_count":  result.part_count,
                "parts":       [],
            }

            for part in result.parts:
                all_inners = sorted(part.holes + part.inners, key=lambda x: x.area, reverse=True)
                part_golden = {
                    "area_mm2":           round(part.area, 4),
                    "holes_count":        len(all_inners),
                    "outer_perimeter_mm": round(part.outer.polygon.exterior.length, 4),
                    "inner_perimeter_mm": round(sum(i.polygon.exterior.length for i in all_inners), 4),
                    "total_perimeter_mm": round(
                        part.outer.polygon.exterior.length +
                        sum(i.polygon.exterior.length for i in all_inners), 4
                    ),
                    "outer_wkt":     part.outer.polygon.wkt,
                    "inners_wkt":    [i.polygon.wkt for i in all_inners],
                    "outer_layer":   part.outer.layer,
                    "inners_layers": [i.layer for i in all_inners],
                    "custom":        dict(part.custom),
                }
                golden["parts"].append(part_golden)

            golden_path.write_text(
                json.dumps(golden, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            print(f"  OK: {dxf_path.name} → {golden_path.name} ({result.part_count} parti)")
            generated += 1

        except Exception as ex:
            print(f"  ERRORE: {dxf_path.name} — {ex}")
            failed += 1

    print(f"\nGenerati: {generated}  Skippati: {skipped}  Errori: {failed}")
    print(f"Golden salvati in: {GOLDEN_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Sovrascrive golden esistenti")
    parser.add_argument("--only",  type=str, default=None, help="Stem del DXF da rigenerare (senza estensione)")
    args = parser.parse_args()
    generate(force=args.force, only=args.only)