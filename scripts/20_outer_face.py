"""
20_outer_face.py — contorno esterno come faccia esterna della rete piana
=======================================================================

Prototipo, senza scan. Per ogni file:

  1. isole per vicinanza vera fra segmenti (spatial_islands, ISLAND_GAP);
  2. per isola: nodi dagli estremi reali, tassellature rifittate come
     primitive (fit_primitives), merge/weld/gap di heal;
  3. spezza ogni LineSeg/ArcSeg/CircleSeg dove incrocia o tocca a T un altro
     edge: la rete diventa piana (SplineSeg/EllipseSeg restano interi);
  4. contorno esterno = bordo della faccia esterna: si parte dal nodo più a
     sinistra e a ogni nodo si prende l'edge più in senso antiorario rispetto
     a quello da cui si arriva. Un edge percorso andata e ritorno è una
     sporgenza (asse, segno) e non è contorno;
  5. il resto dell'isola: giri chiusi, non-contorno, non classificati, e
     fuori_contorno (pezzi di una parte della rete staccata e rimasta fuori).

Un'isola il cui contorno sta dentro quello di un'altra non è un cluster: fa
parte dell'interno dell'isola più esterna che la contiene (un foro, una
finestra, una vista dentro la cornice). Con la cornice nel disegno l'unico
contorno esterno è la cornice: toglierla prima è compito del chiamante.

Output: pipeline_output/outer_face/<file>.dxf
    OuterContour     il contorno esterno trovato, uno per isola
    sporgenza        edge percorsi andata e ritorno (assi, segni, quote attaccate)
    giro_interno     giri chiusi dentro
    non_contorno     candidati non-contorno (criterio di heal, D49)
    fuori_contorno   pezzi dell'isola rimasti fuori dal contorno (rete staccata)
    Trash            il resto, non classificato

    python scripts/20_outer_face.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import glob
import math
import os
import time
import traceback
from dataclasses import dataclass, field, replace
from typing import Optional

from shapely import STRtree
from shapely.geometry import LineString, Point

import forge
from forge.core.geometry import (
    _line_intersection, _circle_line_intersections,
    _circle_circle_intersections,
)
from forge.core.primitives.segments import (
    LineSeg, ArcSeg, CircleSeg, DEFAULT_TOLERANCE, segment_endpoints, segment_is_closed,
)
from forge.core.primitives.polygon_builder import build_polygon
from forge.core.healing.normalizer import (
    merge_collinear_overlaps, merge_cocircular_overlaps, weld_degenerate_linesegs,
)
from forge.core.healing.gap_solver import (
    free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes, MoveEndpoint,
)
from forge.core.healing.islands import spatial_islands
from forge.tools.simplify_points import simplify_points
from forge.core.topology.graph import build_node_graph
from forge.core.topology.loop_finder import LoopFinder, segments_from_loop, edge_styles_from_loop
from forge.core.topology.non_contour_edges import NonContourEdgeDetector
from forge.model.cluster import ForgeCluster
from forge.model.contour import ForgeContour
from forge.model.feature import OpenFeature
from forge.model.result import ForgeResult
from forge.model.role import ContourRole

# --- CONFIG ----------------------------------------------------------------
INPUT_DIR = r"tests/examples/islands"          # tutti i .dxf/.dwg qui dentro
EXCLUDE = ["_healed"]                           # file il cui nome contiene questi pezzi
TOLERANCE = 0.05
TESSELLATION_SEGMENT = 0.1   # mm — un LineSeg più corto è un candidato punto di tassellatura
TESSELLATION_MIN_RUN = 10    # segmenti corti di fila perché una catena sia una tassellatura
ARC_FIT_TOLERANCE = 0.02     # mm — scostamento massimo per rifittare la catena come arco/cerchio
ISLAND_GAP = 10.0            # mm — distanza massima fra due edge della stessa isola
VIEW_GAP = 0.5              # mm — gap chiusi dal gap solver di heal fra estremi liberi (disegno di vista, non di taglio)
GRAPH_EPSILON = 0.01         # mm — due tagli dello stesso incrocio, calcolati da due edge, sono un nodo solo
OUTDIR = r"pipeline_output/outer_face"
# ---------------------------------------------------------------------------

_EPS = 1e-9
_NODE_DECIMALS = 3        # nodi ricalcolati dagli estremi reali, uguali per ogni pezzo (tagli compresi)
_MIN_PIECE = 1e-4         # mm — sotto, lo spezzone non viene creato
_DIRECTION_SAMPLE = 3.0   # mm — la direzione di un edge a un nodo si legge fin qui (al massimo a metà edge)


# ---------------------------------------------------------------------------
# 1. Normalizzazione + tassellature + gap piccoli
# ---------------------------------------------------------------------------

def _normalize(edges, tol):
    """Stessi passi di heal, ma sulla griglia fine dei tagli: prima i nodi
    dagli estremi reali, poi le tassellature rifittate, poi merge/weld/gap.
    Via gli Edge rimasti a lunghezza zero."""
    edges = _refit_tessellations(_renode(edges))
    edges = weld_degenerate_linesegs(merge_cocircular_overlaps(merge_collinear_overlaps(edges)))
    graph = build_node_graph(edges)
    gap = max(tol, VIEW_GAP)
    fixes = [f for f in compute_gap_fixes(free_endpoints_from_edges(edges, graph), gap)
             if _fix_is_local(f, gap)]
    if fixes:
        edges = apply_gap_fixes(edges, fixes, _NODE_DECIMALS)
    return [e for e in edges if e.start != e.end or segment_is_closed(e.segment)]


def _fix_is_local(fix, gap):
    """Un gap chiuso non sposta un estremo più in là del gap stesso: due rette
    quasi parallele con gli estremi vicini si incontrano lontanissimo, e
    prolungarle fin lì non è chiudere un gap."""
    if not isinstance(fix, MoveEndpoint):
        return True
    s, e = segment_endpoints(fix.ref.segment)
    old = s if fix.role == "start" else e
    return math.dist(old, fix.new_pt) <= gap


def _renode(edges):
    """Nodi di ogni Edge ricalcolati dal punto reale a _NODE_DECIMALS: la
    griglia di heal (1 decimale a tolleranza 0.05) e quella dei tagli devono
    essere la stessa, se no un contatto a T non si riconosce."""
    return [e if segment_is_closed(e.segment) else _make_edge(e, e.segment, _NODE_DECIMALS)
            for e in edges]


def _is_short(edge):
    seg = edge.segment
    return (isinstance(seg, LineSeg) and edge.role == ContourRole.UNKNOWN
            and math.dist(seg.start, seg.end) < TESSELLATION_SEGMENT)


def _short_runs(short_edges):
    """Catene massimali di segmenti corti: percorsi fra nodi di grado != 2,
    o anelli. Ritorna [(edge orientati [(edge, reversed)], chiusa)]."""
    graph = build_node_graph(short_edges)
    used, runs = set(), []

    def walk(start, first_edge, first_other):
        path, node, edge, other = [], start, first_edge, first_other
        while True:
            used.add(id(edge))
            path.append((edge, graph.canonical(edge.start) != node))
            node = other
            nxt = [(e, o) for e, o in graph[node] if id(e) not in used]
            if len(graph[node]) != 2 or not nxt:
                return path, node
            edge, other = nxt[0]

    for n in [n for n in graph if len(graph[n]) != 2]:
        for e, o in graph[n]:
            if id(e) not in used:
                path, _ = walk(n, e, o)
                runs.append((path, False))
    for n in graph:                      # anelli: tutti i nodi di grado 2
        for e, o in graph[n]:
            if id(e) not in used:
                path, last = walk(n, e, o)
                runs.append((path, last == n))
    return runs


def _refit_tessellations(edges):
    """Una catena di almeno TESSELLATION_MIN_RUN LineSeg corti è una curva
    scritta a punti: rifittata con fit_primitives (arco/cerchio se sta entro
    ARC_FIT_TOLERANCE, se no spline). Gli estremi della catena tengono i nodi
    originali, così resta attaccata ai vicini."""
    short = [e for e in edges if _is_short(e) and e.start != e.end]
    replaced, new_edges = set(), []
    for path, closed in _short_runs(short):
        if len(path) < TESSELLATION_MIN_RUN:
            continue
        pts = []
        for edge, rev in path:
            a, b = (edge.segment.end, edge.segment.start) if rev else (edge.segment.start, edge.segment.end)
            if not pts:
                pts.append(a)
            pts.append(b)
        if closed:
            pts = pts[:-1]
        prims = simplify_points(pts, closed=closed, arc_fit_tolerance=ARC_FIT_TOLERANCE)
        if not prims:
            continue
        first, last = path[0], path[-1]
        start_node = first[0].end if first[1] else first[0].start
        end_node = last[0].start if last[1] else last[0].end
        for k, prim in enumerate(prims):
            e = _make_edge(first[0], prim, _NODE_DECIMALS)
            if not closed:
                e = replace(e, start=start_node if k == 0 else e.start,
                            end=end_node if k == len(prims) - 1 else e.end)
            new_edges.append(e)
        replaced |= {id(edge) for edge, _ in path}
    if not replaced:
        return edges
    return [e for e in edges if id(e) not in replaced] + new_edges


# ---------------------------------------------------------------------------
# 2. Spezzamento: LineSeg in t ∈ [0, 1], ArcSeg in s ∈ [0, sweep]
# ---------------------------------------------------------------------------

def _arc_s(seg, pt):
    phi = math.atan2(pt[1] - seg.center[1], pt[0] - seg.center[0])
    delta = (phi - seg.start_angle) if seg.ccw else (seg.start_angle - phi)
    return delta % (2 * math.pi)


def _param(seg, pt):
    """(parametro, distanza del punto dal segmento)."""
    if isinstance(seg, LineSeg):
        dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
        l2 = dx * dx + dy * dy
        if l2 < _EPS:
            return None, float("inf")
        t = ((pt[0] - seg.start[0]) * dx + (pt[1] - seg.start[1]) * dy) / l2
        proj = (seg.start[0] + t * dx, seg.start[1] + t * dy)
        return t, math.dist(proj, pt)
    s = _arc_s(seg, pt)
    if s > seg._sweep() + _EPS:
        return None, float("inf")
    return s, abs(math.dist(pt, seg.center) - seg.radius)


def _param_range(seg):
    return 1.0 if isinstance(seg, LineSeg) else seg._sweep()


def _piece_length(seg, p0, p1):
    if isinstance(seg, LineSeg):
        return math.dist(seg.start, seg.end) * (p1 - p0)
    return seg.radius * (p1 - p0)


def _cutters(edge):
    seg = edge.segment
    if isinstance(seg, LineSeg):
        return [("line", seg.start, seg.end)]
    if isinstance(seg, ArcSeg):
        return [("arc", seg)]
    if isinstance(seg, CircleSeg):
        return [("arc", _circle_as_arc(seg))]
    pts = seg.discretize(DEFAULT_TOLERANCE)
    return [("line", pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


def _circle_as_arc(circle, start_angle=0.0):
    """Un cerchio come arco di 360° che parte da `start_angle`: stessa
    matematica di intersezione e spezzamento degli archi."""
    return ArcSeg(center=circle.center, radius=circle.radius,
                  start_angle=start_angle, end_angle=start_angle + 2 * math.pi, ccw=True)


def _crossings(seg, cutter):
    """Incroci reali (non sul prolungamento) fra `seg` e un cutter."""
    if cutter[0] == "line":
        p, q = cutter[1], cutter[2]
        if isinstance(seg, LineSeg):
            ix = _line_intersection(seg.start, seg.end, p, q)
            pts = [ix] if ix else []
        else:
            pts = _circle_line_intersections(seg.center[0], seg.center[1], seg.radius, p, q)
        out = []
        for pt in pts:
            t, _ = _param(LineSeg(p, q), pt)
            if t is not None and -_EPS <= t <= 1 + _EPS:
                out.append(pt)
        return out
    other = cutter[1]
    if isinstance(seg, LineSeg):
        pts = _circle_line_intersections(other.center[0], other.center[1], other.radius,
                                         seg.start, seg.end)
    else:
        pts = _circle_circle_intersections(seg.center[0], seg.center[1], seg.radius,
                                           other.center[0], other.center[1], other.radius)
    return [pt for pt in pts if _arc_s(other, pt) <= other._sweep() + _EPS]


def _split_params(edge, near, tol):
    seg = edge.segment
    rng = _param_range(seg)
    params = []
    for other in near:
        if other is edge:
            continue
        pts = [pt for cutter in _cutters(other) for pt in _crossings(seg, cutter)]
        pts.extend(segment_endpoints(other.segment))   # contatto a T entro tol
        for pt in pts:
            p, dist = _param(seg, pt)
            if p is None or dist > tol:
                continue
            if _piece_length(seg, 0, p) > _MIN_PIECE and _piece_length(seg, p, rng) > _MIN_PIECE:
                params.append(p)
    params.sort()
    dedup = []
    for p in params:
        if not dedup or _piece_length(seg, dedup[-1], p) > _MIN_PIECE:
            dedup.append(p)
    return dedup


def _make_edge(edge, seg, decimals):
    s, e = segment_endpoints(seg)
    r = lambda pt: (round(pt[0], decimals), round(pt[1], decimals))
    return replace(edge, start=r(s), end=r(e), segment=seg)


def _split(edge, params, decimals):
    seg = edge.segment
    bounds = [0.0] + params + [_param_range(seg)]
    out = []
    for p0, p1 in zip(bounds, bounds[1:]):
        if isinstance(seg, LineSeg):
            at = lambda t: (seg.start[0] + t * (seg.end[0] - seg.start[0]),
                            seg.start[1] + t * (seg.end[1] - seg.start[1]))
            a = seg.start if p0 == 0.0 else at(p0)
            b = seg.end if p1 == 1.0 else at(p1)
            piece = LineSeg(start=a, end=b)
        else:
            sign = 1.0 if seg.ccw else -1.0
            piece = ArcSeg(center=seg.center, radius=seg.radius,
                           start_angle=seg.start_angle + sign * p0,
                           end_angle=seg.start_angle + sign * p1, ccw=seg.ccw)
        cut = _make_edge(edge, piece, decimals)
        # primo e ultimo pezzo tengono i nodi dell'edge (saldati, gap chiusi):
        # solo i tagli interni hanno un nodo nuovo
        cut = replace(cut, start=edge.start if p0 == 0.0 else cut.start,
                      end=edge.end if p1 == bounds[-1] else cut.end)
        out.append(cut)
    return out


def _geometry(edge):
    pts = edge.segment.discretize(DEFAULT_TOLERANCE)
    if len(pts) < 2 or all(p == pts[0] for p in pts):
        return Point(pts[0])
    return LineString(pts)


def _node_all(edges, tol, decimals):
    """Spezza ogni LineSeg/ArcSeg dove incontra un altro edge. I vicini da
    controllare li dà l'STRtree (entro tol), non il confronto con tutti."""
    geoms = [_geometry(e) for e in edges]
    tree = STRtree(geoms)
    pieces = []
    for i, e in enumerate(edges):
        near = [edges[j] for j in tree.query(geoms[i], predicate="dwithin", distance=tol)]
        if isinstance(e.segment, (LineSeg, ArcSeg)) and e.start != e.end:
            pieces.extend(_split(e, _split_params(e, near, tol), decimals))
        elif isinstance(e.segment, CircleSeg):
            pieces.extend(_split_circle(e, near, tol, decimals))
        else:
            pieces.append(e)
    return pieces


