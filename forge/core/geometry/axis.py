"""
forge/core/geometry/axis.py
---------------------------
Fatti su segmenti orizzontali e verticali: intervalli e loro copertura,
rettangoli i cui quattro lati sono coperti da segmenti, linee che attraversano
un rettangolo, quanta parte di un disegno è allineata agli assi. Geometria
pura: che un rettangolo sia una cornice o un cartiglio, o che una vista sia
ortogonale, lo dice il consumatore (MAP.md D94).

Un "tratto" è qualunque oggetto con `start` e `end` (un `Edge`, un `LineSeg`):
chi chiama passa solo tratti dritti.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from shapely.geometry import box

from ..primitives.segments import LineSeg

Interval = Tuple[float, float]
Bounds = Tuple[float, float, float, float]

AXIS_EPS = 0.5             # scarto massimo dall'asse di un tratto orizzontale / verticale
CLUSTER_TOLERANCE = 1.5    # due coordinate più vicine di così sono la stessa
SIDE_COVERAGE = 0.85       # frazione minima di un lato coperta dai tratti


# ---------------------------------------------------------------------------
# Intervalli
# ---------------------------------------------------------------------------

def merge_intervals(intervals: Iterable[Interval], tolerance: float = 0.0) -> List[Interval]:
    """Unisce gli intervalli che si sovrappongono o distano al più `tolerance`, in ordine."""
    merged: List[Interval] = []
    for a, b in sorted(intervals):
        if merged and a <= merged[-1][1] + tolerance:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def interval_coverage(intervals: Iterable[Interval], lo: float, hi: float) -> float:
    """Frazione di [lo, hi] coperta dall'unione degli intervalli."""
    if hi <= lo:
        return 0.0
    clipped = [(max(lo, a), min(hi, b)) for a, b in intervals if min(hi, b) > max(lo, a)]
    return sum(b - a for a, b in merge_intervals(clipped)) / (hi - lo)


def cluster_values(values: Iterable[float], tolerance: float = CLUSTER_TOLERANCE) -> List[float]:
    """
    I valori ordinati, tenendo per ogni gruppo il più piccolo: un valore entro
    `tolerance` dall'ultimo tenuto appartiene al suo gruppo.
    """
    out: List[float] = []
    for v in sorted(values):
        if out and v - out[-1] <= tolerance:
            continue
        out.append(v)
    return out


# ---------------------------------------------------------------------------
# Tratti sugli assi
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AxisLine:
    """
    Un tratto orizzontale o verticale.

    item: il tratto ricevuto
    lo, hi: l'intervallo che copre lungo il suo asse (x per un orizzontale)
    at: la coordinata costante (y per un orizzontale), media dei due capi
    """
    item: object
    lo: float
    hi: float
    at: float


def axis_lines(items: Iterable, eps: float = AXIS_EPS) -> Tuple[List[AxisLine], List[AxisLine]]:
    """(orizzontali, verticali): i tratti che si scostano dall'asse al più di `eps`; gli altri non compaiono."""
    horiz: List[AxisLine] = []
    vert: List[AxisLine] = []
    for item in items:
        (x0, y0), (x1, y1) = item.start, item.end
        if abs(y0 - y1) <= eps and abs(x0 - x1) > eps:
            horiz.append(AxisLine(item, min(x0, x1), max(x0, x1), (y0 + y1) / 2.0))
        elif abs(x0 - x1) <= eps and abs(y0 - y1) > eps:
            vert.append(AxisLine(item, min(y0, y1), max(y0, y1), (x0 + x1) / 2.0))
    return horiz, vert


def _covered_at(lines: Sequence[AxisLine], at: float, lo: float, hi: float, tol: float) -> float:
    return interval_coverage([(l.lo, l.hi) for l in lines if abs(l.at - at) <= tol], lo, hi)


# ---------------------------------------------------------------------------
# Rettangoli coperti e linee che li attraversano
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CoveredRectangle:
    """
    Un rettangolo allineato agli assi i cui quattro lati sono coperti da tratti.

    polygon: il rettangolo (shapely)
    items:   i tratti che stanno sui suoi lati, compresi quelli corti collineari
    """
    polygon: object
    items: tuple

    @property
    def bbox(self) -> Bounds:
        return tuple(self.polygon.bounds)

    @property
    def area(self) -> float:
        return self.polygon.area

    @property
    def long_side(self) -> float:
        minx, miny, maxx, maxy = self.polygon.bounds
        return max(maxx - minx, maxy - miny)

    @property
    def short_side(self) -> float:
        minx, miny, maxx, maxy = self.polygon.bounds
        return min(maxx - minx, maxy - miny)

    @property
    def ratio(self) -> float:
        """Lato lungo / lato corto; 0 per un rettangolo degenere."""
        s = self.short_side
        return (self.long_side / s) if s else 0.0


