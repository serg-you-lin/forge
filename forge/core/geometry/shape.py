"""
forge/core/geometry/shape.py
----------------------------
Fatti di forma di un contorno chiuso: cerchio, stadio, rettangolo, poligono.
Geometria pura, vale uguale su `heal()` e su `island()`. "circle" non vuol
dire foro: cosa sia quel cerchio lo dice chi legge il disegno o il processo
(MAP.md D68).
In coda i fatti fra più contorni: cerchi concentrici, archi attorno a un
cerchio (MAP.md D91).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from shapely.geometry import Polygon

from .measure import chord_angle_deg
from ..primitives.segments import ArcSeg, CircleSeg, LineSeg

Point = Tuple[float, float]

CIRCLE = "circle"
STADIUM = "stadium"
RECTANGLE = "rectangle"
POLYGON = "polygon"
OTHER = "other"

SHAPE_TOLERANCE = 0.01       # frazione della dimensione del contorno
ANGLE_TOLERANCE_DEG = 1.0


@dataclass(frozen=True)
class ContourShape:
    """
    kind:   circle | stadium | rectangle | polygon | other
    center: centro (cerchio, stadio, rettangolo) o baricentro (il resto)
    length: dimensione maggiore — cerchio: diametro; stadio: fuori tutto
    width:  dimensione minore — cerchio: diametro; stadio: 2 × raggio
    angle:  gradi [0, 180) dell'asse lungo; None per il cerchio
    sides:  segmenti del contorno dopo la ricomposizione
    """
    kind: str
    center: Point
    length: float
    width: float
    angle: Optional[float]
    sides: int

    @property
    def diameter(self) -> Optional[float]:
        return self.length if self.kind == CIRCLE else None

    def to_dict(self) -> dict:
        return {"kind": self.kind, "center": list(self.center),
                "length": round(self.length, 4), "width": round(self.width, 4),
                "angle": None if self.angle is None else round(self.angle, 4),
                "sides": self.sides}


def contour_shape(item, tolerance: float = SHAPE_TOLERANCE,
                  angle_tolerance: float = ANGLE_TOLERANCE_DEG) -> Optional[ContourShape]:
    """
    Forma di un contorno chiuso (`ForgeContour`, o qualunque oggetto con
    `.segments`, o la lista di segmenti). None se non ci sono segmenti.
    I segmenti consecutivi sulla stessa retta o circonferenza sono prima
    ricomposti, così un lato spezzato da un nodo resta un lato.
    """
    segments = list(getattr(item, "segments", item) or [])
    if not segments:
        return None
    segments, _ = merge_runs(segments, [None] * len(segments))
    for rule in (_circle, _stadium, _rectangle):
        shape = rule(segments, tolerance, angle_tolerance)
        if shape is not None:
            return shape
    return _generic(segments)


def _circle(segments, tol, _angle_tol):
    if not all(isinstance(s, (ArcSeg, CircleSeg)) for s in segments):
        return None
    s0 = segments[0]
    if any(abs(s.radius - s0.radius) > tol * s0.radius
           or math.dist(s.center, s0.center) > tol * s0.radius for s in segments):
        return None
    sweep = sum(2 * math.pi if isinstance(s, CircleSeg) else s._sweep() for s in segments)
    if abs(sweep - 2 * math.pi) > math.radians(1.0):
        return None
    d = 2 * s0.radius
    return ContourShape(CIRCLE, tuple(s0.center), d, d, None, len(segments))


def _stadium(segments, tol, angle_tol):
    if len(segments) != 4:
        return None
    k = 0 if isinstance(segments[0], ArcSeg) else 1
    a1, l1, a2, l2 = segments[k:] + segments[:k]
    if not (isinstance(a1, ArcSeg) and isinstance(a2, ArcSeg)
            and isinstance(l1, LineSeg) and isinstance(l2, LineSeg)):
        return None
    r = a1.radius
    if abs(a2.radius - r) > tol * r:
        return None
    if any(abs(a._sweep() - math.pi) > math.radians(angle_tol) for a in (a1, a2)):
        return None
    axis = math.dist(a1.center, a2.center)
    if axis <= tol * r:
        return None
    angle = chord_angle_deg(a1.center, a2.center)
    for line in (l1, l2):
        if abs(_length(line) - axis) > tol * (axis + 2 * r):
            return None
        if _angle_diff(chord_angle_deg(line.start, line.end), angle) > angle_tol:
            return None
    center = ((a1.center[0] + a2.center[0]) / 2, (a1.center[1] + a2.center[1]) / 2)
    return ContourShape(STADIUM, center, axis + 2 * r, 2 * r, angle, 4)


def _rectangle(segments, tol, angle_tol):
    if len(segments) != 4 or not all(isinstance(s, LineSeg) for s in segments):
        return None
    angles = [chord_angle_deg(s.start, s.end) for s in segments]
    if any(abs(_angle_diff(angles[i], angles[i - 1]) - 90) > angle_tol for i in range(4)):
        return None
    lengths = [_length(s) for s in segments]
    size = max(lengths)
    if abs(lengths[0] - lengths[2]) > tol * size or abs(lengths[1] - lengths[3]) > tol * size:
        return None
    i = 0 if lengths[0] >= lengths[1] else 1
    xs = [s.start[0] for s in segments]
    ys = [s.start[1] for s in segments]
    center = (sum(xs) / 4, sum(ys) / 4)
    return ContourShape(RECTANGLE, center, lengths[i], lengths[1 - i], angles[i], 4)


def _generic(segments):
    kind = POLYGON if len(segments) >= 3 and all(isinstance(s, LineSeg) for s in segments) else OTHER
    points = [p for s in segments for p in s.discretize()]
    polygon = Polygon(points) if len(points) >= 3 else Polygon()
    box = polygon.minimum_rotated_rectangle
    if box.geom_type != "Polygon":
        return None
    corners = list(box.exterior.coords)[:4]
    sides = [math.dist(corners[i], corners[i + 1]) for i in range(3)]
    i = 0 if sides[0] >= sides[1] else 1
    angle = chord_angle_deg(corners[i], corners[i + 1])
    c = polygon.centroid
    return ContourShape(kind, (c.x, c.y), sides[i], sides[1 - i], angle, len(segments))


def _length(line: LineSeg) -> float:
    return math.dist(line.start, line.end)


def _angle_diff(a: float, b: float) -> float:
    """Differenza fra due direzioni modulo 180, in [0, 90]."""
    d = abs(a - b) % 180
    return min(d, 180 - d)


# ---------------------------------------------------------------------------
# Cerchi concentrici, archi attorno a un cerchio (MAP.md D91)
# ---------------------------------------------------------------------------
# Fatti geometrici fra più contorni: "questi cerchi hanno lo stesso centro",
# "questo arco gira attorno a quel cerchio". Cosa siano (svasatura, sede,
# cresta di un filetto) e con che soglie lo decide il consumatore.

CONCENTRIC_TOLERANCE = 0.1   # distanza massima fra i centri, unità del disegno


@dataclass(frozen=True)
class ConcentricGroup:
    """
    Contorni circolari con lo stesso centro, dal raggio minore al maggiore.

    center: centro del cerchio più piccolo (il riferimento del gruppo)
    items:  i contorni, nell'ordine dei raggi
    shapes: la `ContourShape` di ciascuno, nello stesso ordine
    """
    center: Point
    items: tuple
    shapes: Tuple[ContourShape, ...]

    @property
    def diameters(self) -> Tuple[float, ...]:
        return tuple(s.length for s in self.shapes)


def concentric_groups(items, tolerance: float = CONCENTRIC_TOLERANCE) -> list[ConcentricGroup]:
    """
    Partizione dei contorni circolari di `items` per centro: ogni cerchio sta
    in un solo gruppo, anche da solo. Un cerchio entra nel gruppo il cui
    centro dista al più `tolerance` dal suo; i non circolari non compaiono.
    Gruppi ordinati per centro (x, y).
    """
    circles = [(item, shape) for item in items
               if (shape := contour_shape(item)) is not None and shape.kind == CIRCLE]
    circles.sort(key=lambda c: (c[1].length, c[1].center))
    groups: list[list] = []
    for item, shape in circles:
        group = next((g for g in groups if math.dist(g[0][1].center, shape.center) <= tolerance), None)
        if group is None:
            groups.append([(item, shape)])
        else:
            group.append((item, shape))
    out = [ConcentricGroup(tuple(g[0][1].center), tuple(i for i, _ in g), tuple(s for _, s in g))
           for g in groups]
    return sorted(out, key=lambda g: g.center)


@dataclass(frozen=True)
class ArcAround:
    """
    Un arco concentrico a un cerchio e più grande di lui.

    arc:          l'`ArcSeg`
    sweep:        angolo spazzato, in gradi
    radius_ratio: raggio dell'arco / raggio del cerchio (> 1)
    """
    arc: ArcSeg
    sweep: float
    radius_ratio: float


def arcs_around(center: Point, radius: float, arcs,
                tolerance: float = CONCENTRIC_TOLERANCE) -> list[ArcAround]:
    """
    Gli archi di `arcs` col centro entro `tolerance` da `center` e raggio
    maggiore di `radius`, dal più vicino al cerchio al più lontano.
    """
    out = [ArcAround(a, math.degrees(a._sweep()), a.radius / radius) for a in arcs
           if isinstance(a, ArcSeg) and a.radius > radius and math.dist(a.center, center) <= tolerance]
    return sorted(out, key=lambda a: a.radius_ratio)


# ---------------------------------------------------------------------------
# Ricomposizione di un giro (usata qui e da island(), D95)
# ---------------------------------------------------------------------------

def merge_runs(segments: list, styles: list):
    """
    Segmenti consecutivi di un giro chiuso sulla stessa circonferenza (o
    retta), nello stesso verso e con lo stesso stile, fusi in uno: il merge
    di `_normalize` toglie i doppioni prima del taglio, questo ricompone
    dopo quello che `split_at_crossings` ha spezzato. Un giro fatto tutto di
    archi dello stesso cerchio torna un CircleSeg.
    """
    n = len(segments)
    if n < 2 or len(styles) != n:
        return segments, styles
    same = [_continues(segments[i - 1], styles[i - 1], segments[i], styles[i]) for i in range(n)]
    if all(same):
        s0 = segments[0]
        if isinstance(s0, ArcSeg):
            return [CircleSeg(center=s0.center, radius=s0.radius)], [styles[0]]
        return segments, styles
    k = same.index(False)          # il giro riparte da un inizio di tratto
    segments, styles, same = segments[k:] + segments[:k], styles[k:] + styles[:k], same[k:] + same[:k]
    out_s, out_st = [], []
    for seg, st, cont in zip(segments, styles, same):
        if cont:
            out_s[-1] = _joined(out_s[-1], seg)
        else:
            out_s.append(seg)
            out_st.append(st)
    return out_s, out_st


_MERGE_EPS = 1e-3   # mm — la griglia dei nodi (NODE_DECIMALS)


def _continues(prev, prev_style, seg, style) -> bool:
    """`seg` prosegue `prev` sulla stessa curva, nello stesso verso?"""
    if style != prev_style or type(seg) is not type(prev):
        return False
    if isinstance(seg, ArcSeg):
        return (seg.ccw == prev.ccw and abs(seg.radius - prev.radius) < _MERGE_EPS
                and math.dist(seg.center, prev.center) < _MERGE_EPS)
    if isinstance(seg, LineSeg):
        (ax, ay), (bx, by) = prev.start, prev.end
        length = math.hypot(bx - ax, by - ay)
        if length < _MERGE_EPS:
            return False
        ex, ey = seg.end
        cross = (bx - ax) * (ey - ay) - (by - ay) * (ex - ax)
        dot = (bx - ax) * (ex - bx) + (by - ay) * (ey - by)
        return abs(cross) / length < _MERGE_EPS and dot > 0
    return False


def _joined(prev, seg):
    if isinstance(prev, ArcSeg):
        return ArcSeg(center=prev.center, radius=prev.radius, start_angle=prev.start_angle,
                      end_angle=seg.end_angle, ccw=prev.ccw)
    return LineSeg(start=prev.start, end=seg.end)
