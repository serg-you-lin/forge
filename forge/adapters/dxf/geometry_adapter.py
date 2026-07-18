
"""
adapters/dxf/geometry_adapter.py
---------------------------------
Traduce entità ezdxf in geometria Shapely e coordinate Python.
Gestisce anche il writeback DXF per la chiusura dei gap.

Questo modulo conosce ezdxf. Il core non lo importa mai.

Funzioni pubbliche:
    arc_endpoints           — (start, end) di un ARC
    arc_to_bulge            — ARC → (entry, exit, bulge) per LWPOLYLINE
    arc_to_linestrings      — ARC → lista di LineString Shapely
    entity_to_polygon       — entità → Polygon Shapely
    entity_length           — lunghezza di una entità
    entity_midpoint         — punto medio geometrico
    get_representative_point — punto rappresentativo per classificazione
    free_endpoints_from_msp — endpoint liberi nel grafo
"""

import math
import numpy as np
from ezdxf import upright as _upright
from ezdxf.math import bulge_to_arc
from typing import Optional, Tuple, List
from shapely.geometry import Point, MultiPoint, Polygon, LineString

from ...core.geometry import (
    num_segments_for_bulge,
    spline_endpoints
)

Point2D = Tuple[float, float]


# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------

_LENGTH_HANDLERS  = {}
_POLYGON_HANDLERS = {}
_REPR_PT_HANDLERS = {}


def _register_length(*dxftypes: str):
    def decorator(fn):
        for t in dxftypes:
            _LENGTH_HANDLERS[t] = fn
        return fn
    return decorator


def _register_polygon(*dxftypes: str):
    def decorator(fn):
        for t in dxftypes:
            _POLYGON_HANDLERS[t] = fn
        return fn
    return decorator


def _register_repr_pt(*dxftypes: str):
    def decorator(fn):
        for t in dxftypes:
            _REPR_PT_HANDLERS[t] = fn
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Endpoint di entità
# ---------------------------------------------------------------------------


def arc_endpoints(entity) -> Tuple[Point2D, Point2D]:
    s = entity.start_point
    e = entity.end_point
    return (s.x, s.y), (e.x, e.y)


def arc_to_bulge(entity, reversed: bool = False) -> Tuple[Point2D, Point2D, float]:
    """
    Converte un ARC in (entry_pt, exit_pt, bulge) per LWPOLYLINE.
    Se reversed=True, inverte direzione e segno del bulge.
    """
    start_angle = entity.dxf.start_angle
    end_angle   = entity.dxf.end_angle
    if end_angle < start_angle:
        end_angle += 360.0
    delta = end_angle - start_angle
    bulge = np.tan(np.radians(delta) / 4.0)
    start_pt, end_pt = arc_endpoints(entity)
    if reversed:
        return end_pt, start_pt, -bulge
    return start_pt, end_pt, bulge


def arc_to_linestrings(entity, num_segments: int = 8) -> List[LineString]:
    """
    Approssima un ARC in segmenti LineString Shapely.
    Usato nel fallback polygonize.
    """
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    start = np.radians(entity.dxf.start_angle)
    end   = np.radians(entity.dxf.end_angle)
    if start > end:
        end += 2 * np.pi
    angles = np.linspace(start, end, num_segments + 1)
    pts = [(cx + r * np.cos(a), cy + r * np.sin(a)) for a in angles]
    return [LineString([pts[i], pts[i + 1]]) for i in range(len(pts) - 1)]


def spline_to_points(spline, tolerance: float = 0.01) -> list:
    try:
        pts = list(spline.flattening(tolerance))
        return [(p[0], p[1]) for p in pts]
    except Exception:
        return []
    
# ---------------------------------------------------------------------------
# Conversione entità → Polygon Shapely
# ---------------------------------------------------------------------------

def entity_to_polygon(entity) -> Optional[Polygon]:
    """
    Converte una entità strutturale in un Polygon Shapely.
    Restituisce None se il tipo non è supportato o la conversione fallisce.
    """
    handler = _POLYGON_HANDLERS.get(entity.dxftype())
    if handler is None:
        return None
    try:
        return handler(entity)
    except Exception:
        return None
    # return handler(entity)   # Momentaneamente senza try/except per debug

