"""
generate_golden.py
------------------
Genera i golden file per il test di regressione.

Runna UNA VOLTA quando sei soddisfatto dell'output corrente.
I golden file vengono salvati in tests/examples/golden/json/.

DXF sorgente: tests/examples/golden/
Golden JSON:  tests/examples/golden/json/

Per ogni DXF è possibile affiancare un file di configurazione opzionale:
    tests/examples/config/la_104.json

Formato config (tutti i campi sono opzionali):
    {
        "label_map": {"MARK": "engrave", "Bend": "bending"},
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

import forge

EXAMPLES_DIR      = project_root / "tests" / "examples"
GOLDEN_DXF_DIR    = EXAMPLES_DIR / "golden"
GOLDEN_JSON_DIR   = EXAMPLES_DIR / "golden" / "json"
DEFAULT_TOLERANCE = 0.5

GLOBAL_LABEL_MAP = {
    "MARK":      "engrave",
    "Signature": "engrave",
}


def _load_config(dxf_path: Path) -> dict:
    config_path = EXAMPLES_DIR / "config" / f"{dxf_path.stem}.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def generate(force: bool = False, only: str = None):
    GOLDEN_JSON_DIR.mkdir(parents=True, exist_ok=True)

    dxf_files = [
        f for f in GOLDEN_DXF_DIR.glob("*")
        if f.is_file()
        and f.suffix.lower() == ".dxf"
        and not f.stem.endswith("_healed")
    ]

    if only:
        dxf_files = [f for f in dxf_files if f.stem == only]
        if not dxf_files:
            print(f"Nessun DXF trovato con stem '{only}'")
            return

    print(f"Trovati {len(dxf_files)} DXF in {GOLDEN_DXF_DIR}\n")

    generated = 0
    skipped   = 0
    failed    = 0

    for dxf_path in sorted(dxf_files):
        golden_path = GOLDEN_JSON_DIR / f"{dxf_path.stem}.json"

        if golden_path.exists() and not force:
            print(f"  SKIP (golden esiste): {dxf_path.name}")
            skipped += 1
            continue

        try:
            config    = _load_config(dxf_path)
            tolerance = config.get("tolerance", DEFAULT_TOLERANCE)
            label_map = {**GLOBAL_LABEL_MAP, **config.get("label_map", {})}


            doc = forge.load_dxf(
                dxf_path, explode_inserts=True, flatten_z_flag=True,
                verbose=False, label_map=label_map,
            )

            result = forge.heal(
                doc,
                tolerance=tolerance,
            )

            forge.detect(result)

            forge.inject(result)

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
                holes  = sorted(part.holes,  key=lambda x: x.area, reverse=True)
                inners = sorted(part.inners, key=lambda x: x.area, reverse=True)

                part_golden = {
                    # — geometria base —
                    "area_mm2":           round(part.area, 4),
                    "outer_perimeter_mm": round(part.outer.polygon.exterior.length, 4),
                    "inner_perimeter_mm": round(
                        sum(h.polygon.exterior.length for h in holes) +
                        sum(i.polygon.exterior.length for i in inners),
                        4,
                    ),
                    "total_perimeter_mm": round(
                        part.outer.polygon.exterior.length +
                        sum(h.polygon.exterior.length for h in holes) +
                        sum(i.polygon.exterior.length for i in inners),
                        4,
                    ),
                    # — contorno esterno —
                    "outer_wkt": part.outer.polygon.wkt,
                    # — fori —
                    "holes_count": len(holes),
                    "holes_wkt":   [h.polygon.wkt for h in holes],
                    "holes":       [h.to_dict() for h in holes],
                    # — contorni interni (non fori) —
                    "inners_count": len(inners),
                    "inners_wkt":   [i.polygon.wkt for i in inners],
                    "inners":       [i.to_dict() for i in inners],
                    # — pieghe —
                    "bending_lines_count": len(part.bending_lines),
                    "bending_lines":       [bl.to_dict() for bl in part.bending_lines],
                    # — incisioni —
                    "total_engrave_length": round(
                        sum(e.length for e in part.engrave_lines), 4
                    ),
                    "engrave_lines_count": len(part.engrave_lines),
                    "engrave_lines":       [e.to_dict() for e in part.engrave_lines],
                    # — custom — rimane per compatibilità, ora sempre {} —
                    "custom": dict(part.custom),
                }
                golden["parts"].append(part_golden)

            golden_path.write_text(
                json.dumps(golden, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            print(f"  OK: {dxf_path.name} → {golden_path.name} ({result.part_count} parti)")
            generated += 1

        except Exception as ex:
            import traceback
            print(f"  ERRORE: {dxf_path.name} — {ex}")
            traceback.print_exc()
            failed += 1

    print(f"\nGenerati: {generated}  Skippati: {skipped}  Errori: {failed}")
    print(f"Golden salvati in: {GOLDEN_JSON_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Sovrascrive golden esistenti")
    parser.add_argument("--only",  type=str, default=None, help="Stem del DXF da rigenerare (senza estensione)")
    args = parser.parse_args()
    generate(force=args.force, only=args.only)