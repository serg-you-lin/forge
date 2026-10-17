"""
topo/core/geometry/regions.py
------------------------------
Un contorno chiuso e una regione: dove cade un punto sul contorno (in mezzo a
un lato, su uno spigolo, su un raccordo), un tratto tagliato da una regione,
un contorno meno una regione (MAP.md D118).

Contorno e regione sono anelli di primitive testa-coda (`contour.segments`,
`topo.geometry.circle`, `topo.geometry.rectangle`, ...): una regione è un
contorno chiuso qualunque, non una forma con un nome. I tagli cadono nei punti
esatti di `intersections`; i pezzi restano primitive dello stesso tipo (un
arco tagliato è un arco). Lo shapely serve solo a dire se il punto medio di un
pezzo sta dentro o fuori.

Puro: solo primitive, nessun formato.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from shapely.geometry import Point as SPoint

from ..primitives.polygon_builder import build_polygon
from ..primitives.segments import (
    ArcSeg, CircleSeg, LineSeg, DEFAULT_TOLERANCE, angle_from_start, point_on_circle,
)
from ..primitives.trim import sub_segment
from .intersections import CURVE_TOLERANCE, intersections

Point = Tuple[float, float]

TANGENT_TOLERANCE = 1e-3   # radianti: sotto, due lati proseguono uno nell'altro
_JOIN = 1e-6               # capi più vicini di così sono lo stesso nodo
_MIN_PIECE = 1e-6          # pezzi più corti di così non esistono
_POLYGON_TOLERANCE = 1e-5  # sagitta della discretizzazione per i test dentro/fuori
_ON_BORDER = 5e-5          # un punto medio più vicino di così al bordo ci corre sopra


# ---------------------------------------------------------------------------
# Parametro lungo una primitiva: retta 0..1, arco 0..ampiezza, cerchio 0..2π,
# spline ed ellisse lunghezza lungo la loro discretizzazione
# ---------------------------------------------------------------------------

def _polyline(seg) -> List[Point]:
    return [tuple(q[:2]) for q in seg.discretize(CURVE_TOLERANCE)]


def _span(seg) -> float:
    if isinstance(seg, LineSeg):
        return 1.0
    if isinstance(seg, ArcSeg):
        return seg._sweep()
    if isinstance(seg, CircleSeg):
        return 2 * math.pi
    pts = _polyline(seg)
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def _param(seg, pt: Point) -> float:
    if isinstance(seg, LineSeg):
        dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
        l2 = dx * dx + dy * dy
        return 0.0 if l2 == 0 else ((pt[0] - seg.start[0]) * dx + (pt[1] - seg.start[1]) * dy) / l2
    if isinstance(seg, ArcSeg):
        s = angle_from_start(seg.center, seg.start_angle, seg.ccw, pt)
        return 0.0 if s > seg._sweep() + (2 * math.pi - seg._sweep()) / 2 else s
    if isinstance(seg, CircleSeg):
        return math.atan2(pt[1] - seg.center[1], pt[0] - seg.center[0]) % (2 * math.pi)
    pts, run, best = _polyline(seg), 0.0, (float("inf"), 0.0)
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        if L == 0:
            continue
        t = max(0.0, min(1.0, ((pt[0] - a[0]) * (b[0] - a[0]) + (pt[1] - a[1]) * (b[1] - a[1])) / L ** 2))
        d = math.dist(pt, (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
        if d < best[0]:
            best = (d, run + t * L)
        run += L
    return best[1]


def _at(seg, s: float) -> Point:
    if isinstance(seg, LineSeg):
        return (seg.start[0] + s * (seg.end[0] - seg.start[0]), seg.start[1] + s * (seg.end[1] - seg.start[1]))
    if isinstance(seg, ArcSeg):
        return point_on_circle(seg.center, seg.radius, seg.start_angle + (s if seg.ccw else -s))
    if isinstance(seg, CircleSeg):
        return point_on_circle(seg.center, seg.radius, s)
    pts, run = _polyline(seg), 0.0
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        if L > 0 and run + L >= s:
            t = (s - run) / L
            return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        run += L
    return pts[-1]


def _length(seg, s0: float, s1: float) -> float:
    if isinstance(seg, LineSeg):
        return math.dist(seg.start, seg.end) * (s1 - s0)
    if isinstance(seg, (ArcSeg, CircleSeg)):
        return seg.radius * (s1 - s0)
    return s1 - s0


def _ends(seg) -> Tuple[Point, Point]:
    return _at(seg, 0.0), _at(seg, _span(seg))


def _middle(seg) -> Point:
    return _at(seg, _span(seg) / 2)


def _piece(seg, s0: float, s1: float):
    """Il tratto di `seg` fra i parametri `s0` < `s1`, stessa primitiva."""
    if isinstance(seg, LineSeg):
        return LineSeg(start=seg.start if s0 == 0.0 else _at(seg, s0),
                       end=seg.end if s1 == 1.0 else _at(seg, s1))
    if isinstance(seg, (ArcSeg, CircleSeg)):
        start, sign, ccw = ((seg.start_angle, 1.0 if seg.ccw else -1.0, seg.ccw)
                            if isinstance(seg, ArcSeg) else (0.0, 1.0, True))
        return ArcSeg(center=seg.center, radius=seg.radius, start_angle=start + sign * s0,
                      end_angle=start + sign * s1, ccw=ccw)
    piece = sub_segment(seg, _at(seg, s0), _at(seg, s1), _at(seg, (s0 + s1) / 2))
    if piece is None:
        raise ValueError(f"{type(seg).__name__} non si taglia esatto")
    return piece


def _split(seg, points: Sequence[Point]) -> list:
    """`seg` spezzato nei `points` che gli stanno sopra, nel suo verso."""
    span = _span(seg)
    params = []
    for p in points:
        s = max(0.0, min(span, _param(seg, p)))
        if math.dist(_at(seg, s), p) <= _JOIN:      # solo i punti che gli stanno sopra
            params.append(s)
    params.sort()
    if isinstance(seg, CircleSeg):
        cuts = []
        for s in params:
            if not cuts or _length(seg, cuts[-1], s) > _MIN_PIECE:
                cuts.append(s)
        if len(cuts) > 1 and _length(seg, cuts[-1], cuts[0] + span) <= _MIN_PIECE:
            cuts.pop()
        if len(cuts) < 2:
            return [seg]
        return [_piece(seg, a, b) for a, b in zip(cuts, cuts[1:] + [cuts[0] + span])]
    bounds = [0.0]
    for s in params:
        if _length(seg, bounds[-1], s) > _MIN_PIECE and _length(seg, s, span) > _MIN_PIECE:
            bounds.append(s)
    bounds.append(span)
    return [_piece(seg, a, b) for a, b in zip(bounds, bounds[1:])]


def _tangent(seg, at_end: bool) -> Tuple[float, float]:
    """Direzione di percorrenza di `seg` nel suo capo iniziale o finale."""
    if isinstance(seg, LineSeg):
        dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
    elif isinstance(seg, ArcSeg):
        a = seg.start_angle + ((seg._sweep() if seg.ccw else -seg._sweep()) if at_end else 0.0)
        dx, dy = (-math.sin(a), math.cos(a)) if seg.ccw else (math.sin(a), -math.cos(a))
    else:
        pts = _polyline(seg)
        (ax, ay), (bx, by) = (pts[-2], pts[-1]) if at_end else (pts[0], pts[1])
        dx, dy = bx - ax, by - ay
    n = math.hypot(dx, dy) or 1.0
    return dx / n, dy / n


def _full_arc(seg):
    """Un cerchio come arco di 360°: un arco si inverte, un CircleSeg no (è
    sempre antiorario) e si discretizza senza tetto di lati."""
    if isinstance(seg, CircleSeg):
        return ArcSeg(center=seg.center, radius=seg.radius, start_angle=0.0,
                      end_angle=2 * math.pi, ccw=True)
    return seg


def _signed_area(ring: Sequence) -> float:
    pts = [q for seg in ring for q in _polyline(_full_arc(seg))[:-1]]
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) / 2


def _reversed(ring: Sequence) -> list:
    return [_full_arc(s).reversed() for s in reversed(ring)]


def _polygon(ring: Sequence):
    polygon = build_polygon([_full_arc(s) for s in ring], _POLYGON_TOLERANCE)
    if polygon is None:
        raise ValueError("i segmenti non chiudono un poligono valido")
    return polygon


def _side(polygon, pt: Point) -> int:
    """+1 dentro, -1 fuori, 0 sul bordo."""
    p = SPoint(pt)
    if polygon.exterior.distance(p) <= _ON_BORDER:
        return 0
    return 1 if polygon.contains(p) else -1


# ---------------------------------------------------------------------------
# Un punto sul contorno
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContourPoint:
    """
    Dove cade un punto su un contorno.

    kind:      "vertex" (due lati si incontrano con un angolo), "smooth" (si
               incontrano proseguendo uno nell'altro: un raccordo), "edge"
               (in mezzo a un lato)
    segments:  indici in `segments`: due per un vertice (entrante, uscente),
               uno per un punto in mezzo a un lato
    turn_deg:  di quanto gira il contorno nel punto, 0 se non gira
    concave:   True se l'interno occupa più di mezzo giro attorno al punto
    """
    point:    Point
    kind:     str
    segments: Tuple[int, ...]
    turn_deg: float
    concave:  bool


def point_on_contour(segments: Sequence, point: Point, tolerance: float = DEFAULT_TOLERANCE,
                     angle_tolerance: float = TANGENT_TOLERANCE) -> Optional[ContourPoint]:
    """
    Dove cade `point` sull'anello `segments` (testa-coda): su un vertice, su
    un raccordo, in mezzo a un lato. None se dista più di `tolerance` dal
    contorno. Un vertice è un raccordo se i due lati girano di meno di
    `angle_tolerance` radianti; concavo o convesso lo dice il verso
    dell'anello, non un test dentro/fuori.
    """
    segs = list(segments)
    n = len(segs)
    if n > 1:
        for k in range(n):
            if math.dist(_ends(segs[k])[0], point) <= tolerance:
                t_in, t_out = _tangent(segs[k - 1], at_end=True), _tangent(segs[k], at_end=False)
                cross = t_in[0] * t_out[1] - t_in[1] * t_out[0]
                turn = abs(math.atan2(cross, t_in[0] * t_out[0] + t_in[1] * t_out[1]))
                if turn < angle_tolerance:
                    return ContourPoint(point, "smooth", ((k - 1) % n, k), math.degrees(turn), False)
                concave = cross * _signed_area(segs) < 0
                return ContourPoint(point, "vertex", ((k - 1) % n, k), math.degrees(turn), concave)
    for i, seg in enumerate(segs):
        s = max(0.0, min(_span(seg), _param(seg, point)))
        if math.dist(_at(seg, s), point) <= tolerance:
            return ContourPoint(point, "edge", (i,), 0.0, False)
    return None


# ---------------------------------------------------------------------------
# Un tratto tagliato da una regione
# ---------------------------------------------------------------------------

def cut_by(segment, region: Sequence, keep: str = "outside") -> list:
    """
    I pezzi di `segment` fuori (`keep="outside"`) o dentro (`keep="inside"`)
    la regione chiusa `region`, nel verso di `segment`. Un pezzo che corre
    lungo il bordo della regione → ValueError: né dentro né fuori.
    """
    if keep not in ("outside", "inside"):
        raise ValueError(f"keep: 'outside' o 'inside', non {keep!r}")
    polygon = _polygon(region)
    points = [p for r in region for p in intersections(segment, r)]
    want = -1 if keep == "outside" else 1
    out = []
    for piece in _split(segment, points):
        side = _side(polygon, _middle(piece))
        if side == 0:
            raise ValueError("un pezzo corre lungo il bordo della regione")
        if side == want:
            out.append(piece)
    return out


# ---------------------------------------------------------------------------
# Contorno meno regione
# ---------------------------------------------------------------------------

def _chain(pieces: list) -> List[list]:
    """Pezzi orientati incatenati testa-coda in anelli chiusi."""
    left = list(pieces)
    rings = []
    while left:
        ring = [left.pop(0)]
        start = _ends(ring[0])[0]
        while math.dist(_ends(ring[-1])[1], start) > _JOIN:
            tail = _ends(ring[-1])[1]
            k = next((i for i, p in enumerate(left) if math.dist(_ends(p)[0], tail) <= _JOIN), None)
            if k is None:
                raise ValueError("i pezzi non si chiudono in un anello")
            ring.append(left.pop(k))
        rings.append(ring)
    return rings


def contour_minus(contour: Sequence, region: Sequence) -> List[list]:
    """
    L'anello `contour` meno la regione chiusa `region` (tutti e due anelli di
    primitive testa-coda): gli anelli del bordo che resta. Ogni anello ha il
    verso di `contour` se è un contorno esterno, quello opposto se è un foro
    (la regione tutta dentro il contorno). Lista vuota se la regione copre
    tutto il contorno.

    Tanti anelli quanti ne vengono: un taglio che stacca un pezzo ne dà due.
    Quale tenere lo decide il chiamante. Bordi che corrono uno sull'altro →
    ValueError: lì il risultato non è un punto di taglio ma un tratto in comune.
    """
    contour, region = list(contour), list(region)
    # il bordo della regione entra nel risultato al contrario del contorno:
    # `same` dice se la regione, così com'è, gira come il contorno
    same = _signed_area(region) * _signed_area(contour) > 0
    contour_polygon, region_polygon = _polygon(contour), _polygon(region)
    points = []
    for c in contour:
        for r in region:
            for p in intersections(c, r):
                if all(math.dist(p, q) > _JOIN for q in points):
                    points.append(p)
    if len(points) < 2:
        # nessun incrocio (un tocco solo non cambia la forma)
        if _side(region_polygon, _middle(contour[0])) == 1:
            return []
        if _side(contour_polygon, _middle(region[0])) == 1:
            return [contour, _reversed(region) if same else [_full_arc(r) for r in region]]
        return [contour]
    kept = []
    for c in contour:
        for piece in _split(c, points):
            side = _side(region_polygon, _middle(piece))
            if side == 0:
                raise ValueError("il contorno corre lungo il bordo della regione")
            if side == -1:
                kept.append(piece)
    for r in region:
        for piece in _split(r, points):
            side = _side(contour_polygon, _middle(piece))
            if side == 0:
                raise ValueError("la regione corre lungo il bordo del contorno")
            if side == 1:
                kept.append(piece.reversed() if same else piece)
    return _chain(kept)
