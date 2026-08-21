import sys
from pathlib import Path

import numpy as np

if __package__:
    from forge.adapters.dxf import sanitize
    from ..model.result import ForgeResult
    from ..core.topology.graph import build_node_graph
    from ..adapters.dxf.geometry_adapter import _spline_is_closed
    from ..adapters.dxf.sanitize import deduplicate as _deduplicate_entities
    from ..core.geometry import spline_endpoints, round_point
    # from ..adapters.dxf.gap_adapter import extract_free_endpoints, apply_gap_fixes
    from ..adapters.dxf.sanitize import _explode_inserts
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from forge.adapters.dxf import sanitize
    from forge.model.result import ForgeResult
    from forge.core.topology.graph import build_node_graph
    from forge.adapters.dxf.geometry_adapter import _spline_is_closed
    from forge.adapters.dxf.sanitize import deduplicate as _deduplicate_entities
    from forge.core.geometry import spline_endpoints, round_point
    # from forge.adapters.dxf.gap_adapter import extract_free_endpoints, apply_gap_fixes
    from forge.adapters.dxf.sanitize import _explode_inserts

class HealStep:
    def __init__(
        self,
        adapter,
        msp,
        tolerance,
        label="",
        source_file="",
        ignore_layers=None,
        special_layers=None,
    ):
        self.adapter         = adapter
        self.msp             = msp
        self.tolerance       = tolerance
        self.label           = label
        self.source_file     = source_file
        self.ignore_layers   = {l.lower() for l in (ignore_layers or [])}
        self.special_layer_names = {k.lower() for k in (special_layers or {})}

        self.node_decimals = self.adapter.node_decimals
        self.result        = ForgeResult(source_file=source_file)

        if special_layers:
            self.result.label_map = special_layers

        self.candidate_bending_ids  = set()
        self.classified_entity_ids  = set()
        self.classified_virtual_ids = set()
        self.entities_in_loops      = set()

        self.proxies = []

        self.all_lines      = []
        self.all_arcs       = []
        self.all_plines     = []
        self.all_circles    = []
        self.all_splines    = []
        self.closed_splines = []
        self.open_splines   = []

    def run(self):
        self._load()
        if not self.result.is_valid:
            return self.result
        self._preprocess()
        self.result.all_arcs = self.adapter.to_circular_arcs()
        self._find_bending_candidates()
        self._find_loops()
        self._reintegrate_bending()
        self._build_hierarchy()
        self._build_trash()
        return self.result
    

    def _build_graph(self, exclude_ids=None):
        edges = self.adapter.to_edges()
        if exclude_ids:
            edges = [e for e in edges if id(e.source_ref) not in exclude_ids]
        return build_node_graph(edges)

    def _load(self):
        entities         = self.adapter.load_entity_lists()
        self.all_lines   = entities["lines"]
        self.all_arcs    = entities["arcs"]
        self.all_plines  = entities["plines"]
        self.all_circles = entities["circles"]
        self.all_splines = entities["splines"]

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
        endpoints = self.adapter.extract_free_endpoints(graph_pre)

        if endpoints:
            from ..core.healing.gap_solver import compute_gap_fixes
            fixes = compute_gap_fixes(endpoints, self.tolerance)
            fixed = self.adapter.apply_gap_fixes(fixes)

            if fixed:
                entities = self.adapter.load_entity_lists()
                self.all_lines = entities["lines"]
                self.all_arcs  = entities["arcs"]
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

        from ..core.topology.bending_detector import BendingDetector
        graph_full = self._build_graph()
        edges      = self.adapter.to_edges()

        raw_candidates = BendingDetector(self.tolerance).detect(graph_full, edges)

        # La bending detection deve escludere dal grafo solo entita LINE.
        # Con to_edges() anche LWPOLYLINE/POLYLINE vengono esplose in Edge: se
        # un loro id finisce qui, rimuoverle spezza contorni strutturali.
        self.candidate_bending_ids = {
            id(e)
            for e in self.msp.query("LINE")
            if id(e) in raw_candidates
        }

        if self.candidate_bending_ids:
            self.result.warnings.append(
                f"{len(self.candidate_bending_ids)} LINE candidate come bending "
                f"escluse dal grafo (entrambi gli endpoint su nodi di branching)."
            )
            self.all_lines = [
                l for l in self.all_lines
                if id(l) not in self.candidate_bending_ids
            ]

    def _find_loops(self):
        if not (self.all_lines or self.all_arcs or self.open_splines
                or self.all_circles or self.all_plines or self.closed_splines):
            return

        from ..core.topology.loop_finder import LoopFinder
        graph = self._build_graph(exclude_ids=self.candidate_bending_ids)
        # LoopFinder().find() include già i loop degeneri (CIRCLE, SPLINE
        # chiuse) presi da graph.degenerate_loops — non vanno riaggiunti qui,
        # altrimenti ogni CIRCLE/loop degenere viene duplicato in due proxy
        # identici, che l'albero di contenimento interpreta come un
        # countersink (cerchio dentro sé stesso).
        loops = LoopFinder().find(graph, exclude_ids=self.candidate_bending_ids)

        if not loops:
            self._fallback_polygonize()
            return

        self._classify_and_build(loops, graph)

    def _reintegrate_bending(self):
        all_lines_full = list(self.msp.query("LINE"))
        self.all_lines = self.all_lines + [
            l for l in all_lines_full if id(l) in self.candidate_bending_ids
        ]


