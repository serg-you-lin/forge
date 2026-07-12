

"""
core/virtual.py
---------------
Rappresentazione in memoria di una shape da costruire.

VirtualShape è indipendente dal formato sorgente (DXF, PDF, SVG, raster).
Riceve primitive geometriche pure (LineSeg, ArcSeg, SplineSeg) prodotte
dall'adapter e costruisce la rappresentazione interna.

Zero dipendenze da ezdxf.

source_ref è un campo opaco — il core non lo tocca mai.
Ogni adapter ci mette quello che serve per la tracciabilità:
    DXF   → loop: List[(Edge, rev)]
    PDF   → oggetto pdfminer/pymupdf originale
    raster → contorno OpenCV numpy array
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional
from shapely.geometry import Polygon
import math

from . import LineSeg, ArcSeg, SplineSeg, DiscretizedArcSeg
from ..geometry import num_segments_for_bulge

try:
    from ezdxf.math import bulge_to_arc
except ImportError:
    bulge_to_arc = None


# ---------------------------------------------------------------------------
# VirtualShape
# ---------------------------------------------------------------------------

@dataclass
class VirtualShape:
    polygon:      Polygon
    layer:        str
    color:        int
    has_spline:   bool         = False
    source_layer: str          = ""
    source_ref:   Optional[Any] = None  # opaco — vedi docstring modulo

    @classmethod
    def from_primitives(
        cls,
        primitives: List,
        layer:      str,
        color:      int,
        loop:       list = None,  # mantenuto per compatibilità — finisce in source_ref
    ) -> Optional['VirtualShape']:

        has_spline = any(isinstance(p, SplineSeg) for p in primitives)

        if has_spline:
            return cls._from_spline_primitives(primitives, layer, color, loop or [])
        return cls._from_line_arc_primitives(primitives, layer, color, loop or [])

    @classmethod
    def _from_line_arc_primitives(cls, primitives, layer, color, loop):
        pts_with_bulge = []

        for prim in primitives:
            if isinstance(prim, LineSeg):
                pts_with_bulge.append((prim.start[0], prim.start[1], 0.0, 0.0, 0.0))

            elif isinstance(prim, ArcSeg):
                if pts_with_bulge and pts_with_bulge[-1][4] == 0.0:
                    last = pts_with_bulge[-1]
                    pts_with_bulge[-1] = (last[0], last[1], 0.0, 0.0, 0.0)
                pts_with_bulge.append((prim.start[0], prim.start[1], 0.0, 0.0, prim.bulge))

        poly_pts = _discretize_pts_with_bulge(pts_with_bulge)
        poly = _build_polygon(poly_pts)
        if poly is None:
            return None

        source_layer = _extract_source_layer(loop)
        return cls(
            polygon=poly,
            layer=layer,
            color=color,
            has_spline=False,
            source_layer=source_layer,
            source_ref={"loop": loop, "pts_with_bulge": pts_with_bulge},
        )

    @classmethod
    def _from_spline_primitives(cls, primitives, layer, color, loop):
        poly_pts = []

        for prim in primitives:
            if isinstance(prim, LineSeg):
                poly_pts.append(prim.start)
            elif isinstance(prim, DiscretizedArcSeg):
                poly_pts.extend(prim.points[1:])
            elif isinstance(prim, SplineSeg):
                for pt in prim.points[1:]:
                    poly_pts.append(pt)

        poly = _build_polygon(poly_pts)
        if poly is None:
            return None

        source_layer = _extract_source_layer(loop)
        return cls(
            polygon=poly,
            layer=layer,
            color=color,
            has_spline=True,
            source_layer=source_layer,
            source_ref={"loop": loop, "pts_with_bulge": []},
        )


# ---------------------------------------------------------------------------
# Helper privati
# ---------------------------------------------------------------------------

def _extract_source_layer(loop: list) -> str:
    if not loop:
        return ""
    source_layers = {
        e.layer for e, _ in loop
        if hasattr(e, 'layer') and e.layer and e.layer != "0"
    }
    return source_layers.pop() if len(source_layers) == 1 else ""


def _discretize_pts_with_bulge(pts_with_bulge: list) -> list:
    poly_pts = []
    n = len(pts_with_bulge)
    for i in range(n):
        x1, y1, _, _, bulge = pts_with_bulge[i]
        x2, y2, _, _, _     = pts_with_bulge[(i + 1) % n]
        poly_pts.append((x1, y1))
        if abs(bulge) > 1e-6:
            center, _, _, radius = bulge_to_arc((x1, y1), (x2, y2), bulge)
            cx, cy = center.x, center.y
            a1 = math.atan2(y1 - cy, x1 - cx)
            a2 = math.atan2(y2 - cy, x2 - cx)
            if bulge > 0:
                if a2 <= a1:
                    a2 += 2 * math.pi
            else:
                if a2 >= a1:
                    a2 -= 2 * math.pi
            angle = a2 - a1
            num_seg = num_segments_for_bulge(bulge)
            for j in range(1, num_seg):
                a = a1 + angle * j / num_seg
                poly_pts.append((cx + radius * math.cos(a),
                                 cy + radius * math.sin(a)))
    return poly_pts


def _build_polygon(pts: list) -> Optional[Polygon]:
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