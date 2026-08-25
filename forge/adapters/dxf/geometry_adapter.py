"""
forge/adapters/dxf/geometry_adapter.py
----------------------------------------
Funzioni geometriche per entità DXF.

IMPORTANTE: Questo modulo NON discretizza più.
La discretizzazione è centralizzata in forge/core/primitives/segments.py.
Qui convertiamo solo entità DXF in primitive o calcoliamo proprietà
geometriche dirette (lunghezze, punti rappresentativi, ecc).
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from shapely.geometry import Polygon

from forge.core.primitives.segments import (
    LineSeg,
    ArcSeg,
    SplineSeg,
    DEFAULT_TOLERANCE,
)
from forge.core.primitives.polygon_builder import build_polygon


# ---------------------------------------------------------------------------
# Endpoint e proprietà base
# ---------------------------------------------------------------------------

def arc_endpoints(entity) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Restituisce (start, end) di un ARC in gradi."""
    start = (entity.dxf.center.x + entity.dxf.radius * math.cos(math.radians(entity.dxf.start_angle)),
             entity.dxf.center.y + entity.dxf.radius * math.sin(math.radians(entity.dxf.start_angle)))
    end = (entity.dxf.center.x + entity.dxf.radius * math.cos(math.radians(entity.dxf.end_angle)),
           entity.dxf.center.y + entity.dxf.radius * math.sin(math.radians(entity.dxf.end_angle)))
    return start, end


def _arc_endpoint(arc, role: str) -> Tuple[float, float]:
    """Endpoint di un arco ezdxf — 'start' o 'end'."""
    angle = arc.dxf.start_angle if role == 'start' else arc.dxf.end_angle
    rad = math.radians(angle)
    cx = arc.dxf.center.x
    cy = arc.dxf.center.y
    r = arc.dxf.radius
    return (cx + r * math.cos(rad), cy + r * math.sin(rad))


def entity_endpoints(entity):
    """
    Restituisce (start, end) per LINE, ARC, SPLINE, LWPOLYLINE, POLYLINE.
    Ritorna (None, None) se non supportata.
    """
    t = entity.dxftype()
    
    if t == 'LINE':
        return (entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)
    
    elif t == 'ARC':
        return arc_endpoints(entity)
    
    elif t == 'SPLINE':
        return spline_endpoints(entity)
    
    elif t in ('LWPOLYLINE', 'POLYLINE'):
        pts = list(entity.get_points('xy'))
        if not pts:
            return (None, None)
        return pts[0], pts[-1]
    
    elif t == 'CIRCLE':
        # Cerchio: start = end = punto a 0 gradi
        cx = entity.dxf.center.x
        cy = entity.dxf.center.y
        r = entity.dxf.radius
        pt = (cx + r, cy)
        return pt, pt
    
    return (None, None)


def spline_endpoints(spline) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
    """Endpoint di una SPLINE ezdxf."""
    try:
        pts = list(spline.flattening(DEFAULT_TOLERANCE))
        if len(pts) < 2:
            return None, None
        return (pts[0][0], pts[0][1]), (pts[-1][0], pts[-1][1])
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Conversione in primitive (NON discretizza)
# ---------------------------------------------------------------------------

