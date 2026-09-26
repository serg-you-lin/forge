"""
core/healing/islands.py
-----------------------
Partizione spaziale degli Edge in isole: due edge stanno nella stessa isola
se la distanza vera fra i loro segmenti è al massimo `gap_tolerance` (a
catena). Nessuna nozione di nodo, grafo o chiusura — solo vicinanza, quindi
non eredita l'ambiguità della connettività che rompe il grafo sulle viste
proiettate.

Distanza vera, non fra bbox: la bbox di una diagonale lunga (vista
isometrica) copre un rettangolo vuoto che tocca le viste accanto.

Un'isola è una vista o un pezzo candidato: quale delle due lo decide il
chiamante. Anche `gap_tolerance` è del chiamante: dipende da come è
impaginato il disegno, non dalla geometria. Un foro lontano dai lati resta
un'isola a sé: che stia DENTRO un'altra lo dice solo il contorno esterno,
non la vicinanza.

Puro: solo Edge e primitive, nessun formato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Tuple

from shapely import STRtree
from shapely.geometry import LineString, Point

from ..topology.edge import Edge
from ..primitives.segments import DEFAULT_TOLERANCE

BBox = Tuple[float, float, float, float]   # xmin, ymin, xmax, ymax


@dataclass
class Island:
    """Gruppo di Edge vicini, con la bbox che li contiene tutti."""
    edges:  List[Edge]   = field(default_factory=list)   # ordine di input
    bbox:   BBox         = (0.0, 0.0, 0.0, 0.0)

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def spatial_islands(edges: Iterable[Edge], gap_tolerance: float) -> List[Island]:
    """
    Union-find sulle coppie di Edge a distanza <= gap_tolerance (STRtree,
    predicato `dwithin`, sui segmenti discretizzati). Isole ordinate per area
    di bbox, decrescente.
    """
    edges = list(edges)
    if not edges:
        return []

    geoms = [_geometry(e) for e in edges]
    parent = list(range(len(edges)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    tree = STRtree(geoms)
    left, right = tree.query(geoms, predicate="dwithin", distance=gap_tolerance)
    for i, j in zip(left.tolist(), right.tolist()):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    groups: dict = {}
    for i in range(len(edges)):
        groups.setdefault(find(i), []).append(i)

    islands = []
    for members in groups.values():
        bounds = [geoms[i].bounds for i in members]
        islands.append(Island(
            edges=[edges[i] for i in members],
            bbox=(min(b[0] for b in bounds), min(b[1] for b in bounds),
                  max(b[2] for b in bounds), max(b[3] for b in bounds)),
        ))
    islands.sort(key=lambda isl: isl.width * isl.height, reverse=True)
    return islands


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _geometry(edge: Edge):
    pts = edge.segment.discretize(DEFAULT_TOLERANCE)
    if len(pts) < 2 or all(p == pts[0] for p in pts):
        return Point(pts[0])
    return LineString(pts)
