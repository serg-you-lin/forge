"""
workflow/healer/_helpers.py
---------------------------
Helper privati di heal() — geometria e topologia, zero semantica.
"""

import math
from typing import Optional, Set

from shapely.geometry import Polygon

from ...core.geometry import arc_endpoints
from ...core.graph import spline_to_points, spline_endpoints, round_point


def _spline_is_closed(spline, tolerance: float = 0.01) -> bool:
    """Restituisce True se la SPLINE è chiusa (start ≈ end)."""
    s, e = spline_endpoints(spline)
    if s is None or e is None:
        return False
    return math.sqrt((e[0] - s[0]) ** 2 + (e[1] - s[1]) ** 2) < tolerance


def _spline_to_polygon(spline) -> Optional[Polygon]:
    """
    Converte una SPLINE chiusa in Polygon Shapely via discretizzazione.
    Usato solo internamente per la gerarchia padre-figlio.
    """
    pts = spline_to_points(spline)
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
    