def entity_to_primitive(entity, rev: bool = False):
    """
    Converte un'entità DXF in una primitiva del core.
    NON discretizza — restituisce LineSeg, ArcSeg, SplineSeg.
    
    Returns:
        primitiva o lista di primitive (per CIRCLE/POLYLINE)
        None se non supportata
    """
    t = entity.dxftype()
    
    if t == 'LINE':
        if rev:
            return LineSeg(
                start=(entity.dxf.end.x, entity.dxf.end.y),
                end=(entity.dxf.start.x, entity.dxf.start.y),
            )
        return LineSeg(
            start=(entity.dxf.start.x, entity.dxf.start.y),
            end=(entity.dxf.end.x, entity.dxf.end.y),
        )
    
    elif t == 'ARC':
        sa = math.radians(entity.dxf.start_angle)
        ea = math.radians(entity.dxf.end_angle)
        ccw = True
        if rev:
            sa, ea = ea, sa
            ccw = False
        return ArcSeg(
            center=(entity.dxf.center.x, entity.dxf.center.y),
            radius=entity.dxf.radius,
            start_angle=sa,
            end_angle=ea,
            ccw=ccw,
        )
    
    elif t == 'CIRCLE':
        cx = entity.dxf.center.x
        cy = entity.dxf.center.y
        r = entity.dxf.radius
        # Cerchio completo → 2 archi di 180°
        return [
            ArcSeg(center=(cx, cy), radius=r, start_angle=0.0, end_angle=math.pi, ccw=True),
            ArcSeg(center=(cx, cy), radius=r, start_angle=math.pi, end_angle=2*math.pi, ccw=True),
        ]
    
    elif t == 'SPLINE':
        # Per ora: estrai punti di controllo dal flattening
        try:
            pts = [(p[0], p[1]) for p in entity.flattening(DEFAULT_TOLERANCE)]
        except Exception:
            pts = []
        
        if rev:
            pts = list(reversed(pts))
        
        if not pts:
            return None
        
        return SplineSeg(
            degree=0,
            control_points=pts,
            knots=[],
            weights=None,
        )
    
    elif t in ('LWPOLYLINE', 'POLYLINE'):
        # Polilinea: converti in lista di primitive
        if t == 'POLYLINE':
            pts = [(v.dxf.location.x, v.dxf.location.y, getattr(v.dxf, "bulge", 0.0)) 
                   for v in entity.vertices]
        else:
            pts = list(entity.get_points('xyb'))
        
        if not pts:
            return []
        
        is_closed = bool(getattr(entity, "is_closed", False) or getattr(entity, "closed", False))

        if is_closed and len(pts) > 1:
            first_xy = (pts[0][0], pts[0][1])
            last_xy  = (pts[-1][0], pts[-1][1])
            if first_xy == last_xy:
                pts = pts[:-1]

        if rev:
            # Inverti e nega i bulge
            n = len(pts)
            new_pts = []
            for i in range(n):
                idx = (-i) % n
                x, y, _ = pts[idx]
                if is_closed:
                    prev_idx = (idx - 1) % n
                    bulge = -pts[prev_idx][2]
                else:
                    prev_idx = idx - 1
                    bulge = -pts[prev_idx][2] if prev_idx >= 0 else 0.0
                new_pts.append((x, y, bulge))
            pts = new_pts
        
        primitives = []
        n = len(pts)
        edge_count = n if is_closed else max(0, n - 1)
        for i in range(edge_count):
            x1, y1, bulge = pts[i]
            if is_closed:
                x2, y2, _ = pts[(i + 1) % n]
            else:
                x2, y2, _ = pts[i + 1]
            
            if abs(bulge) > 1e-6:
                # Converti bulge in arco
                arc = _bulge_to_arc((x1, y1), (x2, y2), bulge)
                if arc:
                    primitives.append(arc)
            else:
                primitives.append(LineSeg(start=(x1, y1), end=(x2, y2)))
        
        return primitives
    
    return None