def _split_circle(edge, near, tol, decimals):
    """Un cerchio incrociato da altri edge diventa archi fra un taglio e
    l'altro, come ogni altro pezzo della rete. Con meno di due tagli resta
    un cerchio intero."""
    circle = edge.segment
    params = _split_params(replace(edge, segment=_circle_as_arc(circle)), near, tol)
    if len(params) < 2:
        return [edge]
    arc = _circle_as_arc(circle, start_angle=params[0])
    start = _make_edge(edge, arc, decimals)
    start = replace(start, end=start.start)
    return _split(start, [p - params[0] for p in params[1:]], decimals)


# ---------------------------------------------------------------------------
# 3. Faccia esterna
# ---------------------------------------------------------------------------

def _leaving_angle(edge, node, graph):
    """Direzione con cui `edge` lascia `node`, letta a _DIRECTION_SAMPLE (o a
    metà edge, se più corto): un raccordo tangente a una retta si distingue
    da lei solo più avanti, non al primo micron."""
    pts = edge.segment.discretize(DEFAULT_TOLERANCE)
    if graph.canonical(edge.start) != node:
        pts = list(reversed(pts))
    total = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    reach = min(_DIRECTION_SAMPLE, total / 2)
    walked, target = 0.0, pts[-1]
    for i in range(len(pts) - 1):
        step = math.dist(pts[i], pts[i + 1])
        if step > 0 and walked + step >= reach:
            t = (reach - walked) / step
            target = (pts[i][0] + t * (pts[i + 1][0] - pts[i][0]),
                      pts[i][1] + t * (pts[i + 1][1] - pts[i][1]))
            break
        walked += step
    return math.atan2(target[1] - pts[0][1], target[0] - pts[0][0])


