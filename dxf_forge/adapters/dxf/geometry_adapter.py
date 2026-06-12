"""
adapters/dxf/geometry_adapter.py
---------------------------
Writeback DXF per la chiusura dei gap tra entità LINE e ARC.

Questo modulo conosce ezdxf e modifica entità in-place.
La logica geometrica pura (intersezioni, distanze) vive in core/geometry.py.

Funzioni pubbliche:
    free_endpoints_from_msp — trova endpoint liberi nel grafo
    close_gaps              — corregge gap e overlap tra LINE e ARC
"""

import math
from typing import List, Tuple, Optional

from ...core.geometry import arc_endpoints, round_point, _distance, _line_intersection, _circle_line_intersections, _circle_circle_intersections, _closest_to
from ...core.graph import spline_endpoints

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Writeback DXF — lettura e scrittura su entity.dxf
# ---------------------------------------------------------------------------

def _arc_endpoint(arc, role: str) -> Point:
    cx, cy = arc.dxf.center.x, arc.dxf.center.y
    r = arc.dxf.radius
    angle = arc.dxf.start_angle if role == 'start' else arc.dxf.end_angle
    return (cx + r * math.cos(math.radians(angle)),
            cy + r * math.sin(math.radians(angle)))


def _point_to_arc_angle(arc, pt: Point) -> float:
    cx, cy = arc.dxf.center.x, arc.dxf.center.y
    return math.degrees(math.atan2(pt[1] - cy, pt[0] - cx)) % 360


def _line_endpoints(line) -> Tuple[Point, Point]:
    return (
        (line.dxf.start.x, line.dxf.start.y),
        (line.dxf.end.x,   line.dxf.end.y),
    )


def _set_endpoint(entity, role: str, pt: Point):
    """Sposta l'endpoint dell'entità al punto pt — modifica entity.dxf in-place."""
    if entity.dxftype() == 'LINE':
        if role == 'start':
            entity.dxf.start = (pt[0], pt[1], entity.dxf.start.z)
        else:
            entity.dxf.end = (pt[0], pt[1], entity.dxf.end.z)
    elif entity.dxftype() == 'ARC':
        angle = _point_to_arc_angle(entity, pt)
        if role == 'start':
            entity.dxf.start_angle = angle
        else:
            entity.dxf.end_angle = angle


def _fix_pair(msp, entity_a, role_a, pt_a, entity_b, role_b, pt_b) -> bool:
    type_a = entity_a.dxftype()
    type_b = entity_b.dxftype()

    if type_a == 'LINE' and type_b == 'LINE':
        s_a, e_a = _line_endpoints(entity_a)
        s_b, e_b = _line_endpoints(entity_b)
        ix = _line_intersection(s_a, e_a, s_b, e_b)
        if ix is None:
            msp.add_line((pt_a[0], pt_a[1], 0.0), (pt_b[0], pt_b[1], 0.0))
            return True
        _set_endpoint(entity_a, role_a, ix)
        _set_endpoint(entity_b, role_b, ix)
        return True

    if (type_a == 'ARC' and type_b == 'LINE') or \
       (type_a == 'LINE' and type_b == 'ARC'):
        arc      = entity_a if type_a == 'ARC'  else entity_b
        line     = entity_a if type_a == 'LINE' else entity_b
        arc_role  = role_a  if type_a == 'ARC'  else role_b
        line_role = role_a  if type_a == 'LINE' else role_b
        pt_arc    = pt_a    if type_a == 'ARC'  else pt_b
        s_l, e_l = _line_endpoints(line)
        candidates = _circle_line_intersections(
            arc.dxf.center.x, arc.dxf.center.y, arc.dxf.radius,
            s_l, e_l,
        )
        ix = _closest_to(candidates, pt_arc)
        if ix is None:
            msp.add_line((pt_a[0], pt_a[1], 0.0), (pt_b[0], pt_b[1], 0.0))
            return True
        _set_endpoint(arc,  arc_role,  ix)
        _set_endpoint(line, line_role, ix)
        return True

    if type_a == 'ARC' and type_b == 'ARC':
        candidates = _circle_circle_intersections(
            entity_a.dxf.center.x, entity_a.dxf.center.y, entity_a.dxf.radius,
            entity_b.dxf.center.x, entity_b.dxf.center.y, entity_b.dxf.radius,
        )
        ix = _closest_to(candidates, pt_a)
        if ix is None:
            msp.add_line((pt_a[0], pt_a[1], 0.0), (pt_b[0], pt_b[1], 0.0))
            return True
        _set_endpoint(entity_a, role_a, ix)
        _set_endpoint(entity_b, role_b, ix)
        return True

    if type_a == 'SPLINE' or type_b == 'SPLINE':
        msp.add_line((pt_a[0], pt_a[1], 0.0), (pt_b[0], pt_b[1], 0.0))
        return True

    return False


