# import numpy as np
# from shapely.geometry import Polygon, LineString
# from shapely.ops import unary_union, snap, polygonize

# from ...models import (
#     ForgeResult,
#     ForgePart,
#     ForgeContour,
#     GeometryHints,
#     Edge,
#     Hole,
#     HOLE_TYPE_UNKNOWN,
# )
# from ...core.geometry import (
#     pline_to_polygon,
#     circle_to_polygon,
#     arc_to_linestrings,
# )
# from ...core.graph import (
#     build_node_graph,
#     find_closed_loops,
#     classify_loops,
#     check_loop_ambiguity,
#     _normalized_endpoints,
# )
# from ...core.virtual import (
#     VirtualShape,
#     _loop_to_virtual_shape,
# )
# from ._helpers import (
#     _free_endpoints,
#     _spline_is_closed,
#     _spline_to_polygon,
# )
# from ._utils import (
#     _deduplicate_entities,
#     _deduplicate_loops,
#     _explode_inserts,
#     _filter_spurious_loops,
# )
# from ...core.gap import close_gaps
# from ...core.graph import spline_endpoints
# from ...core.geometry import round_point

# from ...rules.layers import (
#     LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
#     COLOR_OUTER, COLOR_INNER,
#     HOLE_DIAMETER_THRESHOLD, STRUCTURAL_LAYERS,
# )


# class HealerPipeline:
#     def __init__(
#         self,
#         msp,
#         tolerance,
#         label="",
#         source_file="",
#         explode_inserts=False,
#         ignore_layers=None,
#         special_layers=None,
#     ):
#         self.msp             = msp
#         self.tolerance       = tolerance
#         self.label           = label
#         self.source_file     = source_file
#         self.explode_inserts = explode_inserts
#         self.ignore_layers   = {l.lower() for l in (ignore_layers or [])}
#         # nomi layer (lowercase) da non inghiottire nei loop
#         self.special_layer_names = {k.lower() for k in (special_layers or {})}

#         self.node_decimals = max(round(-np.log10(tolerance * 2)), 1)
#         self.result        = ForgeResult(source_file=source_file)

#         # salva special_layers nel result — detect() lo legge da qui
#         if special_layers:
#             self.result.special_layers = special_layers

#         self.candidate_bending_ids  = set()
#         self.classified_entity_ids  = set()
#         self.classified_virtual_ids = set()
#         self.entities_in_loops      = set()

#         self.all_lines      = []
#         self.all_arcs       = []
#         self.all_plines     = []
#         self.all_circles    = []
#         self.all_splines    = []
#         self.closed_splines = []
#         self.open_splines   = []

#     def run(self):
#         self._handle_inserts()
#         self._load()
#         if not self.result.is_valid:
#             return self.result
#         self._preprocess()
#         self._find_bending_candidates()
#         self._find_loops()
#         self._build_hierarchy()
#         self._build_trash()
#         return self.result


#     def _build_graph(self, exclude_ids=None):
#         edges = self._edges_from_msp(exclude_ids=exclude_ids)
#         return build_node_graph(edges)

#     def _handle_inserts(self):
#         inserts_found = list(self.msp.query("INSERT"))
#         if inserts_found:
#             if self.explode_inserts:
#                 n = _explode_inserts(self.msp)
#                 self.result.warnings.append(f"{n} INSERT esplosi prima dell'healing.")
#             else:
#                 self.result.warnings.append(
#                     f"Trovati {len(inserts_found)} INSERT (blocchi) non esplosi — "
#                     f"usa explode_inserts=True in heal() per includerli."
#                 )

#     def _load(self):
#         removed = _deduplicate_entities(self.msp, tolerance=self.tolerance)
#         if removed > 0:
#             self.result.warnings.append(f"Rimosse {removed} entità duplicate dal msp.")

#         self.all_lines   = list(self.msp.query("LINE"))
#         self.all_arcs    = list(self.msp.query("ARC"))
#         self.all_plines  = list(self.msp.query("LWPOLYLINE POLYLINE"))
#         self.all_circles = list(self.msp.query("CIRCLE"))
#         self.all_splines = list(self.msp.query("SPLINE"))

