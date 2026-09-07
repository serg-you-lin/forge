"""
06_split.py — un documento DXF per parte (funzione pura)
=======================================================

API forge usate:
    split    ForgeResult -> list[Drawing], uno per parte. NON tocca il disco.

Per salvare davvero: itera il risultato e chiama .saveas(), oppure usa
split_to_files() (vedi 07). Le parti sotto min_area (mm²) vengono scartate.

    python 06_split.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import os
import forge

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/examples/golden/example_4_polylines.dxf"   # 4 parti
TOLERANCE = 0.5
OUTDIR    = "pipeline_output/split_demo"
MIN_AREA  = 50.0
# -------------------------------------------------------------------------

os.makedirs(OUTDIR, exist_ok=True)

doc = forge.load_dxf(INPUT, tolerance=TOLERANCE)
result = forge.heal_and_detect(doc, label="batch", features="all")
if not result.is_valid:
    raise SystemExit(f"non valido: {result.errors}")


# namer: callable(i, cluster) -> str — assegna cluster.label, così il nome file
# resta ricavabile a valle come f"{cluster.label}.dxf"
def namer(i, cluster):
    return f"pezzo_{i + 1:02d}"


# on_part: hook per parte, callable(cluster, doc_out), prima che il Drawing
# entri nella lista — utile per scrivere metadati / marcature sul doc figlio
def on_part(cluster, doc_out):
    forge.write_metadata_to_dxf(doc_out, cluster)


docs = forge.split(
    result,
    source_doc=doc,
    namer=namer,
    min_area=MIN_AREA,
    exclude_types={"TEXT"},     # rimuove i TEXT da ogni documento figlio
    on_part=on_part,
    include_annotations=True,
)

kept = [p for p in result.clusters if p.outer.polygon.area >= MIN_AREA]
for d, cluster in zip(docs, kept):
    path = os.path.join(OUTDIR, f"{cluster.label}.dxf")
    d.saveas(path)
    print(f"   {path}  (area {cluster.outer.polygon.area:.0f} mm²)")

for w in result.warnings:
    print(f"   warn: {w}")
