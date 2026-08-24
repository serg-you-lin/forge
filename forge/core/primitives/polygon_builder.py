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

try:
    from ezdxf.math import bulge_to_arc as _ez_bulge_to_arc
except Exception:
    _ez_bulge_to_arc = None

from . import LineSeg, ArcSeg, SplineSeg, CircleSeg


def build_polygon(
    primitives: List[LineSeg | ArcSeg | SplineSeg | CircleSeg],
    tolerance:  float = 0.01,
) -> Optional[Polygon]:
    """
    Costruisce un Polygon shapely da una lista di primitive geometriche.

    Supporta LineSeg, ArcSeg, CircleSeg, SplineSeg.
    Tutte le primitive hanno il metodo discretize().
    Restituisce None se la geometria non è valida o ha meno di 3 punti.
    """
    if not primitives:
        return None

    pts: list = []
    for i, prim in enumerate(primitives):
        if hasattr(prim, "discretize"):
            seg_pts = prim.discretize(tolerance)
        elif hasattr(prim, "bulge") and hasattr(prim, "start") and hasattr(prim, "end"):
            seg_pts = _discretize_bulge_segment(prim.start, prim.end, prim.bulge)
        else:
            # Fallback per compatibilità
            seg_pts = [prim.start, prim.end]
            
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


def _discretize_bulge_segment(start, end, bulge: float) -> list:
    """
    Discretizza un segmento con bulge (per retrocompatibilità con _BulgeSeg).
    """
    x1, y1 = start
    x2, y2 = end

    if abs(bulge) <= 1e-12:
        return [start, end]

    included = 4.0 * math.atan(abs(bulge))
    n_segments = max(8, int(included / math.pi * 32))

    if _ez_bulge_to_arc is not None:
        center, _, _, radius = _ez_bulge_to_arc((x1, y1), (x2, y2), bulge)
        cx, cy = center.x, center.y
    else:
        chord = math.hypot(x2 - x1, y2 - y1)
        if chord <= 1e-12:
            return [start, end]
        radius = chord / (2.0 * math.sin(included / 2.0))
        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        dx, dy = x2 - x1, y2 - y1
        nx, ny = -dy / chord, dx / chord
        dist = radius * math.cos(included / 2.0)
        if bulge > 0:
            cx, cy = mx + nx * dist, my + ny * dist
        else:
            cx, cy = mx - nx * dist, my - ny * dist

    start_a = math.atan2(y1 - cy, x1 - cx)
    end_a = math.atan2(y2 - cy, x2 - cx)
    if bulge > 0:
        if end_a <= start_a:
            end_a += 2.0 * math.pi
    else:
        if end_a >= start_a:
            end_a -= 2.0 * math.pi
    sweep = end_a - start_a

    points = []
    for i in range(n_segments + 1):
        t = i / n_segments
        a = start_a + t * sweep
        points.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))

    return points