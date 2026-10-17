"""
forge/core/geometry/intersections.py
------------------------------------
Intersezioni pure: retta/retta, cerchio/retta, cerchio/cerchio,
polilinea/retta, e `intersections(a, b)` fra due primitive qualunque.
"""

import math
from typing import Optional, Tuple, List

from ..primitives.segments import (
    ArcSeg, CircleSeg, LineSeg, angle_from_start,
)

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


# ---------------------------------------------------------------------------
# Due primitive qualunque
# ---------------------------------------------------------------------------

_ON = 1e-9            # quanto un punto può sforare un capo e restare sul tratto
_SAME_POINT = 1e-7    # due radici più vicine di così sono lo stesso punto
CURVE_TOLERANCE = 1e-4  # discretizzazione di spline ed ellissi per incrociarle


def _exact_parts(seg) -> list:
    """Retta, arco, cerchio restano se stessi; spline ed ellisse diventano
    rette fitte (`CURVE_TOLERANCE`): non hanno un'intersezione in forma chiusa."""
    if isinstance(seg, (LineSeg, ArcSeg, CircleSeg)):
        return [seg]
    pts = [tuple(q[:2]) for q in seg.discretize(CURVE_TOLERANCE)]
    return [LineSeg(start=a, end=b) for a, b in zip(pts, pts[1:]) if a != b]


def _on_line(seg: LineSeg, pt: Point) -> bool:
    dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return False
    t = ((pt[0] - seg.start[0]) * dx + (pt[1] - seg.start[1]) * dy) / l2
    return -_ON <= t <= 1 + _ON


def _on_arc(seg, pt: Point) -> bool:
    if isinstance(seg, CircleSeg):
        return True
    s = angle_from_start(seg.center, seg.start_angle, seg.ccw, pt)
    return s <= seg._sweep() + _ON or s >= 2 * math.pi - _ON


def _meet(a, b) -> List[Point]:
    if isinstance(a, LineSeg) and isinstance(b, LineSeg):
        ix = _line_intersection(a.start, a.end, b.start, b.end)
        return [ix] if ix and _on_line(a, ix) and _on_line(b, ix) else []
    if isinstance(a, LineSeg) or isinstance(b, LineSeg):
        line, arc = (a, b) if isinstance(a, LineSeg) else (b, a)
        pts = _circle_line_intersections(arc.center[0], arc.center[1], arc.radius, line.start, line.end)
        return [p for p in pts if _on_line(line, p) and _on_arc(arc, p)]
    pts = _circle_circle_intersections(a.center[0], a.center[1], a.radius,
                                       b.center[0], b.center[1], b.radius)
    return [p for p in pts if _on_arc(a, p) and _on_arc(b, p)]


def intersections(a, b) -> List[Point]:
    """
    I punti dove due primitive si incontrano: incroci e tocchi, capi compresi.
    Esatti fra rette, archi e cerchi (forma chiusa); su spline ed ellissi
    entro `CURVE_TOLERANCE`, perché lì una forma chiusa non c'è. Due tratti
    sovrapposti (stessa retta, stesso cerchio) non danno punti: il loro
    incontro è un tratto, non un punto.
    """
    out: List[Point] = []
    for pa in _exact_parts(a):
        for pb in _exact_parts(b):
            for p in _meet(pa, pb):
                if all(_distance(p, q) > _SAME_POINT for q in out):
                    out.append(p)
    return out
