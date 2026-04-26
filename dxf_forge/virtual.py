"""
virtual.py
-----------
Crea una rappresentazione in memoria di una shape da costruire.

VirtualShape ha due modalità:
  - from_loop:         loop di LINE/ARC → materializzata come LWPOLYLINE nel msp
  - from_spline_loop:  loop con SPLINE → entità originali restano nel msp
                       con layer/colore assegnati. La geometria esatta della
                       SPLINE viene preservata.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any
from shapely.geometry import Polygon
from .geometry import arc_to_linestrings
from .graph import spline_to_points, arc_to_bulge, spline_endpoints


# ---------------------------------------------------------------------------
# VirtualShape — shape costruita in memoria dal passo 1
# ---------------------------------------------------------------------------

@dataclass
class VirtualShape:
    """
    Rappresentazione in memoria di una shape da costruire.
    Prodotta dal passo 1, consumata dal passo 3.

    Non costruire direttamente — usa i classmethod:
      - VirtualShape.from_loop(loop, layer, color)
      - VirtualShape.from_spline_loop(loop, layer, color)

    from_loop:         has_spline=False, pts_with_bulge popolato
    from_spline_loop:  has_spline=True,  pts_with_bulge vuoto, loop salvato
    """
    pts_with_bulge: list          # vertici per LWPOLYLINE (solo se not has_spline)
    polygon: Polygon              # polygon Shapely per gerarchia (sempre)
    layer: str
    color: int
    has_spline: bool = False      # True se il loop contiene almeno una SPLINE
    loop: list = field(default_factory=list)  # entità originali (entity, rev)
    entity: Optional[Any] = None  # LWPOLYLINE materializzata (solo se not has_spline)

    # -----------------------------------------------------------------------
    # Costruttori
    # -----------------------------------------------------------------------

    @classmethod
    def from_loop(cls, loop, layer: str, color: int) -> Optional['VirtualShape']:
        """
        Costruisce un VirtualShape da un loop di LINE e/o ARC.
        Popola pts_with_bulge con bulge reali per gli ARC.
        Ritorna None se il loop non forma un polygon valido.
        """
        pts_with_bulge = []
        poly_pts = []
        _last_exit = None

        for entity, rev in loop:
            if entity.dxftype() == 'LINE':
                if rev:
                    sx, sy = entity.dxf.end.x,   entity.dxf.end.y
                    ex, ey = entity.dxf.start.x, entity.dxf.start.y
                else:
                    sx, sy = entity.dxf.start.x, entity.dxf.start.y
                    ex, ey = entity.dxf.end.x,   entity.dxf.end.y
                pts_with_bulge.append((sx, sy, 0.0, 0.0, 0.0))
                poly_pts.append((sx, sy))
                _last_exit = (ex, ey)

            elif entity.dxftype() == 'ARC':
                if _last_exit is not None:
                    poly_pts.append(_last_exit)
                    _last_exit = None
                entry_pt, _, bulge = arc_to_bulge(entity, reversed=rev)
                pts_with_bulge.append((entry_pt[0], entry_pt[1], 0.0, 0.0, bulge))
                arc_pts = []
                for seg in arc_to_linestrings(entity, num_segments=32):
                    for coord in seg.coords:
                        arc_pts.append(coord)
                if rev:
                    arc_pts = list(reversed(arc_pts))
                poly_pts.extend(arc_pts)

        poly = _build_polygon(poly_pts)
        if poly is None:
            return None

        return cls(
            pts_with_bulge=pts_with_bulge,
            polygon=poly,
            layer=layer,
            color=color,
            has_spline=False,
            loop=loop,
        )

    @classmethod
    def from_spline_loop(cls, loop, layer: str, color: int) -> Optional['VirtualShape']:
        poly_pts = []
        _last_exit = None

        for entity, rev in loop:
            if entity.dxftype() == 'LINE':
                if rev:
                    sx, sy = entity.dxf.end.x,   entity.dxf.end.y
                    ex, ey = entity.dxf.start.x, entity.dxf.start.y
                else:
                    sx, sy = entity.dxf.start.x, entity.dxf.start.y
                    ex, ey = entity.dxf.end.x,   entity.dxf.end.y
                poly_pts.append((sx, sy))
                _last_exit = (ex, ey)

            elif entity.dxftype() == 'ARC':
                if _last_exit is not None:
                    poly_pts.append(_last_exit)
                    _last_exit = None
                arc_pts = []
                for seg in arc_to_linestrings(entity, num_segments=32):
                    for coord in seg.coords:
                        arc_pts.append(coord)
                if rev:
                    arc_pts = list(reversed(arc_pts))
                poly_pts.extend(arc_pts)

            elif entity.dxftype() == 'SPLINE':
                if _last_exit is not None:
                    poly_pts.append(_last_exit)
                    _last_exit = None
                s_pts = spline_to_points(entity)
                if rev:
                    s_pts = list(reversed(s_pts))
                for sp in s_pts[1:]:
                    poly_pts.append(sp)

        poly = _build_polygon(poly_pts)
        if poly is None:
            return None

        return cls(
            pts_with_bulge=[],
            polygon=poly,
            layer=layer,
            color=color,
            has_spline=True,
            loop=loop,
        )
# ---------------------------------------------------------------------------
# Helper privato — costruzione polygon Shapely
# ---------------------------------------------------------------------------

def _build_polygon(pts: list) -> Optional[Polygon]:
    """
    Costruisce un Polygon Shapely da una lista di punti.
    Ritorna None se i punti sono insufficienti o il polygon è invalido.
    """
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
# Passo 1 — routing loop → VirtualShape
# ---------------------------------------------------------------------------

def _loop_to_virtual_shape(loop, layer, color) -> Optional['VirtualShape']:
    """
    Instrada il loop al costruttore corretto in base alla presenza di SPLINE.
    Non scrive nulla nel msp.
    """
    if any(e.dxftype() == 'SPLINE' for e, _ in loop):
        return VirtualShape.from_spline_loop(loop, layer, color)
    return VirtualShape.from_loop(loop, layer, color)


# ---------------------------------------------------------------------------
# Passo 3 — scrittura msp
# ---------------------------------------------------------------------------

def _write_virtual_shape(msp, vs: 'VirtualShape'):
    """
    Materializza una VirtualShape nel msp.

    Se has_spline=False: scrive una LWPOLYLINE e la restituisce.
    Se has_spline=True:  assegna layer/colore alle entità originali del loop
                         e restituisce None (nessuna nuova entità creata).
    """
    if vs.has_spline:
        for entity, _ in vs.loop:
            entity.dxf.layer = vs.layer
            entity.dxf.color = vs.color
        return None

    is_r12 = msp.doc is not None and msp.doc.dxfversion < "AC1015"
    if is_r12:
        pline = msp.add_polyline2d(
            [(p[0], p[1]) for p in vs.pts_with_bulge],
            dxfattribs={'layer': vs.layer, 'color': vs.color},
        )
        for vertex, pt in zip(pline.vertices, vs.pts_with_bulge):
            if pt[4] != 0.0:
                vertex.dxf.bulge = pt[4]
        pline.close(True)
        return pline
    else:
        return msp.add_lwpolyline(
            vs.pts_with_bulge,
            format='xyseb',
            dxfattribs={'layer': vs.layer, 'color': vs.color},
            close=True,
        )