# metodi estratti in moduli separati
if __package__:
    from ..core.topology.loop_finder import LoopFinder, classify_loops, check_loop_ambiguity
    from ..core.healing.hierarchy import _build_hierarchy, _build_trash
    from ..adapters.dxf.virtual_adapter import _loop_to_contour, DxfWriteContext
    from ..adapters.dxf.layers import LAYER_OUTER, LAYER_INNER
    from ..rules.palette import COLOR_OUTER, COLOR_INNER
else:
    from forge.core.topology.loop_finder import LoopFinder, classify_loops, check_loop_ambiguity
    from forge.core.healing.hierarchy import _build_hierarchy, _build_trash
    from forge.adapters.dxf.virtual_adapter import _loop_to_contour, DxfWriteContext
    from forge.adapters.dxf.layers import LAYER_OUTER, LAYER_INNER
    from forge.rules.palette import COLOR_OUTER, COLOR_INNER
from shapely.geometry import Polygon


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
            ctx = DxfWriteContext(
                polygon=poly,
                has_spline=False,
                pts_with_bulge=pts,
                loop=[],
                layer=LAYER_OUTER,
                color=COLOR_OUTER,
            )
            self.result._virtual_shapes.append(ctx)

            for interior in poly.interiors:
                pts_i = [(x, y, 0.0, 0.0, 0.0) for x, y in interior.coords]
                ctx_i = DxfWriteContext(
                    polygon=Polygon(interior),
                    has_spline=False,
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


def _loop_is_structural(loop, label_map) -> bool:
    from ..model.role import ContourRole, layer_to_role

    # Countersink/threaded hole sono fori a tutti gli effetti — vanno
    # inclusi nell'albero di contenimento come HOLE/INNER, altrimenti
    # un loop etichettato via label_map (es. layer "Svasati" ->
    # "countersink") sparisce del tutto invece di diventare un Hole.
    structural_roles = {
        ContourRole.OUTER, ContourRole.INNER, ContourRole.HOLE,
        ContourRole.COUNTERSINK, ContourRole.THREADED_HOLE,
    }
    for edge, _ in loop:
        # Edge.layer è già una stringa cached — zero accessi a source_ref.dxf
        role = layer_to_role(edge.layer, label_map or {})
        if role == ContourRole.UNKNOWN:
            continue
        if role not in structural_roles:
            return False
    return True


def _classify_and_build(self, loops, graph):
    from ..core.topology.loop_finder import classify_loops, check_loop_ambiguity

    branching_check = check_loop_ambiguity(loops, graph)
    if branching_check:
        self.result.warnings.append(
            f"Geometria ambigua: {len(branching_check)} nodi con più di 2 "
            f"connessioni all'interno dei loop chiusi. Verificare il risultato."
        )

    outer_loops, inner_loops = classify_loops(loops)

    structural_loops = [loop for loop in outer_loops if _loop_is_structural(loop, self.result.label_map)]
    structural_loops += [loop for loop in inner_loops if _loop_is_structural(loop, self.result.label_map)]

    self.entities_in_loops = {
        id(edge.source_ref) for loop in structural_loops for edge, _ in loop
    }
    self.result._entities_in_loops_ids = self.entities_in_loops

    for loop in structural_loops:
        if loop in outer_loops:
            ctx = _loop_to_contour(loop, LAYER_OUTER, COLOR_OUTER)
            if ctx is not None:
                self.result._virtual_shapes.append(ctx)
        else:
            ctx = _loop_to_contour(loop, LAYER_INNER, COLOR_INNER)
            if ctx is not None:
                self.result._virtual_shapes.append(ctx)


HealStep._fallback_polygonize = _fallback_polygonize
HealStep._classify_and_build  = _classify_and_build
HealStep._build_hierarchy     = _build_hierarchy
HealStep._build_trash         = _build_trash