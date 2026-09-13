"""
forge/tools/tabs.py
--------------------
Taglio di linguette (ponticelli) in una sequenza di punti grezza: rimuove un
tratto di lunghezza nota, centrato su una posizione nota, lasciando un
ponticello non tagliato in quel punto — così un contorno (o un anello
concentrico rispetto a un altro) resta fisicamente attaccato al resto della
lamiera dopo il taglio.

Meccanica pura, deterministica dato i parametri: questa funzione NON decide
dove/quante linguette servono — quella è una decisione di processo del
chiamante (come lo sono le soglie di `detect()`). Riceve posizione e
larghezza già decise e produce gli stretch aperti risultanti, pronti per
`detect_corners(..., closed=False)` + `fit_primitives` (o
`simplify_points(..., closed=False)`).

Va applicata sui punti GREZZI, prima di qualunque fit — il contenimento/
gerarchia (`heal_and_detect`) va calcolato PRIMA, sugli stessi punti grezzi
non ancora tagliati (vedi smoother/MAP.md D5).

Non è nel contratto pubblico flat di forge (`forge.*`): va importato
esplicitamente da `forge.tools.tabs`, come `detect_corners`/`fit_primitives`
prima di essere provato da un caso reale — un utente che si aspetta
`forge.*` sempre puramente ricostruttivo non deve incappare per caso in
qualcosa che aggiunge un gap che nel disegno sorgente non c'era (MAP.md D39).

Nota: la rappresentazione della posizione di una linguetta (oggi un indice in
`points`) è ancora una decisione aperta, non definitiva — vedi MAP.md D39.
"""

from __future__ import annotations

from typing import List, Tuple

from ..core.primitives.segments import Point
from ..core.geometry import _distance

__all__ = ["cut_tabs"]


def _cumulative_lengths(points: List[Point], closed: bool) -> Tuple[List[float], float]:
    """
    `(cum, total)`: `cum[i]` è la distanza cumulata da `points[0]` a
    `points[i]`; `total` è la lunghezza dell'intera sequenza (per un contorno
    chiuso, include anche il segmento di chiusura verso `points[0]`).
    """
    cum = [0.0]
    for a, b in zip(points, points[1:]):
        cum.append(cum[-1] + _distance(a, b))
    total = cum[-1]
    if closed:
        total += _distance(points[-1], points[0])
    return cum, total


def cut_tabs(
    points: List[Point],
    closed: bool,
    tab_positions: List[int],
    tab_width: float,
) -> List[List[Point]]:
    """
    Rimuove, centrato su ciascun indice di `tab_positions`, un tratto lungo
    `tab_width` (distanza cumulata lungo il perimetro, non numero di punti —
    la densità dei punti non è affidabile).

    Args:
        points:         sequenza di punti (x, y), ordinata, grezza.
        closed:         True se `points` è un contorno chiuso.
        tab_positions:  indici in `points`, il centro di ciascuna linguetta.
        tab_width:      lunghezza del gap, in unità di `points`.

    Ritorna la lista degli stretch **aperti** risultanti (una lista vuota se
    le linguette coprono l'intera sequenza).
    """
    n = len(points)
    if n < 2 or not tab_positions:
        return [list(points)]

    cum, total = _cumulative_lengths(points, closed)
    half = tab_width / 2.0

    def _in_any_gap(s: float) -> bool:
        for idx in tab_positions:
            center = cum[idx]
            if closed:
                d = abs(s - center)
                d = min(d, total - d)
                if d <= half:
                    return True
            elif center - half <= s <= center + half:
                return True
        return False

    kept_mask = [not _in_any_gap(cum[i]) for i in range(n)]
    if all(kept_mask):
        return [points + [points[0]]] if closed else [list(points)]
    if not any(kept_mask):
        return []

    if closed:
        # Ruota l'array in modo che inizi subito dopo un gap (un punto tenuto
        # il cui precedente non lo è), così uno stretch non si spezza
        # artificialmente sul bordo dell'array — stesso trucco già usato in
        # tools/simplify_points.py::_split_into_stretches.
        start = next(i for i in range(n) if kept_mask[i] and not kept_mask[i - 1])
        order = list(range(start, n)) + list(range(start))
    else:
        order = list(range(n))

    stretches: List[List[Point]] = []
    current: List[Point] = []
    for i in order:
        if kept_mask[i]:
            current.append(points[i])
        elif current:
            stretches.append(current)
            current = []
    if current:
        stretches.append(current)
    return stretches
