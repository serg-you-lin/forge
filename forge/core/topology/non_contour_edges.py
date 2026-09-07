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
  1. Non proviene da un percorso già chiuso (closed_path) — quello è
     contorno per definizione
  2. Entrambi gli endpoint sono nodi branching nel grafo (degree > 2)
  3. Il centroide è interno al convex hull — non corre lungo il bordo

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
            if not getattr(e, "closed_path", False)
            if e.start in branching and e.end in branching
        ]
        if not candidates:
            return set()

        hull = MultiPoint(list(graph.nodes.keys())).convex_hull
        excluded = set()

        for edge in candidates:
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