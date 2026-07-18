
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

from ..geometry import round_point
from ...model.edge import Edge

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


# # ---------------------------------------------------------------------------
# # Utility
# # ---------------------------------------------------------------------------


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

