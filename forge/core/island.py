"""
core/island.py
--------------
Secondo modo di leggere un ForgeDocument, accanto a heal(): per isole.

heal() ricostruisce la topologia dall'interno (chi tocca chi, quali giri si
chiudono, come stanno uno dentro l'altro) e trova il pezzo per contenimento.
island() legge il disegno dall'esterno: i pezzi sono gli edge che si
toccano, il contorno esterno di ognuno è la faccia esterna della sua rete
piana, e ogni contorno esterno che non sta dentro un altro è un'isola (D99).
Quello che sta dentro un'isola, chiuso o aperto, è suo per contenimento. È
la lettura giusta per un disegno di viste (3D proiettato, più viste su un
foglio), dove il grafo di heal è ambiguo.

Stesso contratto in uscita: un ForgeResult con un ForgeCluster per isola.
Cosa sia un'isola — vista, pezzo, cornice — lo decide il chiamante (D21).

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, List, Optional

from shapely import make_valid
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..model.cluster import ForgeCluster
from ..model.contour import ForgeContour
from ..model.document import ForgeDocument
from ..model.feature import OpenFeature
from ..model.result import ForgeResult
from ..model.role import ContourRole, is_structural_role
from .primitives.segments import DEFAULT_TOLERANCE, LineSeg, segment_endpoints, segment_is_closed
from .primitives.trim import sub_segment
from .topology.edge import Edge
from .topology.graph import build_node_graph
from .geometry.shape import merge_runs
from .topology.loop_finder import LoopFinder, loop_geometry
from .topology.noding import GRAPH_EPSILON, NODE_DECIMALS, edge_geometry, renode, split_at_crossings
from .topology.non_contour_edges import NonContourEdgeDetector
from .topology.outer_face import OuterFace, outer_face
from .topology.rim import face_segments
from .healing.islands import spatial_islands
from .healing.gap_solver import (
    free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes, local_gap_fixes, MoveEndpoint,
)
from .healing.normalizer import (
    merge_collinear_overlaps, merge_cocircular_overlaps, weld_degenerate_linesegs,
    refit_tessellations,
)


@dataclass
class IslandReading:
    """Cosa island() ha deciso su un'isola, pezzo per pezzo."""
    edges:          List[Edge]                               # dell'isola, come arrivano
    outer:          Optional[OuterFace]    = None            # None: nessun giro chiuso
    inner_loops:    List[list]             = field(default_factory=list)   # loop [(Edge, reversed)]
    spurs:          List[Edge]             = field(default_factory=list)   # percorsi andata e ritorno
    outside:        List[Edge]             = field(default_factory=list)   # fuori dal contorno
    outside_loops:  List[list]             = field(default_factory=list)   # giri chiusi fra gli `outside` (D71)
    non_contour:    List[Edge]             = field(default_factory=list)   # criterio D49
    unclassified:   List[Edge]             = field(default_factory=list)
    off_faces:      List[Edge]             = field(default_factory=list)   # pezzi di un giro fuori da ogni sua faccia (D106)
    nested_in:     Optional[int]          = None            # indice dell'isola che la contiene (anche senza outer)


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def island(doc: ForgeDocument, *, max_gap: float,
           tolerance: Optional[float] = None,
           is_structural: Optional[Callable[[str], bool]] = None) -> ForgeResult:
    """
    Legge `doc` per isole. Un ForgeCluster per ogni contorno esterno che non
    sta dentro un altro: `outer` il contorno, `inners` i giri chiusi dentro.
    Un pezzo il cui contorno sta dentro quello di un'isola diventa suo
    interno, con tutti i suoi giri chiusi (con la cornice nel disegno,
    l'unico contorno esterno è la cornice — toglierla è del chiamante). Gli
    edge aperti vanno in `trash_entities` con `cluster_ref` = l'isola che li
    contiene o che toccano; `None` se stanno fuori da ogni isola (D99).

    max_gap:    due edge più vicini di così si toccano; gap chiusi fra
                estremi liberi, mai spostando un estremo più di così (mm).
                Obbligatorio (D98).
    tolerance:  come heal() — se None, doc.source_meta['tolerance'].
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
    tol = doc.node_tolerance(tolerance)
    structural = is_structural or is_structural_role
    labeled = [e for e in doc.edges if e.role != ContourRole.UNKNOWN and not structural(e.role)]
    labeled_ids = {id(e) for e in labeled}
    edges = [e for e in doc.edges if id(e) not in labeled_ids]
    readings = read_islands(edges, tol, max_gap=max_gap)

    result = ForgeResult(source_file=doc.source_path, annotations=list(doc.annotations))
    result.trash_entities += _open(labeled)
    clusters = {}
    for i, r in enumerate(readings):
        if r.outer is not None and r.nested_in is None:
            clusters[i] = _cluster(r, doc.source_path, tol)
    owned = []   # (OpenFeature, cluster che la contiene)
    for i, r in enumerate(readings):
        host = clusters.get(r.nested_in) if r.nested_in is not None else clusters.get(i)
        if host is None or r.outer is None:
            owned += [(f, host) for f in _open(r.edges)]
            continue
        outside = r.outside
        if r.nested_in is not None:
            host.inners.append(_contour(r.outer.segments, r.outer.styles, r.outer.polygon,
                                        ContourRole.INNER, host.outer))
            host.inners += _inners(r.inner_loops, host.outer, tol)
            # D71: dentro l'ospite, anche i giri fuori dal contorno scelto sono interni
            host.inners += _inners(r.outside_loops, host.outer, tol)
            in_loops = {id(e) for loop in r.outside_loops for e, _ in loop}
            outside = [e for e in r.outside if id(e) not in in_loops]
        owned += [(f, host) for f in _open(r.spurs + outside + r.non_contour + r.unclassified + r.off_faces)]
    result.clusters = sorted(clusters.values(), key=lambda c: c.outer.polygon.area, reverse=True)
    index = {id(c): k for k, c in enumerate(result.clusters)}
    for feature, host in owned:
        feature.cluster_ref = None if host is None else index[id(host)]
    result.trash_entities += [f for f, _ in owned]
    if not result.clusters:
        result.is_valid = False
        result.errors.append("Nessuna isola con un contorno esterno chiuso.")
    return result


def read_islands(edges: List[Edge], tolerance: float, max_gap: float) -> List[IslandReading]:
    """
    I pezzi a contatto (`spatial_islands` a `max_gap`) + `read_island` per
    ognuno, e l'annidamento: un pezzo che sta dentro il contorno di un altro
    — col suo contorno, o senza contorno con tutti i suoi edge — porta in
    `nested_in` l'indice del più esterno che lo contiene.
    """
    readings = [read_island(isl.edges, tolerance, max_gap=max_gap)
                for isl in spatial_islands(edges, max(tolerance, max_gap))]
    outers = [(j, r.outer.polygon.buffer(tolerance), r.outer.polygon.area)
              for j, r in enumerate(readings) if r.outer is not None]
    for i, r in enumerate(readings):
        if r.outer is not None:
            small, area = r.outer.polygon, r.outer.polygon.area
        else:
            small, area = unary_union([edge_geometry(e) for e in r.edges]), 0.0
        hosts = [(j, big_area) for j, probe, big_area in outers
                 if j != i and big_area > area and probe.contains(small)]
        if hosts:
            r.nested_in = max(hosts, key=lambda h: h[1])[0]
    return readings


def read_island(edges: List[Edge], tolerance: float, max_gap: float) -> IslandReading:
    """
    Un'isola: normalizza (nodi dagli estremi reali, tassellature rifittate,
    merge/weld di heal, gap fino a `max_gap`), rende la rete piana, ne
    percorre la faccia esterna, poi classifica il resto: giri chiusi
    interni, non-contorno (D49), fuori dal contorno (e i giri chiusi fra
    questi, `outside_loops`, D71), non classificati.
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
        reading.outside = [e for e in rest if not probe.contains(edge_geometry(e))]
        outside_ids = {id(e) for e in reading.outside}
        rest = [e for e in rest if id(e) not in outside_ids]
        if reading.outside:
            reading.outside_loops, off = _faced(
                LoopFinder().find(build_node_graph(reading.outside, epsilon=GRAPH_EPSILON)), tolerance)
            reading.off_faces += off

    rest_graph = build_node_graph(rest, epsilon=GRAPH_EPSILON)
    loops = LoopFinder().find(rest_graph)
    band = tolerance + max_gap
    reference = face.polygon if face is not None else None
    loops = _drop_boundary_duplicates(loops, reference, band)
    loops, off = _faced(loops, tolerance)
    reading.off_faces += off
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

