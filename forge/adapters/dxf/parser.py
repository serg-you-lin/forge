"""
adapters/dxf/parser.py
----------------------
Traduce entità ezdxf in primitive geometriche pure (LineSeg, ArcSeg, SplineSeg).
Unico file che conosce ezdxf e il formato bulge DXF per il parsing.
"""

from __future__ import annotations

import math
from typing import List

from ...core.primitives import LineSeg, ArcSeg, SplineSeg, CircleSeg
from ...core.primitives.segments import DEFAULT_TOLERANCE


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

class DxfEntityDispatcher:
    """Centralizza il routing per tipo di entità DXF."""

    def __init__(self, entity):
        self.entity = entity
        self.kind = entity.dxftype()

    def parse(self, rev: bool = False, has_spline: bool = False):
        if self.kind == "LINE":
            return _parse_line(self.entity, rev)[0]
        if self.kind == "ARC":
            return _parse_arc(self.entity, rev)
        if self.kind == "SPLINE":
            return _parse_spline(self.entity, rev)
        if self.kind in ("LWPOLYLINE", "POLYLINE"):
            return _parse_polyline(self.entity, rev)
        if self.kind == "CIRCLE":
            return _parse_circle(self.entity)
        return None


# ---------------------------------------------------------------------------
# Parsing ezdxf → primitive
# ---------------------------------------------------------------------------

def _parse_line(entity, rev) -> tuple:
    if rev:
        start = (entity.dxf.end.x,   entity.dxf.end.y)
        end   = (entity.dxf.start.x, entity.dxf.start.y)
    else:
        start = (entity.dxf.start.x, entity.dxf.start.y)
        end   = (entity.dxf.end.x,   entity.dxf.end.y)
    return LineSeg(start=start, end=end), end


def _parse_arc(entity, rev) -> ArcSeg:
    cx = entity.dxf.center.x
    cy = entity.dxf.center.y
    r  = entity.dxf.radius
    sa = math.radians(entity.dxf.start_angle)
    ea = math.radians(entity.dxf.end_angle)

    ccw = True
    if rev:
        sa, ea = ea, sa
        ccw = False

    return ArcSeg(center=(cx, cy), radius=r, start_angle=sa, end_angle=ea, ccw=ccw)


def _parse_spline(entity, rev) -> SplineSeg:
    try:
        cps = [(float(p[0]), float(p[1]), float(p[2] if len(p) > 2 else 0.0)) for p in entity.control_points]
        approx_points = [(float(p[0]), float(p[1])) for p in entity.flattening(DEFAULT_TOLERANCE)]
        knots = [float(k) for k in entity.knots]
        weights = [float(w) for w in entity.weights] if len(entity.weights) else None
        fit_points = [
            (float(p[0]), float(p[1]), float(p[2] if len(p) > 2 else 0.0))
            for p in entity.fit_points
        ] if len(entity.fit_points) else None
        flags = int(getattr(entity.dxf, "flags", 0) or 0)
        periodic = bool(flags & 2)
        closed = bool(getattr(entity, "closed", False) or (flags & 1))

        start_tangent = None
        if entity.dxf.hasattr("start_tangent"):
            st = entity.dxf.start_tangent
            start_tangent = (float(st.x), float(st.y), float(st.z))

        end_tangent = None
        if entity.dxf.hasattr("end_tangent"):
            et = entity.dxf.end_tangent
            end_tangent = (float(et.x), float(et.y), float(et.z))
    except Exception:
        cps = []
        approx_points = []
        knots = []
        weights = None
        fit_points = None
        flags = 0
        periodic = False
        closed = False
        start_tangent = None
        end_tangent = None

    seg = SplineSeg(
        degree=int(getattr(entity.dxf, "degree", 3) or 3),
        control_points=[(p[0], p[1]) for p in cps],
        knots=knots,
        weights=weights,
        approx_points=approx_points or None,
        fit_points=fit_points,
        closed=closed,
        periodic=periodic,
        flags=flags,
        knot_tolerance=float(entity.dxf.knot_tolerance) if entity.dxf.hasattr("knot_tolerance") else None,
        fit_tolerance=float(entity.dxf.fit_tolerance) if entity.dxf.hasattr("fit_tolerance") else None,
        control_point_tolerance=float(entity.dxf.control_point_tolerance) if entity.dxf.hasattr("control_point_tolerance") else None,
        start_tangent=start_tangent,
        end_tangent=end_tangent,
    )
    return seg.reversed() if rev else seg


def _parse_circle(entity) -> CircleSeg:
    return CircleSeg(
        center=(entity.dxf.center.x, entity.dxf.center.y),
        radius=entity.dxf.radius
    )


def _parse_polyline(entity, rev) -> list:
    if entity.dxftype() == "POLYLINE":
        points = [
            (v.dxf.location.x, v.dxf.location.y, getattr(v.dxf, "bulge", 0.0))
            for v in entity.vertices
        ]
    else:
        points = list(entity.get_points('xyb'))

    if not points:
        return []

    is_closed = bool(
        getattr(entity, "is_closed", False) or getattr(entity, "closed", False)
    )

    # Polilinea chiusa con vertice di chiusura esplicito (primo == ultimo):
    # scartalo, altrimenti il ciclo `%n` genera un segmento di lunghezza nulla.
    if is_closed and len(points) > 1:
        if (points[0][0], points[0][1]) == (points[-1][0], points[-1][1]):
            points = points[:-1]

    # Semplice reversal: inverte tutto e basta
    if rev:
        points = list(reversed(points))

    primitives = []
    n = len(points)
    edge_count = n if is_closed else max(0, n - 1)
    
    for i in range(edge_count):
        x1, y1, bulge = points[i]
        if is_closed:
            x2, y2, _ = points[(i + 1) % n]
        else:
            x2, y2, _ = points[i + 1]
        
        if abs(bulge) > 1e-9:
            primitives.append(ArcSeg.from_chord(start=(x1, y1), end=(x2, y2), bulge=bulge))
        else:
            primitives.append(LineSeg(start=(x1, y1), end=(x2, y2)))
    return primitives