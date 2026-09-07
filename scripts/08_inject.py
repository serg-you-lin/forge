"""
08_inject.py — arricchimento CAM dai testi del disegno
=====================================================

API forge usate:
    extract_forge_texts      msp ezdxf -> list[ForgeText] (content + position) — questo va a inject()
    extract_texts_from_msp   msp ezdxf -> list[str] nudi (per chi vuole solo il testo)
    inject                   passa a un data_injector i testi dentro l'outer di ogni parte

inject() è OPZIONALE. Fa una sola cosa: se passi `data_injector` —
callable(cluster, list[str]) -> dict — mette il dict restituito in cluster.custom
(codice pezzo, materiale, spessore, ...). Senza data_injector non fa nulla.

I CONTEGGI delle feature NON si fanno qui: sono cluster.summary (property derivata).

    python 08_inject.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import ezdxf
import forge

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/examples/Multifeature.dxf"
TOLERANCE = 0.5
LABEL_MAP = {"Filettati": "threaded_hole", "Svasati": "countersink",
             "Piega": "bending", "MARK": "engrave"}
# -------------------------------------------------------------------------

# I testi vanno letti dal msp ezdxf — dopo load_dxf() il msp non esiste più,
# quindi qui si riapre il file solo per questo.
msp = ezdxf.readfile(INPUT).modelspace()
texts = forge.extract_forge_texts(msp)          # list[ForgeText] — content + position
print(f"testi trovati: {[t.content for t in texts]}")
print(f"(nudi)       : {forge.extract_texts_from_msp(msp)}")

doc = forge.load_dxf(INPUT, tolerance=TOLERANCE, label_map=LABEL_MAP)
result = forge.heal_and_detect(doc, label="P-1024", features="all")


# data_injector: riceve la parte e SOLO i testi che ricadono geometricamente
# dentro il suo outer (già filtrati da inject). Ritorna il dict per cluster.custom.
# NB: in Multifeature.dxf le sigle "A"/"B" sono quote fuori dal contorno, quindi
# qui `testi_nella_parte` contiene solo i testi interni — è il comportamento
# corretto (ogni parte prende i propri testi, non quelli del vicino).
def leggi_cartiglio(cluster, testi_nella_parte):
    print(f"   [injector] parte {cluster.label}: testi interni = {testi_nella_parte}")
    code = next((t for t in testi_nella_parte if t.strip()), None)
    return {
        "part_code": code or "N/D",
        "material":  "S275JR",
        "thickness": 2.0,
        "quantity":  1,
    }


forge.inject(result, data_injector=leggi_cartiglio, texts=texts)

for i, cluster in enumerate(result.clusters):
    print(f"\nParte {i}  {cluster.label!r}")
    print(f"   custom  : {cluster.custom}")
    print(f"   summary : {cluster.summary}")   # conteggi feature — sempre dal modello