def _outer_face_walk(graph, component, n_edges):
    """Bordo della faccia esterna di un componente connesso: [(edge, dal
    nodo, al nodo)]. Si parte dal punto più a sinistra della geometria — sul
    bordo esterno per forza, anche quando cade a metà di un edge (un arco,
    un cerchio spezzato) — percorrendo quell'edge verso il basso, così
    l'esterno sta a destra. Poi a ogni nodo si prende l'edge che gira meno
    in senso antiorario rispetto alla direzione da cui si è arrivati;
    tornare indietro solo se non c'è altro."""
    angles = {}

    def angle(edge, node):
        key = (id(edge), node)
        if key not in angles:
            angles[key] = _leaving_angle(edge, node, graph)
        return angles[key]

    first = _first_step(graph, component)
    walk, node = [first], first[2]
    back_edge, back_angle = first[0], angle(first[0], node)
    for _ in range(4 * n_edges + 10):
        best, best_turn = None, None
        for edge, other in graph[node]:
            turn = (angle(edge, node) - back_angle) % (2 * math.pi)
            if edge is back_edge or turn < 1e-9:
                turn = 2 * math.pi
            if best_turn is None or turn < best_turn:
                best, best_turn = (edge, other), turn
        edge, other = best
        if node == first[1] and edge is first[0] and other == first[2]:
            break
        walk.append((edge, node, other))
        back_edge, back_angle = edge, angle(edge, other)
        node = other
    return walk


