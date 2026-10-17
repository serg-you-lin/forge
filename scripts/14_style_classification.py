"""
14_style_classification.py — assegnare il ruolo da nome, tratteggio e colore
============================================================================

API topo usate:
    RoleRule                          una regola: condizioni tutte vere → ruolo
    name_rules                        scorciatoia {nome: ruolo} → regole sul nome
    load_dxf(..., role_rules=...)     le regole valutate al load (D63)

Una regola combina segnali neutri — nome del gruppo sorgente, tratteggio,
colore — e vince la prima che matcha, nell'ordine in cui il chiamante le
scrive. "Tratteggiata" è un fatto del pattern (ha dei vuoti), non del nome
del linetype.

    topo.RoleRule("bending", dashed=True)
    topo.RoleRule("engrave", color="cyan")
    topo.RoleRule("construction", name_contains="constr", dashed=True)

Ogni step qui sotto isola UNA regola: se fossero cumulative, un effetto visto
nello step "colore" potrebbe venire in realtà dalla regola sul tratteggio.

    python 14_style_classification.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import os

import topo

# --- CONFIG ------------------------------------------------------------
INPUT     = r"tests/examples/lynetype-color-maps.dxf"
TOLERANCE = 0.5
NAME_ROLES = {"MARK": "engrave"}      # come negli altri script
OUTDIR    = "pipeline_output"         # come negli altri script — ignorato da git
# -------------------------------------------------------------------------

STEPS = [
    ("solo nomi",                topo.name_rules(NAME_ROLES)),
    ("solo tratteggio",          [topo.RoleRule("bending", dashed=True)]),
    ("solo colore",              [topo.RoleRule("engrave", color="cyan")]),
    ("nome + tratteggio",        [topo.RoleRule("bending", name="Bend", dashed=True)]),
]

os.makedirs(OUTDIR, exist_ok=True)


def show(tag, result):
    # i ruoli assegnati al load finiscono in trash col loro ruolo intatto:
    # quante entità per ruolo
    from collections import Counter
    roles = Counter(str(getattr(t, "role", "?")) for t in result.trash_entities)
    print(f"{tag:<20} {dict(roles)}")


for i, (tag, rules) in enumerate(STEPS, start=1):
    doc = topo.load_dxf(INPUT, tolerance=TOLERANCE, role_rules=rules)
    result = topo.heal(doc, tolerance=TOLERANCE)
    show(tag, result)
    out = os.path.join(OUTDIR, f"14_style_classification_{i}.dxf")
    topo.to_dxf(result, doc, include_trash=True).saveas(out)