@_register_polygon('LWPOLYLINE', 'POLYLINE')
def _polygon_pline(entity) -> Optional[Polygon]:
    return pline_to_polygon(entity)


@_register_polygon('CIRCLE')
def _polygon_circle(entity) -> Optional[Polygon]:
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    angles = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    pts = [(cx + r * np.cos(a), cy + r * np.sin(a)) for a in angles]
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly if not poly.is_empty else None


@_register_polygon('SPLINE', 'ELLIPSE')
def _polygon_flattened(entity) -> Optional[Polygon]:
    pts = [(p[0], p[1]) for p in entity.flattening(0.01)]
    if len(pts) < 3:
        return None
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly if not poly.is_empty else None


def pline_to_polygon(pline) -> Optional[Polygon]:
    if pline.dxftype() == 'POLYLINE':
        pts = [(v.dxf.location.x, v.dxf.location.y) for v in pline.vertices]
    else:
        pts = []
        points = list(pline.get_points('xyb'))
        n = len(points)
        for i in range(n):
            x1, y1, bulge = points[i]
            x2, y2, _     = points[(i + 1) % n]
            pts.append((x1, y1))
            if abs(bulge) > 1e-6:
                center, start_angle, end_angle, radius = bulge_to_arc(
                    (x1, y1), (x2, y2), bulge
                )
                cx, cy = center.x, center.y
                a1 = math.atan2(y1 - cy, x1 - cx)
                a2 = math.atan2(y2 - cy, x2 - cx)
                if bulge > 0:
                    if a2 <= a1:
                        a2 += 2 * math.pi
                else:
                    if a2 >= a1:
                        a2 -= 2 * math.pi
                angle   = a2 - a1
                num_seg = num_segments_for_bulge(bulge)
                for j in range(1, num_seg):
                    a = a1 + angle * j / num_seg
                    pts.append((cx + radius * math.cos(a),
                                cy + radius * math.sin(a)))

    if len(pts) < 3:
        return None
    try:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.geom_type == 'MultiPolygon':
            poly = max(poly.geoms, key=lambda p: p.area)
        return poly if not poly.is_empty else None
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Lunghezza entità
# ---------------------------------------------------------------------------

def entity_length(entity) -> float:
    """
    Calcola la lunghezza di una entità DXF.
    Restituisce 0.0 se il tipo non è supportato o il calcolo fallisce.
    """
    handler = _LENGTH_HANDLERS.get(entity.dxftype())
    if handler is None:
        return 0.0
    try:
        return handler(entity)
    except Exception:
        return 0.0


@_register_length('LINE')
def _line_length(entity) -> float:
    s = entity.dxf.start
    e = entity.dxf.end
    return math.hypot(e.x - s.x, e.y - s.y)


@_register_length('ARC')
def _arc_length(entity) -> float:
    angle = entity.dxf.end_angle - entity.dxf.start_angle
    if angle < 0:
        angle += 360
    return math.radians(angle) * entity.dxf.radius


@_register_length('CIRCLE')
def _circle_length(entity) -> float:
    return 2 * math.pi * entity.dxf.radius