def _drop_boundary_duplicates(loops: list, reference: Optional[Polygon], band: float) -> list:
    """Scarta un giro chiuso il cui intero bordo sta entro `band` dal bordo di
    un giro più grande già accettato (il contorno esterno `reference`, o un
    altro giro già tenuto, in ordine di area): non è una feature annidata,
    è la stessa curva ritracciata un po' spostata (entro tolleranza+gap) —
    tipicamente la parete visibile di un foro in una vista isometrica,
    quasi sovrapposta alla sua stessa apertura. Raffina D71 ("ogni giro
    chiuso è un inner"), che resta corretto per isole scollegate ma non per
    un giro che segue quasi lo stesso bordo di un altro già tenuto."""
    accepted: List[Polygon] = [reference] if reference is not None else []
    scored = []
    for loop in loops:
        geometry = loop_geometry(loop)
        area = geometry[2].area if geometry is not None else -1.0
        scored.append((area, loop, geometry))
    kept = []
    for _, loop, geometry in sorted(scored, key=lambda t: -t[0]):
        if geometry is None:
            kept.append(loop)
            continue
        polygon = geometry[2]
        if any(g.exterior.buffer(band).contains(polygon.exterior) for g in accepted):
            continue
        accepted.append(polygon)
        kept.append(loop)
    return kept