#         if not any([self.all_lines, self.all_arcs, self.all_plines,
#                     self.all_circles, self.all_splines]):
#             self.result.errors.append("Modelspace vuoto: nessuna geometria trovata.")
#             self.result.is_valid = False
#             return

#         self.closed_splines = [s for s in self.all_splines if     _spline_is_closed(s, self.tolerance)]
#         self.open_splines   = [s for s in self.all_splines if not _spline_is_closed(s, self.tolerance)]

#     def _preprocess(self):
#         if not (self.all_lines or self.all_arcs):
#             return

#         graph_pre = self._build_graph()
#         free = _free_endpoints(graph_pre, self.msp, self.node_decimals)

#         if free:
#             fixed = close_gaps(self.msp, free, self.tolerance)
#             if fixed:
#                 self.all_lines = list(self.msp.query("LINE"))
#                 self.all_arcs  = list(self.msp.query("ARC"))
#                 graph_pre      = None

#         if self.open_splines:
#             if graph_pre is None:
#                 graph_pre = self._build_graph()
#             for spline in self.open_splines:
#                 s, e = spline_endpoints(spline)
#                 if s is None or e is None:
#                     continue
#                 s_r = round_point(s)
#                 e_r = round_point(e)
#                 if len(graph_pre.get(s_r, [])) < 2 or len(graph_pre.get(e_r, [])) < 2:
#                     self.result.warnings.append(
#                         "SPLINE con endpoint non connesso trovata — "
#                         "gap tra SPLINE e altre entità gestito con una linea di congiunzione. "
#                         "Verificare manualmente la correttezza del file."
#                     )
#                     break


#     def _find_bending_candidates(self):
#         if not (self.all_lines or self.all_arcs):
#             return

#         graph_full      = self._build_graph()
#         branching_nodes = {
#             node for node, neighbors in graph_full.items() if len(neighbors) > 2
#         }

#         if not branching_nodes:
#             return

#         for line in self.all_lines:
#             s = round_point((line.dxf.start.x, line.dxf.start.y), self.node_decimals)
#             e = round_point((line.dxf.end.x,   line.dxf.end.y),   self.node_decimals)
#             if s in branching_nodes and e in branching_nodes:
#                 self.candidate_bending_ids.add(id(line))

#         if not self.candidate_bending_ids:
#             return

#         from shapely.geometry import MultiPoint, LineString as SLS
#         hull = MultiPoint(list(graph_full.keys())).convex_hull

#         confirmed_bending_ids = set()
#         for line in self.all_lines:
#             if id(line) not in self.candidate_bending_ids:
#                 continue

#             test_graph = self._build_graph(exclude_ids={id(line)})
#             if not test_graph:
#                 continue
#             start = next(iter(test_graph))
#             visited = {start}
#             queue = [start]
#             while queue:
#                 node = queue.pop()
#                 for _, neighbor in test_graph[node]:
#                     if neighbor not in visited:
#                         visited.add(neighbor)
#                         queue.append(neighbor)
#             is_bridge = len(visited) < len(test_graph)

#             line_geom   = SLS([(line.dxf.start.x, line.dxf.start.y),
#                             (line.dxf.end.x,   line.dxf.end.y)])
#             is_interior = hull.boundary.distance(line_geom.centroid) > self.tolerance

#             if is_interior:
#                 confirmed_bending_ids.add(id(line))

#         self.candidate_bending_ids = confirmed_bending_ids

#         if self.candidate_bending_ids:
#             self.result.warnings.append(
#                 f"{len(self.candidate_bending_ids)} LINE candidate come bending "
#                 f"escluse dal grafo (entrambi gli endpoint su nodi di branching)."
#             )
#             self.all_lines = [l for l in self.all_lines if id(l) not in self.candidate_bending_ids]


#     def _find_loops(self):
#         if not (self.all_lines or self.all_arcs or self.open_splines):
#             return

#         graph = self._build_graph(exclude_ids=self.candidate_bending_ids)
#         loops = find_closed_loops(graph)

