
"""
forge/adapters/dxf/geometry_adapter.py
----------------------------------------
Funzioni geometriche PURE per entità DXF.
Nessuna conversione DXF → primitive.
Solo calcoli di endpoint, lunghezze, punti rappresentativi.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from shapely.geometry import Polygon

from forge.core.primitives.segments import DEFAULT_TOLERANCE
from forge.core.primitives.polygon_builder import build_polygon


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

def arc_endpoints(entity) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Restituisce (start, end) di un ARC in coordinate XY."""
    start = (
        entity.dxf.center.x + entity.dxf.radius * math.cos(math.radians(entity.dxf.start_angle)),
        entity.dxf.center.y + entity.dxf.radius * math.sin(math.radians(entity.dxf.start_angle))
    )
    end = (
        entity.dxf.center.x + entity.dxf.radius * math.cos(math.radians(entity.dxf.end_angle)),
        entity.dxf.center.y + entity.dxf.radius * math.sin(math.radians(entity.dxf.end_angle))
    )
    return start, end


def entity_endpoints(entity) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
    """
    Restituisce (start, end) per entità DXF supportate.
    Ritorna (None, None) se non supportata.
    """
    t = entity.dxftype()
    
    if t == 'LINE':
        return (
            (entity.dxf.start.x, entity.dxf.start.y),
            (entity.dxf.end.x, entity.dxf.end.y)
        )
    
    elif t == 'ARC':
        return arc_endpoints(entity)
    
    elif t == 'CIRCLE':
        cx, cy = entity.dxf.center.x, entity.dxf.center.y
        r = entity.dxf.radius
        pt = (cx + r, cy)
        return pt, pt
    
    elif t == 'SPLINE':
        return _spline_endpoints(entity)
    
    elif t in ('LWPOLYLINE', 'POLYLINE'):
        pts = _polyline_points_xy(entity)
        if not pts:
            return None, None
        return pts[0], pts[-1]
    
    return None, None


def _spline_endpoints(spline) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
    """Endpoint di una SPLINE."""
    try:
        pts = list(spline.flattening(DEFAULT_TOLERANCE))
        if len(pts) < 2:
            return None, None
        return (pts[0][0], pts[0][1]), (pts[-1][0], pts[-1][1])
    except Exception:
        return None, None


def _polyline_points_xy(entity) -> List[Tuple[float, float]]:
    """Punti di una polilinea in coordinate XY."""
    if entity.dxftype() == 'POLYLINE':
        return [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
    try:
        return [(p[0], p[1]) for p in entity.get_points('xy')]
    except Exception:
        return [(p[0], p[1]) for p in entity.get_points()]


def spline_is_closed(spline, tolerance: float = DEFAULT_TOLERANCE) -> bool:
    """True se la spline è chiusa (inizio ≈ fine)."""
    start, end = _spline_endpoints(spline)
    if start is None or end is None:
        return False
    return math.hypot(start[0] - end[0], start[1] - end[1]) < tolerance


# ---------------------------------------------------------------------------
# Lunghezze
# ---------------------------------------------------------------------------

def entity_length(entity) -> float:
    """Lunghezza di un'entità DXF."""
    t = entity.dxftype()
    
    if t == 'LINE':
        return _line_length(entity)
    elif t == 'ARC':
        return _arc_length(entity)
    elif t == 'CIRCLE':
        return _circle_length(entity)
    elif t in ('LWPOLYLINE', 'POLYLINE'):
        return _polyline_length(entity)
    elif t == 'SPLINE':
        return _spline_length(entity)
    
    return 0.0


def _line_length(entity) -> float:
    return math.hypot(
        entity.dxf.end.x - entity.dxf.start.x,
        entity.dxf.end.y - entity.dxf.start.y,
    )


def _arc_length(entity) -> float:
    sweep = (entity.dxf.end_angle - entity.dxf.start_angle) % 360.0
    return entity.dxf.radius * math.radians(sweep)


def _circle_length(entity) -> float:
    return 2 * math.pi * entity.dxf.radius


def _polyline_length(entity) -> float:
    pts = _polyline_points_xy(entity)
    total = 0.0
    for i in range(len(pts) - 1):
        total += math.hypot(pts[i+1][0] - pts[i][0], pts[i+1][1] - pts[i][1])
    return total


def _spline_length(entity) -> float:
    try:
        pts = list(entity.flattening(DEFAULT_TOLERANCE))
        total = 0.0
        for i in range(len(pts) - 1):
            total += math.hypot(pts[i+1][0] - pts[i][0], pts[i+1][1] - pts[i][1])
        return total
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Punti rappresentativi (per annotazioni, ecc)
# ---------------------------------------------------------------------------

def get_representative_point(entity) -> Optional[Tuple[float, float]]:
    """Punto rappresentativo per un'entità DXF."""
    t = entity.dxftype()
    
    if t == 'LINE':
        return _repr_pt_line(entity)
    elif t == 'CIRCLE':
        return (entity.dxf.center.x, entity.dxf.center.y)
    elif t == 'ARC':
        return (entity.dxf.center.x, entity.dxf.center.y)
    elif t in ('LWPOLYLINE', 'POLYLINE'):
        return _repr_pt_polyline(entity)
    elif t == 'SPLINE':
        return _repr_pt_spline(entity)
    elif t in ('TEXT', 'MTEXT'):
        return (entity.dxf.insert.x, entity.dxf.insert.y)
    elif t == 'MULTILEADER':
        return _repr_pt_multileader(entity)
    elif t == 'INSERT':
        return (entity.dxf.insert.x, entity.dxf.insert.y)
    elif t == 'HATCH':
        return _repr_pt_hatch(entity)
    elif t == 'DIMENSION':
        return _repr_pt_dimension(entity)
    
    return _repr_pt_fallback(entity)


def _repr_pt_line(entity) -> Tuple[float, float]:
    return (
        (entity.dxf.start.x + entity.dxf.end.x) / 2,
        (entity.dxf.start.y + entity.dxf.end.y) / 2,
    )


def _repr_pt_polyline(entity) -> Optional[Tuple[float, float]]:
    pts = _polyline_points_xy(entity)
    if not pts:
        return None
    n = len(pts)
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)


