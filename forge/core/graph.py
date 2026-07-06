
"""
graph.py
--------
Costruisce il grafo topologico e trova i loop chiusi.

Il grafo modella Edge come archi tra i loro endpoint arrotondati.
Ogni nodo è un punto (x, y) arrotondato a `decimals` cifre decimali.
Ogni arco è una tupla (Edge, nodo_opposto).

Questo modulo non importa ezdxf e non accede a entity.dxf.
Tutta la geometria viene letta da edge.geometry (LineString shapely)
popolato dall'adapter prima della costruzione del grafo.

Funzioni pubbliche:
    build_node_graph     — costruisce il grafo da list[Edge]
    find_closed_loops    — trova tutti i loop chiusi nel grafo
    classify_loops       — classifica i loop in outer e inner
    loop_to_points       — converte un loop in lista di punti
    check_loop_ambiguity — rileva nodi con più di 2 connessioni
    spline_endpoints     — restituisce (start, end) di una SPLINE
"""

import math
from collections import defaultdict
from shapely.geometry import Polygon, LinearRing

from .geometry import round_point
from ..model.edge import Edge


# ---------------------------------------------------------------------------
# spline_endpoints — helper per geometry_adapter e graph_adapter
# ---------------------------------------------------------------------------

def spline_endpoints(spline):
    """
    Restituisce (start, end) come tuple (x, y) di una SPLINE ezdxf.
    Unica funzione di questo modulo che tocca ezdxf — accetta l'entity
    ma legge solo i punti flattening, non entity.dxf.
    """
    try:
        pts = list(spline.flattening(0.01))
        if len(pts) < 2:
            return None, None
        return (pts[0][0], pts[0][1]), (pts[-1][0], pts[-1][1])
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Costruzione grafo
# ---------------------------------------------------------------------------

def build_node_graph(edges: list) -> dict:
    graph = defaultdict(list)
    for edge in edges:
        graph[edge.start].append((edge, edge.end))
        graph[edge.end].append((edge, edge.start))
    return graph


# ---------------------------------------------------------------------------
# Ricerca loop — legge da edge.geometry, non da entity.dxf
# ---------------------------------------------------------------------------

def _edge_coords(edge: Edge, reversed_flag: bool) -> list:
    """
    Restituisce i punti dell'edge come lista di (x, y).
    Se reversed_flag=True, inverte l'ordine.
    Legge da edge.geometry (LineString) — nessun accesso a entity.dxf.
    """
    if edge.geometry is None:
        pts = [edge.start, edge.end]
    else:
        pts = list(edge.geometry.coords)

    if reversed_flag:
        pts = list(reversed(pts))
    return pts


def _first_coord(edge: Edge):
    """
    Restituisce il primo punto della geometry dell'edge come tuple arrotondata.
    Usato per determinare la direzione di percorrenza.
    """
    if edge.geometry is not None:
        coords = list(edge.geometry.coords)
        if coords:
            return round_point(coords[0])
    return round_point(edge.start)



def _arrival_direction(edge: Edge, rev: bool):
    """
    Vettore di arrivo: direzione degli ultimi due punti dell'edge percorso.
    """
    coords = _edge_coords(edge, rev)
    if len(coords) < 2:
        return None
    dx = coords[-1][0] - coords[-2][0]
    dy = coords[-1][1] - coords[-2][1]
    return (dx, dy)


def _angular_deviation(arrival_dir, edge: Edge, rev: bool):
    """
    Deviazione angolare tra la direzione di arrivo e la direzione
    di partenza del candidato. Minore = più dritto.
    """
    if arrival_dir is None:
        return 0.0
    coords = _edge_coords(edge, rev)
    if len(coords) < 2:
        return 0.0
    dx = coords[1][0] - coords[0][0]
    dy = coords[1][1] - coords[0][1]
    cross = arrival_dir[0] * dy - arrival_dir[1] * dx
    dot   = arrival_dir[0] * dx + arrival_dir[1] * dy
    return abs(math.atan2(cross, dot))


