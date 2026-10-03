"""
core/healing/outer_scan.py
--------------------------
Classificazione dei bordi esterni per ray casting: quali Edge sono, ad
almeno una quota, il primo o l'ultimo punto incontrato da un raggio che
attraversa il disegno. Non ricostruisce il contorno — lo cuciono dopo
gap_solver e loop_finder, sugli Edge originali.

Proprietà globale (min/max su tutta la quota), non connettività locale:
funziona anche dove il grafo è ambiguo (edge quasi coincidenti che
convergono sugli stessi nodi). Scansione su entrambi gli assi, perché un
raggio orizzontale non vede mai un edge orizzontale.

Puro: solo Edge e primitive, nessun formato.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

from ..topology.edge import Edge
from ..primitives.segments import (
    angle_from_start, point_on_circle,
    LineSeg, ArcSeg, CircleSeg, SplineSeg, EllipseSeg, DEFAULT_TOLERANCE,
)

Point = Tuple[float, float]

AXIS_Y = "y"   # raggio orizzontale a quota y, estremi in x
AXIS_X = "x"   # raggio verticale a quota x, estremi in y

SIDE_MIN = "min"
SIDE_MAX = "max"

_EPS = 1e-9


# ---------------------------------------------------------------------------
# Risultato
# ---------------------------------------------------------------------------

@dataclass
class OuterHit:
    """Un raggio per cui l'Edge è stato l'estremo."""
    axis:   str      # AXIS_Y / AXIS_X
    level:  float    # quota del raggio
    side:   str      # SIDE_MIN / SIDE_MAX
    point:  Point    # punto d'intersezione reale


@dataclass
class OuterCandidates:
    """Edge candidati a bordo esterno, con i raggi che li hanno scelti."""
    edges:   List[Edge]                  = field(default_factory=list)   # ordine di input
    hits:    Dict[int, List[OuterHit]]   = field(default_factory=dict)   # id(edge) -> hit
    n_rays:  int                         = 0

    @property
    def ids(self) -> set:
        return set(self.hits)

    def hits_of(self, edge: Edge) -> List[OuterHit]:
        return self.hits.get(id(edge), [])


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def outer_candidate_edges(edges: Iterable[Edge]) -> OuterCandidates:
    """
    Per ogni asse, una quota rappresentativa (punto medio) fra ogni coppia
    di quote-evento consecutive — estremi dei segmenti, estremi degli archi
    lungo l'asse — e per ciascuna il primo e l'ultimo punto d'intersezione.
    L'Edge che li produce è candidato. LineSeg/ArcSeg/CircleSeg analitici,
    SplineSeg/EllipseSeg discretizzati.
    """
    edges = list(edges)
    pieces = [p for edge in edges for p in _pieces(edge)]

    hits: Dict[int, List[OuterHit]] = {}
    n_rays = 0
    for axis in (AXIS_Y, AXIS_X):
        n_rays += _scan_axis(pieces, axis, hits)

    candidates = [e for e in edges if id(e) in hits]
    return OuterCandidates(edges=candidates, hits=hits, n_rays=n_rays)


# ---------------------------------------------------------------------------
# Pezzi elementari: rette e archi di circonferenza
# ---------------------------------------------------------------------------

@dataclass
class _Line:
    edge:  Edge
    p:     Point
    q:     Point


@dataclass
class _Arc:
    edge:   Edge
    center: Point
    radius: float
    start:  float   # radianti
    sweep:  float   # radianti, positivo
    ccw:    bool


def _pieces(edge: Edge) -> list:
    seg = edge.segment
    if isinstance(seg, LineSeg):
        return [_Line(edge, seg.start, seg.end)]
    if isinstance(seg, ArcSeg):
        return [_Arc(edge, seg.center, seg.radius, seg.start_angle, seg._sweep(), seg.ccw)]
    if isinstance(seg, CircleSeg):
        return [_Arc(edge, seg.center, seg.radius, 0.0, 2 * math.pi, True)]
    if isinstance(seg, (SplineSeg, EllipseSeg)):
        pts = seg.discretize(DEFAULT_TOLERANCE)
        return [_Line(edge, pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    return []


def _on_arc(arc: _Arc, pt: Point) -> bool:
    return angle_from_start(arc.center, arc.start, arc.ccw, pt) <= arc.sweep + _EPS


def _arc_point(arc: _Arc, angle: float) -> Point:
    return point_on_circle(arc.center, arc.radius, angle)


def _extent(piece, a: int) -> Tuple[float, float]:
    """(min, max) del pezzo lungo la coordinata `a` (0 = x, 1 = y)."""
    if isinstance(piece, _Line):
        return min(piece.p[a], piece.q[a]), max(piece.p[a], piece.q[a])
    end = piece.start + (piece.sweep if piece.ccw else -piece.sweep)
    values = [_arc_point(piece, piece.start)[a], _arc_point(piece, end)[a]]
    c, r = piece.center[a], piece.radius
    for extreme in (c - r, c + r):
        pt = list(piece.center)
        pt[a] = extreme
        if _on_arc(piece, tuple(pt)):
            values.append(extreme)
    return min(values), max(values)


def _intersections(piece, a: int, level: float) -> List[Point]:
    """Punti del pezzo con coordinata `a` == level."""
    b = 1 - a
    if isinstance(piece, _Line):
        p, q = piece.p, piece.q
        if abs(q[a] - p[a]) < _EPS:
            return []   # parallelo al raggio: lo vede l'altro asse
        t = (level - p[a]) / (q[a] - p[a])
        if t < -_EPS or t > 1 + _EPS:
            return []
        pt = [0.0, 0.0]
        pt[a] = level
        pt[b] = p[b] + t * (q[b] - p[b])
        return [tuple(pt)]

    d = level - piece.center[a]
    if abs(d) > piece.radius:
        return []
    h = math.sqrt(max(piece.radius * piece.radius - d * d, 0.0))
    out = []
    for sign in (-1.0, 1.0):
        pt = [0.0, 0.0]
        pt[a] = level
        pt[b] = piece.center[b] + sign * h
        pt = tuple(pt)
        if _on_arc(piece, pt):
            out.append(pt)
    return out


# ---------------------------------------------------------------------------
# Sweep su un asse
# ---------------------------------------------------------------------------

def _scan_axis(pieces: list, axis: str, hits: Dict[int, List[OuterHit]]) -> int:
    a = 1 if axis == AXIS_Y else 0
    b = 1 - a
    spans = [(_extent(p, a), p) for p in pieces]
    spans.sort(key=lambda s: s[0][0])

    events = sorted({v for (lo, hi), _ in spans for v in (lo, hi)})
    levels = [
        (events[i] + events[i + 1]) / 2
        for i in range(len(events) - 1)
        if events[i + 1] - events[i] > _EPS
    ]

    active: list = []
    nxt = 0
    for level in levels:
        while nxt < len(spans) and spans[nxt][0][0] <= level:
            active.append(spans[nxt])
            nxt += 1
        active = [s for s in active if s[0][1] >= level]

        found = [(pt, piece) for _, piece in active
                 for pt in _intersections(piece, a, level)]
        if not found:
            continue
        lo = min(pt[b] for pt, _ in found)
        hi = max(pt[b] for pt, _ in found)
        for pt, piece in found:
            for side, extreme in ((SIDE_MIN, lo), (SIDE_MAX, hi)):
                if abs(pt[b] - extreme) <= _EPS:
                    hits.setdefault(id(piece.edge), []).append(
                        OuterHit(axis=axis, level=level, side=side, point=pt)
                    )
    return len(levels)
