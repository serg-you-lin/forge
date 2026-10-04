"""
tests/generate_golden.py
------------------------
Genera i golden file per il test di regressione geometrica: solo heal(), un
foro è un contorno interno (MAP.md D88). La metà di processo (fori, pieghe,
incisioni) la genera snapbend, tests/flat/generate_golden_process.py.

Runna UNA VOLTA quando sei soddisfatto dell'output corrente.

DXF sorgente: tests/data/golden/

Per ogni DXF è possibile affiancare un file di configurazione opzionale:
    tests/data/config/la_104.json

Formato config (tutti i campi sono opzionali):
    {
        "name_roles": {"MARK": "engrave", "Bend": "bending"},
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

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import forge

EXAMPLES_DIR      = project_root / "tests" / "data"
GOLDEN_DXF_DIR    = EXAMPLES_DIR / "golden"
GOLDEN_JSON_DIR   = EXAMPLES_DIR / "golden" / "json"
DEFAULT_TOLERANCE = 0.5

GLOBAL_NAME_ROLES = {
    "MARK":      "engrave",
    "Signature": "engrave",
}


def _load_config(dxf_path: Path) -> dict:
    config_path = EXAMPLES_DIR / "config" / f"{dxf_path.stem}.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def _geometry(result, source_file: str) -> dict:
    """Metà forge: outer, perimetri, contorni interni."""
    golden = {"source_file": source_file, "cluster_count": result.cluster_count, "clusters": []}
    for cluster in result.clusters:
        inners = sorted(cluster.inners, key=lambda x: x.area, reverse=True)
        outer_p = cluster.outer.polygon.exterior.length
        inner_p = sum(i.polygon.exterior.length for i in inners)
        golden["clusters"].append({
            "area_mm2":           round(cluster.area, 4),
            "outer_perimeter_mm": round(outer_p, 4),
            "inner_perimeter_mm": round(inner_p, 4),
            "total_perimeter_mm": round(outer_p + inner_p, 4),
            "outer_wkt":          cluster.outer.polygon.wkt,
            "inners_count":       len(inners),
            "inners_wkt":         [i.polygon.wkt for i in inners],
            "inners":             [{"role": i.to_dict()["role"], "area": i.to_dict()["area"]}
                                   for i in inners],
        })
    return golden


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
        geom_path = GOLDEN_JSON_DIR / f"{dxf_path.stem}.json"

        if geom_path.exists() and not force:
            print(f"  SKIP (golden esiste): {dxf_path.name}")
            skipped += 1
            continue

        try:
            config     = _load_config(dxf_path)
            tolerance  = config.get("tolerance", DEFAULT_TOLERANCE)
            name_roles = {**GLOBAL_NAME_ROLES, **config.get("name_roles", {})}

            def _load():
                return forge.load_dxf(
                    dxf_path, upgrade=True, explode_inserts=True, flatten_z_flag=True,
                    tolerance=tolerance, verbose=False, role_rules=forge.name_rules(name_roles),
                )

            geom = forge.heal(_load(), tolerance=tolerance)

            if not geom.is_valid:
                print(f"  SKIP (non valido): {dxf_path.name} — {geom.errors}")
                skipped += 1
                continue

            geom_path.write_text(json.dumps(_geometry(geom, dxf_path.name), indent=2,
                                            ensure_ascii=False), encoding="utf-8")

            print(f"  OK: {dxf_path.name} ({geom.cluster_count} parti)")
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