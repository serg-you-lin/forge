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

from dataclasses import dataclass, field
from typing import Optional, List

from shapely.geometry import Polygon

from ...core.primitives import LineSeg, ArcSeg, SplineSeg, DiscretizedArcSeg
from ...core.primitives.polygon_builder import build_polygon
from ...core.geometry import num_segments_for_bulge
from .geometry_adapter import arc_to_bulge, arc_to_linestrings, spline_to_points


class DxfEntityDispatcher:
    """Centralizes the DXF entity-type routing used by the adapter layer."""

    def __init__(self, entity):
        self.entity = entity
        self.kind = entity.dxftype()

    def parse(self, rev: bool = False, has_spline: bool = False):
        if self.kind == "LINE":
            return _parse_line(self.entity, rev)[0]
        if self.kind == "ARC":
            if has_spline:
                return _parse_arc_discretized(self.entity, rev)
            return _parse_arc(self.entity, rev)
        if self.kind == "SPLINE":
            return _parse_spline(self.entity, rev)
        if self.kind in ("LWPOLYLINE", "POLYLINE"):
            return _parse_polyline(self.entity, rev)
        if self.kind == "CIRCLE":
            return _parse_circle(self.entity)
        return None


def _parse_polyline(entity, rev) -> list:
    if entity.dxftype() == "POLYLINE":
        # POLYLINE (R12 legacy) non ha get_points() — solo LWPOLYLINE lo ha.
        points = [
            (v.dxf.location.x, v.dxf.location.y, v.dxf.bulge)
            for v in entity.vertices
        ]
    else:
        points = list(entity.get_points('xyb'))

    if not points:
        return []

    if rev:
        reversed_points = []
        n = len(points)
        for i in range(n):
            idx = (-i) % n
            x, y, _ = points[idx]
            prev_idx = (idx - 1) % n
            bulge = -points[prev_idx][2]
            reversed_points.append((x, y, bulge))
        points = reversed_points

    primitives = []
    n = len(points)
    for i in range(n):
        x1, y1, bulge = points[i]
        x2, y2, _ = points[(i + 1) % n]
        if abs(bulge) > 1e-6:
            primitives.append(ArcSeg(start=(x1, y1), end=(x2, y2), bulge=bulge))
        else:
            primitives.append(LineSeg(start=(x1, y1), end=(x2, y2)))
    return primitives



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
    origin: str = ""
    pts_with_bulge: list = field(default_factory=list)
    loop:           list = field(default_factory=list)
    layer:          str  = ""
    color:          int  = 256


# ---------------------------------------------------------------------------
# Parsing ezdxf → primitive
# ---------------------------------------------------------------------------

def parse_loop(loop) -> List:
    """
    Converte un loop di (Edge, rev) in lista di primitive geometriche pure.
    Restituisce List[LineSeg | ArcSeg | SplineSeg | DiscretizedArcSeg].
    Se il loop contiene SPLINE, gli archi vengono discretizzati.
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


def _parse_line(entity, rev) -> tuple:
    if rev:
        start = (entity.dxf.end.x,   entity.dxf.end.y)
        end   = (entity.dxf.start.x, entity.dxf.start.y)
    else:
        start = (entity.dxf.start.x, entity.dxf.start.y)
        end   = (entity.dxf.end.x,   entity.dxf.end.y)
    return LineSeg(start=start, end=end), end


def _parse_arc(entity, rev) -> ArcSeg:
    _, _, bulge = arc_to_bulge(entity, reversed=rev)
    if rev:
        start = (entity.end_point.x,   entity.end_point.y)
        end   = (entity.start_point.x, entity.start_point.y)
    else:
        start = (entity.start_point.x, entity.start_point.y)
        end   = (entity.end_point.x,   entity.end_point.y)
    return ArcSeg(start=start, end=end, bulge=bulge)


def _parse_arc_discretized(entity, rev) -> DiscretizedArcSeg:
    _, _, bulge = arc_to_bulge(entity, reversed=rev)
    num_seg = num_segments_for_bulge(bulge)
    pts = []
    for seg in arc_to_linestrings(entity, num_segments=num_seg):
        pts.extend(seg.coords)
    if rev:
        pts = list(reversed(pts))
    return DiscretizedArcSeg(points=pts)


def _parse_spline(entity, rev) -> SplineSeg:
    pts = spline_to_points(entity)
    if rev:
        pts = list(reversed(pts))
    return SplineSeg(points=pts)


def _parse_circle(entity) -> List[ArcSeg]:
    """
    Converte un CIRCLE ezdxf in due ArcSeg da 180° (bulge=1.0).
    
    Il cerchio DXF non ha punto di inizio/fine — costruiamo due semicirconferenze:
    - prima: punto destro → punto sinistro (0° → 180°)
    - seconda: punto sinistro → punto destro (180° → 360°)
    
    bulge = tan(θ/4) dove θ è l'angolo sotteso in radianti.
    Per 180°: bulge = tan(π/4) = 1.0
    """
    cx = entity.dxf.center.x
    cy = entity.dxf.center.y
    r = entity.dxf.radius
    return [
        ArcSeg(start=(cx + r, cy), end=(cx - r, cy), bulge=1.0),
        ArcSeg(start=(cx - r, cy), end=(cx + r, cy), bulge=1.0),
    ]


# ---------------------------------------------------------------------------
# loop → DxfWriteContext
# ---------------------------------------------------------------------------

def _loop_to_contour(loop, layer: str, color: int) -> Optional[DxfWriteContext]:
    primitives = parse_loop(loop)

    has_spline     = any(isinstance(p, SplineSeg) for p in primitives)
    pts_with_bulge = [] if has_spline else _build_pts_with_bulge(primitives)

    polygon = build_polygon(primitives)
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
        elif isinstance(prim, ArcSeg):
            pts.append((prim.start[0], prim.start[1], 0.0, 0.0, prim.bulge))
    return pts


def _extract_origin(loop: list) -> str:
    if not loop:
        return ""
    origins = {
        e.layer for e, _ in loop
        if hasattr(e, "layer") and e.layer
    }
    return origins.pop() if len(origins) == 1 else ""


# ---------------------------------------------------------------------------
# Write-back — unico punto che tocca ezdxf per le forme chiuse
# ---------------------------------------------------------------------------

def _write_virtual_shape(msp, ctx: DxfWriteContext):
    """Scrive il DxfWriteContext su msp come LWPOLYLINE."""
    if ctx.has_spline:
        # Preserve SPLINE exactly as source: no polygon/polyline rewrite.
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