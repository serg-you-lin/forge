"""
core/island.py
--------------
Secondo modo di leggere un ForgeDocument, accanto a heal(): per isole.

heal() ricostruisce la topologia dall'interno (chi tocca chi, quali giri si
chiudono, come stanno uno dentro l'altro) e trova il pezzo per contenimento.
island() legge il disegno dall'esterno: separa le isole per vicinanza, trova
il contorno esterno di ognuna come faccia esterna della sua rete piana, poi
classifica l'interno. È la lettura giusta per un disegno di viste (3D
proiettato, più viste su un foglio), dove il grafo di heal è ambiguo.

Stesso contratto in uscita: un ForgeResult con un ForgeCluster per isola.
Cosa sia un'isola — vista, pezzo, cornice — lo decide il chiamante (D21).

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from shapely.geometry import LineString, Point

from ..model.cluster import ForgeCluster
from ..model.contour import ForgeContour
from ..model.document import ForgeDocument
from ..model.feature import OpenFeature
from ..model.result import ForgeResult
from ..model.role import ContourRole, is_structural_role
from .primitives.polygon_builder import build_polygon
from .primitives.segments import DEFAULT_TOLERANCE, segment_is_closed
from .topology.edge import Edge
from .topology.graph import build_node_graph
from .topology.loop_finder import LoopFinder, segments_from_loop, edge_styles_from_loop
from .topology.noding import NODE_DECIMALS, renode, split_at_crossings
from .topology.non_contour_edges import NonContourEdgeDetector
from .topology.outer_face import OuterFace, outer_face
from .healing.islands import spatial_islands
from .healing.gap_solver import (
    free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes, local_gap_fixes,
)
from .healing.normalizer import (
    merge_collinear_overlaps, merge_cocircular_overlaps, weld_degenerate_linesegs,
    refit_tessellations,
)

GRAPH_EPSILON = 0.01   # mm — due tagli dello stesso incrocio, calcolati da due edge, sono un nodo solo


@dataclass
class IslandReading:
    """Cosa island() ha deciso su un'isola, pezzo per pezzo."""
    edges:          List[Edge]                               # dell'isola, come arrivano
    outer:          Optional[OuterFace]    = None            # None: nessun giro chiuso
    inner_loops:    List[list]             = field(default_factory=list)   # loop [(Edge, reversed)]
    spurs:          List[Edge]             = field(default_factory=list)   # percorsi andata e ritorno
    outside:        List[Edge]             = field(default_factory=list)   # fuori dal contorno
    non_contour:    List[Edge]             = field(default_factory=list)   # criterio D49
    unclassified:   List[Edge]             = field(default_factory=list)
    nested_in:      Optional[int]          = None            # indice dell'isola che la contiene


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def island(doc: ForgeDocument, tolerance: Optional[float] = None,
           island_gap: float = 10.0, max_gap: float = 0.5,
           is_structural: Optional[Callable[[str], bool]] = None) -> ForgeResult:
    """
    Legge `doc` per isole. Un ForgeCluster per isola: `outer` il contorno
    esterno, `inners` i giri chiusi dentro. Un'isola il cui contorno sta
    dentro quello di un'altra non è un cluster: diventa interno dell'isola
    più esterna che la contiene (con la cornice nel disegno, l'unico
    contorno esterno è la cornice — toglierla è del chiamante).

    tolerance:  come heal() — se None, doc.source_meta['tolerance'].
    island_gap: distanza massima fra due edge della stessa isola (mm).
    max_gap:    gap chiusi fra estremi liberi, mai spostando un estremo più
                di così (mm).
    is_structural: come heal() (D30): un Edge con un ruolo già deciso e non
                strutturale (cornice, cartiglio, ...) resta fuori dalla
                lettura e va in trash col suo ruolo. Senza, solo outer/inner
                sono strutturali.
    """
    if not isinstance(doc, ForgeDocument):
        raise TypeError(
            "forge.island() richiede un ForgeDocument da forge.load_dxf(); "
            f"ricevuto {type(doc).__name__}"
        )
    tol = tolerance if tolerance is not None else doc.source_meta.get("tolerance", 0.05)
    structural = is_structural or is_structural_role
    labeled = [e for e in doc.edges if e.role != ContourRole.UNKNOWN and not structural(e.role)]
    labeled_ids = {id(e) for e in labeled}
    edges = [e for e in doc.edges if id(e) not in labeled_ids]
    readings = read_islands(edges, tol, island_gap=island_gap, max_gap=max_gap)

    result = ForgeResult(source_file=doc.source_path, annotations=list(doc.annotations))
    result.trash_entities += _open(labeled)
    label_map = doc.source_meta.get("label_map") or {}
    if label_map:
        result.label_map = label_map
    clusters = {}
    for i, r in enumerate(readings):
        if r.outer is not None and r.nested_in is None:
            clusters[i] = _cluster(r, doc.source_path)
    for i, r in enumerate(readings):
        host = clusters.get(r.nested_in) if r.nested_in is not None else clusters.get(i)
        if host is None:
            result.trash_entities += _open(r.edges)
            continue
        if r.nested_in is not None:
            host.inners.append(_contour(r.outer.segments, r.outer.styles, r.outer.polygon,
                                        ContourRole.INNER, host.outer))
            host.inners += _inners(r.inner_loops, host.outer)
        result.trash_entities += _open(r.spurs + r.outside + r.non_contour + r.unclassified)
    result.clusters = sorted(clusters.values(), key=lambda c: c.outer.polygon.area, reverse=True)
    if not result.clusters:
        result.is_valid = False
        result.errors.append("Nessuna isola con un contorno esterno chiuso.")
    return result


