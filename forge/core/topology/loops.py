# from shapely.geometry import Point, Polygon, LineString, LinearRing
# from shapely.ops import unary_union, snap, polygonize

# from .graph import _first_coord, _arrival_direction, _angular_deviation, _edge_coords, round_point, _prune_dead_ends
# from ..primitives.virtual import VirtualShape
# from ...adapters.dxf.virtual_adapter import _loop_to_contour
# from ...adapters.dxf.geometry_adapter import arc_to_linestrings
# from ...adapters.dxf.geometry_adapter import arc_to_bulge, entity_midpoint, spline_to_points
# from ...adapters.dxf.virtual_adapter import DxfWriteContext

# from ...rules.layers import (
#     LAYER_OUTER, LAYER_INNER,
#     COLOR_OUTER, COLOR_INNER,
# )

# def find_closed_loops(graph: dict) -> list:
#     pruned        = _prune_dead_ends(graph)
#     branching     = {n for n, conn in pruned.items() if len(conn) > 2}
#     visited_edges = set()
#     loops         = []

#     for start_node in pruned:
#         for (edge, next_node) in pruned[start_node]:
#             if id(edge) in visited_edges:
#                 continue

#             first_pt    = _first_coord(edge)
#             is_reversed = (first_pt != start_node) if first_pt else False

#             chain = [(edge, is_reversed)]
#             visited_edges.add(id(edge))
#             current_node = next_node

#             while current_node != start_node:
#                 candidates = [
#                     (e, n) for (e, n) in pruned[current_node]
#                     if id(e) not in visited_edges
#                 ]
#                 if not candidates:
#                     break

#                 if current_node in branching and len(candidates) > 1:
#                     prev_edge, prev_rev = chain[-1]
#                     arrival = _arrival_direction(prev_edge, prev_rev)

#                     def _score(candidate):
#                         e, n = candidate
#                         first = _first_coord(e)
#                         rev   = (first != current_node) if first else False
#                         return _angular_deviation(arrival, e, rev)

#                     next_edge, current_node = min(candidates, key=_score)
#                 else:
#                     next_edge, current_node = candidates[0]

#                 visited_edges.add(id(next_edge))

#                 prev_edge, prev_rev = chain[-1]
#                 prev_pts    = _edge_coords(prev_edge, prev_rev)
#                 arrive_from = round_point(prev_pts[-1]) if prev_pts else None

#                 next_first  = _first_coord(next_edge)
#                 ne_reversed = (next_first != arrive_from) if (arrive_from and next_first) else False
#                 chain.append((next_edge, ne_reversed))

#             if current_node != start_node:
#                 continue

#             pts = loop_to_points(chain)
#             if len(pts) >= 3:
#                 try:
#                     if not LinearRing(pts).is_ccw:
#                         chain = [(e, not rev) for e, rev in reversed(chain)]
#                 except Exception:
#                     pass

#             loops.append(chain)

#     return loops

# # ---------------------------------------------------------------------------
# # Classificazione loop
# # ---------------------------------------------------------------------------

# def classify_loops(loops: list):
#     shapely_polygons = []
#     for loop in loops:
#         pts = loop_to_points(loop)
#         shapely_polygons.append(Polygon(pts) if len(pts) >= 3 else None)

#     outer, inners = [], []
#     for i, (loop, poly) in enumerate(zip(loops, shapely_polygons)):
#         if poly is None or not poly.is_valid:
#             outer.append(loop)
#             continue
#         is_inner = any(
#             j != i
#             and shapely_polygons[j] is not None
#             and shapely_polygons[j].contains(poly)
#             for j in range(len(shapely_polygons))
#         )
#         inners.append(loop) if is_inner else outer.append(loop)

#     return outer, inners


# def _collect_loops(self, graph):
#     branching_nodes = [n for n, conn in graph.items() if len(conn) > 2]
#     if branching_nodes:
#         self.result.warnings.append(
#             f"Geometria ambigua: {len(branching_nodes)} nodi con più di 2 "
#             f"connessioni. Il risultato potrebbe essere impreciso."
#         )
#     loops = find_closed_loops(graph)

