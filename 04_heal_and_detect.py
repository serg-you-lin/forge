"""
04_heal_and_detect.py — la via del 90%
======================================

API forge usate:
    heal_and_detect    heal() + detect() in un colpo solo

A differenza di detect() nudo, qui features="all" è il DEFAULT: fori, pieghe e
incisioni vengono classificati. detect() viene saltato se heal() non produce
parti valide (il result torna comunque, is_valid=False).

Questo è lo snippet da mettere nel README / negli altri script.

    python 04_heal_and_detect.py
"""

import forge

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/examples/Multifeature.dxf"
TOLERANCE = 0.5
LABEL_MAP = {
    "Filettati": "threaded_hole",
    "Svasati":   "countersink",
    "Piega":     "bending",
    "MARK":      "engrave",
}
# -------------------------------------------------------------------------

doc = forge.load_dxf(INPUT, tolerance=TOLERANCE, label_map=LABEL_MAP)

result = forge.heal_and_detect(
    doc,
    label="P-1024",
    features="all",              # default; oppure "holes" / ("holes", "bending") / None
    max_drill_diameter=32.1,
    bending_tolerance=1.0,
)

if not result.is_valid:
    raise SystemExit(f"non valido: {result.errors}")

for i, part in enumerate(result.parts):
    s = part.summary
    print(f"Parte {i}  {part.label!r}")
    print(f"   area           : {part.area:.1f} mm²")
    print(f"   fori piani      : {s['plain_holes_count']}")
    print(f"   svasati         : {s['countersink_count']}")
    print(f"   filettati       : {s['threaded_holes_count']}")
    print(f"   pieghe          : {s['bending_lines']}")
    print(f"   incisioni (mm)  : {s['total_engrave_length']:.1f}")
    print(f"   contorni interni: {len(part.inners)}")
