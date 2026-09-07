"""
05_to_dxf.py — render del modello in UN documento DXF
====================================================

API forge usate:
    to_dxf    ForgeResult -> Drawing ezdxf NUOVO (R2010)

to_dxf NON rilegge entità dalla sorgente: costruisce tutto dai segmenti del
modello. `source_doc` serve solo a riportare gli header ($INSUNITS,
$MEASUREMENT). La posizione XY del mondo è preservata (vedi MAP.md D17).

Solleva ValueError se result.is_valid è False — controllalo sempre prima.

    python 05_to_dxf.py
"""

import forge

from _paths import EXAMPLES, OUTPUT

# --- CONFIG ----------------------------------------------------------------
INPUT     = EXAMPLES / "Multifeature.dxf"
TOLERANCE = 0.5
LABEL_MAP = {
    "Filettati": "threaded_hole",
    "Svasati":   "countersink",
    "Piega":     "bending",
    "MARK":      "engrave",
}
OUTDIR = OUTPUT
# -------------------------------------------------------------------------

OUTDIR.mkdir(parents=True, exist_ok=True)
base = INPUT.stem

doc = forge.load_dxf(INPUT, tolerance=TOLERANCE, label_map=LABEL_MAP)
result = forge.heal_and_detect(doc, label=base, features="all")

if not result.is_valid:
    raise SystemExit(f"non valido: {result.errors}")

# 1. documento completo, tutte le parti
out = forge.to_dxf(
    result,
    source_doc=doc,             # solo per gli header
    include_trash=True,         # geometria non classificata sul layer "Trash"
    annotation_layer="Annotation",   # "Trash" / altro nome / None (= layer originale)
)
path = OUTDIR / f"{base}_healed.dxf"
out.saveas(path)
print(f"completo         -> {path}")
print("   layer:", sorted(l.dxf.name for l in out.layers if l.dxf.name.isupper() or l.dxf.name[0].isupper()))

# 2. solo le parti che passano un filtro (callable(cluster) -> bool)
big = forge.to_dxf(result, doc, filter_cluster=lambda p: p.outer.polygon.area > 1000)
path = OUTDIR / f"{base}_big_only.dxf"
big.saveas(path)
print(f"filter_cluster area -> {path}")
