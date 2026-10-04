"""
forge/core/geometry/intersections.py
------------------------------------
Intersezioni pure: retta/retta, cerchio/retta, cerchio/cerchio,
polilinea/retta.
"""

import math
from typing import Optional, Tuple, List

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Intersezioni geometriche pure — usate da core/healing/gap_solver.py
# ---------------------------------------------------------------------------

def _line_intersection(p1: Point, p2: Point,
                       p3: Point, p4: Point) -> Optional[Point]:
    """Intersezione tra retta (p1,p2) e retta (p3,p4). None se parallele."""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-10:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def _distance(p1: Point, p2: Point) -> float:
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)


def _circle_line_intersections(cx: float, cy: float, r: float,
                                p1: Point, p2: Point) -> List[Point]:
    """
    Intersezioni tra la circonferenza (cx, cy, r) e la retta infinita (p1, p2).
    Restituisce lista di 0, 1 o 2 punti.
    """
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    fx = p1[0] - cx
    fy = p1[1] - cy

    a = dx * dx + dy * dy
    if a < 1e-12:
        return []
    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - r * r

    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return []

    results = []
    for sign in (-1, 1):
        t = (-b + sign * math.sqrt(max(discriminant, 0))) / (2 * a)
        results.append((p1[0] + t * dx, p1[1] + t * dy))

    if discriminant < 1e-10:
        return [results[0]]
    return results


def _circle_circle_intersections(cx1: float, cy1: float, r1: float,
                                  cx2: float, cy2: float, r2: float) -> List[Point]:
    """Intersezioni tra due circonferenze. Restituisce 0, 1 o 2 punti."""
    d = _distance((cx1, cy1), (cx2, cy2))
    if d < 1e-10 or d > r1 + r2 + 1e-10 or d < abs(r1 - r2) - 1e-10:
        return []

    a    = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h_sq = r1 * r1 - a * a
    if h_sq < 0:
        return []
    h = math.sqrt(max(h_sq, 0))

    mx = cx1 + a * (cx2 - cx1) / d
    my = cy1 + a * (cy2 - cy1) / d

    if h < 1e-10:
        return [(mx, my)]

    px = h * (cy2 - cy1) / d
    py = h * (cx2 - cx1) / d
    return [(mx + px, my - py), (mx - px, my + py)]


def _closest_to(candidates: List[Point], ref: Point) -> Optional[Point]:
    """Restituisce il punto più vicino a ref tra i candidati."""
    if not candidates:
        return None
    return min(candidates, key=lambda p: _distance(p, ref))


def polyline_line_intersections(
    points: List[Point], closed: bool, p1: Point, p2: Point
) -> List[Tuple[Point, int]]:
    """
    Intersezioni fra la retta infinita (p1, p2) e la spezzata `points` (ogni
    coppia di punti consecutivi è un lato; se `closed`, anche l'ultimo->primo).

    Generalizza `_circle_line_intersections` a qualunque contorno già
    discretizzato in punti — arco, polilinea, cerchio: una volta discretizzato
    è comunque solo una sequenza di lati retti, a prescindere da cos'era in
    origine (usato da `tools/tabs.py::bridge_tabs`).

    Ritorna `(punto, indice)` per ogni intersezione che cade DENTRO il lato
    (non sul suo prolungamento infinito) — `indice` è `i` tale che il lato è
    `(points[i], points[(i+1) % n])`.
    """
    n = len(points)
    if n < 2:
        return []
    edge_indices = range(n) if closed else range(n - 1)
    results: List[Tuple[Point, int]] = []
    for i in edge_indices:
        a, b = points[i], points[(i + 1) % n]
        if a == b:
            continue
        ix = _line_intersection(a, b, p1, p2)
        if ix is None:
            continue
        eps = 1e-9
        if (min(a[0], b[0]) - eps <= ix[0] <= max(a[0], b[0]) + eps
                and min(a[1], b[1]) - eps <= ix[1] <= max(a[1], b[1]) + eps):
            results.append((ix, i))
    return results
