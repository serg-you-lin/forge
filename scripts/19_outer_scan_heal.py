"""
19_outer_scan_heal.py — contorno esterno per scan + ponti, interno classificato
==============================================================================

Prototipo di composizione alternativa a heal() con i suoi stessi ingredienti
(il codice di spezzamento e dei ponti vive qui finché non si decide se e dove
promuoverlo in core). Per ogni file — per ora un file = un'isola:

  1. normalizza (collinear / cocircular / weld) e chiude i gap piccoli
     (gap_solver, stessa tolleranza di heal);
  2. spezza ogni LineSeg/ArcSeg nei punti dove incrocia o tocca a T un altro
     edge — SplineSeg/EllipseSeg restano interi;
  3. scan sui pezzi: un pezzo colpito da un raggio è contorno VISTO; i gap
     fino a SEEN_GAP attorno ai suoi estremi liberi si chiudono (gap solver);
     un visto con un estremo che non tocca niente (punta d'asse, sfioramento)
     esce; quelli che restano sono contorno CERTO;
  4. ponti: dove la catena dei certi si interrompe, il percorso più corto fra
     due estremi liberi usando solo pezzi NON certi (le tasche che i raggi non
     vedono); poi via i monconi, e il giro più grande è il contorno esterno;
  5. l'interno resta: giri chiusi (LoopFinder), non-contorno
     (NonContourEdgeDetector), il resto non classificato.

Output: pipeline_output/outer_scan_heal/<file>.dxf, un layer per decisione:
    OuterContour     il contorno esterno trovato
    contorno_certo   i pezzi visti dai raggi che ne fanno parte
    ponte            i pezzi aggiunti per chiudere le tasche
    certo_scartato   pezzi visti dai raggi ma rimasti monconi (assi, segni)
    giro_interno     giri chiusi dentro
    non_contorno     candidati non-contorno (criterio di heal, D49)
    Trash            il resto, non classificato

    python scripts/19_outer_scan_heal.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import heapq
import math
import os
from dataclasses import dataclass, field, replace
from typing import List, Optional, Tuple

from shapely.geometry import Point

import forge
from forge.core.geometry import (
    _line_intersection, _circle_line_intersections,
    _circle_circle_intersections,
)
from forge.core.primitives.segments import (
    LineSeg, ArcSeg, DEFAULT_TOLERANCE, segment_endpoints, segment_is_closed,
)
from forge.core.primitives.polygon_builder import build_polygon
from forge.core.healing.normalizer import (
    merge_collinear_overlaps, merge_cocircular_overlaps, weld_degenerate_linesegs,
)
from forge.core.healing.gap_solver import (
    free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes,
)
from forge.core.healing.outer_scan import outer_candidate_edges
from forge.core.healing.islands import spatial_islands
from forge.core.primitives.fitting import simplify_points
from forge.core.topology.graph import build_node_graph
from forge.core.topology.loop_finder import LoopFinder, segments_from_loop, edge_styles_from_loop
from forge.core.topology.non_contour_edges import NonContourEdgeDetector
from forge.model.cluster import ForgeCluster
from forge.model.contour import ForgeContour
from forge.model.feature import OpenFeature
from forge.model.result import ForgeResult
from forge.model.role import ContourRole

# --- CONFIG ----------------------------------------------------------------
INPUTS = [
    r"tests/examples/islands/SHEETCODE.dxf",      # foglio completo, 3 viste
    r"tests/examples/islands/SHEETCODE.dxf",     # 4 viste, una isometrica
    r"tests/examples/islands/3d_1.dxf",
    r"tests/examples/islands/SHEETCODE_1.dxf",
    r"tests/examples/islands/SHEETCODE_2.dxf",
    r"tests/examples/islands/SHEETCODE_3.dxf",
]
TOLERANCE = 0.05
TESSELLATION_SEGMENT = 0.1   # mm — un LineSeg più corto è un candidato punto di tassellatura
TESSELLATION_MIN_RUN = 10    # segmenti corti di fila perché una catena sia una tassellatura
ARC_FIT_TOLERANCE = 0.02     # mm — scostamento massimo per rifittare la catena come arco/cerchio
ISLAND_GAP = 10.0      # mm — distanza massima fra due edge della stessa isola (scelta sui fogli sopra)
SEEN_GAP = 0.5         # mm — gap massimo chiuso attorno a un estremo libero di un pezzo visto dai raggi
GRAPH_EPSILON = 0.01   # mm — due tagli dello stesso incrocio, calcolati da due edge, sono un nodo solo
OUTDIR = r"pipeline_output/outer_scan_heal"
# ---------------------------------------------------------------------------

_EPS = 1e-9
_NODE_DECIMALS = 3  # nodi ricalcolati dagli estremi reali, uguali per ogni pezzo (tagli compresi)
_MIN_PIECE = 1e-4   # mm — sotto, lo spezzone non viene creato


# ---------------------------------------------------------------------------
# 1. Normalizzazione + gap piccoli
# ---------------------------------------------------------------------------

def _normalize(edges, tol):
    """Stessi passi di heal, ma sulla griglia fine dei tagli: prima i nodi
    dagli estremi reali, poi le tassellature rifittate, poi merge/weld/gap —
    così la saldatura resta valida anche dopo lo spezzamento. Via gli Edge
    rimasti a lunghezza zero."""
    edges = _refit_tessellations(_renode(edges))
    edges = weld_degenerate_linesegs(merge_cocircular_overlaps(merge_collinear_overlaps(edges)))
    graph = build_node_graph(edges)
    fixes = compute_gap_fixes(free_endpoints_from_edges(edges, graph), tol)
    if fixes:
        edges = apply_gap_fixes(edges, fixes, _NODE_DECIMALS)
    return [e for e in edges if e.start != e.end or segment_is_closed(e.segment)]


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

    ends = [n for n in graph if len(graph[n]) != 2]
    for n in ends:
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
    pts = seg.discretize(DEFAULT_TOLERANCE)
    return [("line", pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


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


def _bbox(edge):
    pts = edge.segment.discretize(DEFAULT_TOLERANCE)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _split_params(edge, box, others, tol):
    seg = edge.segment
    rng = _param_range(seg)
    x0, y0, x1, y1 = box
    params = []
    for other, (ox0, oy0, ox1, oy1) in others:
        if other is edge:
            continue
        if ox1 < x0 - tol or ox0 > x1 + tol or oy1 < y0 - tol or oy0 > y1 + tol:
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


def _renode(edges):
    """Nodi di ogni Edge ricalcolati dal punto reale a _NODE_DECIMALS: la
    griglia di heal (1 decimale a tolleranza 0.05) e quella dei tagli devono
    essere la stessa, se no un contatto a T non si riconosce."""
    return [e if segment_is_closed(e.segment) else _make_edge(e, e.segment, _NODE_DECIMALS)
            for e in edges]


def _node_all(edges, tol, decimals):
    boxes = [(e, _bbox(e)) for e in edges]
    pieces = []
    for e, box in boxes:
        if isinstance(e.segment, (LineSeg, ArcSeg)) and e.start != e.end:
            pieces.extend(_split(e, _split_params(e, box, boxes, tol), decimals))
        else:
            pieces.append(e)
    return pieces


# ---------------------------------------------------------------------------
# 4. Ponti e contorno esterno
# ---------------------------------------------------------------------------

def _length(edge):
    seg = edge.segment
    if isinstance(seg, LineSeg):
        return math.dist(seg.start, seg.end)
    if isinstance(seg, ArcSeg):
        return seg.radius * seg._sweep()
    pts = seg.discretize(DEFAULT_TOLERANCE)
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def _degree_in(graph, node, ids):
    return sum(1 for e, _ in graph[node] if id(e) in ids)


def _shortest_bridge(graph, start, targets, certain_ids):
    """Dijkstra da `start` al più vicino dei `targets`, solo su pezzi NON certi.
    Ritorna (lunghezza, pezzi, nodo d'arrivo) o None."""
    dist = {start: 0.0}
    prev = {}
    heap = [(0.0, start)]
    while heap:
        d, node = heapq.heappop(heap)
        if d > dist.get(node, float("inf")):
            continue
        if node != start and node in targets:
            end, path = node, []
            while node != start:
                edge, node = prev[node]
                path.append(edge)
            return d, path, end
        for edge, nb in graph[node]:
            if id(edge) in certain_ids:
                continue
            nd = d + _length(edge)
            if nd < dist.get(nb, float("inf")):
                dist[nb] = nd
                prev[nb] = (edge, node)
                heapq.heappush(heap, (nd, nb))
    return None


def _close_seen_gaps(pieces, seen_ids, decimals):
    """Gap solver di heal, a SEEN_GAP invece che alla tolleranza, ma solo sugli
    estremi liberi di pezzi visti dai raggi e su quelli a portata di mano: un
    contorno visto che si interrompe di pochi decimi è un gap di disegno, non
    una punta. Ritorna (pezzi, id dei visti) — apply_gap_fixes tiene le
    posizioni, i segmenti aggiunti vanno in fondo."""
    graph = build_node_graph(pieces, epsilon=GRAPH_EPSILON)
    free = free_endpoints_from_edges(pieces, graph)
    seen_pts = [ep.pt for ep in free if id(ep.ref) in seen_ids]
    near = [ep for ep in free
            if id(ep.ref) in seen_ids
            or any(math.dist(ep.pt, q) <= SEEN_GAP for q in seen_pts)]
    fixes = compute_gap_fixes(near, SEEN_GAP)
    if not fixes:
        return pieces, seen_ids
    seen_idx = [i for i, e in enumerate(pieces) if id(e) in seen_ids]
    pieces = apply_gap_fixes(pieces, fixes, decimals)
    return pieces, {id(pieces[i]) for i in seen_idx}


def _drop_certain_tips(graph, certain_ids):
    """Un pezzo certo con un estremo che non tocca nessun altro edge del
    disegno (grado totale 1) non può stare su una sagoma chiusa: punta di un
    asse, sfioramento di una linea nascosta. Via, a ripetizione."""
    ids = set(certain_ids)
    degree = {n: len(conn) for n, conn in graph.nodes.items()}
    changed = True
    while changed:
        changed = False
        for node, conn in graph.nodes.items():
            if degree[node] != 1:
                continue
            for edge, other in conn:
                if id(edge) in ids:
                    ids.discard(id(edge))
                    degree[node] -= 1
                    degree[other] -= 1
                    changed = True
    return ids


def _bridges(graph, certain_ids):
    """Accoppia gli estremi liberi della catena dei certi col ponte più corto,
    dal più corto in su; ogni estremo e ogni pezzo in un ponte solo."""
    free = {n for n in graph if _degree_in(graph, n, certain_ids) == 1}
    options = []
    for n in free:
        found = _shortest_bridge(graph, n, free - {n}, certain_ids)
        if found:
            d, path, end = found
            options.append((d, n, end, path))
    options.sort(key=lambda o: o[0])
    used_nodes, used_edges, bridges = set(), set(), []
    for d, a, b, path in options:
        if a in used_nodes or b in used_nodes or any(id(e) in used_edges for e in path):
            continue
        used_nodes |= {a, b}
        used_edges |= {id(e) for e in path}
        bridges.extend(path)
    return bridges


def _prune_spurs(edges):
    """Toglie a ripetizione i pezzi con un estremo libero: restano solo i giri."""
    edges = list(edges)
    while True:
        g = build_node_graph(edges, epsilon=GRAPH_EPSILON)
        leaves = set(g.open_nodes())
        keep = [e for e in edges
                if g.canonical(e.start) not in leaves and g.canonical(e.end) not in leaves]
        if len(keep) == len(edges):
            return edges
        edges = keep


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
    edges:    list                           # Edge dell'isola, come arrivano
    cluster:  Optional[ForgeCluster] = None  # None: nessun contorno esterno chiuso
    trash:    list = field(default_factory=list)
    stats:    dict = field(default_factory=dict)


def analyze_island(island_edges, tol) -> IslandReading:
    edges = _normalize(island_edges, tol)
    pieces = _node_all(edges, tol, _NODE_DECIMALS)

    seen_ids = outer_candidate_edges(pieces).ids
    pieces, seen_ids = _close_seen_gaps(pieces, seen_ids, _NODE_DECIMALS)
    graph = build_node_graph(pieces, epsilon=GRAPH_EPSILON)
    certain_ids = _drop_certain_tips(graph, seen_ids)
    bridges = _bridges(graph, certain_ids)

    core = _prune_spurs([e for e in pieces if id(e) in certain_ids] + bridges)
    best = _outer_loop(core)

    reading = IslandReading(edges=list(island_edges))
    reading.stats = {"edge": len(island_edges), "normalizzati": len(edges), "pezzi": len(pieces),
                     "visti": len(seen_ids), "certi": len(certain_ids), "ponti": len(bridges)}
    outer_ids = set()
    if best is not None:
        loop, segments, poly = best
        outer_ids = {id(e) for e, _ in loop}
        reading.cluster = ForgeCluster(outer=ForgeContour(
            polygon=poly, role=ContourRole.OUTER, segments=segments,
            styles=edge_styles_from_loop(loop)))
        reading.stats["area esterno"] = round(poly.area)

    bridge_ids = {id(e) for e in bridges}
    trash = reading.trash
    trash += _open("contorno_certo",
                   [e for e in pieces if id(e) in outer_ids and id(e) in certain_ids])
    trash += _open("ponte",
                   [e for e in pieces if id(e) in outer_ids and id(e) in bridge_ids])
    trash += _open("certo_scartato",
                   [e for e in pieces if id(e) in seen_ids and id(e) not in outer_ids])

    rest = [e for e in pieces if id(e) not in outer_ids and id(e) not in seen_ids]
    rest_graph = build_node_graph(rest, epsilon=GRAPH_EPSILON)
    loop_ids = {id(e) for loop in LoopFinder().find(rest_graph) for e, _ in loop}
    loop_ids |= {id(e) for e in rest_graph.degenerate_loops}
    non_contour_ids = NonContourEdgeDetector(tol).detect(graph, pieces)

    inner = [e for e in rest if id(e) in loop_ids]
    non_contour = [e for e in rest if id(e) in non_contour_ids and id(e) not in loop_ids]
    unknown = [e for e in rest if id(e) not in loop_ids and id(e) not in non_contour_ids]
    trash += _open("giro_interno", inner)
    trash += _open("non_contorno", non_contour)
    trash += _open(ContourRole.UNKNOWN, unknown)
    reading.stats.update({"giro_interno": len(inner), "non_contorno": len(non_contour),
                          "non classificati": len(unknown)})
    return reading


def _inside(small: IslandReading, big: IslandReading) -> bool:
    """Tutta la geometria di `small` sta dentro il contorno esterno di `big`."""
    if big.cluster is None or small is big:
        return False
    poly = big.cluster.outer.polygon
    return all(poly.contains(Point(p)) for e in small.edges
               for p in e.segment.discretize(DEFAULT_TOLERANCE))


def analyze(doc, tol) -> Tuple[ForgeResult, List[IslandReading]]:
    """Isole → contorno esterno per isola → un'isola tutta dentro il contorno
    di un'altra (un foro lontano dai lati) viene assorbita e l'isola che la
    contiene si rilegge con dentro anche quella."""
    readings = [analyze_island(isl.edges, tol)
                for isl in spatial_islands(doc.edges, ISLAND_GAP)]

    absorbed = True
    while absorbed:
        absorbed = False
        for small in readings:
            host = next((big for big in readings if _inside(small, big)), None)
            if host is not None:
                readings.remove(small)
                readings[readings.index(host)] = analyze_island(host.edges + small.edges, tol)
                absorbed = True
                break

    result = ForgeResult(source_file=doc.source_path, annotations=list(doc.annotations))
    for r in readings:
        if r.cluster is not None:
            result.clusters.append(r.cluster)
        result.trash_entities += r.trash
    if not result.clusters:
        result.is_valid = False
        result.errors.append("Nessuna isola con un contorno esterno chiuso.")
    return result, readings


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    for path in INPUTS:
        stem = os.path.splitext(os.path.basename(path))[0]
        doc = forge.load_dxf(path, tolerance=TOLERANCE)
        result, readings = analyze(doc, TOLERANCE)
        print(f"{stem}: {len(readings)} isole, {len(result.clusters)} con contorno esterno")
        for n, r in enumerate(readings, 1):
            print(f"  isola {n}: " + ", ".join(f"{k} {v}" for k, v in r.stats.items()))
        suffix = ""
        if not result.is_valid:
            # to_dxf rifiuta un risultato invalido: qui lo si vuole vedere lo stesso
            result.is_valid, result.errors = True, []
            suffix = "_INVALIDO"
        out = os.path.abspath(os.path.join(OUTDIR, f"{stem}{suffix}.dxf"))
        forge.to_dxf(result, doc, include_trash=True).saveas(out)
        print(f"  -> {out}")


if __name__ == "__main__":
    main()
