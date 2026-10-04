"""
tests/generate_golden_split.py
------------------------------
Genera i golden file per il test di regressione dello splitting, in due metà
(MAP.md D88).

Struttura attesa:
    tests/data/golden_multipli/          ← DXF multiparte sorgente
    tests/data/golden_multipli/config/   ← config opzionali
    tests/data/golden_multipli/golden/   ← geometria (heal → split), uno per parte
    tests/data/golden_multipli/process/  ← layer dei fori e summary (heal →
                                           detect_flat); passa a snapbend

Il golden di ogni parte viene costruito direttamente dal result del padre
(result.clusters[i]) — senza riprocessare il figlio.

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
from forge.adapters.dxf.layers import role_to_dxf_layer
from forge.tools.detect import describe_features

MULTIPLI_DIR      = project_root / "tests" / "data" / "golden_multipli"
GOLDEN_DIR        = MULTIPLI_DIR / "golden"
PROC_DIR          = MULTIPLI_DIR / "process"
DEFAULT_TOLERANCE = 0.5


def _load_config(dxf_path: Path) -> dict:
    config_path = MULTIPLI_DIR / "config" / f"{dxf_path.stem}.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def generate(force: bool = False, only: str = None):
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    PROC_DIR.mkdir(parents=True, exist_ok=True)

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
            doc = forge.load_dxf(parent_path, upgrade=True, explode_inserts=True)
            result = forge.heal(doc, tolerance=tolerance)
            proc = forge.heal(forge.load_dxf(parent_path, upgrade=True, explode_inserts=True),
                              tolerance=tolerance)

            if not result.is_valid or not result.clusters:
                print(f"  SKIP (non valido): {parent_path.name}")
                skipped += 1
                continue

            forge.detect_flat(proc, features="all")

            forge.split(
                result,
                doc,
                namer=lambda i, cluster: f"{cluster.label}_P{i + 1:03d}",
            )

            print(f"  {parent_path.name} → {len(result.clusters)} parti")

            for part_index, (cluster, pcluster) in enumerate(zip(result.clusters, proc.clusters)):
                golden_stem = f"{parent_path.stem}__{part_index:03d}"
                golden_path = GOLDEN_DIR / f"{golden_stem}.json"
                proc_path   = PROC_DIR / f"{golden_stem}.json"

                if golden_path.exists() and proc_path.exists() and not force:
                    print(f"    SKIP (golden esiste): {golden_stem}.json")
                    skipped += 1
                    continue

                inners = sorted(cluster.inners, key=lambda x: x.area, reverse=True)
                golden = {
                    "parent_file":         parent_path.name,
                    "part_index":          part_index,
                    "area_mm2":            round(cluster.area, 4),
                    "inners_count":        len(inners),
                    "outer_perimeter_mm":  round(cluster.outer.polygon.exterior.length, 4),
                    "inner_perimeter_mm":  round(sum(i.polygon.exterior.length for i in inners), 4),
                    "total_perimeter_mm":  round(
                        cluster.outer.polygon.exterior.length +
                        sum(i.polygon.exterior.length for i in inners),
                        4,
                    ),
                    "outer_wkt":     cluster.outer.polygon.wkt,
                    "inners_wkt":    [i.polygon.wkt for i in inners],
                    "outer_layer":   role_to_dxf_layer(cluster.outer.role),
                    "inners_layers": [role_to_dxf_layer(i.role) for i in inners],
                }
                process = {
                    "parent_file":   parent_path.name,
                    "part_index":    part_index,
                    # area e outer per agganciare il pezzo
                    "area_mm2":      round(pcluster.area, 4),
                    "outer_wkt":     pcluster.outer.polygon.wkt,
                    # role_to_dxf_layer: un ruolo di processo (es. "hole") ha il
                    # suo layer solo via il registro di rules/palette.py
                    "inners_layers": [role_to_dxf_layer(i.role)
                                      for i in pcluster.features("holes") + pcluster.inners],
                    "summary":       {
                        k: v for k, v in
                        {**pcluster.summary, **describe_features(pcluster)}.items()
                        if v
                    },
                }

                for path, data in ((golden_path, golden), (proc_path, process)):
                    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"    OK: {golden_stem}.json (area={golden['area_mm2']} mm²)")
                generated += 1

        except Exception as ex:
            print(f"  ERRORE: {parent_path.name} — {ex}")
            traceback.print_exc()
            failed += 1

    print(f"\nGenerati: {generated}  Skippati: {skipped}  Errori: {failed}")
    print(f"Golden salvati in: {GOLDEN_DIR} e {PROC_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--only",  type=str, default=None)
    args = parser.parse_args()
    generate(force=args.force, only=args.only)