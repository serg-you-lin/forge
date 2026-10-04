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

import _paths  # noqa: F401  — chdir alla radice del repo

import json
import os

import forge

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/data/Multifeature.dxf"
TOLERANCE = 0.5
NAME_ROLES = {
    "Filettati": "threaded_hole",
    "Svasati":   "countersink",
    "Piega":     "bending",
    "MARK":      "engrave",
}
OUTDIR = "pipeline_output"
# -------------------------------------------------------------------------

os.makedirs(OUTDIR, exist_ok=True)
base = os.path.splitext(os.path.basename(INPUT))[0]

doc = forge.load_dxf(INPUT, tolerance=TOLERANCE, role_rules=forge.name_rules(NAME_ROLES))
result = forge.heal(doc, label=base)

# 1. view model — il JSON per un renderer esterno
vm = forge.to_view_model(result, tolerance=0.05)
cluster = vm["clusters"][0]
print(f"parti          : {vm['cluster_count']}")
print(f"bbox           : {vm['bbox']}")
print(f"outer          : {len(cluster['outer']['points'])} punti, colore {cluster['outer']['color']}")
print(f"inner          : {len(cluster['inners'])}")
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
    true_circles=True,
)

# variante: sfondo trasparente, senza trash, per incollarlo in un documento
forge.save_svg(
    result,
    os.path.join(OUTDIR, f"{base}_clean.svg"),
    include_trash=False,
    include_annotations=False,
    background=None,
)
