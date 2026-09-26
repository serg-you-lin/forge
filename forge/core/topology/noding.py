"""
core/topology/noding.py
-----------------------
Rete piana: ogni LineSeg/ArcSeg/CircleSeg spezzato dove incrocia o tocca a T
un altro edge, così che due edge si incontrino solo nei nodi. È la premessa
per percorrere la faccia esterna (outer_face.py): su una rete non piana un
incrocio a metà di due edge non è un nodo e il percorso ci passa sopra.

SplineSeg/EllipseSeg restano interi (nessun taglio esatto semplice): fanno da
coltello per gli altri, discretizzati.

Puro: solo Edge e primitive, nessun formato.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Dict, List

from shapely import STRtree
from shapely.geometry import LineString, Point

from .edge import Edge
from ..geometry import (
    _line_intersection, _circle_line_intersections, _circle_circle_intersections,
)
from ..primitives.segments import (
    LineSeg, ArcSeg, CircleSeg, DEFAULT_TOLERANCE, segment_endpoints, segment_is_closed,
)

NODE_DECIMALS = 3   # griglia dei nodi della rete: tagli e estremi sulla stessa

_EPS = 1e-9
_MIN_PIECE = 1e-4   # mm — sotto, lo spezzone non viene creato


@dataclass
class NodedEdges:
    """La rete piana: i pezzi, e per ognuno l'Edge da cui viene."""
    pieces:  List[Edge]            = field(default_factory=list)
    parent:  Dict[int, Edge]       = field(default_factory=dict)   # id(pezzo) -> Edge originale

    def parent_of(self, piece: Edge) -> Edge:
        return self.parent[id(piece)]


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def renode(edges: List[Edge], decimals: int = NODE_DECIMALS) -> List[Edge]:
    """Nodi di ogni Edge ricalcolati dal punto reale del segmento a
    `decimals`: un contatto a T si riconosce solo se estremi e tagli stanno
    sulla stessa griglia. Gli edge chiusi restano come sono."""
    return [e if segment_is_closed(e.segment) else _with_nodes(e, e.segment, decimals)
            for e in edges]


def split_at_crossings(edges: List[Edge], tolerance: float,
                       decimals: int = NODE_DECIMALS) -> NodedEdges:
    """
    Spezza ogni LineSeg/ArcSeg/CircleSeg nei punti dove incrocia un altro
    edge o dove un estremo di un altro edge gli cade sopra entro `tolerance`.
    I vicini da controllare li dà un STRtree. Primo e ultimo pezzo tengono i
    nodi dell'edge originale; un cerchio con meno di due tagli resta intero.
    """
    geoms = [_geometry(e) for e in edges]
    tree = STRtree(geoms)
    noded = NodedEdges()
    for i, edge in enumerate(edges):
        near = [edges[j] for j in tree.query(geoms[i], predicate="dwithin", distance=tolerance)]
        seg = edge.segment
        if isinstance(seg, (LineSeg, ArcSeg)) and edge.start != edge.end:
            pieces = _split(edge, _split_params(edge, near, tolerance), decimals)
        elif isinstance(seg, CircleSeg):
            pieces = _split_circle(edge, near, tolerance, decimals)
        else:
            pieces = [edge]
        for piece in pieces:
            noded.pieces.append(piece)
            noded.parent[id(piece)] = edge
    return noded


# ---------------------------------------------------------------------------
# Parametrizzazione: LineSeg in t ∈ [0, 1], ArcSeg in s ∈ [0, sweep]
# ---------------------------------------------------------------------------

def _arc_s(seg, pt):
    phi = math.atan2(pt[1] - seg.center[1], pt[0] - seg.center[0])
    delta = (phi - seg.start_angle) if seg.ccw else (seg.start_angle - phi)
    return delta % (2 * math.pi)


def _param(seg, pt):
    """(parametro, distanza del punto dal segmento)."""
    if isinstance(seg, LineSeg):
        dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
        l2 = dx * dx + dy * dy
        if l2 < _EPS:
            return None, float("inf")
        t = ((pt[0] - seg.start[0]) * dx + (pt[1] - seg.start[1]) * dy) / l2
        proj = (seg.start[0] + t * dx, seg.start[1] + t * dy)
        return t, math.dist(proj, pt)
    s = _arc_s(seg, pt)
    if s > seg._sweep() + _EPS:
        return None, float("inf")
    return s, abs(math.dist(pt, seg.center) - seg.radius)


def _param_range(seg):
    return 1.0 if isinstance(seg, LineSeg) else seg._sweep()


def _piece_length(seg, p0, p1):
    if isinstance(seg, LineSeg):
        return math.dist(seg.start, seg.end) * (p1 - p0)
    return seg.radius * (p1 - p0)


def _circle_as_arc(circle, start_angle=0.0):
    """Un cerchio come arco di 360° da `start_angle`: stessa matematica degli archi."""
    return ArcSeg(center=circle.center, radius=circle.radius,
                  start_angle=start_angle, end_angle=start_angle + 2 * math.pi, ccw=True)


# ---------------------------------------------------------------------------
# Punti di taglio
# ---------------------------------------------------------------------------

