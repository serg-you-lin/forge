"""
core/primitives/contour.py
--------------------------
Contorno chiuso format-agnostic.

Contour è il risultato della traduzione adapter → core: una sequenza di
primitive geometriche pure che forma un anello chiuso, con il poligono
shapely già costruito.

Zero dipendenze da ezdxf o qualsiasi formato specifico.

source_ref è opaco — il core non lo tocca mai.
Ogni adapter ci mette quello che serve per la tracciabilità:
    DXF    → {"loop": [...], "pts_with_bulge": [...]}
    PDF    → oggetto pdfminer/pymupdf originale
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


@dataclass
class Contour:
    """
    Contorno chiuso formato-agnostico.

    polygon:      rappresentazione shapely — usata per containment e area
    segments:     primitive geometriche pure che compongono il contorno
    source_layer: layer sorgente (stringa vuota se non determinabile)
    source_ref:   dato opaco per tracciabilità — il core non lo tocca
    """
    polygon:      Polygon
    segments:     List[LineSeg | ArcSeg | SplineSeg | DiscretizedArcSeg] = field(default_factory=list)
    source_layer: str           = ""
    source_ref:   Optional[Any] = None

    @property
    def has_spline(self) -> bool:
        return any(isinstance(s, SplineSeg) for s in self.segments)

    @classmethod
    def from_primitives(
        cls,
        primitives:   List,
        source_layer: str  = "",
        source_ref:   Any  = None,
    ) -> Optional["Contour"]:

        has_spline = any(isinstance(p, SplineSeg) for p in primitives)

        if has_spline:
            return cls._from_spline_primitives(primitives, source_layer, source_ref)
        return cls._from_line_arc_primitives(primitives, source_layer, source_ref)

    @classmethod
    def _from_line_arc_primitives(cls, primitives, source_layer, source_ref):
        pts_with_bulge = []

        for prim in primitives:
            if isinstance(prim, LineSeg):
                pts_with_bulge.append((prim.start[0], prim.start[1], 0.0, 0.0, 0.0))
            elif isinstance(prim, ArcSeg):
                pts_with_bulge.append((prim.start[0], prim.start[1], 0.0, 0.0, prim.bulge))

        poly_pts = _discretize_pts_with_bulge(pts_with_bulge)
        poly = _build_polygon(poly_pts)
        if poly is None:
            return None

        return cls(
            polygon=poly,
            segments=primitives,
            source_layer=source_layer,
            source_ref=source_ref,
        )

    @classmethod
    def _from_spline_primitives(cls, primitives, source_layer, source_ref):
        poly_pts = []

        for prim in primitives:
            if isinstance(prim, LineSeg):
                poly_pts.append(prim.start)
            elif isinstance(prim, DiscretizedArcSeg):
                poly_pts.extend(prim.points[1:])
            elif isinstance(prim, SplineSeg):
                poly_pts.extend(prim.points[1:])

        poly = _build_polygon(poly_pts)
        if poly is None:
            return None

        return cls(
            polygon=poly,
            segments=primitives,
            source_layer=source_layer,
            source_ref=source_ref,
        )


# ---------------------------------------------------------------------------
# Helper privati
# ---------------------------------------------------------------------------

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
        if poly.geom_type == "MultiPolygon":
            poly = max(poly.geoms, key=lambda p: p.area)
        return poly if not poly.is_empty else None
    except Exception:
        return None