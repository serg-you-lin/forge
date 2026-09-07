"""
08_inject.py — arricchimento CAM dai testi del disegno
=====================================================

API forge usate:
    inject    passa a un `data_injector` esterno i testi che ricadono dentro
              l'outer di ogni cluster, e mette il dict risultante in cluster.custom

`inject()` è OPZIONALE e fa una sola cosa: se passi `data_injector` —
`callable(cluster, list[str]) -> dict` — mette il dict restituito in
`cluster.custom` (codice pezzo, materiale, spessore, ...). Senza `data_injector`
non fa nulla.

I testi arrivano da `result.annotations`: il modello tipato (`Note`, `Dimension`,
`Leader`) prodotto da `load_dxf()` e portato sul result da `heal()`. Niente
`msp`, niente `import ezdxf`, niente liste sciolte — dopo il load il formato
sorgente è sparito (MAP.md D20).

I CONTEGGI delle feature NON si fanno qui: sono `cluster.summary` (property
derivata dal modello).

    python 08_inject.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import forge

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/examples/Multifeature.dxf"
TOLERANCE = 0.5
LABEL_MAP = {"Filettati": "threaded_hole", "Svasati": "countersink",
             "Piega": "bending", "MARK": "engrave"}
# -------------------------------------------------------------------------

doc = forge.load_dxf(INPUT, tolerance=TOLERANCE, label_map=LABEL_MAP)
result = forge.heal_and_detect(doc, label="P-1024", features="all")

# Le annotazioni sono già nel modello, tipate e con posizione. `display_text` è
# il testo pulito (MTEXT senza codici di formato, quote con il loro valore).
print(f"annotazioni nel modello: {len(result.annotations)}")
for ann in result.annotations:
    if ann.display_text and ann.display_text.strip():
        pos = tuple(round(c, 1) for c in ann.position)
        print(f"   {type(ann).__name__:<10} {ann.display_text!r:<8} @ {pos}")


# data_injector: riceve il cluster e SOLO i testi che ricadono geometricamente
# dentro il suo outer (già filtrati da inject). Ritorna il dict per cluster.custom.
# NB: in Multifeature.dxf le sigle "A"/"B" e molte quote sono fuori dal contorno,
# quindi qui `testi_nel_cluster` contiene solo i testi interni — è il
# comportamento corretto (ogni cluster prende i propri testi, non quelli del vicino).
def leggi_cartiglio(cluster, testi_nel_cluster):
    print(f"   [injector] {cluster.label}: testi interni = {testi_nel_cluster}")
    code = next((t for t in testi_nel_cluster if t.strip()), None)
    return {
        "part_code": code or "N/D",
        "material":  "S275JR",
        "thickness": 2.0,
        "quantity":  1,
    }


forge.inject(result, data_injector=leggi_cartiglio)

for i, cluster in enumerate(result.clusters):
    print(f"\nCluster {i}  {cluster.label!r}")
    print(f"   custom  : {cluster.custom}")
    print(f"   summary : {cluster.summary}")   # conteggi feature — sempre dal modello
