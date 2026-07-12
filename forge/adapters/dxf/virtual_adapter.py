

"""
adapters/dxf/virtual_adapter.py
--------------------------------
Traduce entità ezdxf in primitive geometriche pure (LineSeg, ArcSeg, SplineSeg)
e le passa a VirtualShape.

DxfWriteContext tiene i dati DXF-specifici (pts_with_bulge, loop) necessari
per riscrivere la shape su msp — questi dati non appartengono al core.

Unico punto che tocca ezdxf per tutto ciò che riguarda VirtualShape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Any

from ...core.primitives.virtual import VirtualShape, _build_polygon
from ...core.primitives import LineSeg, ArcSeg, SplineSeg, DiscretizedArcSeg
from ...core.geometry import num_segments_for_bulge
from .geometry_adapter import arc_to_bulge, arc_to_linestrings, spline_to_points


# ---------------------------------------------------------------------------
# Contesto DXF per la scrittura — dati formato-specifici
# ---------------------------------------------------------------------------

@dataclass
class DxfWriteContext:
    """
    Dati DXF-specifici associati a una VirtualShape.

    pts_with_bulge: necessario per ricostruire fedelmente gli archi
                    nella LWPOLYLINE di output.
    loop:           riferimento alle entità ezdxf originali — tracciabilità.

    Non appartiene al core — vive solo nell'adapter.
    """
    vs:             VirtualShape
    pts_with_bulge: list = field(default_factory=list)
    loop:           list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing ezdxf → primitive
# ---------------------------------------------------------------------------

def parse_loop(loop) -> List:
    """
    Converte un loop di (Edge, rev) in lista di primitive geometriche pure.

    Restituisce List[LineSeg | ArcSeg | SplineSeg | DiscretizedArcSeg].
    Se il loop contiene SPLINE, gli archi vengono discretizzati via
    arc_to_linestrings (DiscretizedArcSeg).
    """
    has_spline = any(edge.entity.dxftype() == 'SPLINE' for edge, _ in loop)
    primitives = []

    for edge, rev in loop:
        entity = edge.entity

        if entity.dxftype() == 'LINE':
            seg, _ = _parse_line(entity, rev)
            primitives.append(seg)

        elif entity.dxftype() == 'ARC':
            if has_spline:
                primitives.append(_parse_arc_discretized(entity, rev))
            else:
                primitives.append(_parse_arc(entity, rev))

        elif entity.dxftype() == 'SPLINE':
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
# Routing loop → DxfWriteContext
# ---------------------------------------------------------------------------

def _loop_to_virtual_shape(loop, layer, color) -> Optional[DxfWriteContext]:
    """
    Converte un loop in DxfWriteContext.

    Restituisce None se la shape non è costruibile (loop vuoto, degenere).
    Il chiamante usa ctx.vs per la topologia, ctx.pts_with_bulge per la scrittura.
    """
    primitives = parse_loop(loop)
    vs = VirtualShape.from_primitives(primitives, layer, color, loop=loop)
    if vs is None:
        return None

    pts_with_bulge = vs.source_ref.get("pts_with_bulge", []) if vs.source_ref else []

    return DxfWriteContext(
        vs=vs,
        pts_with_bulge=pts_with_bulge,
        loop=loop,
    )


# ---------------------------------------------------------------------------
# Scrittura msp — unico punto che tocca ezdxf per VirtualShape
# ---------------------------------------------------------------------------

def _write_virtual_shape(msp, ctx: DxfWriteContext):
    """Scrive la VirtualShape su msp usando i dati DXF-specifici del contesto."""
    vs = ctx.vs

    if vs.has_spline:
        pts = [(x, y, 0.0, 0.0, 0.0)
               for x, y in list(vs.polygon.exterior.coords)[:-1]]
        return msp.add_lwpolyline(
            pts,
            format='xyseb',
            dxfattribs={'layer': vs.layer, 'color': vs.color},
            close=True,
        )

    is_r12 = msp.doc is not None and msp.doc.dxfversion < "AC1015"
    if is_r12:
        pline = msp.add_polyline2d(
            [(p[0], p[1]) for p in ctx.pts_with_bulge],
            dxfattribs={'layer': vs.layer, 'color': vs.color},
        )
        for vertex, pt in zip(pline.vertices, ctx.pts_with_bulge):
            if pt[4] != 0.0:
                vertex.dxf.bulge = pt[4]
        pline.close(True)
        return pline
    else:
        return msp.add_lwpolyline(
            ctx.pts_with_bulge,
            format='xyseb',
            dxfattribs={'layer': vs.layer, 'color': 256},
            close=True,
        )