@_register_length('LWPOLYLINE', 'POLYLINE')
def _polyline_length(entity) -> float:
    pts = [p[:2] for p in entity.get_points()]
    length = 0.0
    for i in range(len(pts) - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dy = pts[i + 1][1] - pts[i][1]
        length += math.hypot(dx, dy)
    return length


@_register_length('SPLINE')
def _spline_length(entity) -> float:
    pts = list(entity.flattening(distance=0.01))
    length = 0.0
    for i in range(len(pts) - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dy = pts[i + 1][1] - pts[i][1]
        length += math.hypot(dx, dy)
    return length


# ---------------------------------------------------------------------------
# Punto rappresentativo
# ---------------------------------------------------------------------------

def get_representative_point(entity) -> Optional[Point]:
    """
    Restituisce un punto rappresentativo dell'entità per classificazione.
    Restituisce None se non riesce.
    """
    handler = _REPR_PT_HANDLERS.get(entity.dxftype())
    if handler is None:
        return _repr_pt_fallback(entity)
    try:
        return handler(entity)
    except Exception:
        return None


@_register_repr_pt('LINE')
def _repr_pt_line(entity) -> Optional[Point]:
    s, e = entity.dxf.start, entity.dxf.end
    return Point((s.x + e.x) / 2, (s.y + e.y) / 2)


@_register_repr_pt('CIRCLE', 'ARC', 'ELLIPSE')
def _repr_pt_centered(entity) -> Optional[Point]:
    c = entity.dxf.center
    return Point(c.x, c.y)


@_register_repr_pt('TEXT', 'MTEXT')
def _repr_pt_text(entity) -> Optional[Point]:
    p = entity.dxf.insert
    return Point(p.x, p.y)


@_register_repr_pt('MULTILEADER')
def _repr_pt_multileader(entity) -> Optional[Point]:
    try:
        pt = entity.context.mtext.insert
        return Point(pt.x, pt.y)
    except Exception:
        pass
    try:
        pt = entity.context.leaders[0].lines[0].vertices[0]
        return Point(pt.x, pt.y)
    except Exception:
        return None


@_register_repr_pt('INSERT')
def _repr_pt_insert(entity) -> Optional[Point]:
    p = entity.dxf.insert
    return Point(p.x, p.y)


@_register_repr_pt('LWPOLYLINE')
def _repr_pt_lwpolyline(entity) -> Optional[Point]:
    pts = [(p[0], p[1]) for p in entity.get_points()]
    return MultiPoint(pts).convex_hull.representative_point()


@_register_repr_pt('SPLINE')
def _repr_pt_spline(entity) -> Optional[Point]:
    pts = [(p[0], p[1]) for p in entity.control_points]
    return MultiPoint(pts).convex_hull.representative_point()


@_register_repr_pt('HATCH')
def _repr_pt_hatch(entity) -> Optional[Point]:
    if entity.seeds:
        return Point(entity.seeds[0][0], entity.seeds[0][1])
    return None


@_register_repr_pt('DIMENSION')
def _repr_pt_dimension(entity) -> Optional[Point]:
    p = entity.dxf.defpoint
    return Point(p.x, p.y)


def _repr_pt_fallback(entity) -> Optional[Point]:
    try:
        for attr in ('insert', 'start', 'center'):
            if entity.dxf.hasattr(attr):
                p = getattr(entity.dxf, attr)
                return Point(p.x, p.y)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Punto medio geometrico
# ---------------------------------------------------------------------------

def entity_midpoint(entity) -> Optional[Point2D]:
    """
    Restituisce il punto medio geometrico dell'entità:
    - LINE: media aritmetica dei due endpoint
    - ARC:  punto sull'arco all'angolo medio (non media degli endpoint)
    """
    try:
        dtype = entity.dxftype()
        if dtype == 'LINE':
            return (
                (entity.dxf.start.x + entity.dxf.end.x) / 2,
                (entity.dxf.start.y + entity.dxf.end.y) / 2,
            )
        if dtype == 'ARC':
            start_a = math.radians(entity.dxf.start_angle)
            end_a   = math.radians(entity.dxf.end_angle)
            if end_a < start_a:
                end_a += 2 * math.pi
            mid_a = (start_a + end_a) / 2
            cx, cy = entity.dxf.center.x, entity.dxf.center.y
            r      = entity.dxf.radius
            return (cx + r * math.cos(mid_a), cy + r * math.sin(mid_a))
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# Gap closing — writeback DXF in-place
# ---------------------------------------------------------------------------

def _arc_endpoint(arc, role: str) -> Point2D:
    cx, cy = arc.dxf.center.x, arc.dxf.center.y
    r = arc.dxf.radius
    angle = arc.dxf.start_angle if role == 'start' else arc.dxf.end_angle
    return (cx + r * math.cos(math.radians(angle)),
            cy + r * math.sin(math.radians(angle)))


def _spline_to_polygon(spline) -> Optional[Polygon]:
    pts = spline_to_points(spline)
    if len(pts) < 3:
        return None
    try:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.geom_type == "MultiPolygon":
            poly = max(poly.geoms, key=lambda p: p.area)
        return poly if not poly.is_empty else None
    except Exception:
        return None


def _spline_is_closed(spline, tolerance: float = 0.01) -> bool:
    s, e = spline_endpoints(spline)
    if s is None or e is None:
        return False
    return math.sqrt((e[0] - s[0]) ** 2 + (e[1] - s[1]) ** 2) < tolerance

