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
# Anello filettato (rappresentazione 3/4 di cerchio)
# ---------------------------------------------------------------------------
# L'arco a ~270° che rappresenta la cresta della filettatura è concentrico al
# preforo e ha raggio di poco maggiore: per le filettature metriche il rapporto
# diametro nominale / diametro preforo è ~1.1–1.3 (M6: 6.0/5.0 = 1.2). Un arco
# molto più grande (bordo esterno di una flangia tonda scantonata, estremità
# raggiata di un profilo) NON è un anello filettato: lo si scarta con questa
# soglia sul rapporto dei raggi.
THREADED_ARC_MAX_RADIUS_RATIO: float = 1.6

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