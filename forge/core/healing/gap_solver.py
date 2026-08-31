"""
core/healing/gap_solver.py
---------------------------
Calcolo geometrico puro della chiusura dei gap tra segmenti.

Zero dipendenze da ezdxf, PDF, SVG o qualsiasi formato.
Lavora su coordinate Python e restituisce istruzioni di correzione (GapFix).

Il chiamante (adapter) è responsabile di:
    - estrarre GapEndpoint dal formato sorgente
    - applicare GapFix al documento nativo

Tipi pubblici:
    GapEndpoint   — endpoint libero con ref opaco al formato sorgente
    MoveEndpoint  — istruzione: sposta endpoint di ref a new_pt
    AddSegment    — istruzione: aggiungi segmento tra pt_a e pt_b
    GapFix        — Union[MoveEndpoint, AddSegment]

Funzioni pubbliche:
    compute_gap_fixes — dato un insieme di endpoint liberi, calcola i fix
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple, Union

from ..geometry import (
    round_point,
    _distance,
    _line_intersection,
    _circle_line_intersections,
    _circle_circle_intersections,
    _closest_to,
)
from ..primitives.segments import LineSeg, ArcSeg, SplineSeg, segment_endpoints
from ..topology.edge import Edge
from ...model.role import ContourRole

Point2D = Tuple[float, float]


# ---------------------------------------------------------------------------
# Tipi di input
# ---------------------------------------------------------------------------

@dataclass
class GapEndpoint:
    """
    Endpoint libero nel grafo topologico.

    Attributi:
        pt   : coordinate (x, y) dell'endpoint
        ref  : riferimento opaco all'entità sorgente — l'adapter sa cos'è
        role : 'start' | 'end'
        kind : tipo geometrico — 'line' | 'arc' | 'spline' | altro
               usato dal solver per scegliere la strategia di fix
        meta : dati aggiuntivi che il solver può usare per il calcolo
               per LINE: {'start': pt, 'end': pt}
               per ARC:  {'cx': float, 'cy': float, 'radius': float}
               per SPLINE: {} (nessun dato utile al solver)
    """
    pt:   Point2D
    ref:  Any
    role: str
    kind: str
    meta: dict


# ---------------------------------------------------------------------------
# Tipi di output (GapFix)
# ---------------------------------------------------------------------------

@dataclass
class MoveEndpoint:
    """
    Istruzione: sposta l'endpoint role di ref al punto new_pt.
    L'adapter traduce ref → entità nativa e applica lo spostamento.
    """
    ref:    Any
    role:   str
    new_pt: Point2D


@dataclass
class AddSegment:
    """
    Istruzione: aggiungi un segmento retto tra pt_a e pt_b.
    Usato come fallback quando non si trova un'intersezione geometrica.
    """
    pt_a: Point2D
    pt_b: Point2D


GapFix = Union[MoveEndpoint, AddSegment]


# ---------------------------------------------------------------------------
# Solver geometrico — logica per coppia di kind
# ---------------------------------------------------------------------------

def _solve_line_line(
    ep_a: GapEndpoint,
    ep_b: GapEndpoint,
) -> List[GapFix]:
    s_a = ep_a.meta['start']
    e_a = ep_a.meta['end']
    s_b = ep_b.meta['start']
    e_b = ep_b.meta['end']
    ix = _line_intersection(s_a, e_a, s_b, e_b)
    if ix is None:
        return [AddSegment(pt_a=ep_a.pt, pt_b=ep_b.pt)]
    return [
        MoveEndpoint(ref=ep_a.ref, role=ep_a.role, new_pt=ix),
        MoveEndpoint(ref=ep_b.ref, role=ep_b.role, new_pt=ix),
    ]


def _solve_arc_line(
    ep_arc:  GapEndpoint,
    ep_line: GapEndpoint,
) -> List[GapFix]:
    cx     = ep_arc.meta['cx']
    cy     = ep_arc.meta['cy']
    radius = ep_arc.meta['radius']
    s_l    = ep_line.meta['start']
    e_l    = ep_line.meta['end']
    candidates = _circle_line_intersections(cx, cy, radius, s_l, e_l)
    ix = _closest_to(candidates, ep_arc.pt)
    if ix is None:
        return [AddSegment(pt_a=ep_arc.pt, pt_b=ep_line.pt)]
    return [
        MoveEndpoint(ref=ep_arc.ref,  role=ep_arc.role,  new_pt=ix),
        MoveEndpoint(ref=ep_line.ref, role=ep_line.role, new_pt=ix),
    ]


def _solve_arc_arc(
    ep_a: GapEndpoint,
    ep_b: GapEndpoint,
) -> List[GapFix]:
    candidates = _circle_circle_intersections(
        ep_a.meta['cx'], ep_a.meta['cy'], ep_a.meta['radius'],
        ep_b.meta['cx'], ep_b.meta['cy'], ep_b.meta['radius'],
    )
    ix = _closest_to(candidates, ep_a.pt)
    if ix is None:
        return [AddSegment(pt_a=ep_a.pt, pt_b=ep_b.pt)]
    return [
        MoveEndpoint(ref=ep_a.ref, role=ep_a.role, new_pt=ix),
        MoveEndpoint(ref=ep_b.ref, role=ep_b.role, new_pt=ix),
    ]


def _solve_spline_any(
    ep_a: GapEndpoint,
    ep_b: GapEndpoint,
) -> List[GapFix]:
    # Le spline non hanno una geometria analitica semplice da intersecare —
    # fallback diretto al segmento di chiusura.
    return [AddSegment(pt_a=ep_a.pt, pt_b=ep_b.pt)]


# Registry: (kind_a, kind_b) → solver
# Le coppie sono normalizzate in ordine canonico in compute_gap_fixes.
_SOLVERS = {
    ('line',   'line'):   _solve_line_line,
    ('arc',    'line'):   lambda a, b: _solve_arc_line(a, b),
    ('line',   'arc'):    lambda a, b: _solve_arc_line(b, a),   # riordina
    ('arc',    'arc'):    _solve_arc_arc,
    ('spline', 'line'):   lambda a, b: _solve_spline_any(a, b),
    ('line',   'spline'): lambda a, b: _solve_spline_any(a, b),
    ('spline', 'arc'):    lambda a, b: _solve_spline_any(a, b),
    ('arc',    'spline'): lambda a, b: _solve_spline_any(a, b),
    ('spline', 'spline'): lambda a, b: _solve_spline_any(a, b),
}


def _get_solver(kind_a: str, kind_b: str):
    solver = _SOLVERS.get((kind_a, kind_b))
    if solver is None:
        # kind sconosciuto → fallback AddSegment
        return lambda a, b: [AddSegment(pt_a=a.pt, pt_b=b.pt)]
    return solver


# ---------------------------------------------------------------------------
# Funzione pubblica
# ---------------------------------------------------------------------------

def compute_gap_fixes(
    endpoints: List[GapEndpoint],
    tolerance: float,
) -> List[GapFix]:
    """
    Calcola i GapFix per tutti gli endpoint liberi entro tolerance.

    Parametri:
        endpoints : lista di GapEndpoint prodotta dall'adapter
        tolerance : distanza massima tra due endpoint per considerarli un gap

    Restituisce:
        Lista di GapFix (MoveEndpoint o AddSegment) da applicare.
        L'ordine non è garantito — ogni fix è indipendente.
    """
    if len(endpoints) < 2:
        return []

    fixes:   List[GapFix] = []
    checked: set           = set()

    for i, ep_a in enumerate(endpoints):
        for j, ep_b in enumerate(endpoints):
            if i >= j:
                continue
            if ep_a.ref is ep_b.ref:
                continue
            pair_key = (id(ep_a.ref), id(ep_b.ref), ep_a.role, ep_b.role)
            if pair_key in checked:
                continue
            checked.add(pair_key)

            if _distance(ep_a.pt, ep_b.pt) > tolerance:
                continue

            solver = _get_solver(ep_a.kind, ep_b.kind)
            fixes.extend(solver(ep_a, ep_b))

    return fixes


# ---------------------------------------------------------------------------
# Ponte Edge <-> GapFix — geometria pura, zero formato sorgente
# ---------------------------------------------------------------------------

_KIND_BY_SEGMENT = {LineSeg: "line", ArcSeg: "arc", SplineSeg: "spline"}


def _endpoint_meta(segment) -> dict:
    """Dati che il solver usa per calcolare l'intersezione, per tipo di segmento."""
    if isinstance(segment, LineSeg):
        return {"start": segment.start, "end": segment.end}
    if isinstance(segment, ArcSeg):
        return {"cx": segment.center[0], "cy": segment.center[1], "radius": segment.radius}
    return {}