#         all_loop_ids = {id(edge.entity) for loop in loops for edge, _ in loop}
#         seen_ids = set()
#         for node, neighbors in graph.items():
#             for edge, _ in neighbors:
#                 if id(edge.entity) not in all_loop_ids and id(edge.entity) not in seen_ids:
#                     seen_ids.add(id(edge.entity))
#                     e = edge.entity
#                     if e.dxftype() == "LINE":
#                         coords = f"({e.dxf.start.x:.1f},{e.dxf.start.y:.1f})->({e.dxf.end.x:.1f},{e.dxf.end.y:.1f})"
#                     elif e.dxftype() == "ARC":
#                         coords = f"center=({e.dxf.center.x:.1f},{e.dxf.center.y:.1f}) r={e.dxf.radius:.1f}"
#                     else:
#                         coords = ""
#                     print(f"  [FUORI LOOP] {e.dxftype()} layer={e.dxf.layer} {coords}")

#         print(f"[DEBUG loops] loop trovati da find_closed_loops: {len(loops)}")
#         for i, loop in enumerate(loops):
#             print(f"  [LOOP {i}] entità: {len(loop)}")
#             for edge, rev in loop:
#                 e = edge.entity
#                 print(f"    {e.dxftype()} layer={e.dxf.layer} rev={rev}")

#         loops = _deduplicate_loops(loops)

#         # reintegra le candidate: devono finire in trash per detect()
#         all_lines_full = list(self.msp.query("LINE"))
#         self.all_lines = self.all_lines + [
#             l for l in all_lines_full if id(l) in self.candidate_bending_ids
#         ]

#         if not loops:
#             self.result.warnings.append("Nessun loop trovato via grafo, uso polygonize come fallback.")
#             segments = []
#             for l in self.all_lines:
#                 segments.append(LineString([
#                     (l.dxf.start.x, l.dxf.start.y),
#                     (l.dxf.end.x,   l.dxf.end.y),
#                 ]))
#             for a in self.all_arcs:
#                 segments.extend(arc_to_linestrings(a))
#             merged   = unary_union(segments)
#             snapped  = snap(merged, merged, self.tolerance)
#             polygons = list(polygonize(snapped))
#             if polygons:
#                 self.result.warnings.append(
#                     f"Geometria ricostruita via fallback polygonize "
#                     f"({len(polygons)} poligoni). Verificare il risultato."
#                 )
#                 self.entities_in_loops = {id(e) for e in self.all_lines + self.all_arcs}
#                 self.result._entities_in_loops_ids = self.entities_in_loops
#                 for poly in polygons:
#                     if not poly.is_valid:
#                         poly = poly.buffer(0)
#                     pts = [(x, y, 0.0, 0.0, 0.0) for x, y in poly.exterior.coords]
#                     self.result._virtual_shapes.append(VirtualShape(
#                         pts_with_bulge=pts, polygon=poly,
#                         layer=LAYER_OUTER, color=COLOR_OUTER,
#                     ))
#                     for interior in poly.interiors:
#                         pts_i = [(x, y, 0.0, 0.0, 0.0) for x, y in interior.coords]
#                         self.result._virtual_shapes.append(VirtualShape(
#                             pts_with_bulge=pts_i, polygon=Polygon(interior),
#                             layer=LAYER_INNER, color=COLOR_INNER,
#                         ))
#             else:
#                 self.result.warnings.append(
#                     "LINE/ARC non formano loop chiusi — "
#                     "potrebbero essere marcature o geometria aperta."
#                 )
#             return

#         branching_check = check_loop_ambiguity(loops, graph)
#         if branching_check:
#             self.result.warnings.append(
#                 f"Geometria ambigua: {len(branching_check)} nodi con più di 2 "
#                 f"connessioni all'interno dei loop chiusi. Verificare il risultato."
#             )

#         outer_loops, inner_loops = classify_loops(loops)
#         self.entities_in_loops = {
#             id(edge.entity) for loop in (outer_loops + inner_loops) for edge, _ in loop
#         }
#         self.result._entities_in_loops_ids = self.entities_in_loops

#         for loop in outer_loops:
#             vs = _loop_to_virtual_shape(loop, LAYER_OUTER, COLOR_OUTER)
#             if vs is not None:
#                 self.result._virtual_shapes.append(vs)
#         for loop in inner_loops:
#             vs = _loop_to_virtual_shape(loop, LAYER_INNER, COLOR_INNER)
#             if vs is not None:
#                 self.result._virtual_shapes.append(vs)

