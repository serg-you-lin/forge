"""
core/primitives/polygon_builder.py
-----------------------------------
Funzione pura per costruire un Polygon shapely da una lista di primitive.

Zero dipendenze da ezdxf o qualsiasi formato specifico.
Chiamata dall'adapter DXF (e futuri adapter) — non la possiede.
"""

from __future__ import annotations

from typing import List, Optional

from shapely.geometry import Polygon

from . import LineSeg, ArcSeg, SplineSeg, CircleSeg, EllipseSeg


def build_polygon(
    primitives: List[LineSeg | ArcSeg | SplineSeg | CircleSeg | EllipseSeg],
    tolerance:  float = 0.01,
) -> Optional[Polygon]:
    """
    Costruisce un Polygon shapely da una lista di primitive geometriche.

    Ogni primitiva di forge si discretizza da sé (LineSeg, ArcSeg, CircleSeg,
    SplineSeg, EllipseSeg).
    Restituisce None se la geometria non è valida o ha meno di 3 punti.
    """
    if not primitives:
        return None

    pts: list = []
    for i, prim in enumerate(primitives):
        seg_pts = prim.discretize(tolerance)
        if i == 0:
            pts.extend(seg_pts)
        else:
            pts.extend(seg_pts[1:])

    return _make_polygon(pts)


# ---------------------------------------------------------------------------
# Helper privato
# ---------------------------------------------------------------------------

def _make_polygon(pts: list) -> Optional[Polygon]:
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