def _repr_pt_spline(entity) -> Optional[Tuple[float, float]]:
    try:
        pts = list(entity.flattening(DEFAULT_TOLERANCE))
        if not pts:
            return None
        n = len(pts)
        return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)
    except Exception:
        return None


def _repr_pt_multileader(entity) -> Optional[Tuple[float, float]]:
    try:
        if hasattr(entity, 'context'):
            ctx = entity.context
            if hasattr(ctx, 'mleader') and ctx.mleader:
                leader = ctx.mleader
                if hasattr(leader, 'vertices') and leader.vertices:
                    v = leader.vertices[0]
                    return (v[0], v[1])
    except Exception:
        pass
    return None


def _repr_pt_hatch(entity) -> Optional[Tuple[float, float]]:
    try:
        if hasattr(entity, 'paths') and entity.paths:
            for path in entity.paths:
                if hasattr(path, 'vertices') and path.vertices:
                    pts = [(v[0], v[1]) for v in path.vertices]
                    n = len(pts)
                    return (sum(p[0] for p in pts)/n, sum(p[1] for p in pts)/n)
    except Exception:
        pass
    return None


def _repr_pt_dimension(entity) -> Optional[Tuple[float, float]]:
    try:
        if hasattr(entity.dxf, 'defpoint'):
            return (entity.dxf.defpoint.x, entity.dxf.defpoint.y)
    except Exception:
        pass
    return None


def _repr_pt_fallback(entity) -> Optional[Tuple[float, float]]:
    """Fallback: cerca qualsiasi attributo punto."""
    for attr in ['center', 'insert', 'start', 'defpoint']:
        if hasattr(entity.dxf, attr):
            try:
                pt = getattr(entity.dxf, attr)
                return (pt.x, pt.y)
            except Exception:
                continue
    return None


def entity_midpoint(entity) -> Optional[Tuple[float, float]]:
    """Punto medio di un'entità."""
    start, end = entity_endpoints(entity)
    if start is None or end is None:
        return None
    return ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)


# ---------------------------------------------------------------------------
# Poligoni da entità (usa build_polygon)
# ---------------------------------------------------------------------------

def entity_to_polygon(entity) -> Optional[Polygon]:
    """
    Converte un'entità chiusa in un Polygon shapely.
    Usa le primitive del core per la discretizzazione.
    """
    from .parser import DxfEntityDispatcher

    prim = DxfEntityDispatcher(entity).parse()

    if prim is None:
        return None
    
    if isinstance(prim, list):
        primitives = prim
    else:
        primitives = [prim]
    
    return build_polygon(primitives, DEFAULT_TOLERANCE)


def pline_to_polygon(pline) -> Optional[Polygon]:
    """Converte una LWPOLYLINE chiusa in Polygon."""
    return entity_to_polygon(pline)