#     def _build_hierarchy(self):
#         shapes = []
#         for vs in self.result._virtual_shapes:
#             shapes.append((vs, vs.polygon, "VIRTUAL"))
#         for pline in self.all_plines:
#             poly = pline_to_polygon(pline)
#             if poly:
#                 shapes.append((pline, poly, "LWPOLYLINE"))
#         for circle in self.all_circles:
#             poly = circle_to_polygon(circle)
#             if poly:
#                 shapes.append((circle, poly, "CIRCLE"))
#         for spline in self.closed_splines:
#             poly = _spline_to_polygon(spline)
#             if poly:
#                 shapes.append((spline, poly, "SPLINE"))

#         if not shapes:
#             self.result.errors.append("Nessuna geometria chiusa trovata dopo healing.")
#             self.result.is_valid = False
#             return

#         shapes.sort(key=lambda x: x[1].area, reverse=True)

#         def _place(obj, poly, tipo, nodes):
#             for node in nodes:
#                 if node[1].contains(poly):
#                     if not _place(obj, poly, tipo, node[3]):
#                         node[3].append([obj, poly, tipo, []])
#                     return True
#             return False

#         fathers = []
#         for obj, poly, tipo in shapes:
#             if not _place(obj, poly, tipo, fathers):
#                 fathers.append([obj, poly, tipo, []])

#         for node in fathers:
#             for child in node[3]:
#                 if child[2] == "VIRTUAL":
#                     child[0].layer = LAYER_INNER
#                     child[0].color = COLOR_INNER

#         for father in fathers:
#             father_obj, father_poly, father_tipo, children = father

#             outer = ForgeContour(
#                 polygon=father_poly,
#                 is_inner=False,
#                 layer=LAYER_OUTER,
#                 entity=father_obj if father_tipo != "VIRTUAL" else None,
#             )

#             if father_tipo == "VIRTUAL":
#                 self.classified_virtual_ids.add(id(father_obj))
#             else:
#                 self.classified_entity_ids.add(id(father_obj))

#             holes  = []
#             inners = []

#             for child in children:
#                 child_obj, child_poly, child_tipo, grandchildren = child

#                 if grandchildren:
#                     if child_tipo == "VIRTUAL":
#                         self.classified_virtual_ids.add(id(child_obj))
#                     else:
#                         self.classified_entity_ids.add(id(child_obj))
#                         self.result.trash_entities.append(child_obj)

#                     outer_diameter = child_obj.dxf.radius * 2 if child_tipo == "CIRCLE" else None

#                     for gc in grandchildren:
#                         gc_obj, gc_poly, gc_tipo, _ = gc

#                         if gc_tipo == "CIRCLE":
#                             diameter = gc_obj.dxf.radius * 2
#                             center   = (gc_obj.dxf.center.x, gc_obj.dxf.center.y)
#                             layer    = LAYER_HOLE if diameter < HOLE_DIAMETER_THRESHOLD else LAYER_INNER
#                             holes.append(Hole(
#                                 polygon=gc_poly,
#                                 diameter=diameter,
#                                 center=center,
#                                 hole_type=HOLE_TYPE_UNKNOWN,
#                                 geometric_hint="countersink",
#                                 layer=layer,
#                                 source_layer=(
#                                     gc_obj.source_layer if gc_tipo == "VIRTUAL"
#                                     else gc_obj.dxf.layer if gc_obj.dxf.hasattr("layer")
#                                     else ""
#                                 ),
#                                 entity=gc_obj,
#                                 outer_diameter=outer_diameter,
#                                 outer_entity=child_obj if child_tipo != "VIRTUAL" else None,
#                             ))
#                         else:
#                             inners.append(ForgeContour(
#                                 polygon=gc_poly,
#                                 is_inner=True,
#                                 layer=LAYER_INNER,
#                                 is_hole=False,
#                                 entity=gc_obj if gc_tipo != "VIRTUAL" else None,
#                                 source_layer=(
#                                     gc_obj.source_layer if gc_tipo == "VIRTUAL"
#                                     else gc_obj.dxf.layer if gc_obj.dxf.hasattr("layer")
#                                     else ""
#                                 ),
#                             ))

#                         if gc_tipo == "VIRTUAL":
#                             self.classified_virtual_ids.add(id(gc_obj))
#                         else:
#                             self.classified_entity_ids.add(id(gc_obj))

