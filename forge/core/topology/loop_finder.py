# forge/core/topology/loop_finder.py

"""
loop_finder.py
--------------
Trova i loop chiusi in un grafo topologico.

Loop = list[tuple[Edge, bool]]
"""

import math
from .graph import Graph
from ...model.edge import Edge


class LoopFinder:

    def find(self, graph: Graph, exclude_ids: set[int] | None = None) -> list[list[tuple[Edge, bool]]]:
        """
        Restituisce i loop chiusi, escludendo gli edge con id in `exclude_ids`.
        """
        # Se ci sono edge da escludere, filtriamo il grafo
        if exclude_ids:
            filtered = Graph(nodes={
                node: [(e, n) for e, n in neighbors if id(e) not in exclude_ids]
                for node, neighbors in graph.nodes.items()
            })
        else:
            filtered = graph

        # 1. Potatura dei dead-end (ora Graph ha il metodo pruned())
        pruned = filtered.pruned()

        # 2. Nodi branching (ci servono dopo per scegliere il percorso)
        branching = set(pruned.branching_nodes())

        visited_edges = set()
        loops = []

        # 3. Ricerca dei loop (identica alla tua vecchia logica, ma usa pruned.nodes)
        for start_node in pruned.nodes:
            for (edge, next_node) in pruned.nodes[start_node]:
                if id(edge) in visited_edges:
                    continue

                # Determina se l'edge è già al contrario
                first_pt = self._first_coord(edge)
                is_reversed = (first_pt != start_node) if first_pt else False

                chain = [(edge, is_reversed)]
                visited_edges.add(id(edge))
                current_node = next_node

                # Camminiamo finché non torniamo allo start_node
                while current_node != start_node:
                    candidates = [
                        (e, n) for (e, n) in pruned.nodes[current_node]
                        if id(e) not in visited_edges
                    ]
                    if not candidates:
                        break

                    if current_node in branching and len(candidates) > 1:
                        # Scegliamo quello con minima deviazione angolare
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

                    # Determina se il nuovo edge va percorso al contrario
                    prev_edge, prev_rev = chain[-1]
                    prev_pts = self._edge_coords(prev_edge, prev_rev)
                    arrive_from = self._round_point(prev_pts[-1]) if prev_pts else None

                    next_first = self._first_coord(next_edge)
                    ne_reversed = (next_first != arrive_from) if (arrive_from and next_first) else False
                    chain.append((next_edge, ne_reversed))

                # Se non siamo tornati allo start_node, scartiamo la catena
                if current_node != start_node:
                    continue

                # 4. Ordiniamo il loop in senso antiorario
                pts = self._loop_to_points(chain)
                if len(pts) >= 3:
                    try:
                        from shapely.geometry import LinearRing
                        if not LinearRing(pts).is_ccw:
                            chain = [(e, not rev) for e, rev in reversed(chain)]
                    except Exception:
                        pass

                loops.append(chain)

        # 5. Deduplica
        return self._deduplicate_loops(loops)

    # ------------------------------------------------------------------
    # Helper interni (uguali a quelli che avevi già)
    # ------------------------------------------------------------------

    @staticmethod
    def _round_point(pt):
        """Arrotonda a 6 decimali (o secondo il tuo modulo geometry)."""
        from ..geometry import round_point as rp
        return rp(pt)

    @staticmethod
    def _first_coord(edge: Edge):
        """Primo punto della geometria (o start)."""
        if edge.geometry is not None:
            coords = list(edge.geometry.coords)
            if coords:
                return LoopFinder._round_point(coords[0])
        return LoopFinder._round_point(edge.start)

    @staticmethod
    def _edge_coords(edge: Edge, reversed_flag: bool) -> list:
        """Restituisce la lista di punti dell'edge, eventualmente invertita."""
        if edge.geometry is None:
            pts = [edge.start, edge.end]
        else:
            pts = list(edge.geometry.coords)
        if reversed_flag:
            pts = list(reversed(pts))
        return pts

    @staticmethod
    def _arrival_direction(edge: Edge, rev: bool):
        """Vettore di arrivo (ultimo segmento) dell'edge percorso in direzione rev."""
        coords = LoopFinder._edge_coords(edge, rev)
        if len(coords) < 2:
            return None
        dx = coords[-1][0] - coords[-2][0]
        dy = coords[-1][1] - coords[-2][1]
        return (dx, dy)

    @staticmethod
    def _angular_deviation(arrival_dir, edge: Edge, rev: bool):
        """Deviazione angolare tra arrival_dir e la direzione di partenza di edge."""
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
        """Converte un Loop in una lista di (x, y) per costruire un anello."""
        pts = []
        for edge, rev in loop:
            coords = LoopFinder._edge_coords(edge, rev)
            if coords:
                pts.append(coords[0])
        return pts

    @staticmethod
    def _deduplicate_loops(loops):
        """Elimina i loop duplicati (stesso insieme di edge di origine)."""
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
# (verranno migrate in LoopClassifier nello Step 5)
# ---------------------------------------------------------------------------

def classify_loops(loops: list) -> tuple:
    """
    Classifica i loop in outer e inner in base alla relazione
    di contenimento dei loro poligoni.
    """
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
            shapely_polygons.append(None)

    outer, inners = [], []
    for i, (loop, poly) in enumerate(zip(loops, shapely_polygons)):
        if poly is None or not poly.is_valid:
            outer.append(loop)
            continue
        # un loop è inner se è contenuto in ALMENO un altro poligono (non se stesso)
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
    """
    Verifica se ci sono nodi con più di 2 connessioni
    all'interno degli edge che fanno parte dei loop.
    Restituisce la lista di tali nodi (branching anomali).
    """
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