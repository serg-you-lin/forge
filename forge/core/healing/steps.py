"""
core/healing/steps.py
---------------------
I passi di heal(), uno per funzione: edge in, edge o risultato parziale out,
nessuno stato condiviso. heal() li compone nell'ordine di sempre; un
chiamante con un altro disegno in mano (snapdraw) li compone come gli serve.

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, FrozenSet, List, Optional, Set, Tuple

from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, snap, unary_union

from ..geometry.measure import node_decimals_for, track_points
from ..primitives import LineSeg
from ..primitives.polygon_builder import build_polygon
from ..primitives.segments import DEFAULT_TOLERANCE, SplineSeg
from ..topology.edge import Edge
from ..topology.graph import build_node_graph
from ..topology.loop_finder import LoopFinder, loop_geometry
from ..topology.non_contour_edges import NonContourEdgeDetector
from ...model.cluster import ForgeCluster
from ...model.feature import ClosedFeature, OpenFeature
from ...model.role import ContourRole, is_structural_role
from .gap_solver import (
    free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes, gap_endpoints_at_nodes,
)
from .hierarchy import HierarchyBuilder, loop_to_closed_feature


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
    return apply_gap_fixes(edges, fixes, node_decimals_for(tolerance))


def dangling_splines(edges: List[Edge]) -> List[Edge]:
    """SplineSeg aperte con almeno un estremo non collegato a nient'altro."""
    open_splines = [e for e in edges if isinstance(e.segment, SplineSeg) and e.start != e.end]
    if not open_splines:
        return []
    graph = build_node_graph(edges)
    return [e for e in open_splines if graph.degree(e.start) < 2 or graph.degree(e.end) < 2]


def find_non_contour_edges(edges: List[Edge], tolerance: float) -> Set[int]:
    """
    id(edge) degli Edge che non chiudono un contorno (branching + centroide
    fuori dal convex hull della componente, D49). heal() li tiene fuori dal
    grafo della ricerca loop.
    """
    return NonContourEdgeDetector(tolerance).detect(build_node_graph(edges), edges)


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
    return apply_gap_fixes(edges, fixes, node_decimals_for(tolerance)), repaired, skipped


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


def loops_to_features(loops: List[list]) -> List[ClosedFeature]:
    """Un ClosedFeature per loop, col ruolo del primo edge; senza poligono valido, niente."""
    features = []
    for loop in loops:
        role = loop[0][0].role if loop else ContourRole.UNKNOWN
        geometry = loop_geometry(loop)
        if geometry is None:
            continue
        segments, styles, polygon = geometry
        feature = loop_to_closed_feature(loop, role=role, polygon=polygon, segments=segments,
                                         styles=styles)
        if feature is not None:
            features.append(feature)
    return features


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


def polygons_to_features(polygons: List[Polygon]) -> List[ClosedFeature]:
    """
    Per poligono un ClosedFeature OUTER dal bordo esterno e uno INNER per
    buco, a LineSeg: la geometria nativa è persa.
    """
    features = []
    for poly in polygons:
        if not poly.is_valid:
            poly = poly.buffer(0)
        outer = loop_to_closed_feature([], role=ContourRole.OUTER, polygon=poly,
                                       segments=_ring_segments(poly.exterior.coords))
        if outer is not None:
            features.append(outer)
        for interior in poly.interiors:
            inner = loop_to_closed_feature([], role=ContourRole.INNER, polygon=Polygon(interior),
                                           segments=_ring_segments(interior.coords))
            if inner is not None:
                features.append(inner)
    return features


def labeled_features(edges: List[Edge]) -> list:
    """
    Gli Edge messi da parte da split_labeled() come feature col loro ruolo
    intatto: ClosedFeature se l'edge è già chiuso da solo (cerchio, spline
    chiusa), OpenFeature altrimenti. Tracce degeneri escluse.
    """
    features = []
    for edge in edges:
        seg = edge.segment
        if seg is None:
            continue
        if edge.start == edge.end:
            polygon = build_polygon([seg], DEFAULT_TOLERANCE)
            if polygon is not None:
                features.append(ClosedFeature(role=edge.role, polygon=polygon,
                                              segments=[seg], styles=[edge.style]))
            continue
        if len(track_points([seg])) >= 2:
            features.append(OpenFeature(role=edge.role, segments=[seg], styles=[edge.style]))
    return features


def build_hierarchy(features: list, label: str = "", source_file: str = "",
                    is_structural: Optional[Callable[[str], bool]] = None
                    ) -> Tuple[List[ForgeCluster], list]:
    """
    Albero di contenimento sui ClosedFeature: ogni radice è un ForgeCluster
    (outer), i discendenti i suoi inners con `depth`/`parent`. Ritorna
    (cluster, trash): trash è ciò che non è finito in un cluster e non è
    strutturale.
    """
    builder = HierarchyBuilder(label=label, source_file=source_file, is_structural=is_structural)
    return builder.build(features)


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