#     all_loop_ids = {id(edge.entity) for loop in loops for edge, _ in loop}
#     seen_ids = set()
#     for node, neighbors in graph.items():
#         for edge, _ in neighbors:
#             if id(edge.entity) not in all_loop_ids and id(edge.entity) not in seen_ids:
#                 seen_ids.add(id(edge.entity))
#                 e = edge.entity
#                 if e.dxftype() == "LINE":
#                     coords = f"({e.dxf.start.x:.1f},{e.dxf.start.y:.1f})->({e.dxf.end.x:.1f},{e.dxf.end.y:.1f})"
#                 elif e.dxftype() == "ARC":
#                     coords = f"center=({e.dxf.center.x:.1f},{e.dxf.center.y:.1f}) r={e.dxf.radius:.1f}"
#                 else:
#                     coords = ""


#     for i, loop in enumerate(loops):
#         # print(f"  [LOOP {i}] entità: {len(loop)}")
#         for edge, rev in loop:
#             e = edge.entity
#             # print(f"    {e.dxftype()} layer={e.dxf.layer} rev={rev}")

#     return _deduplicate_loops(loops)

# # ---------------------------------------------------------------------------
# # Utility
# # ---------------------------------------------------------------------------

# def loop_to_points(loop: list) -> list:
#     """
#     Converte un loop in lista di punti (x, y).
#     Legge da edge.geometry — nessun accesso a entity.dxf.
#     Il primo punto di ogni edge viene preso per evitare duplicati
#     (l'ultimo di un edge coincide con il primo del successivo).
#     """
#     pts = []
#     for edge, rev in loop:
#         coords = _edge_coords(edge, rev)
#         if coords:
#             pts.append(coords[0])
#     return pts


# def check_loop_ambiguity(loops: list, graph: dict) -> list:
#     loop_edge_ids = {id(edge) for loop in loops for edge, _ in loop}
#     branching = []
#     for node, connections in graph.items():
#         loop_connections = [
#             (edge, n) for (edge, n) in connections
#             if id(edge) in loop_edge_ids
#         ]
#         if len(loop_connections) > 2:
#             branching.append(node)
#     return branching


# def _reintegrate_bending(self):
#     all_lines_full = list(self.msp.query("LINE"))
#     self.all_lines = self.all_lines + [
#         l for l in all_lines_full if id(l) in self.candidate_bending_ids
#     ]


# def _fallback_polygonize(self):
#     self.result.warnings.append("Nessun loop trovato via grafo, uso polygonize come fallback.")
#     segments = []
#     for l in self.all_lines:
#         segments.append(LineString([
#             (l.dxf.start.x, l.dxf.start.y),
#             (l.dxf.end.x,   l.dxf.end.y),
#         ]))
#     for a in self.all_arcs:
#         segments.extend(arc_to_linestrings(a))
#     merged   = unary_union(segments)
#     snapped  = snap(merged, merged, self.tolerance)
#     polygons = list(polygonize(snapped))
#     if polygons:
#         self.result.warnings.append(
#             f"Geometria ricostruita via fallback polygonize "
#             f"({len(polygons)} poligoni). Verificare il risultato."
#         )
#         self.entities_in_loops = {id(e) for e in self.all_lines + self.all_arcs}
#         self.result._entities_in_loops_ids = self.entities_in_loops
#         for poly in polygons:
#             if not poly.is_valid:
#                 poly = poly.buffer(0)
#             pts = [(x, y, 0.0, 0.0, 0.0) for x, y in poly.exterior.coords]
#             vs = VirtualShape(polygon=poly, layer=LAYER_OUTER, color=COLOR_OUTER)
#             self.result._virtual_shapes.append(DxfWriteContext(vs=vs, pts_with_bulge=pts, loop=[]))
#             for interior in poly.interiors:
#                 pts_i = [(x, y, 0.0, 0.0, 0.0) for x, y in interior.coords]
#                 vs_i = VirtualShape(polygon=Polygon(interior), layer=LAYER_INNER, color=COLOR_INNER)
#                 self.result._virtual_shapes.append(DxfWriteContext(vs=vs_i, pts_with_bulge=pts_i, loop=[]))

#     else:
#         self.result.warnings.append(
#             "LINE/ARC non formano loop chiusi — "
#             "potrebbero essere marcature o geometria aperta."
#         )


# def _classify_and_build(self, loops, graph):
#     branching_check = check_loop_ambiguity(loops, graph)
#     if branching_check:
#         self.result.warnings.append(
#             f"Geometria ambigua: {len(branching_check)} nodi con più di 2 "
#             f"connessioni all'interno dei loop chiusi. Verificare il risultato."
#         )

#     outer_loops, inner_loops = classify_loops(loops)
#     self.entities_in_loops = {
#         id(edge.entity) for loop in (outer_loops + inner_loops) for edge, _ in loop
#     }
#     self.result._entities_in_loops_ids = self.entities_in_loops

