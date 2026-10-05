"""
core/topology/outer_face.py
---------------------------
Contorno esterno di una rete piana (noding.py) come bordo della sua faccia
esterna: una definizione esatta, deterministica, senza scelte greedy.

Per ogni componente connesso: si parte dal punto più a sinistra della
geometria — sul bordo esterno per forza, anche a metà di un edge — e si
percorre l'edge verso il basso, così l'esterno sta a destra; a ogni nodo si
prende l'edge che gira meno in senso antiorario rispetto a quello da cui si
arriva. Un edge percorso andata e ritorno è una sporgenza (asse, segno, quota
attaccata): non è contorno. Il contorno della rete è la faccia esterna di
area massima fra i componenti (e i loop chiusi da soli, come un cerchio).
Se il giro racchiude meno dell'unione delle facce chiuse del componente
(nodi che non coincidono al millesimo, archi tangenti a linee), il contorno
è il bordo di quell'unione (D100).

Puro: solo Edge, grafo e primitive, nessun formato.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

import shapely
from shapely.geometry import Polygon
from shapely.ops import polygonize, unary_union

from .edge import Edge
from .noding import edge_geometry
from .graph import Graph, build_node_graph
from .loop_finder import LoopFinder, loop_geometry
from ..primitives.segments import DEFAULT_TOLERANCE

DIRECTION_SAMPLE = 3.0   # mm — la direzione di un edge a un nodo si legge fin qui (al massimo a metà edge)


@dataclass
class OuterFace:
    """Il contorno esterno trovato, e cosa il percorso ha scartato."""
    loop:      list                         # [(Edge, reversed)] come dal LoopFinder
    segments:  list                         # primitive orientate del contorno
    styles:    list
    polygon:   Polygon
    spurs:     List[Edge] = field(default_factory=list)   # percorsi andata e ritorno

    @property
    def edges(self) -> List[Edge]:
        return [e for e, _ in self.loop]


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def outer_face(edges: List[Edge], epsilon: float = 0.0) -> Optional[OuterFace]:
    """
    Contorno esterno della rete `edges` (già piana: split_at_crossings). I
    nodi entro `epsilon` sono uno solo. None se non c'è nessun giro chiuso.
    """
    graph = build_node_graph(edges, epsilon=epsilon)
    best, spurs = None, []
    for component in graph.connected_components():
        walk = _outer_face_walk(graph, component, len(edges))
        count: dict = {}
        for edge, _, _ in walk:
            count[id(edge)] = count.get(id(edge), 0) + 1
        spurs += [e for e in edges if count.get(id(e), 0) >= 2]
        boundary = [e for e in edges if count.get(id(e)) == 1]
        found = _largest_loop(boundary, epsilon) if boundary else None
        if found is not None and (best is None or found[3].area > best[3].area):
            best = found
    alone = _largest_loop(graph.degenerate_loops, epsilon)
    if alone is not None and (best is None or alone[3].area > best[3].area):
        best = alone
    # D100: la faccia esterna è il bordo dell'unione delle facce chiuse di
    # tutta la rete, anche se il grafo la vede in più componenti scollegati;
    # se il giro ne racchiude meno, vale l'unione
    united = _faces_union_loop(edges, epsilon)
    if united is not None and (best is None or united[3].area > best[3].area * (1 + 1e-6)):
        best = united
    if best is None:
        return None
    loop, segments, styles, polygon = best
    return OuterFace(loop=loop, segments=segments, styles=styles, polygon=polygon, spurs=spurs)


# ---------------------------------------------------------------------------
# Percorso
# ---------------------------------------------------------------------------

def _outer_face_walk(graph: Graph, component, n_edges: int) -> list:
    """[(edge, dal nodo, al nodo)] lungo il bordo della faccia esterna."""
    angles: dict = {}

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
                turn = 2 * math.pi       # tornare indietro: solo se non c'è altro
            if best_turn is None or turn < best_turn:
                best, best_turn = (edge, other), turn
        edge, other = best
        if node == first[1] and edge is first[0] and other == first[2]:
            break
        walk.append((edge, node, other))
        back_edge, back_angle = edge, angle(edge, other)
        node = other
    return walk


def _first_step(graph: Graph, component):
    """L'edge che contiene il punto più a sinistra del componente, percorso
    verso il basso; se quel punto è un nodo, il primo edge in senso
    antiorario a partire da ovest."""
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
    start = a if i == 0 else b
    choice = min(graph[start],
                 key=lambda eo: (_leaving_angle(eo[0], start, graph) - math.pi) % (2 * math.pi))
    return (choice[0], start, choice[1])


def _leaving_angle(edge: Edge, node, graph: Graph) -> float:
    """Direzione con cui `edge` lascia `node`, letta a DIRECTION_SAMPLE (o a
    metà edge): un raccordo tangente a una retta si distingue da lei solo
    più avanti, non al primo micron."""
    pts = edge.segment.discretize(DEFAULT_TOLERANCE)
    if graph.canonical(edge.start) != node:
        pts = list(reversed(pts))
    total = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    reach = min(DIRECTION_SAMPLE, total / 2)
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


def _faces_union_loop(edges: List[Edge], epsilon: float):
    """(loop, segments, styles, polygon) sul bordo dell'unione delle facce
    chiuse della rete, coi nodi sulla griglia `epsilon` (D100); None se la
    rete non chiude nessuna faccia. Se gli edge del bordo non si chiudono in
    un giro del grafo (componenti scollegati), il poligono è l'unione e il
    giro sono gli edge che ci stanno sopra, nell'ordine dato."""
    faces = list(polygonize(shapely.unary_union([edge_geometry(e) for e in edges],
                                                grid_size=max(epsilon, 1e-6))))
    if not faces:
        return None
    union = unary_union(faces)
    region = max(getattr(union, "geoms", [union]), key=lambda g: g.area)
    rim = region.exterior.buffer(2 * max(epsilon, 1e-6))
    on_rim = [e for e in edges if rim.contains(edge_geometry(e))]
    found = _largest_loop(on_rim, epsilon) if on_rim else None
    if found is not None and found[3].area >= region.area * 0.99:
        return found
    if not on_rim:
        return None
    outer = Polygon(region.exterior)
    return [(e, False) for e in on_rim], [e.segment for e in on_rim], [e.style for e in on_rim], outer


def _largest_loop(edges: List[Edge], epsilon: float):
    """(loop, segments, styles, polygon) del giro di area massima."""
    graph = build_node_graph(edges, epsilon=epsilon)
    best = None
    for loop in LoopFinder().find(graph):
        geometry = loop_geometry(loop)
        if geometry is not None and (best is None or geometry[2].area > best[3].area):
            best = (loop, *geometry)
    return best