def _first_step(graph, component):
    """(edge, dal nodo, al nodo) che contiene il punto più a sinistra del
    componente, percorso verso il basso. Se quel punto è un nodo, si parte
    dal nodo come arrivando da ovest."""
    best = None   # (punto più a sinistra, edge, suoi punti, indice)
    for node in component:
        for edge, _ in graph[node]:
            pts = edge.segment.discretize(DEFAULT_TOLERANCE)
            i = min(range(len(pts)), key=lambda k: (pts[k][0], pts[k][1]))
            if best is None or (pts[i][0], pts[i][1]) < best[0]:
                best = ((pts[i][0], pts[i][1]), edge, pts, i)
    _, edge, pts, i = best
    a, b = graph.canonical(edge.start), graph.canonical(edge.end)
    if 0 < i < len(pts) - 1:
        going_down = pts[i + 1][1] - pts[i - 1][1] < 0
        return (edge, a, b) if going_down else (edge, b, a)
    # il punto più a sinistra è un nodo: fra i suoi edge, il primo in senso
    # antiorario a partire da ovest
    start = a if i == 0 else b
    choice = min(graph[start], key=lambda eo: (_leaving_angle(eo[0], start, graph) - math.pi) % (2 * math.pi))
    return (choice[0], start, choice[1])


