"""
bending_detector.py
-------------------
Rileva gli edge candidati come linee di piega.

Un edge è confermato bending se:
  1. Non proviene da un percorso già chiuso (closed_path) — quella è
     geometria di contorno per definizione, mai una piega
  2. Entrambi gli endpoint sono nodi branching nel grafo (degree > 2)
  3. Il centroide è interno al convex hull — non è un edge di contorno

Input:  Graph, list[Edge]
Output: set[int]  — id() degli Edge confermati bending
"""

from shapely.geometry import MultiPoint, Point

from .graph import Graph
from .edge import Edge


class BendingDetector:

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
        confirmed = set()

        for edge in candidates:
            pts = edge.segment.discretize() if edge.segment else [edge.start, edge.end]
            if len(pts) < 2:
                continue
            mid_x = sum(p[0] for p in pts) / len(pts)
            mid_y = sum(p[1] for p in pts) / len(pts)
            centroid = Point(mid_x, mid_y)
            is_interior = hull.boundary.distance(centroid) > self.tolerance
            if is_interior:
                confirmed.add(id(edge))

        return confirmed