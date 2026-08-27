"""
loop_finder.py
--------------
Trova i loop chiusi in un grafo topologico.

Loop = list[tuple[Edge, bool]]

I loop degeneri (CIRCLE, SPLINE chiusa) arrivano già pronti in
graph.degenerate_loops — non passano per il walking nel grafo.
"""

import math
from .graph import (
    Graph, 
    _edge_coords, 
    _first_coord, 
    _arrival_direction, 
    _angular_deviation
)
from ..geometry import round_point
from ...adapters.bridge.edge import Edge


class LoopFinder:

    def find(self, graph: Graph, exclude_ids: set[int] | None = None) -> list[list[tuple[Edge, bool]]]:
        """
        Restituisce tutti i loop chiusi.

        Scopo del metodo: individuare la struttura topologica del modello,
        non classificare geometria o containment. La gerarchia spaziale
        (outer/inner/nesting) appartiene a HierarchyBuilder, non a LoopFinder.

        Percorsi:
          graph.degenerate_loops  → aggiunti direttamente come loop da 1 edge
          graph.nodes             → walking topologico standard
        """
        if exclude_ids:
            filtered = Graph(
                nodes={
                    node: [(e, n) for e, n in neighbors if id(e) not in exclude_ids]
                    for node, neighbors in graph.nodes.items()
                },
                degenerate_loops=[
                    e for e in graph.degenerate_loops
                    if id(e) not in exclude_ids
                ],
            )
        else:
            filtered = graph

        pruned    = filtered.pruned()
        branching = set(pruned.branching_nodes())

        visited_edges = set()
        loops = []

        # ── 1. Loop degeneri: CIRCLE, SPLINE chiusa ──────────────────────
        for edge in pruned.degenerate_loops:
            if id(edge) not in visited_edges:
                visited_edges.add(id(edge))
                loops.append([(edge, False)])

        # ── 2. Walking topologico standard ───────────────────────────────
        for start_node in pruned.nodes:
            for (edge, next_node) in pruned.nodes[start_node]:
                if id(edge) in visited_edges:
                    continue

                first_pt    = _first_coord(edge)
                is_reversed = (first_pt != start_node) if first_pt else False

                chain = [(edge, is_reversed)]
                visited_edges.add(id(edge))
                current_node = next_node

                while current_node != start_node:
                    candidates = [
                        (e, n) for (e, n) in pruned.nodes[current_node]
                        if id(e) not in visited_edges
                    ]
                    if not candidates:
                        break

                    if current_node in branching and len(candidates) > 1:
                        prev_edge, prev_rev = chain[-1]
                        arrival = _arrival_direction(prev_edge, prev_rev)

                        def _score(candidate):
                            e, n = candidate
                            first = _first_coord(e)
                            rev = (first != current_node) if first else False
                            return _angular_deviation(arrival, e, rev)

                        next_edge, current_node = min(candidates, key=_score)
                    else:
                        next_edge, current_node = candidates[0]

                    visited_edges.add(id(next_edge))

                    prev_edge, prev_rev = chain[-1]
                    prev_pts   = _edge_coords(prev_edge, prev_rev)
                    arrive_from = round_point(prev_pts[-1]) if prev_pts else None

                    next_first  = _first_coord(next_edge)
                    ne_reversed = (next_first != arrive_from) if (arrive_from and next_first) else False
                    chain.append((next_edge, ne_reversed))

                if current_node != start_node:
                    continue

                pts = self._loop_to_points(chain)
                if len(pts) >= 3:
                    try:
                        from shapely.geometry import LinearRing
                        if not LinearRing(pts).is_ccw:
                            chain = [(e, not rev) for e, rev in reversed(chain)]
                    except Exception:
                        pass
                    loops.append(chain)

        return self._deduplicate_loops(loops)

    # ------------------------------------------------------------------
    # Helper interni
    # ------------------------------------------------------------------

    @staticmethod
    def _loop_to_points(loop: list) -> list:
        pts = []
        for edge, rev in loop:
            coords = _edge_coords(edge, rev)
            if not coords:
                continue
            if not pts:
                pts.extend(coords)
            else:
                if coords[0] == pts[-1]:
                    pts.extend(coords[1:])
                else:
                    pts.extend(coords)
        return pts

    @staticmethod
    def _deduplicate_loops(loops):
        seen = {}
        for loop in loops:
            key = frozenset(id(edge) for edge, _ in loop)
            if key not in seen:
                seen[key] = loop
        return list(seen.values())


# ---------------------------------------------------------------------------
# Edge → OpenShape — tracce non consumate da loop strutturali
# ---------------------------------------------------------------------------

def edges_to_open_shapes(edges: list, exclude_ids: set, label_map: dict) -> list:
    """
    Converte gli Edge non assorbiti da un loop strutturale in OpenShape.

    Opera esclusivamente su Edge (source_ref opaco, layer stringa,
    geometry Shapely) — zero dipendenze da ezdxf o altro formato.
    Sostituisce l'uso di adapter.to_open(): la classificazione geometrica
    (pts/length/role) appartiene al core, non all'adapter.

    Args:
        edges:       lista di Edge prodotta da adapter.to_edges()
        exclude_ids: id(Edge) già assorbiti in loop strutturali
        label_map:   {nome_layer: work_type} — tradotto in ContourRole
    """
    from ...adapters.bridge.shape import OpenShape

    def _length(pts) -> float:
        return sum(
            math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1])
            for i in range(len(pts)-1)
        )

    shapes = []
    for edge in edges:
        if id(edge) in exclude_ids:
            continue
        if edge.start == edge.end:
            continue

        pts = edge.segment.discretize() if edge.segment else [edge.start, edge.end]
        if len(pts) < 2:
            continue

        shape_type = "line" if len(pts) == 2 else "curve"

        shapes.append(OpenShape(
            pts=pts,
            length=_length(pts),
            role=edge.role,
            shape_type=shape_type,
        ))

    return shapes