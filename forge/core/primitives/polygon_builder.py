"""
core/primitives/polygon_builder.py
-----------------------------------
Funzione pura per costruire un Polygon shapely da una lista di primitive.

Zero dipendenze da ezdxf o qualsiasi formato specifico.
Chiamata dall'adapter DXF (e futuri adapter) — non la possiede.
"""

from __future__ import annotations

import math
from typing import List, Optional

from shapely.geometry import Polygon

from . import LineSeg, ArcSeg, SplineSeg, DiscretizedArcSeg
from ..geometry import num_segments_for_bulge

try:
    from ezdxf.math import bulge_to_arc
except ImportError:
    bulge_to_arc = None


def build_polygon(
    primitives: List[LineSeg | ArcSeg | SplineSeg | DiscretizedArcSeg],
) -> Optional[Polygon]:
    """
    Costruisce un Polygon shapely da una lista di primitive geometriche.
    Restituisce None se la geometria non è valida o ha meno di 3 punti.
    """
    if not primitives:
        return None

    has_spline = any(isinstance(p, SplineSeg) for p in primitives)

    if has_spline:
        return _polygon_from_spline_primitives(primitives)
    return _polygon_from_line_arc_primitives(primitives)


# ---------------------------------------------------------------------------
# Helper privati
# ---------------------------------------------------------------------------

def _polygon_from_line_arc_primitives(primitives: list) -> Optional[Polygon]:
    pts_with_bulge = []
    for prim in primitives:
        if isinstance(prim, LineSeg):
            pts_with_bulge.append((prim.start[0], prim.start[1], 0.0, 0.0, 0.0))
        elif isinstance(prim, ArcSeg):
            pts_with_bulge.append((prim.start[0], prim.start[1], 0.0, 0.0, prim.bulge))

    pts = _discretize_pts_with_bulge(pts_with_bulge)
    return _make_polygon(pts)


def _polygon_from_spline_primitives(primitives: list) -> Optional[Polygon]:
    pts = []
    for prim in primitives:
        if isinstance(prim, LineSeg):
            pts.append(prim.start)
        elif isinstance(prim, DiscretizedArcSeg):
            pts.extend(prim.points[1:])
        elif isinstance(prim, SplineSeg):
            pts.extend(prim.points[1:])

    return _make_polygon(pts)


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
            angle  = a2 - a1
            num_seg = num_segments_for_bulge(bulge)
            for j in range(1, num_seg):
                a = a1 + angle * j / num_seg
                poly_pts.append((cx + radius * math.cos(a),
                                 cy + radius * math.sin(a)))
    return poly_pts


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