def _bulge_to_arc(p1: Tuple[float, float], p2: Tuple[float, float], 
                  bulge: float) -> Optional[ArcSeg]:
    """
    Converte due punti e un bulge in un ArcSeg.
    bulge > 0: arco in senso antiorario
    bulge < 0: arco in senso orario
    """
    x1, y1 = p1
    x2, y2 = p2
    
    # Angolo incluso (radianti)
    included_angle = 4 * math.atan(abs(bulge))
    
    if included_angle < 1e-12:
        return None
    
    # Corda
    chord = math.hypot(x2 - x1, y2 - y1)
    
    if chord < 1e-12:
        return None
    
    # Raggio
    radius = chord / (2 * math.sin(included_angle / 2))
    
    # Centro (perpendicolare alla corda)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    
    # Vettore perpendicolare normalizzato
    px, py = -dy / chord, dx / chord
    
    # Distanza dal centro alla corda
    dist = radius * math.cos(included_angle / 2)
    
    if bulge > 0:
        cx = mx + px * dist
        cy = my + py * dist
        ccw = True
    else:
        cx = mx - px * dist
        cy = my - py * dist
        ccw = False
    
    # Angoli iniziale e finale
    start_angle = math.atan2(y1 - cy, x1 - cx)
    end_angle = math.atan2(y2 - cy, x2 - cx)
    
    # Normalizza per ccw
    if ccw:
        while end_angle <= start_angle:
            end_angle += 2 * math.pi
    else:
        while end_angle >= start_angle:
            end_angle -= 2 * math.pi
    
    return ArcSeg(
        center=(cx, cy),
        radius=radius,
        start_angle=start_angle,
        end_angle=end_angle,
        ccw=ccw,
    )


# ---------------------------------------------------------------------------
# Calcolo lunghezze
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
    if entity.dxftype() == 'POLYLINE':
        pts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
    else:
        pts = list(entity.get_points('xy'))
    
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
# Poligoni da entità
# ---------------------------------------------------------------------------

def entity_to_polygon(entity) -> Optional[Polygon]:
    """
    Converte un'entità chiusa in un Polygon shapely.
    Usa le primitive del core per la discretizzazione.
    """
    prim = entity_to_primitive(entity)
    
    if prim is None:
        return None
    
    if isinstance(prim, list):
        primitives = prim
    else:
        primitives = [prim]
    
    return build_polygon(primitives, DEFAULT_TOLERANCE)


def pline_to_polygon(pline) -> Optional[Polygon]:
    """Converte una LWPOLYLINE chiusa in Polygon."""
    prim = entity_to_primitive(pline)
    return entity_to_polygon(pline) if prim else None


def _spline_to_polygon(spline) -> Optional[Polygon]:
    """Converte una spline chiusa in Polygon."""
    return entity_to_polygon(spline)


def _spline_is_closed(spline, tolerance: float = DEFAULT_TOLERANCE) -> bool:
    """True se la spline è chiusa (inizio ≈ fine)."""
    start, end = spline_endpoints(spline)
    if start is None or end is None:
        return False
    return math.hypot(start[0] - end[0], start[1] - end[1]) < tolerance


# ---------------------------------------------------------------------------
# Punti rappresentativi
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
        return _repr_pt_lwpolyline(entity)
    elif t == 'SPLINE':
        return _repr_pt_spline(entity)
    elif t == 'TEXT':
        return _repr_pt_text(entity)
    elif t == 'MTEXT':
        return _repr_pt_text(entity)
    elif t == 'MULTILEADER':
        return _repr_pt_multileader(entity)
    elif t == 'INSERT':
        return _repr_pt_insert(entity)
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


def _repr_pt_lwpolyline(entity) -> Optional[Tuple[float, float]]:
    if entity.dxftype() == 'POLYLINE':
        pts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
    else:
        pts = list(entity.get_points('xy'))
    
    if not pts:
        return None
    
    # Centroide semplice dei punti
    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    return (cx, cy)


def _repr_pt_spline(entity) -> Optional[Tuple[float, float]]:
    try:
        pts = list(entity.flattening(DEFAULT_TOLERANCE))
        if not pts:
            return None
        n = len(pts)
        cx = sum(p[0] for p in pts) / n
        cy = sum(p[1] for p in pts) / n
        return (cx, cy)
    except Exception:
        return None


def _repr_pt_text(entity) -> Tuple[float, float]:
    return (entity.dxf.insert.x, entity.dxf.insert.y)


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


def _repr_pt_insert(entity) -> Tuple[float, float]:
    return (entity.dxf.insert.x, entity.dxf.insert.y)


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