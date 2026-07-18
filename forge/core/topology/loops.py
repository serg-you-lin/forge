

from shapely.geometry import Point, Polygon, LineString, LinearRing
from shapely.ops import unary_union, snap, polygonize

from .graph import (
    _first_coord, _arrival_direction, _angular_deviation,
    _edge_coords, round_point, _prune_dead_ends,
)
from ...adapters.dxf.geometry_adapter import (
    arc_to_linestrings, arc_to_bulge, entity_midpoint, spline_to_points,
)


def _collect_loops(self, graph):

    branching_nodes = [n for n, conn in graph.items() if len(conn) > 2]
    if branching_nodes:
        self.result.warnings.append(
            f"Geometria ambigua: {len(branching_nodes)} nodi con più di 2 "
            f"connessioni. Il risultato potrebbe essere impreciso."
        )

    loops = find_closed_loops(graph)
    return _deduplicate_loops(loops)


def find_closed_loops(graph: dict) -> list:
    pruned        = _prune_dead_ends(graph)
    branching     = {n for n, conn in pruned.items() if len(conn) > 2}
    visited_edges = set()
    loops         = []

    for start_node in pruned:
        for (edge, next_node) in pruned[start_node]:
            if id(edge) in visited_edges:
                continue

            first_pt    = _first_coord(edge)
            is_reversed = (first_pt != start_node) if first_pt else False

            chain = [(edge, is_reversed)]
            visited_edges.add(id(edge))
            current_node = next_node

            while current_node != start_node:
                candidates = [
                    (e, n) for (e, n) in pruned[current_node]
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
                        rev   = (first != current_node) if first else False
                        return _angular_deviation(arrival, e, rev)

                    next_edge, current_node = min(candidates, key=_score)
                else:
                    next_edge, current_node = candidates[0]

                visited_edges.add(id(next_edge))

                prev_edge, prev_rev = chain[-1]
                prev_pts    = _edge_coords(prev_edge, prev_rev)
                arrive_from = round_point(prev_pts[-1]) if prev_pts else None

                next_first  = _first_coord(next_edge)
                ne_reversed = (next_first != arrive_from) if (arrive_from and next_first) else False
                chain.append((next_edge, ne_reversed))

            if current_node != start_node:
                continue

            pts = loop_to_points(chain)
            if len(pts) >= 3:
                try:
                    if not LinearRing(pts).is_ccw:
                        chain = [(e, not rev) for e, rev in reversed(chain)]
                except Exception:
                    pass

            loops.append(chain)

    return loops


def classify_loops(loops: list):
    shapely_polygons = []
    for loop in loops:
        pts = loop_to_points(loop)
        shapely_polygons.append(Polygon(pts) if len(pts) >= 3 else None)

    outer, inners = [], []
    for i, (loop, poly) in enumerate(zip(loops, shapely_polygons)):
        if poly is None or not poly.is_valid:
            outer.append(loop)
            continue
        is_inner = any(
            j != i
            and shapely_polygons[j] is not None
            and shapely_polygons[j].contains(poly)
            for j in range(len(shapely_polygons))
        )
        inners.append(loop) if is_inner else outer.append(loop)

    return outer, inners


def loop_to_points(loop: list) -> list:
    pts = []
    for edge, rev in loop:
        coords = _edge_coords(edge, rev)
        if coords:
            pts.append(coords[0])
    return pts


def check_loop_ambiguity(loops: list, graph: dict) -> list:
    loop_edge_ids = {id(edge) for loop in loops for edge, _ in loop}
    branching = []
    for node, connections in graph.items():
        loop_connections = [
            (edge, n) for (edge, n) in connections
            if id(edge) in loop_edge_ids
        ]
        if len(loop_connections) > 2:
            branching.append(node)
    return branching


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

def _filter_spurious_loops(loops):
    valid, spurious = [], []

    for loop in loops:
        pts = loop_to_points(loop)
        if len(pts) < 3:
            spurious.append(loop)
            continue

        try:
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
        except Exception:
            valid.append(loop)
            continue

        is_spurious = False
        for edge, _ in loop:
            entity = edge.source_ref
            mid = entity_midpoint(entity)
            if mid is None:
                continue
            pt   = Point(mid)
            dist = poly.exterior.distance(pt)
            inside = poly.contains(pt)
            if not inside and dist > 1e-3:
                is_spurious = True
                break

        (spurious if is_spurious else valid).append(loop)

    return valid, spurious


def _reintegrate_bending(self):
    all_lines_full = list(self.msp.query("LINE"))
    self.all_lines = self.all_lines + [
        l for l in all_lines_full if id(l) in self.candidate_bending_ids
    ]