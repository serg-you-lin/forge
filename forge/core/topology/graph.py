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
                         separa automaticamente i loop degeneri (start == end)
                         con epsilon > 0 fonde gli endpoint vicini in un solo nodo
    cluster_points     — clustering di punti 2D entro epsilon (union-find)

Utility geometriche interne:
    _edge_coords       — punti dell'edge come lista (x, y)   [loop_finder.py]
    _arrival_direction — vettore di arrivo                   [loop_finder.py]
    _angular_deviation — deviazione angolare tra direzioni   [loop_finder.py]
    _first_coord       — primo punto della geometry (helper generico)

Identità dei nodi
-----------------
Ogni endpoint arriva già arrotondato dall'adapter (`round_point` alla
tolleranza). L'arrotondamento è una quantizzazione su griglia fissa: due
punti fisicamente coincidenti ma a cavallo del confine di una cella finiscono
in nodi diversi e spezzano un contorno che invece è chiuso.

`build_node_graph(edges, epsilon)` con `epsilon > 0` sostituisce la
quantizzazione con un vero clustering: raggruppa gli endpoint entro `epsilon`
(componenti connesse via union-find) e assegna a ciascun cluster un unico nodo
canonico. `epsilon = 0.0` (default) mantiene il comportamento storico —
uguaglianza esatta della tupla arrotondata — così i test e i chiamanti
esistenti non cambiano.

Cautela: il clustering è transitivo. Con `epsilon` grande e nodi reali vicini
si rischia la percolazione (una fila di punti a `0.9*epsilon` l'uno dall'altro
collassa in un nodo solo). In pratica `epsilon` va tenuto <= tolleranza di
healing: i nodi topologici reali (angoli, diramazioni) distano molto di più.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Tuple, List, Dict

from ..geometry import round_point
from ...adapters.bridge.edge import Edge


# ---------------------------------------------------------------------------
# Dataclass Graph
# ---------------------------------------------------------------------------

@dataclass
class Graph:
    """
    Grafo topologico interrogabile.

    nodes:            dict[punto, list[(Edge, punto_opposto)]]
    degenerate_loops: list[Edge] — edge con start == end (CIRCLE, SPLINE chiusa)
                      non entrano nel grafo: sono già loop completi per definizione.
    """
    nodes:            dict       = field(default_factory=dict)
    degenerate_loops: List[Edge] = field(default_factory=list)
    node_map:         Dict[Tuple, Tuple] = field(default_factory=dict)

    def canonical(self, pt: Tuple) -> Tuple:
        """
        Nodo canonico per un endpoint arrotondato.

        Identità se `node_map` è vuoto (grafo non clusterizzato). Altrimenti
        traduce il punto arrotondato dell'edge nel rappresentante del suo
        cluster — è così che loop_finder confronta gli edge con i nodi.
        """
        return self.node_map.get(pt, pt)

    def degree(self, node: Tuple) -> int:
        return len(self.nodes.get(self.canonical(node), []))

    def branching_nodes(self) -> list:
        return [n for n, conn in self.nodes.items() if len(conn) > 2]

    def merged_clusters(self) -> list:
        """
        Cluster in cui il clustering ha fuso più endpoint distinti.

        Restituisce [(nodo_canonico, [membri...]), ...] solo per i cluster con
        più di un membro. Sono esattamente gli angoli dove il grafo esatto
        vedeva un buco: le coordinate da segnalare all'utente perché li
        verifichi, e i candidati naturali per una chiusura esatta via
        gap_solver (estensione all'intersezione reale) invece della semplice
        tolleranza.
        """
        groups: Dict[Tuple, list] = defaultdict(list)
        for pt, canon in self.node_map.items():
            groups[canon].append(pt)
        return [(c, m) for c, m in groups.items() if len(m) > 1]

    def open_nodes(self) -> list:
        """
        Nodi con un solo edge incidente — gli estremi liberi del grafo.

        Un contorno che dovrebbe essere chiuso ha 0 nodi aperti; 2 nodi aperti
        = un solo gap residuo; molti nodi aperti = geometria a matassa
        (marcature, tracce aperte) più che un contorno. `pruned()` li elimina
        in silenzio, quindi va interrogato prima della potatura per avere una
        diagnostica localizzata.
        """
        return [n for n, conn in self.nodes.items() if len(conn) == 1]

    def pruned(self) -> 'Graph':
        """
        Restituisce un nuovo Graph senza nodi dead-end (degree <= 1).
        I degenerate_loops vengono preservati invariati — non hanno
        nodi nel grafo e non sono soggetti a potatura.
        """
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

        return Graph(nodes=g, degenerate_loops=self.degenerate_loops,
                     node_map=self.node_map)

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
# Clustering endpoint
# ---------------------------------------------------------------------------

