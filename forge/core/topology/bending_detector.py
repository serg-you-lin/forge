# forge/core/healing/bending_detector.py

"""
bending_detector.py
-------------------
Rileva gli edge candidati come linee di piega.

Un edge è confermato bending se:
  1. Entrambi gli endpoint sono nodi branching nel grafo (degree > 2)
  2. Il centroide è interno al convex hull — non è un edge di contorno

Input:  Graph, list[Edge]
Output: set[int]  — id() degli edge confermati bending
"""

from shapely.geometry import MultiPoint, LineString

from .graph import Graph
from ...bridge.edge import Edge


class BendingDetector:

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

        hull = MultiPoint(list(graph.nodes.keys())).convex_hull
        confirmed = set()

        for edge in candidates:
            if edge.geometry is None:
                continue
            centroid = edge.geometry.centroid
            is_interior = hull.boundary.distance(centroid) > self.tolerance
            if is_interior:
                confirmed.add(id(edge.source_ref))

        return confirmed