def free_endpoints_from_edges(edges: List[Edge], graph) -> List[GapEndpoint]:
    """
    Estrae gli endpoint liberi (grado < 2 nel grafo) dagli Edge.

    Sostituisce DxfAdapter.extract_free_endpoints: lavora su geometria pura,
    il `ref` di ogni GapEndpoint è l'Edge stesso.
    Considera solo LINE / ARC / SPLINE — i loop degeneri (CIRCLE, SPLINE chiusa)
    non hanno endpoint liberi per definizione.
    """
    free: List[GapEndpoint] = []

    for edge in edges:
        if edge.start == edge.end:
            continue
        kind = _KIND_BY_SEGMENT.get(type(edge.segment))
        if kind is None:
            continue

        meta = _endpoint_meta(edge.segment)
        # pt: coordinate reali non arrotondate (il solver ne ha bisogno per
        # calcolare l'intersezione); il grado si valuta sui nodi arrotondati.
        raw_start, raw_end = segment_endpoints(edge.segment)

        if graph.degree(edge.start) < 2:
            free.append(GapEndpoint(pt=raw_start, ref=edge, role="start", kind=kind, meta=meta))
        if graph.degree(edge.end) < 2:
            free.append(GapEndpoint(pt=raw_end, ref=edge, role="end", kind=kind, meta=meta))

    return free


