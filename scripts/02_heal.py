"""
02_heal.py — ricostruzione della topologia
==========================================

API topo usate:
    heal               doc.edges -> Result (parti, albero outer/inner)
    validate_result    valida l'OUTPUT (heal la chiama già da solo; qui a scopo didattico)

heal() fa il lavoro difficile: chiude i gap, trova i loop chiusi, costruisce
l'albero di contenimento. NON classifica i fori (lettura di processo: snapbend, MAP.md D88):
consegna Cluster(outer, inners=[Contour...]).

    python 02_heal.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import topo

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/data/Linee_piegatura.dxf"
TOLERANCE = 0.5
# -------------------------------------------------------------------------

doc = topo.load_dxf(INPUT, tolerance=TOLERANCE)

result = topo.heal(
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
    for j, inner in enumerate(cluster.inners):
        print(f"      inner {j}: area={inner.polygon.area:.1f}")

# validate_result: heal() la chiama già; utile solo se costruisci un
# Result per altre vie. MUTA il result (aggiunge warnings/errors).
topo.validate_result(result)
print(f"\ndopo validate_result: is_valid={result.is_valid}")
