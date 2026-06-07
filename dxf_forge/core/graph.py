
"""
graph.py
--------
Costruisce il grafo topologico delle entità DXF e trova i loop chiusi.

Il grafo modella LINE/ARC/SPLINE come archi tra i loro endpoint arrotondati.
Ogni nodo è un punto (x, y) arrotondato a `decimals` cifre decimali.
Ogni arco è una tupla (Edge, nodo_opposto).

Funzioni pubbliche:
  build_node_graph     — costruisce il grafo da un modelspace ezdxf
  find_closed_loops    — trova tutti i loop chiusi nel grafo
  classify_loops       — classifica i loop in outer e inner
  check_loop_ambiguity — rileva nodi con più di 2 connessioni
  entity_endpoints     — restituisce (start, end) di un'entità
  round_point          — arrotonda un punto a `decimals` decimali
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
# Helpers — endpoint
# ---------------------------------------------------------------------------

_SUPPORTED_TYPES = frozenset({'LINE', 'ARC', 'SPLINE'})


def spline_endpoints(spline):
    try:
        pts = list(spline.flattening(0.01))
        if len(pts) < 2:
            return None, None
        return (pts[0][0], pts[0][1]), (pts[-1][0], pts[-1][1])
    except Exception:
        return None, None


def entity_endpoints(entity):
    t = entity.dxftype()
    if t == 'LINE':
        return (
            (entity.dxf.start.x, entity.dxf.start.y),
            (entity.dxf.end.x,   entity.dxf.end.y),
        )
    if t == 'ARC':
        return arc_endpoints(entity)
    if t == 'SPLINE':
        return spline_endpoints(entity)
    return None, None


def _normalized_endpoints(entity, decimals):
    if entity.dxftype() not in _SUPPORTED_TYPES:
        return None, None
    s, e = entity_endpoints(entity)
    if s is None or e is None:
        return None, None
    return round_point(s, decimals), round_point(e, decimals)


# ---------------------------------------------------------------------------
# Costruzione grafo
# ---------------------------------------------------------------------------

def build_node_graph(edges: list) -> dict:
    graph = defaultdict(list)
    for edge in edges:
        graph[edge.start].append((edge, edge.end))
        graph[edge.end].append((edge, edge.start))
    return graph

# def build_node_graph(msp, decimals=1, exclude_layers=None, exclude_ids=None):
#     exclude_layers = set(exclude_layers or [])
#     exclude_ids    = set(exclude_ids    or [])

#     def _is_excluded(entity):
#         if id(entity) in exclude_ids:
#             return True
#         if not exclude_layers:
#             return False
#         layer = entity.dxf.layer.lower() if entity.dxf.hasattr('layer') else ''
#         return any(sl in layer for sl in exclude_layers)

#     graph = defaultdict(list)

#     for entity in msp:
#         if _is_excluded(entity):
#             continue
#         s, e = _normalized_endpoints(entity, decimals)
#         if s is None:
#             continue
#         layer = entity.dxf.layer if entity.dxf.hasattr('layer') else ''
#         edge = Edge(entity=entity, layer=layer, start=s, end=e)
#         graph[s].append((edge, e))
#         graph[e].append((edge, s))

#     return graph


# ---------------------------------------------------------------------------
# Ricerca loop
# ---------------------------------------------------------------------------

def find_closed_loops(graph):
    pruned = _prune_dead_ends(graph)
    visited_edges = set()
    loops = []

    for start_node in pruned:
        for (edge, next_node) in pruned[start_node]:
            if id(edge.entity) in visited_edges:
                continue

            e_start, e_end = entity_endpoints(edge.entity)
            if e_start is None:
                continue
            is_reversed = (round_point(e_start) != start_node)

            chain = [(edge, is_reversed)]
            visited_edges.add(id(edge.entity))
            current_node = next_node

            while current_node != start_node:
                candidates = [
                    (e, n) for (e, n) in pruned[current_node]
                    if id(e.entity) not in visited_edges
                ]
                if not candidates:
                    break
                next_edge, current_node = candidates[0]
                visited_edges.add(id(next_edge.entity))

                ne_start, _ = entity_endpoints(next_edge.entity)
                if ne_start is None:
                    break
                prev_edge, prev_rev = chain[-1]
                prev_s, prev_e = entity_endpoints(prev_edge.entity)
                if prev_s is None:
                    break
                arrive_from = round_point(prev_s if prev_rev else prev_e)
                ne_reversed = (round_point(ne_start) != arrive_from)
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

def classify_loops(loops):
    shapely_polygons = []
    for loop in loops:
        pts = []
        for edge, rev in loop:
            entity = edge.entity
            if entity.dxftype() == 'LINE':
                pts.append(
                    (entity.dxf.end.x, entity.dxf.end.y) if rev
                    else (entity.dxf.start.x, entity.dxf.start.y)
                )
            elif entity.dxftype() == 'ARC':
                entry_pt, _, _ = arc_to_bulge(entity, reversed=rev)
                pts.append(entry_pt)
            elif entity.dxftype() == 'SPLINE':
                spline_pts = spline_to_points(entity)
                if rev:
                    spline_pts = list(reversed(spline_pts))
                pts.extend(spline_pts)
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
    pts = []
    for edge, rev in loop:
        e = edge.entity
        if e.dxftype() == "LINE":
            pts.append(
                (e.dxf.end.x,   e.dxf.end.y)   if rev
                else (e.dxf.start.x, e.dxf.start.y)
            )
        elif e.dxftype() == "ARC":
            entry_pt, _, _ = arc_to_bulge(e, reversed=rev)
            pts.append(entry_pt)
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
    loop_entity_ids = {id(edge.entity) for loop in loops for edge, _ in loop}
    branching = []
    for node, connections in graph.items():
        loop_connections = [
            (edge, n) for (edge, n) in connections
            if id(edge.entity) in loop_entity_ids
        ]
        if len(loop_connections) > 2:
            branching.append(node)
    return branching