def find_closed_loops(graph: dict) -> list:
    pruned        = _prune_dead_ends(graph)
    branching     = {n for n, conn in pruned.items() if len(conn) > 2}
    visited_edges = set()
    loops         = []

    for start_node in pruned:
        for (edge, next_node) in pruned[start_node]:
            if id(edge) in visited_edges:
                continue

            first_pt    = _first_coord(edge)
            is_reversed = (first_pt != start_node) if first_pt else False

            chain = [(edge, is_reversed)]
            visited_edges.add(id(edge))
            current_node = next_node

            while current_node != start_node:
                candidates = [
                    (e, n) for (e, n) in pruned[current_node]
                    if id(e) not in visited_edges
                ]
                if not candidates:
                    break

                if current_node in branching and len(candidates) > 1:
                    prev_edge, prev_rev = chain[-1]
                    arrival = _arrival_direction(prev_edge, prev_rev)

                    def _score(candidate):
                        e, n = candidate
                        first = _first_coord(e)
                        rev   = (first != current_node) if first else False
                        return _angular_deviation(arrival, e, rev)

                    next_edge, current_node = min(candidates, key=_score)
                else:
                    next_edge, current_node = candidates[0]

                visited_edges.add(id(next_edge))

                prev_edge, prev_rev = chain[-1]
                prev_pts    = _edge_coords(prev_edge, prev_rev)
                arrive_from = round_point(prev_pts[-1]) if prev_pts else None

                next_first  = _first_coord(next_edge)
                ne_reversed = (next_first != arrive_from) if (arrive_from and next_first) else False
                chain.append((next_edge, ne_reversed))

            if current_node != start_node:
                continue

            pts = loop_to_points(chain)
            if len(pts) >= 3:
                try:
                    if not LinearRing(pts).is_ccw:
                        chain = [(e, not rev) for e, rev in reversed(chain)]
                except Exception:
                    pass

            loops.append(chain)

    return loops


# ---------------------------------------------------------------------------
# Classificazione loop
# ---------------------------------------------------------------------------

def classify_loops(loops: list):
    shapely_polygons = []
    for loop in loops:
        pts = loop_to_points(loop)
        shapely_polygons.append(Polygon(pts) if len(pts) >= 3 else None)

    outer, inners = [], []
    for i, (loop, poly) in enumerate(zip(loops, shapely_polygons)):
        if poly is None or not poly.is_valid:
            outer.append(loop)
            continue
        is_inner = any(
            j != i
            and shapely_polygons[j] is not None
            and shapely_polygons[j].contains(poly)
            for j in range(len(shapely_polygons))
        )
        inners.append(loop) if is_inner else outer.append(loop)

    return outer, inners


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def loop_to_points(loop: list) -> list:
    """
    Converte un loop in lista di punti (x, y).
    Legge da edge.geometry — nessun accesso a entity.dxf.
    Il primo punto di ogni edge viene preso per evitare duplicati
    (l'ultimo di un edge coincide con il primo del successivo).
    """
    pts = []
    for edge, rev in loop:
        coords = _edge_coords(edge, rev)
        if coords:
            pts.append(coords[0])
    return pts


def _prune_dead_ends(graph: dict) -> dict:
    g = {node: list(neighbors) for node, neighbors in graph.items()}

    changed = True
    while changed:
        changed = False
        leaves = [node for node, neighbors in g.items() if len(neighbors) <= 1]
        # for leaf in leaves:
        #     print(f"[PRUNE] rimuovo: {leaf} neighbors={g[leaf]}")
        for leaf in leaves:
            if leaf not in g:
                continue
            if g[leaf]:
                edge, neighbor = g[leaf][0]
                if neighbor in g:
                    g[neighbor] = [(e, n) for e, n in g[neighbor] if n != leaf]
            del g[leaf]
            changed = True

    return g


def check_loop_ambiguity(loops: list, graph: dict) -> list:
    loop_edge_ids = {id(edge) for loop in loops for edge, _ in loop}
    branching = []
    for node, connections in graph.items():
        loop_connections = [
            (edge, n) for (edge, n) in connections
            if id(edge) in loop_edge_ids
        ]
        if len(loop_connections) > 2:
            branching.append(node)
    return branching