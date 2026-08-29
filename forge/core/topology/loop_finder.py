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
    _arrival_direction,
    _angular_deviation,
)
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
                node_map=graph.node_map,
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
        # L'identità di un nodo passa sempre da pruned.canonical(): con il
        # grafo clusterizzato l'endpoint arrotondato dell'edge non coincide
        # con la chiave del nodo (che è il rappresentante del cluster).
        for start_node in pruned.nodes:
            for (edge, next_node) in pruned.nodes[start_node]:
                if id(edge) in visited_edges:
                    continue

                is_reversed = pruned.canonical(edge.start) != start_node

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

                    from_node = current_node

                    if current_node in branching and len(candidates) > 1:
                        prev_edge, prev_rev = chain[-1]
                        arrival = _arrival_direction(prev_edge, prev_rev)

                        def _score(candidate, _from=from_node):
                            e, n = candidate
                            rev = pruned.canonical(e.start) != _from
                            return _angular_deviation(arrival, e, rev)

                        next_edge, current_node = min(candidates, key=_score)
                    else:
                        next_edge, current_node = candidates[0]

                    visited_edges.add(id(next_edge))

                    ne_reversed = pruned.canonical(next_edge.start) != from_node
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
# Loop → segmenti nativi orientati
# ---------------------------------------------------------------------------

def segments_from_loop(loop) -> list:
    """
    Segmenti nativi di un loop, orientati nel verso di percorrenza.

    NON parsa niente: ogni Edge porta già la sua primitiva (`edge.segment`,
    tradotta dall'adapter al load). Qui la si prende, la si inverte con
    `.reversed()` se l'Edge è percorso al contrario nel loop, e la si
    concatena. Logica di dominio pura — nessuna dipendenza da ezdxf.

    (Ex `adapters/dxf/parser.py::parse_loop` — spostata qui e rinominata,
    MAP.md D6: non apparteneva all'adapter e il nome era fuorviante.)
    """
    out = []
    for edge, rev in loop:
        seg = edge.segment
        if seg is None:
            continue
        if isinstance(seg, list):
            # In produzione un Edge di loop non porta mai una lista (le
            # polilinee sono già esplose in Edge singoli): ramo per i test.
            out.extend(seg)
        else:
            out.append(seg.reversed() if rev else seg)
    return out


# ---------------------------------------------------------------------------
# Edge → OpenFeature — tracce non consumate da loop strutturali
# ---------------------------------------------------------------------------

def edges_to_open_features(edges: list, exclude_ids: set, label_map: dict) -> list:
    """
    Converte gli Edge non assorbiti da un loop strutturale in OpenFeature.

    Opera esclusivamente su Edge (role semantico, segmento nativo) —
    zero dipendenze da ezdxf o altro formato.

    L'OpenFeature porta solo `role` + `segments` (primitive native). `pts`,
    `length`, `shape_type` sono valori derivati: chi li consuma (detect,
    write._write_trash, inspect) li ricava dai segmenti con gli helper
    `track_*` di `core.geometry`.

    Args:
        edges:       lista di Edge prodotta da adapter.to_edges()
        exclude_ids: id(Edge) già assorbiti in loop strutturali
        label_map:   {nome_layer: work_type} — tradotto in ContourRole
    """
    from ...model.feature import OpenFeature
    from ...core.primitives.segments import LineSeg
    from ...core.geometry import track_points

    features = []
    for edge in edges:
        if id(edge) in exclude_ids:
            continue
        if edge.start == edge.end:
            continue

        seg = edge.segment or LineSeg(start=edge.start, end=edge.end)
        if len(track_points([seg])) < 2:
            continue

        features.append(OpenFeature(role=edge.role, segments=[seg]))

    return features