#                 else:
#                     if child_tipo == "CIRCLE":
#                         diameter = child_obj.dxf.radius * 2
#                         center   = (child_obj.dxf.center.x, child_obj.dxf.center.y)
#                         layer    = LAYER_HOLE if diameter < HOLE_DIAMETER_THRESHOLD else LAYER_INNER
#                         holes.append(Hole(
#                             polygon=child_poly,
#                             diameter=diameter,
#                             center=center,
#                             hole_type=HOLE_TYPE_UNKNOWN,
#                             geometric_hint="",
#                             layer=layer,
#                             source_layer=(
#                                 child_obj.dxf.layer if child_obj.dxf.hasattr("layer") else ""
#                             ),
#                             entity=child_obj,
#                         ))
#                     else:
#                         inners.append(ForgeContour(
#                             polygon=child_poly,
#                             is_inner=True,
#                             layer=LAYER_INNER,
#                             is_hole=False,
#                             entity=child_obj if child_tipo != "VIRTUAL" else None,
#                             source_layer=(
#                                 child_obj.source_layer if child_tipo == "VIRTUAL"
#                                 else child_obj.dxf.layer if child_obj.dxf.hasattr("layer")
#                                 else ""
#                             ),
#                             vs_id=id(child_obj) if child_tipo == "VIRTUAL" else None,
#                         ))

#                     if child_tipo == "VIRTUAL":
#                         self.classified_virtual_ids.add(id(child_obj))
#                     else:
#                         self.classified_entity_ids.add(id(child_obj))

#             entity_ids = set()
#             entity_ids.add(id(father_obj))

#             for child in children:
#                 child_obj, _, child_tipo, grandchildren = child
#                 entity_ids.add(id(child_obj))
#                 for gc in grandchildren:
#                     gc_obj, _, gc_tipo, _ = gc
#                     entity_ids.add(id(gc_obj))

#             for hole in holes:
#                 if hole.entity is not None:
#                     entity_ids.add(id(hole.entity))
#                 if hole.outer_entity is not None:
#                     entity_ids.add(id(hole.outer_entity))

#             for inner in inners:
#                 if inner.entity is not None:
#                     entity_ids.add(id(inner.entity))

#             part = ForgePart(
#                 outer=outer,
#                 holes=holes,
#                 inners=inners,
#                 label=self.label,
#                 source_file=self.source_file,
#                 custom={},
#                 geometry_hints=GeometryHints(),
#                 entity_ids=entity_ids,
#             )

#             if father_tipo == "VIRTUAL":
#                 self.result._vs_to_part[id(father_obj)] = part

#             for child in children:
#                 child_obj, _, child_tipo, grandchildren = child
#                 if child_tipo == "VIRTUAL":
#                     self.result._vs_to_part[id(child_obj)] = part
#                 for gc in grandchildren:
#                     gc_obj, _, gc_tipo, _ = gc
#                     if gc_tipo == "VIRTUAL":
#                         self.result._vs_to_part[id(gc_obj)] = part

#             self.result.parts.append(part)

#     def _build_trash(self):
#         self.result.trash_entities += [
#             e for e in self.msp
#             if id(e) not in self.classified_entity_ids
#             and id(e) not in self.classified_virtual_ids
#             and e.dxf.hasattr("layer")
#             and e.dxf.layer.upper() not in STRUCTURAL_LAYERS
#             and (
#                 id(e) not in self.entities_in_loops
#                 or e.dxf.layer.lower() in self.special_layer_names
#             )
#         ]

#         self.result.parts.sort(key=lambda p: p.outer.polygon.area, reverse=True)


#     def _edges_from_msp(self, exclude_ids=None):
#         exclude_ids = set(exclude_ids or [])

#         def _is_excluded(entity):
#             if id(entity) in exclude_ids:
#                 return True
#             if not self.ignore_layers:
#                 return False
#             layer = entity.dxf.layer.lower() if entity.dxf.hasattr('layer') else ''
#             return any(sl in layer for sl in self.ignore_layers)

