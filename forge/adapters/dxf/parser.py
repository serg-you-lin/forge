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
        pts = [(p[0], p[1]) for p in entity.flattening(DEFAULT_TOLERANCE)]
    except Exception:
        pts = []

    if rev:
        pts = list(reversed(pts))

    return SplineSeg(degree=0, control_points=pts, knots=[], weights=None)


def _parse_circle(entity) -> CircleSeg:
    return CircleSeg(
        center=(entity.dxf.center.x, entity.dxf.center.y),
        radius=entity.dxf.radius
    )


def _reverse_segment(segment):
    if isinstance(segment, LineSeg):
        return LineSeg(start=segment.end, end=segment.start)
    if isinstance(segment, ArcSeg):
        return ArcSeg(
            center=segment.center,
            radius=segment.radius,
            start_angle=segment.end_angle,
            end_angle=segment.start_angle,
            ccw=not segment.ccw,
        )
    if isinstance(segment, SplineSeg):
        return SplineSeg(
            degree=segment.degree,
            control_points=list(reversed(segment.control_points)),
            knots=list(segment.knots),
            weights=list(segment.weights) if segment.weights is not None else None,
        )
    return segment


def _is_placeholder_segment(edge) -> bool:
    """
    Riconosce Edge di test costruiti con segmenti dummy (0,0)->(0,0).

    In produzione gli Edge hanno segment coerente con start/end reali; nei
    test unitari storici make_edge() usa un LineSeg placeholder da sostituire
    con il parsing della source_ref.
    """
    seg = getattr(edge, "segment", None)
    src = getattr(edge, "source_ref", None)
    if seg is None or src is None or not hasattr(src, "dxftype"):
        return False

    if not isinstance(seg, LineSeg):
        return False

    if seg.start != seg.end:
        return False

    return (
        getattr(edge, "start", None) == getattr(edge, "end", None)
        and getattr(edge, "start", None) == seg.start
        and src.dxftype() in {"LINE", "ARC", "SPLINE", "LWPOLYLINE", "POLYLINE"}
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

# ---------------------------------------------------------------------------
# Loop → primitive
# ---------------------------------------------------------------------------

def parse_loop(loop) -> List:
    """
    Converte un loop di (Edge, rev) in lista di primitive geometriche pure.
    Restituisce List[LineSeg | ArcSeg | SplineSeg].
    """
    has_spline = any(
        isinstance(edge.segment, SplineSeg)
        or (edge.source_ref is not None and edge.source_ref.dxftype() == "SPLINE")
        for edge, _ in loop
    )
    primitives = []

    for edge, rev in loop:
        if edge.segment is not None and not _is_placeholder_segment(edge):
            segment = _reverse_segment(edge.segment) if rev else edge.segment
            primitives.append(segment)
        else:
            entity = edge.source_ref
            if entity is None:
                continue
            parsed = DxfEntityDispatcher(entity).parse(rev=rev, has_spline=has_spline)
            if parsed is None:
                continue
            if isinstance(parsed, list):
                primitives.extend(parsed)
            else:
                primitives.append(parsed)

    return primitives