
import numpy as np

from forge.adapters.dxf import sanitize

from ..model.result import (
    ForgeResult,
)
from ..core.topology.graph import (
    build_node_graph,
)
from ..core.healing.hierarchy import (
    _spline_is_closed,
)
from ..adapters.dxf.dedup_adapter import deduplicate as _deduplicate_entities
from ..core.geometry import spline_endpoints
from ..core.geometry import round_point
from ..adapters.dxf.graph_adapter import edges_from_msp as _edges_from_msp_adapter
from ..adapters.dxf.gap_adapter import extract_free_endpoints, apply_gap_fixes
from ..adapters.dxf.sanitize import _explode_inserts 

from ..rules.layers import (
    STRUCTURAL_LAYERS,
)


class HealStep:
    def __init__(
        self,
        msp,
        tolerance,
        label="",
        source_file="",
        explode_inserts=False,
        flatten_z: bool = True,
        ignore_layers=None,
        special_layers=None,
    ):
        self.msp             = msp
        self.tolerance       = tolerance
        self.label           = label
        self.source_file     = source_file
        self.explode_inserts = explode_inserts
        self.flatten_z       = flatten_z
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
        from ..adapters.dxf.sanitize import sanitize
        sanitize(self.msp, flatten_z_flag=self.flatten_z)
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
        edges = _edges_from_msp_adapter(
            self.msp,
            self.node_decimals,
            exclude_ids=exclude_ids,
            ignore_layers=self.ignore_layers,
        )
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
        endpoints = extract_free_endpoints(graph_pre, self.msp, self.node_decimals)

        if endpoints:
            from ..core.healing.gap_solver import compute_gap_fixes
            fixes = compute_gap_fixes(endpoints, self.tolerance)
            fixed = apply_gap_fixes(fixes, self.msp)

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
                print(f"[BENDING CANDIDATE] s={s} grado={len(graph_full[s])} e={e} grado={len(graph_full[e])}")
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


# metodi estratti in moduli separati
from ..core.topology.loops import _collect_loops, _reintegrate_bending  # noqa: E402
from ..core.healing.hierarchy  import _build_hierarchy, _build_trash         # noqa: E402
from ..adapters.dxf.virtual_adapter import _loop_to_contour, DxfWriteContext  # noqa: E402
from ..core.primitives.contour import Contour                                  # noqa: E402
from ..rules.layers import LAYER_OUTER, LAYER_INNER, COLOR_OUTER, COLOR_INNER  # noqa: E402
from shapely.geometry import Polygon                                            # noqa: E402


def _fallback_polygonize(self):
    from shapely.ops import unary_union, snap, polygonize
    from ..adapters.dxf.geometry_adapter import arc_to_linestrings
    from shapely.geometry import LineString

    self.result.warnings.append("Nessun loop trovato via grafo, uso polygonize come fallback.")
    segments = []
    for l in self.all_lines:
        segments.append(LineString([
            (l.dxf.start.x, l.dxf.start.y),
            (l.dxf.end.x,   l.dxf.end.y),
        ]))
    for a in self.all_arcs:
        segments.extend(arc_to_linestrings(a))

    merged   = unary_union(segments)
    snapped  = snap(merged, merged, self.tolerance)
    polygons = list(polygonize(snapped))

    if polygons:
        self.result.warnings.append(
            f"Geometria ricostruita via fallback polygonize "
            f"({len(polygons)} poligoni). Verificare il risultato."
        )
        self.entities_in_loops = {id(e) for e in self.all_lines + self.all_arcs}
        self.result._entities_in_loops_ids = self.entities_in_loops

        for poly in polygons:
            if not poly.is_valid:
                poly = poly.buffer(0)
            pts = [(x, y, 0.0, 0.0, 0.0) for x, y in poly.exterior.coords]
            contour = Contour(polygon=poly, segments=[], source_layer="", source_ref=None)
            ctx = DxfWriteContext(
                contour=contour,
                pts_with_bulge=pts,
                loop=[],
                layer=LAYER_OUTER,
                color=COLOR_OUTER,
            )
            self.result._virtual_shapes.append(ctx)

            for interior in poly.interiors:
                pts_i   = [(x, y, 0.0, 0.0, 0.0) for x, y in interior.coords]
                contour_i = Contour(
                    polygon=Polygon(interior),
                    segments=[],
                    source_layer="",
                    source_ref=None,
                )
                ctx_i = DxfWriteContext(
                    contour=contour_i,
                    pts_with_bulge=pts_i,
                    loop=[],
                    layer=LAYER_INNER,
                    color=COLOR_INNER,
                )
                self.result._virtual_shapes.append(ctx_i)
    else:
        self.result.warnings.append(
            "LINE/ARC non formano loop chiusi — "
            "potrebbero essere marcature o geometria aperta."
        )


def _classify_and_build(self, loops, graph):
    from ..core.topology.loops import classify_loops, check_loop_ambiguity

    branching_check = check_loop_ambiguity(loops, graph)
    if branching_check:
        self.result.warnings.append(
            f"Geometria ambigua: {len(branching_check)} nodi con più di 2 "
            f"connessioni all'interno dei loop chiusi. Verificare il risultato."
        )

    outer_loops, inner_loops = classify_loops(loops)
    self.entities_in_loops = {
        id(edge.entity) for loop in (outer_loops + inner_loops) for edge, _ in loop
    }
    self.result._entities_in_loops_ids = self.entities_in_loops

    for loop in outer_loops:
        ctx = _loop_to_contour(loop, LAYER_OUTER, COLOR_OUTER)
        if ctx is not None:
            self.result._virtual_shapes.append(ctx)
    for loop in inner_loops:
        ctx = _loop_to_contour(loop, LAYER_INNER, COLOR_INNER)
        if ctx is not None:
            self.result._virtual_shapes.append(ctx)


HealStep._collect_loops       = _collect_loops
HealStep._reintegrate_bending = _reintegrate_bending
HealStep._fallback_polygonize = _fallback_polygonize
HealStep._classify_and_build  = _classify_and_build
HealStep._build_hierarchy     = _build_hierarchy
HealStep._build_trash         = _build_trash