def _cutters(edge):
    seg = edge.segment
    if isinstance(seg, LineSeg):
        return [("line", seg.start, seg.end)]
    if isinstance(seg, ArcSeg):
        return [("arc", seg)]
    if isinstance(seg, CircleSeg):
        return [("arc", _circle_as_arc(seg))]
    pts = seg.discretize(DEFAULT_TOLERANCE)
    return [("line", pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


def _crossings(seg, cutter):
    """Incroci reali (non sul prolungamento) fra `seg` e un cutter."""
    if cutter[0] == "line":
        p, q = cutter[1], cutter[2]
        if isinstance(seg, LineSeg):
            ix = _line_intersection(seg.start, seg.end, p, q)
            pts = [ix] if ix else []
        else:
            pts = _circle_line_intersections(seg.center[0], seg.center[1], seg.radius, p, q)
        out = []
        for pt in pts:
            t, _ = _param(LineSeg(p, q), pt)
            if t is not None and -_EPS <= t <= 1 + _EPS:
                out.append(pt)
        return out
    other = cutter[1]
    if isinstance(seg, LineSeg):
        pts = _circle_line_intersections(other.center[0], other.center[1], other.radius,
                                         seg.start, seg.end)
    else:
        pts = _circle_circle_intersections(seg.center[0], seg.center[1], seg.radius,
                                           other.center[0], other.center[1], other.radius)
    return [pt for pt in pts if _arc_s(other, pt) <= other._sweep() + _EPS]


def _split_params(edge, near, tol):
    seg = edge.segment
    rng = _param_range(seg)
    params = []
    for other in near:
        if other is edge:
            continue
        pts = [pt for cutter in _cutters(other) for pt in _crossings(seg, cutter)]
        pts.extend(segment_endpoints(other.segment))   # contatto a T entro tol
        for pt in pts:
            p, dist = _param(seg, pt)
            if p is None or dist > tol:
                continue
            if _piece_length(seg, 0, p) > _MIN_PIECE and _piece_length(seg, p, rng) > _MIN_PIECE:
                params.append(p)
    params.sort()
    dedup = []
    for p in params:
        if not dedup or _piece_length(seg, dedup[-1], p) > _MIN_PIECE:
            dedup.append(p)
    return dedup


# ---------------------------------------------------------------------------
# Spezzamento
# ---------------------------------------------------------------------------

def _with_nodes(edge, seg, decimals):
    s, e = segment_endpoints(seg)
    r = lambda pt: (round(pt[0], decimals), round(pt[1], decimals))
    return replace(edge, start=r(s), end=r(e), segment=seg)


def _split(edge, params, decimals):
    seg = edge.segment
    bounds = [0.0] + params + [_param_range(seg)]
    out = []
    for p0, p1 in zip(bounds, bounds[1:]):
        if isinstance(seg, LineSeg):
            at = lambda t: (seg.start[0] + t * (seg.end[0] - seg.start[0]),
                            seg.start[1] + t * (seg.end[1] - seg.start[1]))
            a = seg.start if p0 == 0.0 else at(p0)
            b = seg.end if p1 == 1.0 else at(p1)
            piece = LineSeg(start=a, end=b)
        else:
            sign = 1.0 if seg.ccw else -1.0
            piece = ArcSeg(center=seg.center, radius=seg.radius,
                           start_angle=seg.start_angle + sign * p0,
                           end_angle=seg.start_angle + sign * p1, ccw=seg.ccw)
        cut = _with_nodes(edge, piece, decimals)
        # primo e ultimo pezzo tengono i nodi dell'edge (saldati, gap chiusi):
        # solo i tagli interni hanno un nodo nuovo
        cut = replace(cut, start=edge.start if p0 == 0.0 else cut.start,
                      end=edge.end if p1 == bounds[-1] else cut.end)
        out.append(cut)
    return out


def _split_circle(edge, near, tol, decimals):
    circle = edge.segment
    # un taglio che cade proprio dove parte l'arco equivalente verrebbe
    # scartato come "estremo": angoli raccolti da due partenze opposte
    angles = []
    for start_angle in (0.0, math.pi):
        arc = replace(edge, segment=_circle_as_arc(circle, start_angle))
        angles += [(start_angle + p) % (2 * math.pi) for p in _split_params(arc, near, tol)]
    params = []
    for a in sorted(angles):
        if not params or circle.radius * (a - params[-1]) > _MIN_PIECE:
            params.append(a)
    if len(params) > 1 and circle.radius * (params[0] + 2 * math.pi - params[-1]) <= _MIN_PIECE:
        params.pop()
    if len(params) < 2:
        return [edge]
    start = _with_nodes(edge, _circle_as_arc(circle, start_angle=params[0]), decimals)
    start = replace(start, end=start.start)
    return _split(start, [p - params[0] for p in params[1:]], decimals)


def _geometry(edge):
    pts = edge.segment.discretize(DEFAULT_TOLERANCE)
    if len(pts) < 2 or all(p == pts[0] for p in pts):
        return Point(pts[0])
    return LineString(pts)