def _outer_loop(edges):
    """Il giro di area massima fra quelli che il LoopFinder trova."""
    g = build_node_graph(edges, epsilon=GRAPH_EPSILON)
    best = None
    for loop in LoopFinder().find(g):
        segments = segments_from_loop(loop)
        poly = build_polygon(segments, DEFAULT_TOLERANCE)
        if poly is not None and (best is None or poly.area > best[2].area):
            best = (loop, segments, poly)
    return best


# ---------------------------------------------------------------------------
# Composizione per un'isola
# ---------------------------------------------------------------------------

def _open(role, edges):
    return [OpenFeature(role=role, segments=[e.segment], styles=[e.style]) for e in edges]


@dataclass
class IslandReading:
    """Cosa la composizione ha deciso su un'isola."""
    edges:    list
    cluster:  Optional[ForgeCluster] = None  # None: nessun contorno esterno chiuso
    trash:    list = field(default_factory=list)
    stats:    dict = field(default_factory=dict)


def analyze_island(island_edges, tol) -> IslandReading:
    edges = _normalize(island_edges, tol)
    pieces = _node_all(edges, tol, _NODE_DECIMALS)
    graph = build_node_graph(pieces, epsilon=GRAPH_EPSILON)

    # faccia esterna di ogni componente: il contorno dell'isola è quella di
    # area massima (un componente piccolo — una freccia di quota — può avere
    # il nodo più a sinistra di tutta l'isola)
    best, walk, spur_ids = None, [], set()
    for component in graph.connected_components():
        comp_walk = _outer_face_walk(graph, component, len(pieces))
        count = {}
        for edge, _, _ in comp_walk:
            count[id(edge)] = count.get(id(edge), 0) + 1
        spur_ids |= {i for i, c in count.items() if c >= 2}
        boundary = [e for e in pieces if count.get(id(e)) == 1]
        found = _outer_loop(boundary) if boundary else None
        if found is not None and (best is None or found[2].area > best[2].area):
            best, walk = found, comp_walk
    circles = _outer_loop(graph.degenerate_loops)
    if circles is not None and (best is None or circles[2].area > best[2].area):
        best = circles

    reading = IslandReading(edges=list(island_edges))
    reading.stats = {"edge": len(island_edges), "normalizzati": len(edges), "pezzi": len(pieces),
                     "passi": len(walk), "sporgenze": len(spur_ids),
                     "componenti": len(graph.connected_components())}
    outer_ids, poly = set(), None
    if best is not None:
        loop, segments, poly = best
        outer_ids = {id(e) for e, _ in loop}
        reading.cluster = ForgeCluster(outer=ForgeContour(
            polygon=poly, role=ContourRole.OUTER, segments=segments,
            styles=edge_styles_from_loop(loop)))
        reading.stats["area esterno"] = round(poly.area)

    trash = reading.trash
    trash += _open("sporgenza", [e for e in pieces if id(e) in spur_ids])

    rest = [e for e in pieces if id(e) not in outer_ids and id(e) not in spur_ids]
    outside = []
    if poly is not None:
        probe = poly.buffer(tol)
        outside = [e for e in rest if not probe.contains(_geometry(e))]
    outside_ids = {id(e) for e in outside}
    rest = [e for e in rest if id(e) not in outside_ids]

    rest_graph = build_node_graph(rest, epsilon=GRAPH_EPSILON)
    loop_ids = {id(e) for loop in LoopFinder().find(rest_graph) for e, _ in loop}
    loop_ids |= {id(e) for e in rest_graph.degenerate_loops}
    non_contour_ids = NonContourEdgeDetector(tol).detect(graph, pieces)

    inner = [e for e in rest if id(e) in loop_ids]
    non_contour = [e for e in rest if id(e) in non_contour_ids and id(e) not in loop_ids]
    unknown = [e for e in rest if id(e) not in loop_ids and id(e) not in non_contour_ids]
    trash += _open("fuori_contorno", outside)
    trash += _open("giro_interno", inner)
    trash += _open("non_contorno", non_contour)
    trash += _open(ContourRole.UNKNOWN, unknown)
    reading.stats.update({"fuori": len(outside), "giro_interno": len(inner),
                          "non_contorno": len(non_contour), "non classificati": len(unknown)})
    return reading


