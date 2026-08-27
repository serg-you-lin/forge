import sys
from pathlib import Path

if __package__:
    from ..model.result import ForgeResult
    from ..model.document import ForgeDocument
    from ..core.topology.graph import build_node_graph
    from ..core.geometry import node_decimals_for
    from ..core.primitives.segments import ArcSeg, SplineSeg
    from ..core.healing.gap_solver import (
        free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes,
    )
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from forge.model.result import ForgeResult
    from forge.model.document import ForgeDocument
    from forge.core.topology.graph import build_node_graph
    from forge.core.geometry import node_decimals_for
    from forge.core.primitives.segments import ArcSeg, SplineSeg
    from forge.core.healing.gap_solver import (
        free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes,
    )


class HealStep:
    """
    Esegue l'healing su un ForgeDocument — zero ezdxf.

    Lavora su doc.edges: gap closing (puro), individuazione bending,
    ricerca loop, costruzione gerarchia.
    """

    def __init__(
        self,
        doc: ForgeDocument,
        tolerance,
        label="",
        source_file="",
    ):
        self.doc             = doc
        self.tolerance       = tolerance
        self.label           = label
        self.source_file     = source_file

        self.node_decimals = node_decimals_for(tolerance)
        self.result        = ForgeResult(source_file=source_file)

        label_map = doc.source_meta.get("label_map") or {}
        if label_map:
            self.result.label_map = label_map

        self.candidate_bending_ids = set()
        self.loop_edge_ids         = set()
        self.entities_in_loops     = set()

        self.proxies = []
        self.closed_shapes = []
        self.labeled_edges = []

        self.edges = list(doc.edges)

    def run(self):
        self._load()
        if not self.result.is_valid:
            return self.result
        self._split_labeled()
        self._preprocess()
        self.result.all_arcs = [
            e.segment for e in self.edges if isinstance(e.segment, ArcSeg)
        ]
        self._find_bending_candidates()
        self._find_loops()
        self._reintegrate_bending()
        self._build_hierarchy()
        return self.result

    def _build_graph(self, exclude_ids=None):
        edges = self.edges
        if exclude_ids:
            edges = [e for e in edges if id(e) not in exclude_ids]
        return build_node_graph(edges)


    def _load(self):
        if not self.edges:
            self.result.errors.append("Modelspace vuoto: nessuna geometria trovata.")
            self.result.is_valid = False
            return

    def _split_labeled(self):
        """
        Estrae dal flusso topologico gli Edge il cui ruolo è già stato deciso
        da label_map e non è strutturale (engrave, marking).

        Questi non entrano nel grafo né nella ricerca loop: sono geometria di
        marcatura, non contorno. L'unico calcolo che li riguarda è il
        contenimento, fatto da detect(): dentro un part → feature del part,
        fuori → trash, esattamente come ogni entità che non sta dentro l'outer.
        """
        from ..model.role import ContourRole

        non_structural = {ContourRole.ENGRAVE, ContourRole.MARKING}
        self.labeled_edges = [e for e in self.edges if e.role in non_structural]
        if self.labeled_edges:
            self.edges = [e for e in self.edges if e.role not in non_structural]

    def _preprocess(self):
        graph_pre = self._build_graph()
        endpoints = free_endpoints_from_edges(self.edges, graph_pre)

        if endpoints:
            fixes = compute_gap_fixes(endpoints, self.tolerance)
            if fixes:
                self.edges = apply_gap_fixes(self.edges, fixes, self.node_decimals)
                graph_pre  = None

        open_spline_edges = [
            e for e in self.edges
            if isinstance(e.segment, SplineSeg) and e.start != e.end
        ]
        if open_spline_edges:
            if graph_pre is None:
                graph_pre = self._build_graph()
            for edge in open_spline_edges:
                if graph_pre.degree(edge.start) < 2 or graph_pre.degree(edge.end) < 2:
                    self.result.warnings.append(
                        "SPLINE con endpoint non connesso trovata — "
                        "gap tra SPLINE e altre entità gestito con una linea di congiunzione. "
                        "Verificare manualmente la correttezza del file."
                    )
                    break


    def _find_bending_candidates(self):
        from ..core.topology.bending_detector import BendingDetector
        graph_full = self._build_graph()

        self.candidate_bending_ids = BendingDetector(self.tolerance).detect(graph_full, self.edges)

        if self.candidate_bending_ids:
            self.result.warnings.append(
                f"{len(self.candidate_bending_ids)} candidate come bending "
                f"escluse dal grafo (entrambi gli endpoint su nodi di branching)."
            )


    def _find_loops(self):
        if not self.edges:
            return

        from ..core.topology.loop_finder import LoopFinder
        from ..adapters.dxf.parser import parse_loop
        from ..core.healing.hierarchy import loop_to_closed_shape
        from ..model.role import ContourRole

        graph = self._build_graph(exclude_ids=self.candidate_bending_ids)
        loops = LoopFinder().find(graph, exclude_ids=self.candidate_bending_ids)

        if not loops:
            self._fallback_polygonize()
            return

        structural_loops = [
            loop for loop in loops if _loop_is_structural(loop, self.result.label_map)
        ]
        self.loop_edge_ids = {
            id(edge)
            for loop in structural_loops
            for edge, _ in loop
        }

        for loop in structural_loops:
            role = loop[0][0].role if loop else ContourRole.UNKNOWN

            segments = parse_loop(loop)

            from ..core.primitives.polygon_builder import build_polygon
            from ..core.primitives.segments import DEFAULT_TOLERANCE
            polygon = build_polygon(segments, DEFAULT_TOLERANCE)
            if polygon is None:
                continue

            shape = loop_to_closed_shape(
                loop,
                role=role,
                polygon=polygon,
                segments=segments,
            )
            if shape is not None:
                self.closed_shapes.append(shape)

    def _reintegrate_bending(self):
        pass

    def _build_hierarchy(self):
        from ..core.topology.loop_finder import edges_to_open_shapes
        from ..core.healing.hierarchy import HierarchyBuilder

        open_proxies = edges_to_open_shapes(
            self.edges,
            exclude_ids=self.loop_edge_ids,
            label_map=self.result.label_map,
        )

        all_proxies = self.closed_shapes + open_proxies

        if not all_proxies:
            self.result.errors.append("Nessuna geometria chiusa trovata dopo healing.")
            self.result.is_valid = False
            return

        builder = HierarchyBuilder(
            label=self.label,
            source_file=self.source_file,
            label_map=self.result.label_map,
            entities_in_loops=self.entities_in_loops,
        )

        parts, trash = builder.build(all_proxies)

        self.result.parts          = parts
        self.result.trash_entities = trash + self._labeled_proxies()

    def _labeled_proxies(self):
        """
        Converte gli Edge estratti da _split_labeled() in proxy (OpenShape o,
        per tracce già degeneri come CIRCLE / SPLINE chiusa, ClosedShape).

        Restano portatori del loro `role` autoritativo: detect() li smista per
        contenimento senza mai rimetterli in discussione.
        """
        import math
        from ..adapters.bridge.shape import OpenShape, ClosedShape
        from ..core.primitives.polygon_builder import build_polygon
        from ..core.primitives.segments import DEFAULT_TOLERANCE

        proxies = []
        for edge in self.labeled_edges:
            seg = edge.segment
            if seg is None:
                continue
            pts = seg.discretize()

            if edge.start == edge.end:
                polygon = build_polygon([seg], DEFAULT_TOLERANCE)
                if polygon is None:
                    continue
                proxies.append(ClosedShape(
                    polygon=polygon,
                    role=edge.role,
                    segments=[seg],
                ))
                continue

            if len(pts) < 2:
                continue

            length = sum(
                math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                for i in range(len(pts) - 1)
            )
            proxies.append(OpenShape(
                pts=pts,
                length=length,
                role=edge.role,
                shape_type="line" if len(pts) == 2 else "curve",
                segments=[seg],
            ))

        return proxies


