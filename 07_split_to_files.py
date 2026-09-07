"""
07_split_to_files.py — pipeline multi-pezzo completa su disco
============================================================

API forge usate:
    split_to_files    heal -> detect -> split -> .saveas() per parte
                      È L'UNICA funzione della pipeline che scrive su disco.

Ritorna il ForgeResult (per poterci fare save_json dopo). Nome file:
f"{cluster.label}.dxf" dove cluster.label = namer(i, cluster), senza namer f"{label}_P{i+1}".

    python 07_split_to_files.py
"""

import forge

from _paths import EXAMPLES, OUTPUT

# --- CONFIG ----------------------------------------------------------------
INPUT     = EXAMPLES / "golden" / "example_4_polylines.dxf"
TOLERANCE = 0.5
OUTDIR    = OUTPUT / "batch_demo"
LABEL     = "DP10419"
# -------------------------------------------------------------------------

doc = forge.load_dxf(INPUT, tolerance=TOLERANCE)

result = forge.split_to_files(
    doc,
    output_folder=OUTDIR,
    label=LABEL,
    source_file=INPUT.name,
    namer=lambda i, cluster: f"{LABEL}_P{i + 1}",
    min_area=50.0,
    include_annotations=True,
)

print(f"parti scritte : {result.cluster_count}  ->  {OUTDIR}/")
print(f"is_valid      : {result.is_valid}")
for w in result.warnings:
    print(f"   warn: {w}")

# il result serve ancora: metadati dell'intero batch
json_path = OUTDIR / f"{LABEL}.json"
forge.save_json(result, json_path)
print(f"metadati      : {json_path}")
