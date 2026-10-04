"""
00_inspect.py — l'ispettore a 3 livelli
=======================================

API forge usate:
    inspect_file        orchestratore: apre e stampa i 3 livelli in fila
    inspect_dxf         livello 1 — entità DXF grezze ("cosa c'è nel file")
    inspect_document    livello 2 — edge / primitive / grafo ("cosa ha capito l'adapter")
    inspect_result      livello 3 — il modello ("cosa ha prodotto forge")

È il primo strumento da usare quando un file reale non torna. Non salva niente,
stampa tutto su stdout.

    python 00_inspect.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import forge

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/data/Multifeature.dxf"   # non tracciato: usa un tuo file se manca
TOLERANCE = 0.5
NAME_ROLES = {
    "Filettati": "threaded_hole",
    "Svasati":   "countersink",
    "Piega":     "bending",
    "MARK":      "engrave",
}
# -------------------------------------------------------------------------

print("#" * 70)
print("# inspect_file — i 3 livelli in fila")
print("#" * 70)
forge.inspect_file(
    INPUT,
    tolerance=TOLERANCE,
    role_rules=forge.name_rules(NAME_ROLES),
    run_heal=True,
    entities=True,   # dettaglio entità nel livello 1
    coords=False,    # coordinate nel livello 3 (verboso)
)

# I tre livelli si possono anche chiamare uno per volta, su oggetti diversi:
#
#   forge.inspect_dxf(INPUT, entities=True, limit=40)
#
#   doc = forge.load_dxf(INPUT, tolerance=TOLERANCE, role_rules=forge.name_rules(NAME_ROLES))
#   forge.inspect_document(doc, graph=True, limit=60)
#
#   result = forge.heal(doc)
#   forge.inspect_result(result, coords=False)
