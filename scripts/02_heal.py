"""
02_heal.py — ricostruzione della topologia
==========================================

API forge usate:
    heal               doc.edges -> ForgeResult (parti, albero outer/inner)
    validate_result    valida l'OUTPUT (heal la chiama già da solo; qui a scopo didattico)

heal() fa il lavoro difficile: chiude i gap, trova i loop chiusi, costruisce
l'albero di contenimento. NON classifica i fori (quello è detect(), vedi 03):
consegna ForgeCluster(outer, inners=[ForgeContour...]).

    python 02_heal.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import forge

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/examples/Linee_piegatura.dxf"
TOLERANCE = 0.5
# -------------------------------------------------------------------------

doc = forge.load_dxf(INPUT, tolerance=TOLERANCE)

result = forge.heal(
    doc,
    tolerance=TOLERANCE,           # se None: ripreso da doc.source_meta
    label="P-DEMO",                # finisce in cluster.label e nei metadati
    source_file="Linee_piegatura.dxf",
)

print(f"is_valid   : {result.is_valid}")
print(f"parti      : {result.cluster_count}")
print(f"trash      : {len(result.trash_entities)}  (geometria non ancora in un loop)")
for e in result.errors:
    print(f"   ERROR: {e}")
for w in result.warnings:
    print(f"   warn : {w}")

for i, cluster in enumerate(result.clusters):
    print(f"\nParte {i}  label={cluster.label!r}")
    print(f"   outer  : role={cluster.outer.role}  area={cluster.outer.area:.1f}  "
          f"perimetro={cluster.outer.polygon.exterior.length:.1f}")
    print(f"   bbox   : {tuple(round(v, 1) for v in cluster.bbox)}")
    print(f"   inners : {len(cluster.inners)}  (contorni interni, non ancora tipati come foro)")
    print(f"   holes  : {len(cluster.holes)}   (sempre 0 dopo heal — li fa detect)")
    for j, inner in enumerate(cluster.inners):
        print(f"      inner {j}: area={inner.polygon.area:.1f}")

# validate_result: heal() la chiama già; utile solo se costruisci un
# ForgeResult per altre vie. MUTA il result (aggiunge warnings/errors).
forge.validate_result(result)
print(f"\ndopo validate_result: is_valid={result.is_valid}")