def cluster_points(points: list, epsilon: float) -> Dict[Tuple, Tuple]:
    """
    Raggruppa punti 2D entro `epsilon` e restituisce {punto -> rappresentante}.

    Componenti connesse via union-find: due punti finiscono nello stesso
    cluster se distano <= epsilon, e la relazione è transitiva. Il
    rappresentante di un cluster è il suo punto lessicograficamente minimo —
    deterministico e sempre un endpoint reale (non un centroide fittizio).

    `epsilon <= 0` o meno di due punti → mappa identità.

    Il confronto è limitato alle celle adiacenti di una griglia di lato
    `epsilon`, quindi il costo è lineare nel numero di punti per input
    tipici (nessun blow-up O(n²) su file da migliaia di edge).
    """
    pts = list(dict.fromkeys(points))
    if epsilon <= 0 or len(pts) < 2:
        return {p: p for p in pts}

    parent = {p: p for p in pts}

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if rb < ra:
            ra, rb = rb, ra
        parent[rb] = ra

    inv_eps = 1.0 / epsilon
    buckets: Dict[Tuple[int, int], list] = defaultdict(list)
    for p in pts:
        buckets[(math.floor(p[0] * inv_eps), math.floor(p[1] * inv_eps))].append(p)

    eps2 = epsilon * epsilon
    for p in pts:
        cx = math.floor(p[0] * inv_eps)
        cy = math.floor(p[1] * inv_eps)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for q in buckets.get((cx + dx, cy + dy), ()):
                    if q is p:
                        continue
                    ddx = p[0] - q[0]
                    ddy = p[1] - q[1]
                    if ddx * ddx + ddy * ddy <= eps2:
                        union(p, q)

    return {p: find(p) for p in pts}


# ---------------------------------------------------------------------------
# Costruzione grafo
# ---------------------------------------------------------------------------

def build_node_graph(edges: list, epsilon: float = 0.0) -> Graph:
    """
    Costruisce il Graph da list[Edge].

    Edge con start == end (CIRCLE, SPLINE chiusa) vengono separati
    in degenerate_loops — non hanno senso come nodi del grafo perché
    il loro unico nodo sarebbe vicino di se stesso.

    `epsilon > 0` fonde gli endpoint entro `epsilon` in un unico nodo canonico
    (vedi cluster_points e la nota in testa al modulo). Con `epsilon = 0.0` i
    nodi restano le tuple arrotondate esatte, come da comportamento storico.
    """
    raw        = defaultdict(list)
    degenerate = []

    if epsilon > 0:
        endpoints = []
        for edge in edges:
            if edge.start != edge.end:
                endpoints.append(edge.start)
                endpoints.append(edge.end)
        node_map = cluster_points(endpoints, epsilon)
    else:
        node_map = {}

    def canon(pt):
        return node_map.get(pt, pt)

    for edge in edges:
        if edge.start == edge.end:
            # Loop degenere: non entra nel grafo, va diretto al loop finder
            degenerate.append(edge)
            continue

        s = canon(edge.start)
        e = canon(edge.end)
        if s == e:
            # Endpoint distinti collassati dal clustering: sliver più corto di
            # epsilon. Non è un loop strutturale — lo si lascia fuori dal grafo
            # e lo raccoglie edges_to_open_features come traccia aperta.
            continue

        raw[s].append((edge, e))
        raw[e].append((edge, s))

    return Graph(nodes=dict(raw), degenerate_loops=degenerate, node_map=node_map)


# ---------------------------------------------------------------------------
# Utility geometriche (usate da loop_finder.py)
# ---------------------------------------------------------------------------

def _edge_coords(edge: Edge, reversed_flag: bool) -> list:
    pts = edge.segment.discretize() if edge.segment else [edge.start, edge.end]
    if reversed_flag:
        pts = list(reversed(pts))
    return pts


def _first_coord(edge: Edge):
    pts = edge.segment.discretize() if edge.segment else [edge.start, edge.end]
    if pts:
        return round_point(pts[0])
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