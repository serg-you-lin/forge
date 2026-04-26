"""
generate_golden.py
------------------
Genera i golden file per il test di regressione.

Runna UNA VOLTA quando sei soddisfatto dell'output corrente.
I golden file vengono salvati in tests/golden/.

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
            doc = ezdxf.readfile(dxf_path)
            if doc.dxfversion < 'AC1015':
                doc = forge.upgrade_to_r2010(doc)
            msp = doc.modelspace()

            result = forge.heal(msp, tolerance=0.5, write_to_msp=False)

            if not result.is_valid:
                print(f"  SKIP (non valido): {dxf_path.name} — {result.errors}")
                skipped += 1
                continue

            golden = {
                "source_file" : dxf_path.name,
                "part_count"  : result.part_count,
                "parts"       : [],
            }

            for part in result.parts:
                part_golden = {
                    # Metadati calcolati
                    "area_mm2"           : round(part.outer.area - sum(i.area for i in part.inners), 4),
                    "holes_count"        : len(part.inners),
                    "outer_perimeter_mm" : round(part.outer.polygon.exterior.length, 4),
                    "inner_perimeter_mm" : round(sum(i.polygon.exterior.length for i in part.inners), 4),
                    "total_perimeter_mm" : round(
                        part.outer.polygon.exterior.length +
                        sum(i.polygon.exterior.length for i in part.inners), 4
                    ),
                    # Geometria come WKT per confronto shape
                    "outer_wkt"  : part.outer.polygon.wkt,
                    "inners_wkt" : [i.polygon.wkt for i in part.inners],
                    # Layer assegnati
                    "outer_layer"  : part.outer.layer,
                    "inners_layers": [i.layer for i in part.inners],
                }
                golden["parts"].append(part_golden)

            golden_path.write_text(
                json.dumps(golden, indent=2, ensure_ascii=False),
                encoding='utf-8'
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
    args = parser.parse_args()
    generate(force=args.force)



"""
python generate_golden.py --force
"""