# forge/core/topology/loop_finder.py

"""
loop_finder.py
--------------
Trova i loop chiusi in un grafo topologico.

Loop = list[tuple[Edge, bool]]

I loop degeneri (CIRCLE, SPLINE chiusa) arrivano già pronti in
graph.degenerate_loops — non passano per il walking nel grafo.
"""

import math
from .graph import Graph
from ...model.edge import Edge


class LoopFinder:

    def find(self, graph: Graph, exclude_ids: set[int] | None = None) -> list[list[tuple[Edge, bool]]]:
        """
        Restituisce tutti i loop chiusi.

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
        # Ogni edge con start == end è già un contorno completo.
        # Non ha senso fare walking — vengono aggiunti direttamente.
        for edge in pruned.degenerate_loops:
            if id(edge) not in visited_edges:
                visited_edges.add(id(edge))
                loops.append([(edge, False)])

        # ── 2. Walking topologico standard ───────────────────────────────
        for start_node in pruned.nodes:
            for (edge, next_node) in pruned.nodes[start_node]:
                if id(edge) in visited_edges:
                    continue

                first_pt    = self._first_coord(edge)
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
                        arrival = self._arrival_direction(prev_edge, prev_rev)

                        def _score(candidate):
                            e, n = candidate
                            first = self._first_coord(e)
                            rev = (first != current_node) if first else False
                            return self._angular_deviation(arrival, e, rev)

                        next_edge, current_node = min(candidates, key=_score)
                    else:
                        next_edge, current_node = candidates[0]

                    visited_edges.add(id(next_edge))

                    prev_edge, prev_rev = chain[-1]
                    prev_pts   = self._edge_coords(prev_edge, prev_rev)
                    arrive_from = self._round_point(prev_pts[-1]) if prev_pts else None

                    next_first  = self._first_coord(next_edge)
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
    def _round_point(pt):
        from ..geometry import round_point as rp
        return rp(pt)

    @staticmethod
    def _first_coord(edge: Edge):
        if edge.geometry is not None:
            coords = list(edge.geometry.coords)
            if coords:
                return LoopFinder._round_point(coords[0])
        return LoopFinder._round_point(edge.start)

    @staticmethod
    def _edge_coords(edge: Edge, reversed_flag: bool) -> list:
        if edge.geometry is None:
            pts = [edge.start, edge.end]
        else:
            pts = list(edge.geometry.coords)
        if reversed_flag:
            pts = list(reversed(pts))
        return pts

    @staticmethod
    def _arrival_direction(edge: Edge, rev: bool):
        coords = LoopFinder._edge_coords(edge, rev)
        if len(coords) < 2:
            return None
        dx = coords[-1][0] - coords[-2][0]
        dy = coords[-1][1] - coords[-2][1]
        return (dx, dy)

    @staticmethod
    def _angular_deviation(arrival_dir, edge: Edge, rev: bool):
        if arrival_dir is None:
            return 0.0
        coords = LoopFinder._edge_coords(edge, rev)
        if len(coords) < 2:
            return 0.0
        dx = coords[1][0] - coords[0][0]
        dy = coords[1][1] - coords[0][1]
        cross = arrival_dir[0] * dy - arrival_dir[1] * dx
        dot   = arrival_dir[0] * dx + arrival_dir[1] * dy
        return abs(math.atan2(cross, dot))

    @staticmethod
    def _loop_to_points(loop: list) -> list:
        pts = []
        for edge, rev in loop:
            coords = LoopFinder._edge_coords(edge, rev)
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
            key = frozenset(
                id(edge.source_ref) if edge.source_ref is not None else id(edge)
                for edge, _ in loop
            )
            if key not in seen:
                seen[key] = loop
        return list(seen.values())


# ---------------------------------------------------------------------------
# Funzioni di utilità: classificazione e controllo ambiguità
# ---------------------------------------------------------------------------

def classify_loops(loops: list) -> tuple:
    shapely_polygons = []
    for loop in loops:
        pts = LoopFinder._loop_to_points(loop)
        if len(pts) >= 3:
            try:
                from shapely.geometry import Polygon
                poly = Polygon(pts)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                shapely_polygons.append(poly)
            except Exception:
                shapely_polygons.append(None)
        else:
            # loop degenere — costruiamo il polygon dalla geometry dell'edge
            edge = loop[0][0]
            try:
                from shapely.geometry import Polygon
                if edge.geometry is not None:
                    coords = list(edge.geometry.coords)
                    poly = Polygon(coords)
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    shapely_polygons.append(poly if not poly.is_empty else None)
                else:
                    shapely_polygons.append(None)
            except Exception:
                shapely_polygons.append(None)

    outer, inners = [], []
    for i, (loop, poly) in enumerate(zip(loops, shapely_polygons)):
        if poly is None or not poly.is_valid:
            outer.append(loop)
            continue
        is_inner = any(
            j != i
            and shapely_polygons[j] is not None
            and shapely_polygons[j].is_valid
            and shapely_polygons[j].contains(poly)
            for j in range(len(shapely_polygons))
        )
        if is_inner:
            inners.append(loop)
        else:
            outer.append(loop)

    return outer, inners


def check_loop_ambiguity(loops: list, graph: 'Graph') -> list:
    loop_edge_ids = {id(edge) for loop in loops for edge, _ in loop}
    branching = []
    for node, connections in graph.nodes.items():
        loop_connections = [
            (edge, n) for (edge, n) in connections
            if id(edge) in loop_edge_ids
        ]
        if len(loop_connections) > 2:
            branching.append(node)
    return branching


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
        exclude_ids: id(source_ref) già assorbiti in loop strutturali
        label_map:   {nome_layer: work_type} — tradotto in ContourRole
    """
    from ...model.role import layer_to_role
    from ...model.shape import OpenShape

    shapes = []
    for edge in edges:
        if id(edge.source_ref) in exclude_ids:
            continue
        if edge.start == edge.end:
            # loop degenere (CIRCLE, SPLINE chiusa) — non è una traccia aperta
            continue

        if edge.geometry is not None:
            pts = list(edge.geometry.coords)
            length = edge.geometry.length
        else:
            pts = [edge.start, edge.end]
            length = 0.0

        if len(pts) < 2:
            continue

        # Una traccia "line" è geometricamente un segmento a 2 punti.
        # Archi e spline sono discretizzati con più punti da to_edges().
        shape_type = "line" if len(pts) == 2 else "curve"

        shapes.append(OpenShape(
            pts=pts,
            length=length,
            source_ref=edge.source_ref,
            role=layer_to_role(edge.layer, label_map),
            shape_type=shape_type,
        ))

    return shapes