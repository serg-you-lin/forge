"""
12_to_svg.py — view model + render SVG del modello
=================================================

API forge usate:
    to_view_model   ForgeResult -> dict JSON con la geometria di OGNI feature
                    (outer, inner, fori, pieghe, incisioni, trash) + colore
    to_svg          ForgeResult -> stringa SVG (renderer del modello, MAP.md D12)
    save_svg        idem, scritto su file

`to_view_model` è ciò che consumerebbe una dashboard JS (rendering SVG/Canvas nel
browser). `to_svg` è il renderer "batterie incluse" per anteprime / report.

    python 12_to_svg.py
"""

import json
import os

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
OUTDIR = "pipeline_output"
# -------------------------------------------------------------------------

os.makedirs(OUTDIR, exist_ok=True)
base = os.path.splitext(os.path.basename(INPUT))[0]

doc = forge.load_dxf(INPUT, tolerance=TOLERANCE, label_map=LABEL_MAP)
result = forge.heal_and_detect(doc, label=base, features="all")

# 1. view model — il JSON per un renderer esterno
vm = forge.to_view_model(result, tolerance=0.05)
part = vm["parts"][0]
print(f"parti          : {vm['part_count']}")
print(f"bbox           : {vm['bbox']}")
print(f"outer          : {len(part['outer']['points'])} punti, colore {part['outer']['color']}")
print(f"fori           : {[(h['hole_type'], round(h['diameter'], 1), h['color']) for h in part['holes'][:4]]} …")
print(f"pieghe         : {len(part['bending_lines'])}")
print(f"incisioni      : {len(part['engrave_lines'])}")
print(f"trash          : {len(vm['trash'])}")
print(f"palette        : {vm['palette']}")

vm_path = os.path.join(OUTDIR, f"{base}_view.json")
with open(vm_path, "w", encoding="utf-8") as f:
    json.dump(vm, f, indent=1)
print(f"\nview model     -> {vm_path}")

# 2. SVG — sfondo scuro, fori come cerchi veri
forge.save_svg(
    result,
    os.path.join(OUTDIR, f"{base}.svg"),
    tolerance=0.05,
    include_trash=True,
    background="#1e1e1e",
    holes_as_circles=True,
)

# variante: sfondo trasparente, senza trash, per incollarlo in un documento
forge.save_svg(
    result,
    os.path.join(OUTDIR, f"{base}_clean.svg"),
    include_trash=False,
    include_annotations=False,
    background=None,
)
