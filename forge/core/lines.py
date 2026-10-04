"""
forge/core/lines.py
-------------------
Fatti fra rette e poligoni: distanza da una retta, tratti sulla stessa retta,
file di tratti unite attraverso dei poligoni, una corda che divide un
poligono. Geometria pura: che quella corda sia una piega lo dice il
consumatore (MAP.md D93).

Un tratto è una `LineString` o una coppia di punti `(start, end)`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence, Tuple

from shapely.geometry import LineString
from shapely.ops import split

Point = Tuple[float, float]

COLLINEAR_TOLERANCE = 0.1        # distanza massima dalla retta, unità del disegno
COLLINEAR_ANGLE_TOLERANCE = 1e-6  # differenza massima di direzione, radianti


def _ends(item) -> Tuple[Point, Point]:
    """I due capi di un tratto: `LineString` (primo e ultimo punto) o `(start, end)`."""
    if hasattr(item, "coords"):
        coords = list(item.coords)
        return tuple(coords[0]), tuple(coords[-1])
    start, end = item
    return tuple(start), tuple(end)


def point_line_distance(point: Point, a: Point, b: Point) -> float:
    """Distanza di `point` dalla retta infinita per `a`, `b`; da `a` se i due coincidono."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return math.dist(point, a)
    return abs(dy * (point[0] - a[0]) - dx * (point[1] - a[1])) / length


def are_collinear(a, b, tolerance: float = COLLINEAR_TOLERANCE,
                  angle_tolerance: float = COLLINEAR_ANGLE_TOLERANCE) -> bool:
    """
    I tratti `a` e `b` stanno sulla stessa retta infinita: direzioni uguali
    entro `angle_tolerance` (radianti, a meno del verso) e i due capi di `b`
    entro `tolerance` dalla retta di `a`.
    """
    (a0, a1), (b0, b1) = _ends(a), _ends(b)
    ang_a = math.atan2(a1[1] - a0[1], a1[0] - a0[0]) % math.pi
    ang_b = math.atan2(b1[1] - b0[1], b1[0] - b0[0]) % math.pi
    diff = abs(ang_a - ang_b)
    if min(diff, math.pi - diff) > angle_tolerance:
        return False
    return all(point_line_distance(q, a0, a1) <= tolerance for q in (b0, b1))


def group_collinear_lines(lines: list, tolerance: float = COLLINEAR_TOLERANCE,
                          angle_tolerance: float = COLLINEAR_ANGLE_TOLERANCE) -> list:
    """
    Tratti raggruppati per retta: [[L1, L2], [L3], ...]. Ogni gruppo prende la
    retta del suo primo tratto, nell'ordine dato.
    """
    groups = []
    assigned = set()
    for i, line in enumerate(lines):
        if i in assigned:
            continue
        group = [line]
        assigned.add(i)
        for j, other in enumerate(lines):
            if j not in assigned and are_collinear(line, other, tolerance, angle_tolerance):
                group.append(other)
                assigned.add(j)
        groups.append(group)
    return groups


def splits_polygon(polygon, start: Point, end: Point, reach: float = 0.0) -> bool:
    """La corda `start`-`end`, prolungata di `reach` ai due capi, divide `polygon` in due o più parti."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    norm = math.hypot(dx, dy)
    if norm == 0:
        return False
    ux, uy = dx / norm * reach, dy / norm * reach
    cutter = LineString([(start[0] - ux, start[1] - uy), (end[0] + ux, end[1] + uy)])
    return len(split(polygon, cutter).geoms) >= 2


@dataclass(frozen=True)
class CollinearRun:
    """
    Tratti sulla stessa retta, in fila lungo di essa.

    start, end: i capi esterni della fila
    members:    indici dei tratti nell'input, nell'ordine lungo la retta
    """
    start: Point
    end: Point
    members: Tuple[int, ...]


def bridged_runs(segments: Sequence, bridges: Sequence, tolerance: float = COLLINEAR_TOLERANCE,
                 angle_tolerance: float = COLLINEAR_ANGLE_TOLERANCE) -> list[CollinearRun]:
    """
    File di due o più tratti sulla stessa retta in cui lo spazio fra un tratto
    e il successivo sta tutto dentro uno dei poligoni di `bridges`. Un tratto
    sta in una sola fila; quelli rimasti da soli non compaiono.
    """
    ends = [_ends(s) for s in segments]
    runs: list[CollinearRun] = []
    used: set[int] = set()
    for i, (p0, p1) in enumerate(ends):
        if i in used:
            continue
        group = [j for j in range(len(ends))
                 if j not in used and are_collinear((p0, p1), ends[j], tolerance, angle_tolerance)]
        used.update(group)
        if len(group) < 2:
            continue
        norm = math.dist(p0, p1)
        ux, uy = (p1[0] - p0[0]) / norm, (p1[1] - p0[1]) / norm
        along = lambda q: (q[0] - p0[0]) * ux + (q[1] - p0[1]) * uy
        spans = sorted(((along(lo), lo, hi, j) for j in group
                        for lo, hi in [sorted(ends[j], key=along)]), key=lambda t: t[0])
        chain = [spans[0]]
        for span in spans[1:]:
            gap = LineString([chain[-1][2], span[1]])
            if gap.length > 0 and any(p.buffer(1e-6).covers(gap) for p in bridges):
                chain.append(span)
                continue
            if len(chain) >= 2:
                runs.append(CollinearRun(chain[0][1], chain[-1][2], tuple(t[3] for t in chain)))
            chain = [span]
        if len(chain) >= 2:
            runs.append(CollinearRun(chain[0][1], chain[-1][2], tuple(t[3] for t in chain)))
    return runs