#     # for loop in outer_loops:
#     #     vs = _loop_to_virtual_shape(loop, LAYER_OUTER, COLOR_OUTER)
#     #     if vs is not None:
#     #         self.result._virtual_shapes.append(vs)
#     # for loop in inner_loops:
#     #     vs = _loop_to_virtual_shape(loop, LAYER_INNER, COLOR_INNER)
#     #     if vs is not None:
#     #         self.result._virtual_shapes.append(vs)
#     # _classify_and_build — già corretto, _loop_to_virtual_shape restituisce DxfWriteContext
#     for loop in outer_loops:
#         ctx = _loop_to_contour(loop, LAYER_OUTER, COLOR_OUTER)
#         if ctx is not None:
#             self.result._virtual_shapes.append(ctx)
#     for loop in inner_loops:
#         ctx = _loop_to_contour(loop, LAYER_INNER, COLOR_INNER)
#         if ctx is not None:
#             self.result._virtual_shapes.append(ctx)


# def _deduplicate_loops(loops):
#     """Per ogni coppia diretta/inversa, tieni solo quella con area maggiore."""
    
#     seen = {}  # frozenset(id) -> (loop, area)
#     for loop in loops:
#         key = frozenset(id(edge.entity) for edge, _ in loop)
#         pts = []
#         for edge, rev in loop:
#             entity = edge.entity
#             if entity.dxftype() == 'LINE':
#                 pts.append(
#                     (entity.dxf.end.x, entity.dxf.end.y) if rev
#                     else (entity.dxf.start.x, entity.dxf.start.y)
#                 )
#             elif entity.dxftype() == 'ARC':
#                 entry_pt, _, _ = arc_to_bulge(entity, reversed=rev)
#                 pts.append(entry_pt)
#             elif entity.dxftype() == 'SPLINE':
#                 spline_pts = spline_to_points(entity)
#                 if rev:
#                     spline_pts = list(reversed(spline_pts))
#                 pts.extend(spline_pts)
#         poly = Polygon(pts) if len(pts) >= 3 else None
#         area = poly.area if poly and poly.is_valid else 0.0
#         if key not in seen or area > seen[key][1]:
#             seen[key] = (loop, area)
#     return [loop for loop, _ in seen.values()]

# def _filter_spurious_loops(loops):
#     """
#     Scarta i loop in cui almeno un'entità ha il midpoint fuori dal poligono
#     formato dal loop stesso.
#     """
#     valid, spurious = [], []

#     for loop in loops:
#         pts = loop_to_points(loop)
#         if len(pts) < 3:
#             spurious.append(loop)
#             continue

#         try:
#             poly = Polygon(pts)
#             if not poly.is_valid:
#                 poly = poly.buffer(0)
#         except Exception:
#             valid.append(loop)
#             continue

#         is_spurious = False
#         for edge, _ in loop:
#             entity = edge.entity
#             mid = entity_midpoint(entity)
#             if mid is None:
#                 continue
#             pt = Point(mid)
#             dist = poly.exterior.distance(pt)
#             inside = poly.contains(pt)
#             print(f"    [DEBUG] {entity.dxftype()} mid={mid} inside={inside} dist_border={dist:.4f}")

#             if not poly.contains(pt) and poly.exterior.distance(pt) > 1e-3:
#                 is_spurious = True
#                 break

#         (spurious if is_spurious else valid).append(loop)

#     return valid, spurious



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
        key = frozenset(id(edge.entity) for edge, _ in loop)
        pts = []
        for edge, rev in loop:
            entity = edge.entity
            if entity.dxftype() == "LINE":
                pts.append(
                    (entity.dxf.end.x, entity.dxf.end.y) if rev
                    else (entity.dxf.start.x, entity.dxf.start.y)
                )
            elif entity.dxftype() == "ARC":
                entry_pt, _, _ = arc_to_bulge(entity, reversed=rev)
                pts.append(entry_pt)
            elif entity.dxftype() == "SPLINE":
                spline_pts = spline_to_points(entity)
                if rev:
                    spline_pts = list(reversed(spline_pts))
                pts.extend(spline_pts)
        poly = Polygon(pts) if len(pts) >= 3 else None
        area = poly.area if poly and poly.is_valid else 0.0
        if key not in seen or area > seen[key][1]:
            seen[key] = (loop, area)
    return [loop for loop, _ in seen.values()]


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
            entity = edge.entity
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