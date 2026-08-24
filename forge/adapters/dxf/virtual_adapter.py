
"""
adapters/dxf/virtual_adapter.py
--------------------------------
Traduce entità ezdxf in primitive geometriche pure (LineSeg, ArcSeg, SplineSeg).
Unico file che conosce ezdxf, il formato bulge DXF, e scrive LWPOLYLINE.

Fase 3: DxfWriteContext eliminato. write_contour_to_msp() riceve un
ForgeContour o Hole e lavora direttamente su segments.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

from shapely.geometry import Polygon

from ...core.primitives import LineSeg, ArcSeg, SplineSeg
from ...core.primitives.polygon_builder import build_polygon
from ...core.primitives.segments import DEFAULT_TOLERANCE


# ---------------------------------------------------------------------------
# Tipo privato — bulge DXF per write-back fedele.
# Prodotto da _parse_polyline, consumato da segments_to_pts_with_bulge.
# ---------------------------------------------------------------------------

@dataclass
class _BulgeSeg:
    """Arco LWPOLYLINE con bulge — non esce da questo file."""
    start: tuple
    end:   tuple
    bulge: float


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


def _parse_circle(entity) -> List[ArcSeg]:
    cx = entity.dxf.center.x
    cy = entity.dxf.center.y
    r  = entity.dxf.radius
    return [
        ArcSeg(center=(cx, cy), radius=r, start_angle=0.0,     end_angle=math.pi,   ccw=True),
        ArcSeg(center=(cx, cy), radius=r, start_angle=math.pi, end_angle=2*math.pi, ccw=True),
    ]


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

    if rev:
        reversed_points = []
        n = len(points)
        for i in range(n):
            idx = (-i) % n
            x, y, _ = points[idx]
            if is_closed:
                prev_idx = (idx - 1) % n
                bulge = -points[prev_idx][2]
            else:
                prev_idx = idx - 1
                bulge = -points[prev_idx][2] if prev_idx >= 0 else 0.0
            reversed_points.append((x, y, bulge))
        points = reversed_points

    primitives = []
    n = len(points)
    edge_count = n if is_closed else max(0, n - 1)
    for i in range(edge_count):
        x1, y1, bulge = points[i]
        if is_closed:
            x2, y2, _ = points[(i + 1) % n]
        else:
            x2, y2, _ = points[i + 1]
        if abs(bulge) > 1e-6:
            primitives.append(_BulgeSeg(start=(x1, y1), end=(x2, y2), bulge=bulge))
        else:
            primitives.append(LineSeg(start=(x1, y1), end=(x2, y2)))
    return primitives


# ---------------------------------------------------------------------------
# Loop → primitive
# ---------------------------------------------------------------------------

def parse_loop(loop) -> List:
    """
    Converte un loop di (Edge, rev) in lista di primitive geometriche pure.
    Restituisce List[LineSeg | ArcSeg | SplineSeg | _BulgeSeg].
    """
    if loop:
        source_refs = {id(edge.source_ref) for edge, _ in loop}
        if len(source_refs) == 1:
            first_edge = loop[0][0]
            if first_edge.source_ref.dxftype() in ("LWPOLYLINE", "POLYLINE"):
                parsed = DxfEntityDispatcher(first_edge.source_ref).parse(rev=loop[0][1])
                return parsed if isinstance(parsed, list) else [parsed]

    has_spline = any(edge.source_ref.dxftype() == "SPLINE" for edge, _ in loop)
    primitives = []

    for edge, rev in loop:
        entity = edge.source_ref
        parsed = DxfEntityDispatcher(entity).parse(rev=rev, has_spline=has_spline)
        if parsed is None:
            continue
        if isinstance(parsed, list):
            primitives.extend(parsed)
        else:
            primitives.append(parsed)

    return primitives


# ---------------------------------------------------------------------------
# ArcSeg → bulge DXF
# ---------------------------------------------------------------------------

def arc_seg_to_bulge(arc: ArcSeg) -> float:
    """
    Converte ArcSeg in valore bulge DXF.

    bulge = tan(Δθ / 4)
    Positivo = CCW, negativo = CW.
    """
    delta = arc.end_angle - arc.start_angle
    delta = delta % (2 * math.pi)
    if delta == 0.0:
        delta = 2 * math.pi  # arco completo

    bulge = math.tan(delta / 4.0)
    if not arc.ccw:
        bulge = -bulge
    return bulge


def _arc_start_point(arc: ArcSeg) -> tuple:
    """Punto sul cerchio all'angolo start_angle."""
    x = arc.center[0] + arc.radius * math.cos(arc.start_angle)
    y = arc.center[1] + arc.radius * math.sin(arc.start_angle)
    return (x, y)


def segments_to_pts_with_bulge(segments: list) -> list:
    """
    Converte List[LineSeg | ArcSeg | SplineSeg | _BulgeSeg]
    in lista di tuple (x, y, s, e, bulge) pronte per LWPOLYLINE format='xyseb'.

    SplineSeg ignorato — has_spline va controllato a monte.
    _BulgeSeg ancora prodotto da _parse_polyline per le LWPOLYLINE durevoli
    con archi — gestito qui finché Fase 3 non converte tutto in ArcSeg puri.
    """
    pts = []
    for seg in segments:
        if isinstance(seg, LineSeg):
            pts.append((seg.start[0], seg.start[1], 0.0, 0.0, 0.0))
        elif isinstance(seg, ArcSeg):
            start = _arc_start_point(seg)
            pts.append((start[0], start[1], 0.0, 0.0, arc_seg_to_bulge(seg)))
        elif isinstance(seg, _BulgeSeg):
            pts.append((seg.start[0], seg.start[1], 0.0, 0.0, seg.bulge))
    return pts


# ---------------------------------------------------------------------------
# Write-back — unico punto che tocca ezdxf per le forme chiuse
# ---------------------------------------------------------------------------

def write_contour_to_msp(msp, contour, layer: str) -> Optional[object]:
    """
    Materializza un ForgeContour o Hole su msp come LWPOLYLINE.

    Lavora su contour.segments — non tocca ezdxf direttamente salvo
    per add_lwpolyline / add_polyline2d.

    Restituisce l'entità creata, o None se:
      - segments è vuoto (forma durevole con source_ref, o spline)
      - tutti i segmenti sono SplineSeg
    """
    segments = getattr(contour, "segments", [])
    if not segments:
        return None

    has_spline = any(isinstance(s, SplineSeg) for s in segments)
    if has_spline:
        return None

    pts = segments_to_pts_with_bulge(segments)
    if not pts:
        return None

    is_r12 = msp.doc is not None and msp.doc.dxfversion < "AC1015"
    if is_r12:
        pline = msp.add_polyline2d(
            [(p[0], p[1]) for p in pts],
            dxfattribs={"layer": layer, "color": 256},
        )
        for vertex, pt in zip(pline.vertices, pts):
            if pt[4] != 0.0:
                vertex.dxf.bulge = pt[4]
        pline.close(True)
        return pline
    else:
        return msp.add_lwpolyline(
            pts,
            format="xyseb",
            dxfattribs={"layer": layer, "color": 256},
            close=True,
        )