def read_islands(edges: List[Edge], tolerance: float, island_gap: float = 10.0,
                 max_gap: float = 0.5) -> List[IslandReading]:
    """
    `spatial_islands` + `read_island` per ognuna, e l'annidamento: un'isola
    il cui contorno sta dentro quello di un'altra porta in `nested_in`
    l'indice della più esterna che la contiene.
    """
    readings = [read_island(isl.edges, tolerance, max_gap=max_gap)
                for isl in spatial_islands(edges, island_gap)]
    for i, r in enumerate(readings):
        if r.outer is None:
            continue
        small = r.outer.polygon
        hosts = [j for j, big in enumerate(readings)
                 if j != i and big.outer is not None
                 and big.outer.polygon.area > small.area
                 and big.outer.polygon.buffer(tolerance).contains(small)]
        if hosts:
            r.nested_in = max(hosts, key=lambda j: readings[j].outer.polygon.area)
    return readings


def read_island(edges: List[Edge], tolerance: float, max_gap: float = 0.5) -> IslandReading:
    """
    Un'isola: normalizza (nodi dagli estremi reali, tassellature rifittate,
    merge/weld di heal, gap fino a `max_gap`), rende la rete piana, ne
    percorre la faccia esterna, poi classifica il resto: giri chiusi
    interni, non-contorno (D49), fuori dal contorno, non classificati.
    """
    normalized = _normalize(edges, tolerance, max_gap)
    noded = split_at_crossings(normalized, tolerance)
    pieces = noded.pieces
    face = outer_face(pieces, epsilon=GRAPH_EPSILON)

    reading = IslandReading(edges=list(edges), outer=face)
    taken = set()
    if face is not None:
        taken = {id(e) for e in face.edges} | {id(e) for e in face.spurs}
        reading.spurs = list(face.spurs)
    rest = [e for e in pieces if id(e) not in taken]
    if face is not None:
        probe = face.polygon.buffer(tolerance)
        reading.outside = [e for e in rest if not probe.contains(_geometry(e))]
        outside_ids = {id(e) for e in reading.outside}
        rest = [e for e in rest if id(e) not in outside_ids]

    rest_graph = build_node_graph(rest, epsilon=GRAPH_EPSILON)
    loops = LoopFinder().find(rest_graph)
    reading.inner_loops = loops
    in_loops = {id(e) for loop in loops for e, _ in loop}
    full_graph = build_node_graph(pieces, epsilon=GRAPH_EPSILON)
    non_contour_ids = NonContourEdgeDetector(tolerance).detect(full_graph, pieces)
    reading.non_contour = [e for e in rest if id(e) not in in_loops and id(e) in non_contour_ids]
    reading.unclassified = [e for e in rest if id(e) not in in_loops and id(e) not in non_contour_ids]
    return reading


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _normalize(edges: List[Edge], tolerance: float, max_gap: float) -> List[Edge]:
    """Stessi passi di heal, ma sulla griglia fine della rete piana: prima i
    nodi dagli estremi reali (renode), poi tassellature, merge, weld e gap —
    così la saldatura resta valida anche dopo lo spezzamento."""
    edges = refit_tessellations(renode(edges), node_decimals=NODE_DECIMALS)
    edges = weld_degenerate_linesegs(merge_cocircular_overlaps(merge_collinear_overlaps(edges)))
    gap = max(tolerance, max_gap)
    graph = build_node_graph(edges)
    fixes = local_gap_fixes(compute_gap_fixes(free_endpoints_from_edges(edges, graph), gap), gap)
    if fixes:
        edges = apply_gap_fixes(edges, fixes, NODE_DECIMALS)
    return [e for e in edges if e.start != e.end or segment_is_closed(e.segment)]


def _cluster(reading: IslandReading, source_file: str) -> ForgeCluster:
    face = reading.outer
    outer = _contour(face.segments, face.styles, face.polygon, ContourRole.OUTER, None)
    cluster = ForgeCluster(outer=outer, source_file=source_file)
    cluster.inners = _inners(reading.inner_loops, outer)
    return cluster


def _inners(loops, parent: ForgeContour) -> List[ForgeContour]:
    """Un ForgeContour inner per giro chiuso; un giro senza poligono valido no."""
    inners = []
    for loop in loops:
        segments = segments_from_loop(loop)
        polygon = build_polygon(segments, DEFAULT_TOLERANCE)
        if polygon is not None:
            inners.append(_contour(segments, edge_styles_from_loop(loop), polygon,
                                   ContourRole.INNER, parent))
    return inners


def _contour(segments, styles, polygon, role, parent) -> ForgeContour:
    return ForgeContour(polygon=polygon, role=role, segments=list(segments),
                        styles=list(styles), depth=0 if parent is None else 1, parent=parent)


def _open(edges: List[Edge]) -> list:
    return [OpenFeature(role=e.role, segments=[e.segment], styles=[e.style]) for e in edges]


def _geometry(edge: Edge):
    pts = edge.segment.discretize(DEFAULT_TOLERANCE)
    if len(pts) < 2 or all(p == pts[0] for p in pts):
        return Point(pts[0])
    return LineString(pts)