def analyze(doc, tol):
    """Isole → contorno esterno per isola. Un'isola il cui contorno sta dentro
    quello di un'altra non è un cluster: il suo contorno diventa un
    giro_interno dell'isola più esterna che la contiene, e tutto il resto
    della sua lettura la segue."""
    readings = [analyze_island(isl.edges, tol)
                for isl in spatial_islands(doc.edges, ISLAND_GAP)]

    def host_of(i):
        """L'isola più esterna il cui contorno contiene quello di i."""
        small = readings[i].cluster.outer.polygon
        hosts = [j for j, big in enumerate(readings)
                 if j != i and big.cluster is not None
                 and big.cluster.outer.polygon.area > small.area
                 and big.cluster.outer.polygon.buffer(tol).contains(small)]
        return max(hosts, key=lambda j: readings[j].cluster.outer.polygon.area) if hosts else None

    hosts = {i: host_of(i) for i, r in enumerate(readings) if r.cluster is not None}
    for i, j in hosts.items():
        if j is None:
            continue
        r = readings[i]
        readings[j].trash.append(OpenFeature(role="giro_interno", segments=r.cluster.outer.segments,
                                             styles=r.cluster.outer.styles))
        readings[j].trash += r.trash
        r.trash = []
        r.cluster = None
        r.stats["dentro isola"] = j + 1

    result = ForgeResult(source_file=doc.source_path, annotations=list(doc.annotations))
    for r in readings:
        if r.cluster is not None:
            result.clusters.append(r.cluster)
        result.trash_entities += r.trash
    if not result.clusters:
        result.is_valid = False
        result.errors.append("Nessuna isola con un contorno esterno chiuso.")
    return result, readings


