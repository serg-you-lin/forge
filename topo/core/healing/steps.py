"""
core/healing/steps.py
---------------------
I passi di heal(), uno per funzione: edge in, edge o risultato parziale out,
nessuno stato condiviso. heal() li compone nell'ordine di sempre; un
chiamante con un altro disegno in mano (snapdraw) li compone come gli serve.

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Callable, FrozenSet, List, Optional, Set, Tuple

from shapely import STRtree
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, snap, unary_union

from ..geometry.measure import round_point, track_points
from ..primitives import LineSeg
from ..primitives.polygon_builder import build_polygon
from ..primitives.segments import (
    DEFAULT_TOLERANCE, ArcSeg, CircleSeg, SplineSeg, segment_endpoints,
)
from ..topology.edge import Edge
from ..topology.graph import build_node_graph
from ..topology.loop_finder import LoopFinder, loop_geometry
from ..topology.non_contour_edges import NonContourEdgeDetector
from ...model.cluster import Cluster
from ...model.curve import ClosedCurve, OpenCurve
from ...model.role import ContourRole, is_structural_role
from .gap_solver import (
    free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes, gap_endpoints_at_nodes,
)
from .hierarchy import HierarchyBuilder, loop_to_closed_curve


@dataclass
class LoopSearch:
    """Come find_loops() ha chiuso (o non chiuso) i giri, gradino per gradino."""
    edges:              List[Edge]                                  # dopo l'eventuale riparazione angoli
    loops:              List[list]  = field(default_factory=list)   # loop [(Edge, reversed)]
    method:             str         = "none"                        # exact | corner_repair | tolerant | none
    repaired:           int         = 0                             # angoli chiusi all'intersezione reale
    skipped_corners:    list        = field(default_factory=list)   # cluster con 3+ estremi, non riparati
    unrepaired_corners: list        = field(default_factory=list)   # fusi solo nel grafo tollerante
    open_nodes:         list        = field(default_factory=list)   # estremi liberi, se nessun loop


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def split_non_finite(edges: List[Edge]) -> Tuple[List[Edge], List[Edge]]:
    """
    Separa gli Edge con una coordinata non finita (NaN, inf): ritorna
    (finiti, non finiti). Un punto senza posizione non sta in nessun grafo
    né in nessuna uscita; heal() li conta in `errors` e il risultato non è
    valido.
    """
    def finite(edge: Edge) -> bool:
        try:
            points = [edge.start, edge.end] + list(edge.segment.discretize())
        except (ValueError, ArithmeticError):
            return False
        return all(math.isfinite(v) for p in points for v in p[:2])

    bad = [e for e in edges if not finite(e)]
    if not bad:
        return list(edges), []
    bad_ids = {id(e) for e in bad}
    return [e for e in edges if id(e) not in bad_ids], bad


def split_labeled(edges: List[Edge],
                  is_structural: Optional[Callable[[str], bool]] = None
                  ) -> Tuple[List[Edge], List[Edge]]:
    """
    Separa gli Edge con un ruolo già deciso e non strutturale (cornice,
    marcatura, un manifatturiero non riconosciuto senza predicato — D30):
    ritorna (restano nel grafo, etichettati). Senza `is_structural`, solo
    outer/inner sono strutturali.
    """
    structural = is_structural or is_structural_role
    labeled = [e for e in edges if e.role != ContourRole.UNKNOWN and not structural(e.role)]
    if not labeled:
        return list(edges), []
    labeled_ids = {id(e) for e in labeled}
    return [e for e in edges if id(e) not in labeled_ids], labeled


NEAR_FULL_ARC_MISSING = math.radians(2.0)   # angolo mancante oltre il quale un arco non è un cerchio (D112)


def close_near_full_arcs(edges: List[Edge], tolerance: float,
                         max_missing_angle: float = NEAR_FULL_ARC_MISSING) -> Tuple[List[Edge], int]:
    """
    Un ArcSeg coi due capi liberi diventa CircleSeg (stesso centro e raggio)
    solo se il gap fra i capi è entro `tolerance` E l'angolo mancante è entro
    `max_missing_angle` (MAP.md D112): la tolleranza dice se il buco è un gap,
    l'angolo se l'arco è un cerchio. `tolerance=math.inf` lascia solo l'angolo.
    Ritorna (edge, n_archi_chiusi).
    """
    graph = build_node_graph(edges)
    closed, out = 0, []
    for edge in edges:
        seg = edge.segment
        if isinstance(seg, ArcSeg) and _is_near_full_arc(edge, graph, tolerance, max_missing_angle):
            node = round_point(segment_endpoints(CircleSeg(center=seg.center, radius=seg.radius))[0])
            edge = replace(edge, start=node, end=node,
                           segment=CircleSeg(center=seg.center, radius=seg.radius))
            closed += 1
        out.append(edge)
    return out, closed


def _is_near_full_arc(edge: Edge, graph, tolerance: float, max_missing_angle: float) -> bool:
    seg = edge.segment
    if 2 * math.pi - seg._sweep() > max_missing_angle:
        return False
    start, end = segment_endpoints(seg)
    if math.dist(start, end) > tolerance:
        return False
    # un capo che tocca altra geometria non è libero: l'arco fa parte di un giro.
    # Capi fusi nello stesso nodo: il self-loop sta fra i degeneri, quindi il
    # nodo deve restare senza altri edge (la punta di uno spigolo non è un cerchio)
    if edge.start == edge.end:
        return graph.degree(edge.start) == 0
    return graph.degree(edge.start) == 1 and graph.degree(edge.end) == 1


def close_free_gaps(edges: List[Edge], tolerance: float) -> List[Edge]:
    """
    Chiude i gap fra estremi liberi entro `tolerance` col gap solver
    (estensione all'intersezione reale o linea di congiunzione).
    """
    graph = build_node_graph(edges)
    endpoints = free_endpoints_from_edges(edges, graph)
    if not endpoints:
        return list(edges)
    fixes = compute_gap_fixes(endpoints, tolerance)
    if not fixes:
        return list(edges)
    return apply_gap_fixes(edges, fixes)


def dangling_splines(edges: List[Edge]) -> List[Edge]:
    """SplineSeg aperte con almeno un estremo non collegato a nient'altro."""
    open_splines = [e for e in edges if isinstance(e.segment, SplineSeg) and e.start != e.end]
    if not open_splines:
        return []
    graph = build_node_graph(edges)
    return [e for e in open_splines if graph.degree(e.start) < 2 or graph.degree(e.end) < 2]


def find_non_contour_edges(edges: List[Edge], tolerance: float) -> Set[int]:
    """
    id(edge) degli Edge che non chiudono un contorno (branching, e non sul
    bordo della faccia esterna della componente, D111). heal() li tiene fuori
    dal grafo della ricerca loop. `tolerance`: due tagli più vicini sono un
    contatto solo, nella rete piana su cui si percorre la faccia esterna.
    """
    return NonContourEdgeDetector(tolerance).detect(build_node_graph(edges), edges)


def find_joining_edges(edges: List[Edge], candidate_ids: Set[int]) -> List[Edge]:
    """
    Gli Edge fra `candidate_ids` (di solito i non-contorno) che uniscono due
    forme altrimenti staccate: tolti, i loro due estremi non sono più
    collegati. Fra due forme chiuse è il nodo ambiguo per eccellenza — un
    pezzo con una linea attaccata, o due pezzi? heal() li legge come due e
    lo dice in un warning (D111).
    """
    graph = build_node_graph(edges)
    joining = []
    for edge in edges:
        if id(edge) not in candidate_ids:
            continue
        start, goal = graph.canonical(edge.start), graph.canonical(edge.end)
        if start == goal:
            continue
        seen, todo = {start}, [start]
        while todo and goal not in seen:
            node = todo.pop()
            for other_edge, other in graph[node]:
                if other_edge is not edge and other not in seen:
                    seen.add(other)
                    todo.append(other)
        if goal not in seen:
            joining.append(edge)
    return joining


def free_ends(edges: List[Edge], epsilon: float = 0.0) -> List[Tuple[Tuple, float]]:
    """
    (estremo, distanza dal nodo più vicino) per ogni estremo che nessun altro
    edge tocca, dal più vicino a un nodo: un estremo a pochi mm da un vertice
    è un gap che la tolleranza non ha chiuso. `epsilon`: quello del grafo su
    cui i loop sono stati chiusi, perché un estremo fuso lì non è libero.
    """
    graph = build_node_graph(edges, epsilon=epsilon)
    open_nodes = graph.open_nodes()
    if not open_nodes:
        return []
    nodes = list(graph.nodes)
    tree = STRtree([Point(q) for q in nodes])
    ends = []
    for node in open_nodes:
        hit = tree.query_nearest(Point(node), exclusive=True, return_distance=True)
        ends.append((node, float(hit[1][0]) if len(hit[1]) else math.inf))
    return sorted(ends, key=lambda item: item[1])


def repair_merged_corners(edges: List[Edge], tolerance: float,
                          exclude_ids: FrozenSet[int] = frozenset()
                          ) -> Tuple[List[Edge], int, list]:
    """
    Chiude gli angoli che il grafo esatto vede aperti e il clustering degli
    estremi (epsilon = `tolerance`) fonde: i due estremi vanno alla loro
    intersezione reale. Solo i cluster di esattamente due estremi; con tre o
    più (diramazioni) l'intersezione a due non è definita e il cluster resta.

    Ritorna (edge, n_angoli_riparati, [coordinate_cluster_saltati]).
    """
    graph = _graph(edges, exclude_ids, epsilon=tolerance)
    fixes, repaired, skipped = [], 0, []
    for canon, members in graph.merged_clusters():
        endpoints = gap_endpoints_at_nodes(edges, set(members))
        found = compute_gap_fixes(endpoints, tolerance=float("inf")) if len(endpoints) == 2 else []
        if found:
            fixes.extend(found)
            repaired += 1
        else:
            skipped.append(canon)
    if not fixes:
        return list(edges), 0, skipped
    return apply_gap_fixes(edges, fixes), repaired, skipped


def find_loops(edges: List[Edge], non_contour_ids: Set[int], tolerance: float) -> LoopSearch:
    """
    La scala di heal() per chiudere i giri, esclusi `non_contour_ids`:
    grafo esatto → riparazione angoli se restano estremi liberi (D57) →
    grafo tollerante (epsilon = `tolerance`). Se nessun gradino chiude,
    `loops` è vuota e `open_nodes` dice dove.
    """
    search = LoopSearch(edges=list(edges))
    if not edges:
        return search
    exclude = frozenset(non_contour_ids)
    graph = _graph(edges, exclude)
    search.loops = LoopFinder().find(graph, exclude_ids=exclude)
    search.method = "exact"
    if search.loops and not graph.open_nodes():
        return search

    search.edges, search.repaired, search.skipped_corners = repair_merged_corners(
        edges, tolerance, exclude)
    if search.repaired:
        search.loops = LoopFinder().find(_graph(search.edges, exclude), exclude_ids=exclude)
        search.method = "corner_repair"
    if search.loops:
        return search

    graph_c = _graph(search.edges, exclude, epsilon=tolerance)
    # un edge i cui due capi il clustering fonde si chiuderebbe su se stesso
    # per sola tolleranza: resta fuori dal giro (D112)
    folded = {id(e) for e in search.edges
              if e.start != e.end and id(e) not in exclude
              and graph_c.canonical(e.start) == graph_c.canonical(e.end)}
    if folded:
        exclude = exclude | folded
        graph_c = _graph(search.edges, exclude, epsilon=tolerance)
    search.loops = LoopFinder().find(graph_c, exclude_ids=exclude)
    if search.loops:
        search.method = "tolerant"
        search.unrepaired_corners = [c for c, _ in graph_c.merged_clusters()]
    else:
        search.method = "none"
        search.open_nodes = graph_c.open_nodes()
    return search


def structural_loops(loops: List[list],
                     is_structural: Optional[Callable[[str], bool]] = None) -> List[list]:
    """
    I loop in cui ogni edge con ruolo deciso è strutturale: un solo edge non
    strutturale (engrave, frame, ...) declassa l'intero loop.
    """
    structural = is_structural or is_structural_role
    return [loop for loop in loops
            if all(e.role == ContourRole.UNKNOWN or structural(e.role) for e, _ in loop)]


def loops_to_curves(loops: List[list]) -> List[ClosedCurve]:
    """Un ClosedCurve per loop, col ruolo del primo edge; senza poligono valido, niente."""
    curves = []
    for loop in loops:
        role = loop[0][0].role if loop else ContourRole.UNKNOWN
        geometry = loop_geometry(loop)
        if geometry is None:
            continue
        segments, styles, polygon = geometry
        curve = loop_to_closed_curve(loop, role=role, polygon=polygon, segments=segments,
                                     styles=styles)
        if curve is not None:
            curves.append(curve)
    return curves


def polygonize_edges(edges: List[Edge], tolerance: float) -> List[Polygon]:
    """
    Ultima spiaggia quando nessun grafo chiude: le facce dell'intero disegno
    discretizzato, con snap a `tolerance`.
    """
    lines = []
    for edge in edges:
        if edge.segment is None:
            continue
        pts = edge.segment.discretize(DEFAULT_TOLERANCE)
        if len(pts) >= 2:
            lines.append(LineString(pts))
    merged = unary_union(lines)
    return list(polygonize(snap(merged, merged, tolerance)))


def polygons_to_curves(polygons: List[Polygon]) -> List[ClosedCurve]:
    """
    Per poligono un ClosedCurve OUTER dal bordo esterno e uno INNER per
    buco, a LineSeg: la geometria nativa è persa.
    """
    curves = []
    for poly in polygons:
        if not poly.is_valid:
            poly = poly.buffer(0)
        outer = loop_to_closed_curve([], role=ContourRole.OUTER, polygon=poly,
                                     segments=_ring_segments(poly.exterior.coords))
        if outer is not None:
            curves.append(outer)
        for interior in poly.interiors:
            inner = loop_to_closed_curve([], role=ContourRole.INNER, polygon=Polygon(interior),
                                         segments=_ring_segments(interior.coords))
            if inner is not None:
                curves.append(inner)
    return curves


def labeled_curves(edges: List[Edge]) -> list:
    """
    Gli Edge messi da parte da split_labeled() come curve col loro ruolo
    intatto: ClosedCurve se l'edge è già chiuso da solo (cerchio, spline
    chiusa), OpenCurve altrimenti. Tracce degeneri escluse.
    """
    curves = []
    for edge in edges:
        seg = edge.segment
        if seg is None:
            continue
        if edge.start == edge.end:
            polygon = build_polygon([seg], DEFAULT_TOLERANCE)
            if polygon is not None:
                curves.append(ClosedCurve(role=edge.role, polygon=polygon,
                                          segments=[seg], styles=[edge.style]))
            continue
        if len(track_points([seg])) >= 2:
            curves.append(OpenCurve(role=edge.role, segments=[seg], styles=[edge.style]))
    return curves


def build_hierarchy(curves: list, label: str = "", source_file: str = "",
                    is_structural: Optional[Callable[[str], bool]] = None
                    ) -> Tuple[List[Cluster], list]:
    """
    Albero di contenimento sui ClosedCurve: ogni radice è un Cluster
    (outer), i discendenti i suoi inners con `depth`/`parent`. Ritorna
    (cluster, trash): trash è ciò che non è finito in un cluster e non è
    strutturale.
    """
    builder = HierarchyBuilder(label=label, source_file=source_file, is_structural=is_structural)
    return builder.build(curves)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _graph(edges: List[Edge], exclude_ids: FrozenSet[int], epsilon: float = 0.0):
    if exclude_ids:
        edges = [e for e in edges if id(e) not in exclude_ids]
    return build_node_graph(edges, epsilon=epsilon)


def _ring_segments(coords) -> List[LineSeg]:
    pts = [(x, y) for x, y in coords]
    return [LineSeg(start=pts[i], end=pts[i + 1]) for i in range(len(pts) - 1)]
