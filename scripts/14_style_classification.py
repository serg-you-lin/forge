"""
14_style_classification.py — assegnare il ruolo da nome, tratteggio e colore
============================================================================

API forge usate:
    RoleRule                          una regola: condizioni tutte vere → ruolo
    name_rules                        scorciatoia {nome: ruolo} → regole sul nome
    load_dxf(..., role_rules=...)     le regole valutate al load (D63)

Una regola combina segnali neutri — nome del gruppo sorgente, tratteggio,
colore — e vince la prima che matcha, nell'ordine in cui il chiamante le
scrive. "Tratteggiata" è un fatto del pattern (ha dei vuoti), non del nome
del linetype.

    forge.RoleRule("bending", dashed=True)
    forge.RoleRule("engrave", color="cyan")
    forge.RoleRule("construction", name_contains="constr", dashed=True)

Ogni step qui sotto isola UNA regola: se fossero cumulative, un effetto visto
nello step "colore" potrebbe venire in realtà dalla regola sul tratteggio.

    python 14_style_classification.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import os

import forge

# --- CONFIG ------------------------------------------------------------
INPUT     = r"tests/examples/lynetype-color-maps.dxf"
TOLERANCE = 0.5
NAME_ROLES = {"MARK": "engrave"}      # come negli altri script
OUTDIR    = "pipeline_output"         # come negli altri script — ignorato da git
# -------------------------------------------------------------------------

STEPS = [
    ("solo nomi",                forge.name_rules(NAME_ROLES)),
    ("solo tratteggio",          [forge.RoleRule("bending", dashed=True)]),
    ("solo colore",              [forge.RoleRule("engrave", color="cyan")]),
    ("nome + tratteggio",        [forge.RoleRule("bending", name="Bend", dashed=True)]),
]

os.makedirs(OUTDIR, exist_ok=True)


def show(tag, result):
    p = result.clusters[0]
    print(f"{tag:<20} bending={len(p.features('bending_lines')):<3} "
          f"engrave={len(p.features('engrave_lines')):<3} trash={len(result.trash_entities):<3}")


for i, (tag, rules) in enumerate(STEPS, start=1):
    doc = forge.load_dxf(INPUT, tolerance=TOLERANCE, role_rules=rules)
    result = forge.heal(doc, tolerance=TOLERANCE)
    forge.detect_flat(result)
    show(tag, result)
    out = os.path.join(OUTDIR, f"14_style_classification_{i}.dxf")
    forge.to_dxf(result, doc, include_trash=True).saveas(out)
