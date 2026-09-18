"""
tools/thresholds.py
-------------------
Costanti e regole di detect() — zero dipendenze da formato.

Spostate da rules/thresholds.py (branch refactor/detect-overlay): verificato
che i due usi (`detect.py`, `hole_detector.py`) sono entrambi già in tools/ —
non sono soglie di dominio generiche come `rules/palette.py` (che resta in
`rules/`, mappa colore per l'intero vocabolario dei ruoli, non solo quelli di
detect).

Chi le usa:
    detect.py         — HOLE_DIAMETER_THRESHOLD come default di
                        `detect(max_drill_diameter=...)`
    hole_detector.py  — THREADED_ARC_MAX_RADIUS_RATIO

La tassonomia dei ruoli (`STRUCTURAL_ROLES`, `is_structural_role`) sta in
`model/role.py`, non qui: è un fatto sul vocabolario dei ruoli, non una soglia.
"""

# ---------------------------------------------------------------------------
# Soglia diametro fori — default di detect(max_drill_diameter=...)
# ---------------------------------------------------------------------------
# È un parametro di PROCESSO (capacità di foratura di macchina/utensile), non
# una costante di topologia: per questo la classificazione hole/inner vive in
# detect() e non in heal()/hierarchy (MAP.md D15).
# contorno circolare con Ø < soglia  → Hole (foro da punta)
# contorno circolare con Ø >= soglia → ForgeContour (inner, tagliato a contorno)
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