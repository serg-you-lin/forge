
"""
adapters/dxf/virtual_adapter.py
--------------------------------
Traduce loop ezdxf in Contour (core) + DxfWriteContext (dati DXF-specifici).

DxfWriteContext è l'unico oggetto che circola in _virtual_shapes:
    - contour   → geometria pura, usata da hierarchy.py per containment
    - pts_with_bulge, loop → dati DXF per il write-back
    - layer, color → metadati DXF assegnati da hierarchy.py

Unico punto che tocca ezdxf per tutto ciò che riguarda Contour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Any

from ...core.primitives import LineSeg, ArcSeg, SplineSeg, DiscretizedArcSeg
from ...core.primitives.contour import Contour
from ...core.geometry import num_segments_for_bulge
from .geometry_adapter import arc_to_bulge, arc_to_linestrings, spline_to_points


# ---------------------------------------------------------------------------
# DxfWriteContext — dati DXF-specifici, non appartengono al core
# ---------------------------------------------------------------------------

@dataclass
class DxfWriteContext:
    """
    Wrapper DXF attorno a un Contour.

    contour:        geometria pura — usata da hierarchy per containment
    pts_with_bulge: ricostruzione fedele degli archi per LWPOLYLINE
    loop:           entità ezdxf originali — tracciabilità e swap id()
    layer:          layer DXF finale (OUTER/INNER) — assegnato da hierarchy
    color:          colore DXF finale — assegnato da hierarchy
    """
    contour:        Contour
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
    has_spline = any(edge.source_ref.dxftype() == "SPLINE" for edge, _ in loop)
    primitives = []

    for edge, rev in loop:
        entity = edge.source_ref

        if entity.dxftype() == "LINE":
            seg, _ = _parse_line(entity, rev)
            primitives.append(seg)

        elif entity.dxftype() == "ARC":
            if has_spline:
                primitives.append(_parse_arc_discretized(entity, rev))
            else:
                primitives.append(_parse_arc(entity, rev))

        elif entity.dxftype() == "SPLINE":
            primitives.append(_parse_spline(entity, rev))

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


# ---------------------------------------------------------------------------
# loop → DxfWriteContext
# ---------------------------------------------------------------------------

def _loop_to_contour(loop, layer: str, color: int) -> Optional[DxfWriteContext]:
    primitives = parse_loop(loop)

    has_spline = any(isinstance(p, SplineSeg) for p in primitives)
    pts_with_bulge = [] if has_spline else _build_pts_with_bulge(primitives)

    origin = _extract_origin(loop)
    source_ref   = {"loop": loop, "pts_with_bulge": pts_with_bulge}

    contour = Contour.from_primitives(
        primitives=primitives,
        origin=origin,
        source_ref=source_ref,
    )
    if contour is None:
        return None

    return DxfWriteContext(
        contour=contour,
        pts_with_bulge=pts_with_bulge,
        loop=loop,
        layer=layer,
        color=color,
    )


def _build_pts_with_bulge(primitives: list) -> list:
    """Costruisce la lista pts_with_bulge dai primitivi line/arc."""
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
        if hasattr(e, "layer") and e.layer and e.layer != "0"
    }
    return origins.pop() if len(origins) == 1 else ""


# ---------------------------------------------------------------------------
# Write-back — unico punto che tocca ezdxf per Contour
# ---------------------------------------------------------------------------

def _write_virtual_shape(msp, ctx: DxfWriteContext):
    """Scrive il Contour su msp come LWPOLYLINE usando i dati DXF del contesto."""
    if ctx.contour.has_spline:
        pts = [
            (x, y, 0.0, 0.0, 0.0)
            for x, y in list(ctx.contour.polygon.exterior.coords)[:-1]
        ]
        return msp.add_lwpolyline(
            pts,
            format="xyseb",
            dxfattribs={"layer": ctx.layer, "color": ctx.color},
            close=True,
        )

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
            dxfattribs={"layer": ctx.layer, "color": 256},
            close=True,
        )