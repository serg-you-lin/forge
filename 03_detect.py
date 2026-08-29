"""
03_detect.py — classificazione delle feature
============================================

API forge usate:
    detect         classifica le feature dentro le parti già trovate da heal()
    ALL_FEATURES   la costante iterabile {"holes", "bending", "engrave"}

detect(result) NUDO fa solo il minimo: la lane label_map (autoritativa) +
pulizia topologia. I fori arrivano SOLO dai layer mappati in label_map; nessun
foro dedotto dalla geometria — è il default per il taglio laser.
Le lane geometriche sono OPT-IN via `features`:

    detect(result, "holes")     cerchi Ø < max_drill_diameter -> Hole
    detect(result, "bending")   linee di piega geometriche
    detect(result, "engrave")   inferenza incisioni (oggi no-op)
    detect(result, "all")       tutte e tre

detect() MUTA il result in-place E lo ritorna.

    python 03_detect.py
"""

import forge

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/examples/Multifeature.dxf"   # ha Filettati/Svasati/Piega/MARK
TOLERANCE = 0.5
LABEL_MAP = {
    "Filettati": "threaded_hole",
    "Svasati":   "countersink",
    "Piega":     "bending",
    "MARK":      "engrave",
}
MAX_DRILL_DIAMETER = 32.1   # parametro di PROCESSO: sopra questo Ø non è un foro da punta
# -------------------------------------------------------------------------

print(f"ALL_FEATURES = {forge.ALL_FEATURES}\n")


def show(tag, result):
    p = result.parts[0]
    print(f"{tag:<28} holes={len(p.holes):<3} inners={len(p.inners):<3} "
          f"bending={len(p.bending_lines):<3} engrave={len(p.engrave_lines):<3}")


# 1. detect nudo — solo label_map + topologia
doc = forge.load_dxf(INPUT, tolerance=TOLERANCE, label_map=LABEL_MAP)
r = forge.heal(doc, tolerance=TOLERANCE)
forge.detect(r)
show("detect(result)", r)

# 2. solo fori
doc = forge.load_dxf(INPUT, tolerance=TOLERANCE, label_map=LABEL_MAP)
r = forge.heal(doc, tolerance=TOLERANCE)
forge.detect(r, "holes", max_drill_diameter=MAX_DRILL_DIAMETER)
show("detect(result, 'holes')", r)

# 3. tutto
doc = forge.load_dxf(INPUT, tolerance=TOLERANCE, label_map=LABEL_MAP)
r = forge.heal(doc, tolerance=TOLERANCE)
forge.detect(r, "all", max_drill_diameter=MAX_DRILL_DIAMETER, bending_tolerance=1.0)
show("detect(result, 'all')", r)

# dettaglio fori tipati
print()
for i, h in enumerate(r.parts[0].holes):
    print(f"   hole {i:<2} type={h.hole_type:<12} Ø={h.diameter:.2f}  "
          f"center={tuple(round(c, 1) for c in h.center)}  "
          f"source={h.source} conf={h.confidence}")
print("\n   summary:", r.parts[0].summary)