# ---------------------------------------------------------------------------
# Funzioni module-level
# ---------------------------------------------------------------------------

if __package__:
    from ..core.topology.loop_finder import LoopFinder
    from ..adapters.dxf.layers import LAYER_OUTER, LAYER_INNER
    from ..rules.palette import COLOR_OUTER, COLOR_INNER
else:
    from forge.core.topology.loop_finder import LoopFinder
    from forge.adapters.dxf.layers import LAYER_OUTER, LAYER_INNER
    from forge.rules.palette import COLOR_OUTER, COLOR_INNER

from shapely.geometry import Polygon


def _fallback_polygonize(self):
    import math
    from shapely.ops import unary_union, snap, polygonize
    from shapely.geometry import LineString, Polygon
    from ..core.primitives.segments import ArcSeg, DEFAULT_TOLERANCE
    from ..core.healing.hierarchy import loop_to_closed_shape
    from ..model.role import ContourRole

    self.result.warnings.append("Nessun loop trovato via grafo, uso polygonize come fallback.")
    segments = []

    for edge in self.edges:
        if edge.segment is None:
            continue
        pts = edge.segment.discretize(DEFAULT_TOLERANCE)
        if len(pts) >= 2:
            segments.append(LineString(pts))

    merged   = unary_union(segments)
    snapped  = snap(merged, merged, self.tolerance)
    polygons = list(polygonize(snapped))

    if polygons:
        self.result.warnings.append(
            f"Geometria ricostruita via fallback polygonize "
            f"({len(polygons)} poligoni). Verificare il risultato."
        )

        for poly in polygons:
            if not poly.is_valid:
                poly = poly.buffer(0)
            pts = [(x, y) for x, y in poly.exterior.coords]

            from ..core.primitives import LineSeg
            fallback_segments = [
                LineSeg(start=pts[i], end=pts[i + 1])
                for i in range(len(pts) - 1)
            ]
            shape = loop_to_closed_shape(
                [],
                role=ContourRole.OUTER,
                polygon=poly,
                segments=fallback_segments,
            )
            if shape is not None:
                self.closed_shapes.append(shape)

            for interior in poly.interiors:
                pts_i = [(x, y) for x, y in interior.coords]
                inner_segments = [
                    LineSeg(start=pts_i[i], end=pts_i[i + 1])
                    for i in range(len(pts_i) - 1)
                ]
                inner_poly = Polygon(interior)
                shape_i = loop_to_closed_shape(
                    [],
                    role=ContourRole.INNER,
                    polygon=inner_poly,
                    segments=inner_segments,
                )
                if shape_i is not None:
                    self.closed_shapes.append(shape_i)
    else:
        self.result.warnings.append(
            "LINE/ARC non formano loop chiusi — "
            "potrebbero essere marcature o geometria aperta."
        )

def _loop_is_structural(loop, label_map) -> bool:
    from ..model.role import ContourRole

    structural_roles = {
        ContourRole.OUTER, ContourRole.INNER, ContourRole.HOLE,
        ContourRole.COUNTERSINK, ContourRole.THREADED_HOLE,
    }
    for edge, _ in loop:
        if edge.role == ContourRole.UNKNOWN:
            continue
        if edge.role not in structural_roles:
            return False
    return True


HealStep._fallback_polygonize = _fallback_polygonize
