"""
non_contour_edges.py
--------------------
Individua gli edge che NON fanno parte di un contorno e vanno esclusi dal
grafo prima della ricerca dei loop.

Non è classificazione di feature: qui non si decide che un edge "è una piega".
Si decide solo, per topologia, che un edge non chiude contorno — tipicamente
una linea che attraversa il pezzo da parte a parte (spesso una linea di piega,
ma anche un asse, una mezzeria, una tracciatura passante). La semantica vera
sta in `tools/detect._detect_bending`, che li ripesca dalla trash.

Un edge è escluso se:
  1. Entrambi gli endpoint sono nodi branching nel grafo (degree > 2)
  2. Il centroide è interno al convex hull della SUA componente connessa —
     non corre lungo il bordo di quella forma

Nessun'altra condizione: da dove viene l'edge nel formato sorgente (una
LWPOLYLINE già chiusa piuttosto che una LINE sciolta) non è mai un criterio
qui — un lato vero di contorno, comunque tracciato, sta sempre sul bordo del
hull (criterio 2 lo salva da solo); solo una vera diagonale interna ci
finisce dentro, a prescindere da come è stata disegnata.

Il convex hull è per componente connessa, non sull'intero documento: un
foglio con più viste/pezzi indipendenti (nessun edge in comune) userebbe
altrimenti un hull dominato dalla forma più grande, e i lati di contorno
veri di una vista piccola verrebbero scambiati per "interni" solo perché
topologicamente vicini al centro del foglio invece che al centro della loro
stessa forma.

Input:  Graph, list[Edge]
Output: set[int]  — id() degli Edge da escludere dal grafo dei contorni
"""

from shapely.geometry import MultiPoint, Point

from .graph import Graph
from .edge import Edge


class NonContourEdgeDetector:

    def __init__(self, tolerance: float = 0.1):
        self.tolerance = tolerance

    def detect(self, graph: Graph, edges: list[Edge]) -> set[int]:
        branching = set(graph.branching_nodes())
        if not branching:
            return set()

        candidates = [
            e for e in edges
            if e.start in branching and e.end in branching
        ]
        if not candidates:
            return set()

        hull_by_node = {}
        for component in graph.connected_components():
            hull = MultiPoint(list(component)).convex_hull
            for node in component:
                hull_by_node[node] = hull

        excluded = set()

        for edge in candidates:
            hull = hull_by_node.get(edge.start)
            if hull is None:
                continue
            pts = edge.segment.discretize() if edge.segment else [edge.start, edge.end]
            if len(pts) < 2:
                continue
            mid_x = sum(p[0] for p in pts) / len(pts)
            mid_y = sum(p[1] for p in pts) / len(pts)
            centroid = Point(mid_x, mid_y)
            is_interior = hull.boundary.distance(centroid) > self.tolerance
            if is_interior:
                excluded.add(id(edge))

        return excluded