def gap_endpoints_at_nodes(edges: List[Edge], nodes: set) -> List[GapEndpoint]:
    """
    GapEndpoint per gli endpoint che cadono su uno dei `nodes` — tuple di
    coordinate già arrotondate — **a prescindere dal grado nel grafo**.

    Complementare a free_endpoints_from_edges: quello prende solo gli endpoint
    liberi (grado < 2), questo prende un insieme di nodi deciso da un'altra
    logica. Serve a riparare gli angoli individuati dal clustering degli
    endpoint (build_node_graph con epsilon > 0): lì i due lati si toccano
    quasi — grado >= 2 — quindi il filtro sul grado non li vede, ma la
    geometria va comunque portata all'intersezione reale.

    Considera solo LINE / ARC / SPLINE.
    """
    out: List[GapEndpoint] = []
    for edge in edges:
        if edge.start == edge.end:
            continue
        kind = _KIND_BY_SEGMENT.get(type(edge.segment))
        if kind is None:
            continue
        meta = _endpoint_meta(edge.segment)
        raw_start, raw_end = segment_endpoints(edge.segment)
        if edge.start in nodes:
            out.append(GapEndpoint(pt=raw_start, ref=edge, role="start", kind=kind, meta=meta))
        if edge.end in nodes:
            out.append(GapEndpoint(pt=raw_end, ref=edge, role="end", kind=kind, meta=meta))
    return out


def _moved_segment(segment, role: str, new_pt: Point2D):
    """Nuovo segmento con l'endpoint `role` spostato su `new_pt`. None se non gestito."""
    if isinstance(segment, LineSeg):
        if role == "start":
            return LineSeg(start=(new_pt[0], new_pt[1]), end=segment.end)
        return LineSeg(start=segment.start, end=(new_pt[0], new_pt[1]))

    if isinstance(segment, ArcSeg):
        angle = math.atan2(new_pt[1] - segment.center[1], new_pt[0] - segment.center[0])
        if role == "start":
            return ArcSeg(center=segment.center, radius=segment.radius,
                          start_angle=angle, end_angle=segment.end_angle, ccw=segment.ccw)
        return ArcSeg(center=segment.center, radius=segment.radius,
                      start_angle=segment.start_angle, end_angle=angle, ccw=segment.ccw)

    return None


def apply_gap_fixes(edges: List[Edge], fixes: List[GapFix], node_decimals: int = 1) -> List[Edge]:
    """
    Applica i GapFix restituendo una NUOVA lista di Edge — `edges` non viene mutata.

    Sostituisce DxfAdapter.apply_gap_fixes: invece di mutare entità ezdxf,
    ricostruisce gli Edge coinvolti (MoveEndpoint) e ne aggiunge di nuovi
    (AddSegment, sempre una LINE di congiunzione).
    """
    replacements: dict = {}   # id(edge_originale) -> Edge aggiornato
    added: List[Edge] = []

    for fix in fixes:
        if isinstance(fix, MoveEndpoint):
            base = replacements.get(id(fix.ref), fix.ref)
            if not isinstance(base, Edge):
                continue
            # Il segmento conserva il punto reale (il poligono si costruisce da
            # qui); solo il nodo topologico dell'Edge viene arrotondato.
            new_seg = _moved_segment(base.segment, fix.role, fix.new_pt)
            if new_seg is None:
                continue
            node = round_point(fix.new_pt, node_decimals)
            replacements[id(fix.ref)] = Edge(
                role=base.role,
                start=node if fix.role == "start" else base.start,
                end=node if fix.role == "end" else base.end,
                segment=new_seg,
                closed_path=getattr(base, "closed_path", False),
            )
        elif isinstance(fix, AddSegment):
            a = (float(fix.pt_a[0]), float(fix.pt_a[1]))
            b = (float(fix.pt_b[0]), float(fix.pt_b[1]))
            if round_point(a, node_decimals) == round_point(b, node_decimals):
                continue
            added.append(Edge(
                role=ContourRole.UNKNOWN,
                start=round_point(a, node_decimals),
                end=round_point(b, node_decimals),
                segment=LineSeg(start=a, end=b),
            ))

    if not replacements and not added:
        return list(edges)

    out = [replacements.get(id(e), e) for e in edges]
    out.extend(added)
    return out
