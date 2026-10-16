"""
non_contour_edges.py
--------------------
Individua gli edge che NON fanno parte di un contorno e vanno esclusi dal
grafo prima della ricerca dei loop.

Non è classificazione di feature: qui non si decide che un edge "è una piega".
Si decide solo, per topologia, che un edge non chiude contorno — tipicamente
una linea che attraversa il pezzo da parte a parte (spesso una linea di piega,
ma anche un asse, una mezzeria, una tracciatura passante). La semantica vera
sta in un consumatore (snapbend `detect_flat`), che li ripesca dalla trash.

Un edge è escluso se:
  1. Entrambi gli endpoint sono nodi branching nel grafo (degree > 2)
  2. Non confina con la faccia esterna della SUA componente connessa da un
     lato solo: il bordo di quella faccia non lo percorre, o lo percorre
     andata e ritorno (MAP.md D111, riapre D49)

Il criterio 2 è topologico: un lato vero di contorno ha il materiale da una
parte e l'esterno dall'altra, una corda ha una faccia chiusa da tutti e due
i lati. Vale per un pezzo concavo come per uno convesso (il convex hull di
D49 scartava i lati della parte concava quando una piega finiva nei loro due
vertici), e per componente: un foglio con più viste non mescola le forme.
Da dove viene l'edge nel formato sorgente non è mai un criterio.

La faccia esterna si percorre sulla rete piana (`split_at_crossings`, la
stessa di island(), D101): due lati che nel file si incrociano senza un
nodo — una tacca coi fianchi accavallati di un decimo — ingannerebbero il
percorso, che passerebbe sull'incrocio. Un edge è sul bordo se lo sono
pezzi suoi per più di metà della lunghezza. I tagli entro `tolerance` sono un contatto solo: una corda
che arriva nel nodo arrotondato di fine raccordo non apre una faccia di
qualche centesimo.

Input:  Graph, list[Edge]
Output: set[int]  — id() degli Edge da escludere dal grafo dei contorni
"""

from .graph import Graph, build_node_graph
from .edge import Edge
from .noding import GRAPH_EPSILON, edge_geometry, split_at_crossings
from .outer_face import outer_face_passes


class NonContourEdgeDetector:

    def __init__(self, tolerance: float = 0.1):
        self.tolerance = tolerance

    def detect(self, graph: Graph, edges: list[Edge]) -> set[int]:
        branching = set(graph.branching_nodes())
        if not branching:
            return set()
        candidates = [e for e in edges
                      if graph.canonical(e.start) in branching and graph.canonical(e.end) in branching]
        if not candidates:
            return set()

        noded = split_at_crossings(edges, self.tolerance)
        plane = build_node_graph(noded.pieces, epsilon=GRAPH_EPSILON)
        wanted = {id(e) for e in candidates}
        outside = {}   # id(edge) -> lunghezza dei suoi pezzi che confinano con l'esterno
        # un percorso della faccia esterna per ogni componente che ha candidati
        for component in plane.connected_components():
            pieces = {id(p): p for node in component for p, _ in plane[node]}
            if not {id(noded.parent_of(p)) for p in pieces.values()} & wanted:
                continue
            passes = outer_face_passes(plane, component, len(noded.pieces))
            for key, piece in pieces.items():
                if passes.get(key, 0) == 1:
                    parent = id(noded.parent_of(piece))
                    outside[parent] = outside.get(parent, 0.0) + edge_geometry(piece).length
        # bordo = confina con l'esterno per più di metà della sua lunghezza: un
        # lato vero lo fa per intero, una corda al più per un tratto sfiorato
        # (quasi tangente a un raccordo, sotto la tolleranza di spessore)
        return {id(e) for e in candidates if outside.get(id(e), 0.0) <= edge_geometry(e).length / 2}