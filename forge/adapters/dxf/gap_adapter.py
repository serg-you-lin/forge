"""
adapters/dxf/gap_adapter.py
----------------------------
Traduzione DXF ↔ gap_solver.

Questo modulo è l'unico punto che conosce sia ezdxf che GapEndpoint/GapFix.
Il core (gap_solver) non importa mai ezdxf.

Funzioni pubbliche:
    extract_free_endpoints — msp + grafo → List[GapEndpoint]
    apply_gap_fixes        — List[GapFix] + msp → int (fix applicati)
"""

from __future__ import annotations
import math
from typing import List

from ...core.geometry import round_point
from ...core.healing.gap_solver import (
    GapEndpoint,
    GapFix,
    MoveEndpoint,
    AddSegment,
)
from .graph_adapter import entity_endpoints

# ---------------------------------------------------------------------------
# Costruzione meta per kind
# ---------------------------------------------------------------------------

def _meta_for(entity) -> dict:
    t = entity.dxftype()
    if t == 'LINE':
        return {
            'start': (entity.dxf.start.x, entity.dxf.start.y),
            'end':   (entity.dxf.end.x,   entity.dxf.end.y),
        }
    if t == 'ARC':
        return {
            'cx':     entity.dxf.center.x,
            'cy':     entity.dxf.center.y,
            'radius': entity.dxf.radius,
        }
    return {}


_KIND_MAP = {
    'LINE':   'line',
    'ARC':    'arc',
    'SPLINE': 'spline',
}


# ---------------------------------------------------------------------------
# extract_free_endpoints
# ---------------------------------------------------------------------------

def extract_free_endpoints(
    graph,
    msp,
    node_decimals: int = 1,
) -> List[GapEndpoint]:
    """
    Restituisce i GapEndpoint liberi (grado < 2 nel grafo) per LINE, ARC, SPLINE.

    Parametri:
        graph         : dict prodotto da build_node_graph
        msp           : modelspace ezdxf
        node_decimals : cifre decimali per l'arrotondamento dei nodi
    """
    free: List[GapEndpoint] = []

    for entity in msp.query('LINE ARC SPLINE'):
        kind = _KIND_MAP.get(entity.dxftype())
        if kind is None:
            continue

        s, e = entity_endpoints(entity)
        if s is None or e is None:
            continue

        s_r = round_point(s, node_decimals)
        e_r = round_point(e, node_decimals)
        meta = _meta_for(entity)

        if len(graph.get(s_r, [])) < 2:
            free.append(GapEndpoint(pt=s, ref=entity, role='start', kind=kind, meta=meta))
        if len(graph.get(e_r, [])) < 2:
            free.append(GapEndpoint(pt=e, ref=entity, role='end',   kind=kind, meta=meta))

    return free


# ---------------------------------------------------------------------------
# apply_gap_fixes — registry per tipo di fix
# ---------------------------------------------------------------------------

def _apply_move(fix: MoveEndpoint, msp) -> bool:
    entity = fix.ref
    t      = entity.dxftype()
    pt     = fix.new_pt

    if t == 'LINE':
        if fix.role == 'start':
            entity.dxf.start = (pt[0], pt[1], entity.dxf.start.z)
        else:
            entity.dxf.end   = (pt[0], pt[1], entity.dxf.end.z)
        return True

    if t == 'ARC':
        cx = entity.dxf.center.x
        cy = entity.dxf.center.y
        angle = math.degrees(math.atan2(pt[1] - cy, pt[0] - cx)) % 360
        if fix.role == 'start':
            entity.dxf.start_angle = angle
        else:
            entity.dxf.end_angle   = angle
        return True

    return False   # SPLINE o tipo non gestito — non modifichiamo


def _apply_add_segment(fix: AddSegment, msp) -> bool:
    msp.add_line(
        (fix.pt_a[0], fix.pt_a[1], 0.0),
        (fix.pt_b[0], fix.pt_b[1], 0.0),
    )
    return True


_APPLY_HANDLERS = {
    MoveEndpoint: _apply_move,
    AddSegment:   _apply_add_segment,
}


def apply_gap_fixes(fixes: List[GapFix], msp) -> int:
    """
    Applica i GapFix al modelspace ezdxf in-place.

    Restituisce il numero di fix applicati con successo.
    """
    applied = 0
    for fix in fixes:
        handler = _APPLY_HANDLERS.get(type(fix))
        if handler and handler(fix, msp):
            applied += 1
    return applied