def covered_rectangles(items: Sequence, min_side: float, eps: float = AXIS_EPS,
                       cluster_tolerance: float = CLUSTER_TOLERANCE,
                       coverage: float = SIDE_COVERAGE) -> List[CoveredRectangle]:
    """
    I rettangoli allineati agli assi con ogni lato coperto almeno per
    `coverage` da tratti, costruiti sulle coordinate dei tratti lunghi almeno
    `min_side`. Due coordinate entro `cluster_tolerance` sono la stessa; un
    tratto sta su un lato entro `2 * eps`. Senza `polygonize`: un bordo pieno
    di tacche resta un rettangolo.
    """
    items = list(items)
    if len(items) < 4:
        return []
    horiz, vert = axis_lines(items, eps)
    long_h = [h for h in horiz if (h.hi - h.lo) >= min_side]
    long_v = [v for v in vert if (v.hi - v.lo) >= min_side]
    if len(long_h) < 2 or len(long_v) < 2:
        return []
    ys = cluster_values([h.at for h in long_h], cluster_tolerance)
    xs = cluster_values([v.at for v in long_v], cluster_tolerance)
    tol = 2 * eps

    out: List[CoveredRectangle] = []
    seen: set = set()
    for i in range(len(ys)):
        for j in range(i + 1, len(ys)):
            y_lo, y_hi = ys[i], ys[j]
            for k in range(len(xs)):
                for m in range(k + 1, len(xs)):
                    x_lo, x_hi = xs[k], xs[m]
                    if any(_covered_at(horiz, y, x_lo, x_hi, tol) < coverage for y in (y_lo, y_hi)) \
                            or any(_covered_at(vert, x, y_lo, y_hi, tol) < coverage for x in (x_lo, x_hi)):
                        continue
                    key = (round(x_lo, 1), round(y_lo, 1), round(x_hi, 1), round(y_hi, 1))
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(CoveredRectangle(box(x_lo, y_lo, x_hi, y_hi),
                                                tuple(_on_border(x_lo, y_lo, x_hi, y_hi, items, tol))))
    return out


def _on_border(x_lo, y_lo, x_hi, y_hi, items, tol) -> list:
    owned = []
    for item in items:
        (x0, y0), (x1, y1) = item.start, item.end
        on_h = abs(y0 - y1) <= tol and (abs((y0 + y1) / 2 - y_lo) <= tol or abs((y0 + y1) / 2 - y_hi) <= tol) \
            and min(x0, x1) >= x_lo - tol and max(x0, x1) <= x_hi + tol
        on_v = abs(x0 - x1) <= tol and (abs((x0 + x1) / 2 - x_lo) <= tol or abs((x0 + x1) / 2 - x_hi) <= tol) \
            and min(y0, y1) >= y_lo - tol and max(y0, y1) <= y_hi + tol
        if on_h or on_v:
            owned.append(item)
    return owned


def spanning_lines(bounds: Bounds, items: Iterable, coverage: float = SIDE_COVERAGE,
                   eps: float = AXIS_EPS,
                   cluster_tolerance: float = CLUSTER_TOLERANCE) -> Tuple[List[float], List[float]]:
    """
    (ys, xs): le coordinate delle linee strettamente interne a `bounds` (bordo
    escluso, entro `2 * eps`) che lo attraversano per almeno `coverage` della
    larghezza (le orizzontali) o dell'altezza (le verticali), ordinate.
    """
    horiz, vert = axis_lines(items, eps)
    xmin, ymin, xmax, ymax = bounds
    tol = 2 * eps
    ys = [y for y in cluster_values([h.at for h in horiz if ymin + tol < h.at < ymax - tol], cluster_tolerance)
          if _covered_at(horiz, y, xmin, xmax, tol) >= coverage]
    xs = [x for x in cluster_values([v.at for v in vert if xmin + tol < v.at < xmax - tol], cluster_tolerance)
          if _covered_at(vert, x, ymin, ymax, tol) >= coverage]
    return ys, xs


# ---------------------------------------------------------------------------
# Misure
# ---------------------------------------------------------------------------

def items_inside(bounds: Bounds, items: Iterable, margin: float = 0.0) -> list:
    """I tratti con entrambi i capi dentro `bounds` allargato di `margin`, nell'ordine dato."""
    minx, miny, maxx, maxy = bounds[0] - margin, bounds[1] - margin, bounds[2] + margin, bounds[3] + margin

    def inside(pt) -> bool:
        return minx <= pt[0] <= maxx and miny <= pt[1] <= maxy

    return [i for i in items if inside(i.start) and inside(i.end)]


def sides_on_border(bounds: Bounds, border: Bounds, tolerance: float) -> List[str]:
    """I lati di `bounds` ("left", "bottom", "right", "top") che stanno sul
    lato omologo di `border`, entro `tolerance`."""
    names = ("left", "bottom", "right", "top")
    return [n for n, a, b in zip(names, bounds, border) if abs(a - b) <= tolerance]


def axis_aligned_share(segments: Iterable, angle_tolerance: float) -> Optional[float]:
    """
    Frazione della lunghezza dei `LineSeg` di `segments` orizzontale o
    verticale entro `angle_tolerance` gradi; None se non ci sono `LineSeg`.
    """
    axis = total = 0.0
    for seg in segments:
        if not isinstance(seg, LineSeg):
            continue
        dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
        length = math.hypot(dx, dy)
        angle = math.degrees(math.atan2(dy, dx)) % 90
        if min(angle, 90 - angle) <= angle_tolerance:
            axis += length
        total += length
    return axis / total if total else None
