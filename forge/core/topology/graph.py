
# forge/core/topology/graph.py

"""
graph.py
--------
Costruisce il grafo topologico.

Questo modulo non importa ezdxf e non accede a entity.dxf.
Tutta la geometria viene letta da edge.geometry (LineString shapely).

Tipi pubblici:
    Graph              — grafo tipizzato con metodi di interrogazione
    build_node_graph   — costruisce Graph da list[Edge]

Utility interne (usate da loops.py):
    _edge_coords       — punti dell'edge come lista (x, y)
    _first_coord       — primo punto della geometry
    _arrival_direction — vettore di arrivo
    _angular_deviation — deviazione angolare tra direzioni
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Tuple

from ..geometry import round_point
from ...model.edge import Edge


# ---------------------------------------------------------------------------
# Dataclass Graph
# ---------------------------------------------------------------------------

@dataclass
class Graph:
    """
    Grafo topologico interrogabile.

    nodes: dict[punto, list[(Edge, punto_opposto)]]
    """
    nodes: dict = field(default_factory=dict)

    def degree(self, node: Tuple) -> int:
        return len(self.nodes.get(node, []))

    def branching_nodes(self) -> list:
        return [n for n, conn in self.nodes.items() if len(conn) > 2]

    def pruned(self) -> 'Graph':
        """Restituisce un nuovo Graph senza nodi dead-end (degree ≤ 1)."""
        g = {node: list(neighbors) for node, neighbors in self.nodes.items()}

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

        return Graph(nodes=g)

    def __iter__(self):
        return iter(self.nodes)

    def __getitem__(self, node):
        return self.nodes[node]

    def __contains__(self, node):
        return node in self.nodes

    def items(self):
        return self.nodes.items()
    
    def get(self, node, default=None):
        return self.nodes.get(node, default)


# ---------------------------------------------------------------------------
# Costruzione grafo
# ---------------------------------------------------------------------------

def build_node_graph(edges: list) -> Graph:
    raw = defaultdict(list)
    for edge in edges:
        raw[edge.start].append((edge, edge.end))
        raw[edge.end].append((edge, edge.start))
    return Graph(nodes=dict(raw))


# ---------------------------------------------------------------------------
# Utility geometriche (usate da loops.py)
# ---------------------------------------------------------------------------

def _edge_coords(edge: Edge, reversed_flag: bool) -> list:
    if edge.geometry is None:
        pts = [edge.start, edge.end]
    else:
        pts = list(edge.geometry.coords)
    if reversed_flag:
        pts = list(reversed(pts))
    return pts


def _first_coord(edge: Edge):
    if edge.geometry is not None:
        coords = list(edge.geometry.coords)
        if coords:
            return round_point(coords[0])
    return round_point(edge.start)


def _arrival_direction(edge: Edge, rev: bool):
    coords = _edge_coords(edge, rev)
    if len(coords) < 2:
        return None
    dx = coords[-1][0] - coords[-2][0]
    dy = coords[-1][1] - coords[-2][1]
    return (dx, dy)


def _angular_deviation(arrival_dir, edge: Edge, rev: bool):
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

