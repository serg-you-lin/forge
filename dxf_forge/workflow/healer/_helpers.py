# ---------------------------------------------------------------------------
# Helper privati
# ---------------------------------------------------------------------------

import math
from typing import Optional, Set
from shapely.geometry import Polygon

from ...core.geometry import ( arc_endpoints
                       )
from ...core.graph import (
                    spline_to_points, spline_endpoints,
                    round_point)


def _special_layer_names(special_layers: dict) -> Set[str]:
    if not special_layers:
        return set()
    return {k.lower() for k in special_layers}


def _is_special(entity, special_names: Set[str]) -> bool:
    if not special_names:
        return False
    layer = entity.dxf.layer.lower() if entity.dxf.hasattr("layer") else ""
    return any(sl in layer for sl in special_names)

def _free_endpoints(graph, msp, node_decimals: int = 1,
                    special_names: Set[str] = None) -> list:
    """
    Restituisce gli endpoint di LINE, ARC e SPLINE con grado < 2 nel grafo.
    Esclude le entità su special_layers.
    """
    if special_names is None:
        special_names = set()
    free = []

    for line in msp.query('LINE'):
        if _is_special(line, special_names):
            continue
        s = round_point((line.dxf.start.x, line.dxf.start.y), node_decimals)
        e = round_point((line.dxf.end.x,   line.dxf.end.y),   node_decimals)
        if len(graph.get(s, [])) < 2:
            free.append(((line.dxf.start.x, line.dxf.start.y), line, 'start'))
        if len(graph.get(e, [])) < 2:
            free.append(((line.dxf.end.x, line.dxf.end.y), line, 'end'))

    for arc in msp.query('ARC'):
        if _is_special(arc, special_names):
            continue
        s, e = arc_endpoints(arc)
        s_r = round_point(s, node_decimals)
        e_r = round_point(e, node_decimals)
        if len(graph.get(s_r, [])) < 2:
            free.append((s, arc, 'start'))
        if len(graph.get(e_r, [])) < 2:
            free.append((e, arc, 'end'))

    for spline in msp.query('SPLINE'):
        if _is_special(spline, special_names):
            continue
        s, e = spline_endpoints(spline)
        if s is None or e is None:
            continue
        s_r = round_point(s, node_decimals)
        e_r = round_point(e, node_decimals)
        if len(graph.get(s_r, [])) < 2:
            free.append((s, spline, 'start'))
        if len(graph.get(e_r, [])) < 2:
            free.append((e, spline, 'end'))

    return free


def _spline_is_closed(spline, tolerance: float = 0.01) -> bool:
    """Restituisce True se la SPLINE è chiusa (start ≈ end)."""
    s, e = spline_endpoints(spline)
    if s is None or e is None:
        return False
    return math.sqrt((e[0] - s[0])**2 + (e[1] - s[1])**2) < tolerance


def _spline_to_polygon(spline) -> Optional[Polygon]:
    """
    Converte una SPLINE chiusa in Polygon Shapely via discretizzazione.
    Usato solo internamente per la gerarchia.
    """
    pts = spline_to_points(spline)
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