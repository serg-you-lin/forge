"""
11_batch_heal.py — heal di tutti i DXF di una cartella
=====================================================

Per ogni file `X.dxf` della cartella produce `X_healed.dxf` + `X_healed.json`
NELLA STESSA cartella. Salta i file già `*_healed` / `*_P<n>` / derivati.

Non è una demo di una singola funzione: è lo strumento batch di sempre, sulla
pipeline `load_dxf → heal_and_detect → to_dxf`.

    python 11_batch_heal.py
    python 11_batch_heal.py path/alla/cartella
    python 11_batch_heal.py path/alla/cartella --tol 0.5
"""

import sys
from pathlib import Path

import forge

# --- CONFIG ----------------------------------------------------------------
DEFAULT_DIR = r"tests/examples"
TOLERANCE   = 0.2
LABEL_MAP = {
    "MARK":      "engrave",
    "Signature": "engrave",
    "Filettati": "threaded_hole",
    "Svasati":   "countersink",
    "Piega":     "bending",
}
# salta i file che sono già output di un giro precedente
SKIP_SUFFIXES = ("_healed", "_noframe_healed", "_rebuilt_manual")
# -------------------------------------------------------------------------


def main(argv):
    input_dir = Path(argv[0]).resolve() if argv and not argv[0].startswith("--") \
        else Path(DEFAULT_DIR).resolve()
    tol = TOLERANCE
    if "--tol" in argv:
        tol = float(argv[argv.index("--tol") + 1])

    if not input_dir.is_dir():
        raise SystemExit(f"cartella non trovata: {input_dir}")

    files = sorted(
        p for p in input_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".dxf"
        and not any(p.stem.endswith(s) for s in SKIP_SUFFIXES)
    )
    if not files:
        raise SystemExit(f"nessun DXF da processare in {input_dir}")

    print(f"cartella   : {input_dir}")
    print(f"tolleranza : {tol}")
    print(f"file       : {len(files)}\n")

    ok = 0
    failed: list[tuple[str, str]] = []

    for src in files:
        out_dxf  = src.with_name(f"{src.stem}_healed.dxf")
        out_json = src.with_name(f"{src.stem}_healed.json")
        try:
            doc = forge.load_dxf(
                str(src),
                explode_inserts=True,
                flatten_z_flag=True,
                label_map=LABEL_MAP,
                tolerance=tol,
                verbose=False,
            )
            result = forge.heal_and_detect(
                doc,
                tolerance=tol,
                label=src.stem,
                source_file=src.name,
                features="all",
            )
            forge.save_json(result, str(out_json))

            if not result.is_valid:
                failed.append((src.name, "; ".join(result.errors) or "result non valido"))
                continue

            forge.to_dxf(result, doc).saveas(str(out_dxf))
            ok += 1
            print(f"OK   {src.name} -> {out_dxf.name}  ({result.cluster_count} parti)")

        except Exception as exc:
            failed.append((src.name, f"{type(exc).__name__}: {exc}"))

    print(f"\nprocessati : {len(files)}")
    print(f"ok         : {ok}")
    print(f"falliti    : {len(failed)}")
    for name, err in failed:
        print(f"   {name}: {err}")


if __name__ == "__main__":
    main(sys.argv[1:])