# ---------------------------------------------------------------------------
# Funzioni pubbliche
# ---------------------------------------------------------------------------

def free_endpoints_from_msp(graph, msp, node_decimals: int = 1) -> list:
    """
    Restituisce gli endpoint di LINE, ARC e SPLINE con grado < 2 nel grafo.

    Parametri:
        graph         : grafo topologico — dict prodotto da build_node_graph
        msp           : modelspace ezdxf
        node_decimals : cifre decimali per l'arrotondamento dei nodi

    Restituisce:
        list di (point, entity, role) — endpoint liberi
    """
    free = []

    for line in msp.query("LINE"):
        s = round_point((line.dxf.start.x, line.dxf.start.y), node_decimals)
        e = round_point((line.dxf.end.x,   line.dxf.end.y),   node_decimals)
        if len(graph.get(s, [])) < 2:
            free.append(((line.dxf.start.x, line.dxf.start.y), line, "start"))
        if len(graph.get(e, [])) < 2:
            free.append(((line.dxf.end.x, line.dxf.end.y), line, "end"))

    for arc in msp.query("ARC"):
        s, e = arc_endpoints(arc)
        s_r  = round_point(s, node_decimals)
        e_r  = round_point(e, node_decimals)
        if len(graph.get(s_r, [])) < 2:
            free.append((s, arc, "start"))
        if len(graph.get(e_r, [])) < 2:
            free.append((e, arc, "end"))

    for spline in msp.query("SPLINE"):
        s, e = spline_endpoints(spline)
        if s is None or e is None:
            continue
        s_r = round_point(s, node_decimals)
        e_r = round_point(e, node_decimals)
        if len(graph.get(s_r, [])) < 2:
            free.append((s, spline, "start"))
        if len(graph.get(e_r, [])) < 2:
            free.append((e, spline, "end"))

    return free


def close_gaps(msp, free_endpoints: list, tolerance: float) -> int:
    """
    Corregge gap e overlap tra LINE e ARC modificando le entità in-place.

    Parametri:
        msp            : modelspace ezdxf
        free_endpoints : lista di (point, entity, role) — da free_endpoints_from_msp
        tolerance      : distanza massima per considerare una coppia correggibile

    Restituisce:
        Numero di coppie corrette.
    """
    if len(free_endpoints) < 2:
        return 0

    fixed   = 0
    checked = set()

    for i, (pt_a, entity_a, role_a) in enumerate(free_endpoints):
        for j, (pt_b, entity_b, role_b) in enumerate(free_endpoints):
            if i >= j:
                continue
            if entity_a is entity_b:
                continue
            pair_key = (id(entity_a), id(entity_b), role_a, role_b)
            if pair_key in checked:
                continue
            checked.add(pair_key)
            if _distance(pt_a, pt_b) > tolerance:
                continue
            if _fix_pair(msp, entity_a, role_a, pt_a, entity_b, role_b, pt_b):
                fixed += 1

    return fixed