def _inputs():
    paths = []
    for pattern in ("*.dxf", "*.DXF", "*.dwg", "*.DWG"):
        paths += glob.glob(os.path.join(INPUT_DIR, pattern))
    paths = sorted(dict.fromkeys(os.path.normcase(p) for p in paths))
    return [p for p in paths if not any(x.lower() in os.path.basename(p).lower() for x in EXCLUDE)]


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    for path in _inputs():
        stem = os.path.splitext(os.path.basename(path))[0]
        t0 = time.time()
        try:
            doc = forge.load_dxf(path, tolerance=TOLERANCE)
            result, readings = analyze(doc, TOLERANCE)
        except Exception as exc:
            print(f"{stem}: ERRORE {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=3)
            continue
        closed = len(result.clusters) if result.is_valid else 0
        print(f"{stem}: {len(doc.edges)} edge, {len(readings)} isole, {closed} contorni esterni, "
              f"{time.time() - t0:.1f}s")
        for n, r in enumerate(readings, 1):
            if r.stats["edge"] > 1:
                print(f"  isola {n}: " + ", ".join(f"{k} {v}" for k, v in r.stats.items()))
        suffix = ""
        if not result.is_valid:
            # to_dxf rifiuta un risultato invalido: qui lo si vuole vedere lo stesso
            result.is_valid, result.errors = True, []
            suffix = "_INVALIDO"
        out = os.path.abspath(os.path.join(OUTDIR, f"{stem}{suffix}.dxf"))
        try:
            forge.to_dxf(result, doc, include_trash=True).saveas(out)
            print(f"  -> {out}")
        except PermissionError:
            print(f"  !! {out} è aperto in un altro programma: non sovrascritto")


if __name__ == "__main__":
    main()
