"""
adapters/dxf/virtual_adapter.py
--------------------------------
Traduce loop ezdxf in DxfWriteContext (dati DXF-specifici).

DxfWriteContext è l'unico oggetto che circola in _virtual_shapes:
    - polygon    → geometria pura, usata da hierarchy.py per containment
    - has_spline → flag per il write-back
    - pts_with_bulge, loop → dati DXF per il write-back
    - layer, color → metadati DXF assegnati da hierarchy.py

Unico punto che tocca ezdxf per tutto ciò che riguarda le forme chiuse.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, List

from shapely.geometry import Polygon

from ...core.primitives import LineSeg, ArcSeg, SplineSeg
from ...core.primitives.polygon_builder import build_polygon
from ...core.primitives.segments import DEFAULT_TOLERANCE


# ---------------------------------------------------------------------------
# Tipo privato — bulge DXF per write-back fedele. Eliminato in Fase 3.
# ---------------------------------------------------------------------------

@dataclass
class _BulgeSeg:
    """Arco LWPOLYLINE con bulge — non esce da questo file. Fase 3 lo elimina."""
    start: tuple
    end:   tuple
    bulge: float


# ---------------------------------------------------------------------------
# DxfWriteContext — dati DXF-specifici, non appartengono al core
# ---------------------------------------------------------------------------

@dataclass
class DxfWriteContext:
    """
    Contesto DXF per il write-back di una forma chiusa.

    polygon:        geometria pura — usata da hierarchy per containment
    has_spline:     True se il contorno contiene spline
    pts_with_bulge: ricostruzione fedele degli archi per LWPOLYLINE
    loop:           entità ezdxf originali — tracciabilità e swap id()
    layer:          layer DXF finale (OUTER/INNER) — assegnato da hierarchy
    color:          colore DXF finale — assegnato da hierarchy
    """
    polygon:        Polygon
    has_spline:     bool = False
    origin:         str  = ""
    pts_with_bulge: list = field(default_factory=list)
    loop:           list = field(default_factory=list)
    layer:          str  = ""
    color:          int  = 256


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

class DxfEntityDispatcher:
    """Centralizes the DXF entity-type routing used by the adapter layer."""

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


# def _parse_arc(entity, rev) -> ArcSeg:
#     cx = entity.dxf.center.x
#     cy = entity.dxf.center.y
#     r  = entity.dxf.radius
#     sa = math.radians(entity.dxf.start_angle)
#     ea = math.radians(entity.dxf.end_angle)
#     if rev:
#         sa, ea = ea, sa
#     return ArcSeg(center=(cx, cy), radius=r, start_angle=sa, end_angle=ea, ccw=not rev)

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
    """
    Converte una spline ezdxf in SplineSeg.
    
    FASE 3: popolare degree/control_points/knots/weights dalla spline ezdxf
    e usare SplineSeg.discretize() con BSpline evaluator.
    Per ora: estrai punti dal flattening e usali come control_points.
    """
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
        ArcSeg(center=(cx, cy), radius=r, start_angle=0.0,      end_angle=math.pi,   ccw=True),
        ArcSeg(center=(cx, cy), radius=r, start_angle=math.pi,  end_angle=2*math.pi, ccw=True),
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

    is_closed = bool(getattr(entity, "is_closed", False) or getattr(entity, "closed", False))

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
# loop → DxfWriteContext
# ---------------------------------------------------------------------------

def _loop_to_contour(loop, layer: str, color: int) -> Optional[DxfWriteContext]:
    primitives = parse_loop(loop)

    has_spline     = any(isinstance(p, SplineSeg) for p in primitives)
    pts_with_bulge = [] if has_spline else _build_pts_with_bulge(primitives)

    polygon = build_polygon(primitives, DEFAULT_TOLERANCE)

    if polygon is None:
        return None

    return DxfWriteContext(
        polygon=polygon,
        has_spline=has_spline,
        origin=_extract_origin(loop),
        pts_with_bulge=pts_with_bulge,
        loop=loop,
        layer=layer,
        color=color,
    )


def _build_pts_with_bulge(primitives: list) -> list:
    pts = []
    for prim in primitives:
        if isinstance(prim, LineSeg):
            pts.append((prim.start[0], prim.start[1], 0.0, 0.0, 0.0))
        elif isinstance(prim, _BulgeSeg):
            pts.append((prim.start[0], prim.start[1], 0.0, 0.0, prim.bulge))
    return pts


def _extract_origin(loop: list) -> str:
    """
    Estrae il layer DXF originale dalle entità sorgente del loop.
    
    NOTA: legge da edge.source_ref.dxf.layer, non da edge.layer
    perché vogliamo il layer DXF originale, non il layer topologico.
    """
    if not loop:
        return ""
    
    origins = set()
    for edge, _ in loop:
        source = edge.source_ref
        # Accedi al layer DXF dell'entità sorgente
        if hasattr(source, 'dxf') and hasattr(source.dxf, 'layer'):
            layer = source.dxf.layer
            if layer:  # Solo layer non vuoti
                origins.add(layer)
    
    # Restituisci il layer solo se tutte le entità hanno lo stesso layer
    return origins.pop() if len(origins) == 1 else ""


# ---------------------------------------------------------------------------
# Write-back — unico punto che tocca ezdxf per le forme chiuse
# ---------------------------------------------------------------------------

def _write_virtual_shape(msp, ctx: DxfWriteContext):
    """Scrive il DxfWriteContext su msp come LWPOLYLINE."""
    if ctx.has_spline:
        return None

    is_r12 = msp.doc is not None and msp.doc.dxfversion < "AC1015"
    if is_r12:
        pline = msp.add_polyline2d(
            [(p[0], p[1]) for p in ctx.pts_with_bulge],
            dxfattribs={"layer": ctx.layer, "color": ctx.color},
        )
        for vertex, pt in zip(pline.vertices, ctx.pts_with_bulge):
            if pt[4] != 0.0:
                vertex.dxf.bulge = pt[4]
        pline.close(True)
        return pline
    else:
        return msp.add_lwpolyline(
            ctx.pts_with_bulge,
            format="xyseb",
            dxfattribs={"layer": ctx.layer, "color": ctx.color},
            close=True,
        )