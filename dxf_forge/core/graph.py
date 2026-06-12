

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
    check_loop_ambiguity — rileva nodi con più di 2 connessioni
    spline_to_points     — discretizza una SPLINE in lista di punti
    spline_endpoints     — restituisce (start, end) di una SPLINE
    arc_to_bulge         — converte un ARC in (entry_point, bulge, exit_point)
"""

import math
from collections import defaultdict
from shapely.geometry import Polygon, LinearRing

from .geometry import arc_endpoints, arc_to_bulge, round_point, spline_to_points
from ..models import Edge

# ---------------------------------------------------------------------------
# Helpers — ancora usati da virtual.py e da codice esterno al core
# ---------------------------------------------------------------------------

def spline_endpoints(spline):
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

def _edge_coords(edge, reversed_flag: bool) -> list:
    """
    Restituisce i punti dell'edge come lista di (x, y).
    Se reversed_flag=True, inverte l'ordine.
    Legge da edge.geometry (LineString) — nessun accesso a entity.dxf.
    """
    if edge.geometry is None:
        # fallback difensivo: usa start/end già calcolati dall'adapter
        pts = [edge.start, edge.end]
    else:
        pts = list(edge.geometry.coords)

    if reversed_flag:
        pts = list(reversed(pts))
    return pts


def find_closed_loops(graph):
    pruned = _prune_dead_ends(graph)
    visited_edges = set()
    loops = []
 
    for start_node in pruned:
        for (edge, next_node) in pruned[start_node]:
            if id(edge) in visited_edges:
                continue
 
            first_pt = _first_coord(edge)
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
                next_edge, current_node = candidates[0]
                visited_edges.add(id(next_edge))
 
                prev_edge, prev_rev = chain[-1]
                prev_pts = _edge_coords(prev_edge, prev_rev)
                arrive_from = round_point(prev_pts[-1]) if prev_pts else None
 
                next_first = _first_coord(next_edge)
                if arrive_from and next_first:
                    ne_reversed = (next_first != arrive_from)
                else:
                    ne_reversed = False
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


def _first_coord(edge):
    """
    Restituisce il primo punto della geometry dell'edge come tuple arrotondata.
    Usato per determinare la direzione di percorrenza.
    """
    if edge.geometry is not None:
        coords = list(edge.geometry.coords)
        if coords:
            return round_point(coords[0])
    return round_point(edge.start)


# ---------------------------------------------------------------------------
# Classificazione loop — legge da edge.geometry
# ---------------------------------------------------------------------------

def classify_loops(loops):
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

def loop_to_points(loop) -> list:
    """
    Converte un loop in lista di punti (x, y).
    Legge da edge.geometry — nessun accesso a entity.dxf.
    """
    pts = []
    for edge, rev in loop:
        coords = _edge_coords(edge, rev)
        # prende solo il primo punto di ogni edge per evitare duplicati
        # (l'ultimo punto di un edge coincide con il primo del successivo)
        if coords:
            pts.append(coords[0])
    return pts


def _prune_dead_ends(graph: dict) -> dict:
    g = {node: list(neighbors) for node, neighbors in graph.items()}

    changed = True
    while changed:
        changed = False
        leaves = [node for node, neighbors in g.items() if len(neighbors) <= 1]
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


def check_loop_ambiguity(loops, graph):
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