#         edges = []
#         for entity in self.msp:
#             if _is_excluded(entity):
#                 continue
#             s, e = _normalized_endpoints(entity, self.node_decimals)
#             if s is None:
#                 continue
#             layer = entity.dxf.layer if entity.dxf.hasattr('layer') else ''
#             edges.append(Edge(entity=entity, layer=layer, start=s, end=e))
#         return edges



import numpy as np

from ...models import (
    ForgeResult,
    Edge,
)
from ...core.graph import (
    build_node_graph,
    _normalized_endpoints,
)
from ._helpers import (
    _free_endpoints,
    _spline_is_closed,
)
from ._utils import (
    _deduplicate_entities,
    _explode_inserts,
)
from ...core.gap import close_gaps
from ...core.graph import spline_endpoints
from ...core.geometry import round_point

from ...rules.layers import (
    STRUCTURAL_LAYERS,
)


class HealerPipeline:
    def __init__(
        self,
        msp,
        tolerance,
        label="",
        source_file="",
        explode_inserts=False,
        ignore_layers=None,
        special_layers=None,
    ):
        self.msp             = msp
        self.tolerance       = tolerance
        self.label           = label
        self.source_file     = source_file
        self.explode_inserts = explode_inserts
        self.ignore_layers   = {l.lower() for l in (ignore_layers or [])}
        # nomi layer (lowercase) da non inghiottire nei loop
        self.special_layer_names = {k.lower() for k in (special_layers or {})}

        self.node_decimals = max(round(-np.log10(tolerance * 2)), 1)
        self.result        = ForgeResult(source_file=source_file)

        # salva special_layers nel result — detect() lo legge da qui
        if special_layers:
            self.result.special_layers = special_layers

        self.candidate_bending_ids  = set()
        self.classified_entity_ids  = set()
        self.classified_virtual_ids = set()
        self.entities_in_loops      = set()

        self.all_lines      = []
        self.all_arcs       = []
        self.all_plines     = []
        self.all_circles    = []
        self.all_splines    = []
        self.closed_splines = []
        self.open_splines   = []

    def run(self):
        self._handle_inserts()
        self._load()
        if not self.result.is_valid:
            return self.result
        self._preprocess()
        self._find_bending_candidates()
        self._find_loops()
        self._reintegrate_bending()
        self._build_hierarchy()
        self._build_trash()
        return self.result


    def _build_graph(self, exclude_ids=None):
        edges = self._edges_from_msp(exclude_ids=exclude_ids)
        return build_node_graph(edges)

    def _handle_inserts(self):
        inserts_found = list(self.msp.query("INSERT"))
        if inserts_found:
            if self.explode_inserts:
                n = _explode_inserts(self.msp)
                self.result.warnings.append(f"{n} INSERT esplosi prima dell'healing.")
            else:
                self.result.warnings.append(
                    f"Trovati {len(inserts_found)} INSERT (blocchi) non esplosi — "
                    f"usa explode_inserts=True in heal() per includerli."
                )

    def _load(self):
        removed = _deduplicate_entities(self.msp, tolerance=self.tolerance)
        if removed > 0:
            self.result.warnings.append(f"Rimosse {removed} entità duplicate dal msp.")

        self.all_lines   = list(self.msp.query("LINE"))
        self.all_arcs    = list(self.msp.query("ARC"))
        self.all_plines  = list(self.msp.query("LWPOLYLINE POLYLINE"))
        self.all_circles = list(self.msp.query("CIRCLE"))
        self.all_splines = list(self.msp.query("SPLINE"))

        if not any([self.all_lines, self.all_arcs, self.all_plines,
                    self.all_circles, self.all_splines]):
            self.result.errors.append("Modelspace vuoto: nessuna geometria trovata.")
            self.result.is_valid = False
            return

        self.closed_splines = [s for s in self.all_splines if     _spline_is_closed(s, self.tolerance)]
        self.open_splines   = [s for s in self.all_splines if not _spline_is_closed(s, self.tolerance)]

    def _preprocess(self):
        if not (self.all_lines or self.all_arcs):
            return

        graph_pre = self._build_graph()
        free = _free_endpoints(graph_pre, self.msp, self.node_decimals)

        if free:
            fixed = close_gaps(self.msp, free, self.tolerance)
            if fixed:
                self.all_lines = list(self.msp.query("LINE"))
                self.all_arcs  = list(self.msp.query("ARC"))
                graph_pre      = None

        if self.open_splines:
            if graph_pre is None:
                graph_pre = self._build_graph()
            for spline in self.open_splines:
                s, e = spline_endpoints(spline)
                if s is None or e is None:
                    continue
                s_r = round_point(s)
                e_r = round_point(e)
                if len(graph_pre.get(s_r, [])) < 2 or len(graph_pre.get(e_r, [])) < 2:
                    self.result.warnings.append(
                        "SPLINE con endpoint non connesso trovata — "
                        "gap tra SPLINE e altre entità gestito con una linea di congiunzione. "
                        "Verificare manualmente la correttezza del file."
                    )
                    break


    def _find_bending_candidates(self):
        if not (self.all_lines or self.all_arcs):
            return

        graph_full      = self._build_graph()
        branching_nodes = {
            node for node, neighbors in graph_full.items() if len(neighbors) > 2
        }

        if not branching_nodes:
            return

        for line in self.all_lines:
            s = round_point((line.dxf.start.x, line.dxf.start.y), self.node_decimals)
            e = round_point((line.dxf.end.x,   line.dxf.end.y),   self.node_decimals)
            if s in branching_nodes and e in branching_nodes:
                self.candidate_bending_ids.add(id(line))

        if not self.candidate_bending_ids:
            return

        from shapely.geometry import MultiPoint, LineString as SLS
        hull = MultiPoint(list(graph_full.keys())).convex_hull

        confirmed_bending_ids = set()
        for line in self.all_lines:
            if id(line) not in self.candidate_bending_ids:
                continue

            test_graph = self._build_graph(exclude_ids={id(line)})
            if not test_graph:
                continue
            start = next(iter(test_graph))
            visited = {start}
            queue = [start]
            while queue:
                node = queue.pop()
                for _, neighbor in test_graph[node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            is_bridge = len(visited) < len(test_graph)

            line_geom   = SLS([(line.dxf.start.x, line.dxf.start.y),
                            (line.dxf.end.x,   line.dxf.end.y)])
            is_interior = hull.boundary.distance(line_geom.centroid) > self.tolerance

            if is_interior:
                confirmed_bending_ids.add(id(line))

        self.candidate_bending_ids = confirmed_bending_ids

        if self.candidate_bending_ids:
            self.result.warnings.append(
                f"{len(self.candidate_bending_ids)} LINE candidate come bending "
                f"escluse dal grafo (entrambi gli endpoint su nodi di branching)."
            )
            self.all_lines = [l for l in self.all_lines if id(l) not in self.candidate_bending_ids]


    def _find_loops(self):
        if not (self.all_lines or self.all_arcs or self.open_splines):
            return

        graph = self._build_graph(exclude_ids=self.candidate_bending_ids)
        loops = self._collect_loops(graph)

        if not loops:
            self._fallback_polygonize()
            return

        self._classify_and_build(loops, graph)

    def _edges_from_msp(self, exclude_ids=None):
        exclude_ids = set(exclude_ids or [])

        def _is_excluded(entity):
            if id(entity) in exclude_ids:
                return True
            if not self.ignore_layers:
                return False
            layer = entity.dxf.layer.lower() if entity.dxf.hasattr('layer') else ''
            return any(sl in layer for sl in self.ignore_layers)

        edges = []
        for entity in self.msp:
            if _is_excluded(entity):
                continue
            s, e = _normalized_endpoints(entity, self.node_decimals)
            if s is None:
                continue
            layer = entity.dxf.layer if entity.dxf.hasattr('layer') else ''
            edges.append(Edge(entity=entity, layer=layer, start=s, end=e))
        return edges


# metodi estratti in moduli separati
from ._loops     import _collect_loops, _reintegrate_bending, _fallback_polygonize, _classify_and_build  # noqa: E402
from ._hierarchy import _build_hierarchy, _build_trash  # noqa: E402

HealerPipeline._collect_loops       = _collect_loops
HealerPipeline._reintegrate_bending = _reintegrate_bending
HealerPipeline._fallback_polygonize = _fallback_polygonize
HealerPipeline._classify_and_build  = _classify_and_build
HealerPipeline._build_hierarchy     = _build_hierarchy
HealerPipeline._build_trash         = _build_trash