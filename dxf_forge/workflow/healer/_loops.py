from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union, snap, polygonize

from ...core.graph import find_closed_loops, classify_loops, check_loop_ambiguity
from ...core.virtual import VirtualShape, _loop_to_virtual_shape
from ...core.geometry import arc_to_linestrings
from ._utils import _deduplicate_loops
from ...rules.layers import (
    LAYER_OUTER, LAYER_INNER,
    COLOR_OUTER, COLOR_INNER,
)


def _collect_loops(self, graph):
    loops = find_closed_loops(graph)

    all_loop_ids = {id(edge.entity) for loop in loops for edge, _ in loop}
    seen_ids = set()
    for node, neighbors in graph.items():
        for edge, _ in neighbors:
            if id(edge.entity) not in all_loop_ids and id(edge.entity) not in seen_ids:
                seen_ids.add(id(edge.entity))
                e = edge.entity
                if e.dxftype() == "LINE":
                    coords = f"({e.dxf.start.x:.1f},{e.dxf.start.y:.1f})->({e.dxf.end.x:.1f},{e.dxf.end.y:.1f})"
                elif e.dxftype() == "ARC":
                    coords = f"center=({e.dxf.center.x:.1f},{e.dxf.center.y:.1f}) r={e.dxf.radius:.1f}"
                else:
                    coords = ""
                print(f"  [FUORI LOOP] {e.dxftype()} layer={e.dxf.layer} {coords}")

    print(f"[DEBUG loops] loop trovati da find_closed_loops: {len(loops)}")
    for i, loop in enumerate(loops):
        print(f"  [LOOP {i}] entità: {len(loop)}")
        for edge, rev in loop:
            e = edge.entity
            print(f"    {e.dxftype()} layer={e.dxf.layer} rev={rev}")

    return _deduplicate_loops(loops)


def _reintegrate_bending(self):
    all_lines_full = list(self.msp.query("LINE"))
    self.all_lines = self.all_lines + [
        l for l in all_lines_full if id(l) in self.candidate_bending_ids
    ]


def _fallback_polygonize(self):
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
            self.result._virtual_shapes.append(VirtualShape(
                pts_with_bulge=pts, polygon=poly,
                layer=LAYER_OUTER, color=COLOR_OUTER,
            ))
            for interior in poly.interiors:
                pts_i = [(x, y, 0.0, 0.0, 0.0) for x, y in interior.coords]
                self.result._virtual_shapes.append(VirtualShape(
                    pts_with_bulge=pts_i, polygon=Polygon(interior),
                    layer=LAYER_INNER, color=COLOR_INNER,
                ))
    else:
        self.result.warnings.append(
            "LINE/ARC non formano loop chiusi — "
            "potrebbero essere marcature o geometria aperta."
        )


def _classify_and_build(self, loops, graph):
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
        vs = _loop_to_virtual_shape(loop, LAYER_OUTER, COLOR_OUTER)
        if vs is not None:
            self.result._virtual_shapes.append(vs)
    for loop in inner_loops:
        vs = _loop_to_virtual_shape(loop, LAYER_INNER, COLOR_INNER)
        if vs is not None:
            self.result._virtual_shapes.append(vs)