def _normalize(edges: List[Edge], tolerance: float, max_gap: float) -> List[Edge]:
    """Stessi passi di heal, ma sulla griglia fine della rete piana: prima i
    nodi dagli estremi reali (renode), poi tassellature, merge, weld e gap —
    così la saldatura resta valida anche dopo lo spezzamento."""
    edges = refit_tessellations(renode(edges), node_decimals=NODE_DECIMALS)
    edges = weld_degenerate_linesegs(merge_cocircular_overlaps(merge_collinear_overlaps(edges)))
    gap = max(tolerance, max_gap)
    graph = build_node_graph(edges)
    fixes = compute_gap_fixes(free_endpoints_from_edges(edges, graph), gap, pairwise=False)
    fixes = _drop_redundant_meets(fixes, graph)
    fixes = local_gap_fixes(fixes, gap)
    if fixes:
        edges = apply_gap_fixes(edges, fixes, NODE_DECIMALS)
    return [e for e in edges if e.start != e.end or segment_is_closed(e.segment)]


def _drop_redundant_meets(fixes: list, graph) -> list:
    """Scarta un fix "incontro" (due `MoveEndpoint` sullo stesso punto, la
    retta/arco di ognuno prolungato fino all'intersezione con l'altro)
    quando i due estremi di partenza sono già nella stessa componente
    connessa del grafo: non è un gap da chiudere, un giro li collega già
    altrove senza bisogno di questi due — saldarli comunque apre un secondo
    percorso parallelo spurio (sliver) accanto al contorno che si chiude già
    da solo (stessa famiglia di D100/D101, un passo prima: nel gap-fix,
    invece che nel noding). Un fix fra componenti diverse resta: lì è un
    gap vero, l'unico modo di collegarli."""
    by_point: dict = {}
    for fix in fixes:
        if isinstance(fix, MoveEndpoint):
            by_point.setdefault(fix.new_pt, []).append(fix)
    component_of: dict = {}
    for i, component in enumerate(graph.connected_components()):
        for node in component:
            component_of[node] = i
    drop_ids = set()
    for pair in by_point.values():
        if len(pair) != 2:
            continue
        fa, fb = pair
        node_a = graph.canonical(fa.ref.start if fa.role == "start" else fa.ref.end)
        node_b = graph.canonical(fb.ref.start if fb.role == "start" else fb.ref.end)
        if component_of.get(node_a) == component_of.get(node_b):
            drop_ids.update(id(f) for f in pair)
    return [f for f in fixes if id(f) not in drop_ids]


def _cluster(reading: IslandReading, source_file: str, tolerance: float) -> ForgeCluster:
    face = reading.outer
    outer = _contour(face.segments, face.styles, face.polygon, ContourRole.OUTER, None)
    cluster = ForgeCluster(outer=outer, source_file=source_file)
    cluster.inners = _inners(reading.inner_loops, outer, tolerance)
    return cluster


