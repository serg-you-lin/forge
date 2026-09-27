"""
core/healing/steps.py
---------------------
I passi di heal(), uno per funzione: edge in, edge o risultato parziale out,
nessuno stato condiviso. heal() li compone nell'ordine di sempre; un
chiamante con un altro disegno in mano (framer) li compone come gli serve.

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Set, Tuple

from ..geometry import node_decimals_for
from ..primitives.segments import SplineSeg
from ..topology.edge import Edge
from ..topology.graph import build_node_graph
from ..topology.non_contour_edges import NonContourEdgeDetector
from ...model.role import ContourRole, is_structural_role
from .gap_solver import free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def split_labeled(edges: List[Edge],
                  is_structural: Optional[Callable[[str], bool]] = None
                  ) -> Tuple[List[Edge], List[Edge]]:
    """
    Separa gli Edge con un ruolo già deciso e non strutturale (cornice,
    marcatura, un manifatturiero non riconosciuto senza predicato — D30):
    ritorna (restano nel grafo, etichettati). Senza `is_structural`, solo
    outer/inner sono strutturali.
    """
    structural = is_structural or is_structural_role
    labeled = [e for e in edges if e.role != ContourRole.UNKNOWN and not structural(e.role)]
    if not labeled:
        return list(edges), []
    labeled_ids = {id(e) for e in labeled}
    return [e for e in edges if id(e) not in labeled_ids], labeled


def close_free_gaps(edges: List[Edge], tolerance: float) -> List[Edge]:
    """
    Chiude i gap fra estremi liberi entro `tolerance` col gap solver
    (estensione all'intersezione reale o linea di congiunzione).
    """
    graph = build_node_graph(edges)
    endpoints = free_endpoints_from_edges(edges, graph)
    if not endpoints:
        return list(edges)
    fixes = compute_gap_fixes(endpoints, tolerance)
    if not fixes:
        return list(edges)
    return apply_gap_fixes(edges, fixes, node_decimals_for(tolerance))


def dangling_splines(edges: List[Edge]) -> List[Edge]:
    """SplineSeg aperte con almeno un estremo non collegato a nient'altro."""
    open_splines = [e for e in edges if isinstance(e.segment, SplineSeg) and e.start != e.end]
    if not open_splines:
        return []
    graph = build_node_graph(edges)
    return [e for e in open_splines if graph.degree(e.start) < 2 or graph.degree(e.end) < 2]


def find_non_contour_edges(edges: List[Edge], tolerance: float) -> Set[int]:
    """
    id(edge) degli Edge che non chiudono un contorno (branching + centroide
    fuori dal convex hull della componente, D49). heal() li tiene fuori dal
    grafo della ricerca loop.
    """
    return NonContourEdgeDetector(tolerance).detect(build_node_graph(edges), edges)
