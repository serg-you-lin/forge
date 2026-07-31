"""
rules/thresholds.py
-------------------
Costanti e regole del dominio manifatturiero — zero dipendenze da formato.

Queste soglie appartengono al core perché sono decisioni geometriche/semantiche
indipendenti da come il file è scritto (DXF, SVG, PDF, ...).

Chi le usa:
    hierarchy.py  — HOLE_DIAMETER_THRESHOLD per classificare hole vs inner
    detect.py     — VALID_WORK_TYPES per validare i role in ingresso
"""

# ---------------------------------------------------------------------------
# Soglia diametro fori
# ---------------------------------------------------------------------------
# CIRCLE con diametro < soglia → Hole
# CIRCLE con diametro >= soglia → ForgeContour (inner)
HOLE_DIAMETER_THRESHOLD: float = 32.1   # mm

# ---------------------------------------------------------------------------
# Work type validi — semantica core
# Corrispondono ai valori di ContourRole che detect() sa gestire.
# ---------------------------------------------------------------------------
VALID_WORK_TYPES = frozenset({
    "outer",
    "hole",
    "bend",
    "bending",    # alias accettato in ingresso
    "frame",
    "inner",
    "engrave",
    "marking",
    "countersink",
    "threaded_hole",
})

from ..model.role import ContourRole

STRUCTURAL_ROLES = frozenset({
    ContourRole.OUTER,
    ContourRole.INNER,
    ContourRole.HOLE,
})