def _inners(loops, parent: ForgeContour, tolerance: float) -> List[ForgeContour]:
    """Un ForgeContour inner per faccia di ogni giro chiuso; un giro senza
    poligono valido no."""
    return [_contour(*face, ContourRole.INNER, parent)
            for loop in loops for face in _loop_faces(loop, tolerance)]


def _loop_faces(loop, tolerance: float) -> list:
    """(segmenti, stili, poligono) per ogni faccia di un giro chiuso: una se
    il suo anello è semplice; se tocca se stesso (due archi tangenti, due
    bordi entro tolleranza) una per lobo, coi segmenti letti dal bordo del
    lobo (`face_segments`) — non il solo lobo più grande (D106). Una faccia
    più stretta di `tolerance` non è una faccia: è il contatto fra due
    curve che si toccano (D106)."""
    geometry = loop_geometry(loop)
    if geometry is None:
        return []
    ring = []
    for i, seg in enumerate(geometry[0]):
        pts = seg.discretize(DEFAULT_TOLERANCE)
        ring += pts if i == 0 else pts[1:]
    raw = Polygon(ring)
    if raw.is_valid:
        return [] if _thinner_than(raw, tolerance) else [geometry]
    lobes = [Polygon(g.exterior) for g in _polygons(make_valid(raw))
             if not _thinner_than(g, tolerance)]
    if len(lobes) < 2:
        return [geometry] if lobes else []
    edges = [e for e, _ in loop]
    return [(*face_segments(edges, lobe, 2 * GRAPH_EPSILON), lobe) for lobe in lobes]


def _faced(loops: list, tolerance: float):
    """(giri con almeno una faccia, pezzi dei loro edge fuori da ogni faccia):
    un giro senza facce resta fuori e i suoi edge vanno con il resto; i
    pezzi di un giro che nessuna faccia usa (la zona di contatto fra due
    lobi) vanno nel trash, non spariscono (D106)."""
    kept, off = [], []
    for loop in loops:
        faces = _loop_faces(loop, tolerance)
        if faces:
            kept.append(loop)
            off += _off_faces(loop, faces)
    return kept, off


def _off_faces(loop, faces) -> List[Edge]:
    """I tratti degli edge di `loop` lontani più di `band` dal bordo di ogni
    faccia, ognuno tagliato esatto dal suo edge."""
    band = 2 * GRAPH_EPSILON
    rims = unary_union([face[2].exterior for face in faces]).buffer(band)
    pieces = []
    for edge, _ in loop:
        for part in _lines(edge_geometry(edge).difference(rims)):
            if part.length <= band:
                continue
            a, b = part.coords[0], part.coords[-1]
            middle = part.interpolate(0.5, normalized=True)
            piece = sub_segment(edge.segment, a, b, (middle.x, middle.y))
            chain = [piece] if piece is not None else [
                LineSeg(start=p, end=q) for p, q in zip(part.coords, part.coords[1:])]
            for seg in chain:
                start, end = segment_endpoints(seg)
                pieces.append(replace(edge, segment=seg,
                                      start=(round(start[0], NODE_DECIMALS), round(start[1], NODE_DECIMALS)),
                                      end=(round(end[0], NODE_DECIMALS), round(end[1], NODE_DECIMALS))))
    return pieces


def _lines(geometry) -> list:
    if geometry.geom_type == "LineString":
        return [geometry]
    return [p for g in getattr(geometry, "geoms", []) for p in _lines(g)]


def _thinner_than(polygon: Polygon, width: float) -> bool:
    """Larghezza media (2·area/perimetro: per una striscia, la sua
    larghezza) sotto `width`."""
    return 2 * polygon.area < width * polygon.length


def _polygons(geometry) -> List[Polygon]:
    if geometry.geom_type == "Polygon":
        return [geometry]
    return [p for g in getattr(geometry, "geoms", []) for p in _polygons(g)]


def _contour(segments, styles, polygon, role, parent) -> ForgeContour:
    """Il poligono resta quello dei pezzi della rete piana; i segmenti sono
    ricomposti dove il taglio li aveva spezzati (`geometry.shape.merge_runs`)."""
    segments, styles = merge_runs(list(segments), list(styles))
    return ForgeContour(polygon=polygon, role=role, segments=segments,
                        styles=styles, depth=0 if parent is None else 1, parent=parent)


def _open(edges: List[Edge]) -> list:
    return [OpenFeature(role=e.role, segments=[e.segment], styles=[e.style]) for e in edges]

