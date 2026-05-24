

"""
workflow/healer/__init__.py
---------------------------
API pubblica di healing geometrico.

Responsabilità rispetto ai fori:
    heal() riconosce la struttura geometrica e crea Hole con:
        - hole_type      = HOLE_TYPE_UNKNOWN  (la diagnosi spetta a detect)
        - geometric_hint = "countersink" se il cerchio aveva figli (figlio con nipoti)
                         = "threaded"    NON rilevato qui — troppo costoso senza ARC
                         = ""            foro liscio apparente

    detect() legge geometric_hint e promuove hole_type al tipo definitivo.
    Se detect() non viene chiamato, hole_type resta UNKNOWN — nessuna diagnosi.

Responsabilità rispetto a entity_ids:
    heal() popola part.entity_ids con gli id() di tutte le entità reali appartenenti
    al part durante la costruzione della gerarchia. Per i VirtualShape non-spline,
    registra id(vs) come placeholder in _vs_to_part — write() farà lo swap
    id(VS) → id(LWPOLYLINE) dopo la materializzazione.
    Le entità spline sono già in _entities_in_loops_ids e vengono aggiunte
    direttamente a entity_ids senza placeholder.
"""

from __future__ import annotations

import numpy as np
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union, snap, polygonize

from ...models import (
    ForgeResult,
    ForgePart,
    ForgeContour,
    GeometryHints,
    Hole,
    HOLE_TYPE_UNKNOWN,
)
from ...core.geometry import (
    pline_to_polygon,
    circle_to_polygon,
    arc_to_linestrings,
)
from ...core.graph import (
    build_node_graph,
    find_closed_loops,
    classify_loops,
    check_loop_ambiguity,
)
from ...core.virtual import (
    VirtualShape,
    _loop_to_virtual_shape,
)
from ._helpers import (
    _free_endpoints,
    _spline_is_closed,
    _spline_to_polygon,
)
from ._utils import (
    _deduplicate_entities,
    _deduplicate_loops,
    _explode_inserts,
)
from ...core.gap import close_gaps
from ...core.graph import spline_endpoints
from ...core.geometry import round_point

from ...rules.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    COLOR_OUTER, COLOR_INNER,
    HOLE_DIAMETER_THRESHOLD, STRUCTURAL_LAYERS,
)


def heal(
    msp,
    tolerance:       float = 0.05,
    label:           str   = "",
    source_file:     str   = "",
    explode_inserts: bool  = False,
) -> ForgeResult:
    result = ForgeResult(source_file=source_file)

    # ------------------------------------------------------------------
    # Gestione INSERT
    # ------------------------------------------------------------------
    inserts_found = list(msp.query("INSERT"))
    if inserts_found:
        if explode_inserts:
            n = _explode_inserts(msp)
            result.warnings.append(f"{n} INSERT esplosi prima dell'healing.")
        else:
            result.warnings.append(
                f"Trovati {len(inserts_found)} INSERT (blocchi) non esplosi — "
                f"usa explode_inserts=True in heal() per includerli."
            )

    removed = _deduplicate_entities(msp, tolerance=tolerance)
    if removed > 0:
        result.warnings.append(f"Rimosse {removed} entità duplicate dal msp.")

    # ------------------------------------------------------------------
    # Raccolta entità
    # ------------------------------------------------------------------
    all_lines   = list(msp.query("LINE"))
    all_arcs    = list(msp.query("ARC"))
    all_plines  = list(msp.query("LWPOLYLINE POLYLINE"))
    all_circles = list(msp.query("CIRCLE"))
    all_splines = list(msp.query("SPLINE"))
    print(f"  [HEAL] plines={len(all_plines)} lines={len(all_lines)} arcs={len(all_arcs)} splines={len(all_splines)}")

    if not any([all_lines, all_arcs, all_plines, all_circles, all_splines]):
        result.errors.append("Modelspace vuoto: nessuna geometria trovata.")
        result.is_valid = False
        return result

    closed_splines = [s for s in all_splines if     _spline_is_closed(s, tolerance)]
    open_splines   = [s for s in all_splines if not _spline_is_closed(s, tolerance)]

    # ------------------------------------------------------------------
    # Pre-processing: close_gaps solo su endpoint liberi
    # ------------------------------------------------------------------
    node_decimals = max(round(-np.log10(tolerance * 2)), 1)
    graph_pre     = None

    if all_lines or all_arcs:
        graph_pre = build_node_graph(msp, decimals=node_decimals)
        free = _free_endpoints(graph_pre, msp, node_decimals)
        if free:
            fixed = close_gaps(msp, free, tolerance)
            if fixed:
                all_lines = list(msp.query("LINE"))
                all_arcs  = list(msp.query("ARC"))
                graph_pre = None

    if open_splines:
        if graph_pre is None:
            graph_pre = build_node_graph(msp, decimals=node_decimals)
        for spline in open_splines:
            s, e = spline_endpoints(spline)
            if s is None or e is None:
                continue
            s_r = round_point(s)
            e_r = round_point(e)
            if len(graph_pre.get(s_r, [])) < 2 or len(graph_pre.get(e_r, [])) < 2:
                result.warnings.append(
                    "SPLINE con endpoint non connesso trovata — "
                    "gap tra SPLINE e altre entità gestito con una linea di congiunzione. "
                    "Verificare manualmente la correttezza del file."
                )
                break

    # ------------------------------------------------------------------
    # Passo 1: LINE/ARC/SPLINE → grafo → loop → VirtualShape
    # ------------------------------------------------------------------
    entities_in_loops: set = set()

    if all_lines or all_arcs or open_splines:
        graph = build_node_graph(msp, decimals=node_decimals)
        loops = find_closed_loops(graph)
        loops = _deduplicate_loops(loops)

        if loops:
            branching_nodes = check_loop_ambiguity(loops, graph)
            if branching_nodes:
                result.warnings.append(
                    f"Geometria ambigua: {len(branching_nodes)} nodi con più di 2 "
                    f"connessioni all'interno dei loop chiusi. Verificare il risultato."
                )

            outer_loops, inner_loops = classify_loops(loops)
            entities_in_loops = {
                id(e) for loop in (outer_loops + inner_loops) for e, _ in loop
            }
            result._entities_in_loops_ids = entities_in_loops

            for loop in outer_loops:
                vs = _loop_to_virtual_shape(loop, LAYER_OUTER, COLOR_OUTER)
                if vs is not None:
                    result._virtual_shapes.append(vs)
            for loop in inner_loops:
                vs = _loop_to_virtual_shape(loop, LAYER_INNER, COLOR_INNER)
                if vs is not None:
                    result._virtual_shapes.append(vs)

        else:
            result.warnings.append("Nessun loop trovato via grafo, uso polygonize come fallback.")
            segments = []
            for l in all_lines:
                segments.append(LineString([
                    (l.dxf.start.x, l.dxf.start.y),
                    (l.dxf.end.x,   l.dxf.end.y),
                ]))
            for a in all_arcs:
                segments.extend(arc_to_linestrings(a))

            merged   = unary_union(segments)
            snapped  = snap(merged, merged, tolerance)
            polygons = list(polygonize(snapped))

            if polygons:
                result.warnings.append(
                    f"Geometria ricostruita via fallback polygonize "
                    f"({len(polygons)} poligoni). Verificare il risultato."
                )
                entities_in_loops = {id(e) for e in all_lines + all_arcs}
                result._entities_in_loops_ids = entities_in_loops
                for poly in polygons:
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    pts = [(x, y, 0.0, 0.0, 0.0) for x, y in poly.exterior.coords]
                    result._virtual_shapes.append(VirtualShape(
                        pts_with_bulge=pts, polygon=poly,
                        layer=LAYER_OUTER, color=COLOR_OUTER,
                    ))
                    for interior in poly.interiors:
                        pts_i = [(x, y, 0.0, 0.0, 0.0) for x, y in interior.coords]
                        result._virtual_shapes.append(VirtualShape(
                            pts_with_bulge=pts_i, polygon=Polygon(interior),
                            layer=LAYER_INNER, color=COLOR_INNER,
                        ))
            else:
                result.warnings.append(
                    "LINE/ARC non formano loop chiusi — "
                    "potrebbero essere marcature o geometria aperta."
                )

    # ------------------------------------------------------------------
    # Passo 2: gerarchia — VirtualShape + LWPOLYLINE + CIRCLE + SPLINE chiuse
    # ------------------------------------------------------------------
    shapes = []
    for vs in result._virtual_shapes:
        shapes.append((vs, vs.polygon, "VIRTUAL"))
    for pline in all_plines:
        poly = pline_to_polygon(pline)
        if poly:
            shapes.append((pline, poly, "LWPOLYLINE"))
    for circle in all_circles:
        poly = circle_to_polygon(circle)
        if poly:
            shapes.append((circle, poly, "CIRCLE"))
    for spline in closed_splines:
        poly = _spline_to_polygon(spline)
        if poly:
            shapes.append((spline, poly, "SPLINE"))

    if not shapes:
        result.errors.append("Nessuna geometria chiusa trovata dopo healing.")
        result.is_valid = False
        return result

    shapes.sort(key=lambda x: x[1].area, reverse=True)

    # ------------------------------------------------------------------
    # Gerarchia multi-livello
    # ogni nodo: [obj, poly, tipo, children]
    # ------------------------------------------------------------------
    def _place(obj, poly, tipo, nodes):
        for node in nodes:
            if node[1].contains(poly):
                if not _place(obj, poly, tipo, node[3]):
                    node[3].append([obj, poly, tipo, []])
                return True
        return False

    classified_entity_ids:  set = set()
    classified_virtual_ids: set = set()
    fathers = []

    for obj, poly, tipo in shapes:
        if not _place(obj, poly, tipo, fathers):
            fathers.append([obj, poly, tipo, []])

    for node in fathers:
        for child in node[3]:
            if child[2] == "VIRTUAL":
                child[0].layer = LAYER_INNER
                child[0].color = COLOR_INNER

    # ------------------------------------------------------------------
    # Costruzione ForgeResult — un ForgePart per ogni father
    # ------------------------------------------------------------------
    for father in fathers:
        father_obj, father_poly, father_tipo, children = father

        outer = ForgeContour(
            polygon=father_poly,
            is_inner=False,
            layer=LAYER_OUTER,
            entity=father_obj if father_tipo != "VIRTUAL" else None,
        )

        if father_tipo == "VIRTUAL":
            classified_virtual_ids.add(id(father_obj))
        else:
            classified_entity_ids.add(id(father_obj))

        holes  = []
        inners = []

        for child in children:
            child_obj, child_poly, child_tipo, grandchildren = child

            if grandchildren:
                # -------------------------------------------------------
                # Figlio con nipoti = svasatura geometrica.
                # Il cerchio esterno (child) va in trash — non è materiale.
                # I nipoti (cerchio interno) diventano Hole con hint countersink.
                # detect() deciderà il tipo definitivo leggendo l'hint.
                # -------------------------------------------------------
                if child_tipo == "VIRTUAL":
                    classified_virtual_ids.add(id(child_obj))
                else:
                    classified_entity_ids.add(id(child_obj))
                    result.trash_entities.append(child_obj)

                outer_diameter = child_obj.dxf.radius * 2 if child_tipo == "CIRCLE" else None

                for gc in grandchildren:
                    gc_obj, gc_poly, gc_tipo, _ = gc

                    if gc_tipo == "CIRCLE":
                        diameter = gc_obj.dxf.radius * 2
                        center   = (gc_obj.dxf.center.x, gc_obj.dxf.center.y)
                        layer    = LAYER_HOLE if diameter < HOLE_DIAMETER_THRESHOLD else LAYER_INNER
                        holes.append(Hole(
                            polygon=gc_poly,
                            diameter=diameter,
                            center=center,
                            hole_type=HOLE_TYPE_UNKNOWN,
                            geometric_hint="countersink",
                            layer=layer,
                            source_layer=(
                                gc_obj.source_layer if gc_tipo == "VIRTUAL"
                                else gc_obj.dxf.layer if gc_obj.dxf.hasattr("layer")
                                else ""
                            ),
                            entity=gc_obj,
                            outer_diameter=outer_diameter,
                            outer_entity=child_obj if child_tipo != "VIRTUAL" else None,
                        ))
                    else:
                        gc_layer = LAYER_INNER
                        inners.append(ForgeContour(
                            polygon=gc_poly,
                            is_inner=True,
                            layer=gc_layer,
                            is_hole=False,
                            entity=gc_obj if gc_tipo != "VIRTUAL" else None,
                            source_layer=(
                                gc_obj.source_layer if gc_tipo == "VIRTUAL"
                                else gc_obj.dxf.layer if gc_obj.dxf.hasattr("layer")
                                else ""
                            ),
                        ))

                    if gc_tipo == "VIRTUAL":
                        classified_virtual_ids.add(id(gc_obj))
                    else:
                        classified_entity_ids.add(id(gc_obj))

            else:
                # -------------------------------------------------------
                # Figlio senza nipoti.
                # CIRCLE → Hole con geometric_hint="" (foro liscio apparente)
                # altro   → ForgeContour inner (contorno strutturale)
                # -------------------------------------------------------
                if child_tipo == "CIRCLE":
                    diameter = child_obj.dxf.radius * 2
                    center   = (child_obj.dxf.center.x, child_obj.dxf.center.y)
                    layer    = LAYER_HOLE if diameter < HOLE_DIAMETER_THRESHOLD else LAYER_INNER
                    holes.append(Hole(
                        polygon=child_poly,
                        diameter=diameter,
                        center=center,
                        hole_type=HOLE_TYPE_UNKNOWN,
                        geometric_hint="",
                        layer=layer,
                        source_layer=(
                            child_obj.dxf.layer if child_obj.dxf.hasattr("layer") else ""
                        ),
                        entity=child_obj,
                    ))
                else:
                    layer = LAYER_INNER
                    inners.append(ForgeContour(
                        polygon=child_poly,
                        is_inner=True,
                        layer=layer,
                        is_hole=False,
                        entity=child_obj if child_tipo != "VIRTUAL" else None,
                        source_layer=(
                            child_obj.source_layer if child_tipo == "VIRTUAL"
                            else child_obj.dxf.layer if child_obj.dxf.hasattr("layer")
                            else ""
                        ),
                    ))

                if child_tipo == "VIRTUAL":
                    classified_virtual_ids.add(id(child_obj))
                else:
                    classified_entity_ids.add(id(child_obj))

        # ------------------------------------------------------------------
        # entity_ids — costruito dalla gerarchia già nota, senza ricalcoli
        # ------------------------------------------------------------------
        entity_ids = set()

        # outer
        if father_tipo == "VIRTUAL":
            # placeholder: write() farà lo swap id(VS) → id(LWPOLYLINE)
            entity_ids.add(id(father_obj))
        else:
            entity_ids.add(id(father_obj))

        # children VIRTUAL inner (es. loop LINE/ARC classificato come inner)
        for child in children:
            child_obj, _, child_tipo, grandchildren = child
            if child_tipo == "VIRTUAL":
                entity_ids.add(id(child_obj))
            else:
                entity_ids.add(id(child_obj))
            for gc in grandchildren:
                gc_obj, _, gc_tipo, _ = gc
                if gc_tipo == "VIRTUAL":
                    entity_ids.add(id(gc_obj))
                else:
                    entity_ids.add(id(gc_obj))

        # spline chiuse: le loro entità originali sono già in _entities_in_loops_ids
        # e vengono riusate direttamente — nessun placeholder necessario
        if father_tipo == "SPLINE":
            entity_ids.add(id(father_obj))

        # fori: entity e outer_entity (countersink)
        for hole in holes:
            if hole.entity is not None:
                entity_ids.add(id(hole.entity))
            if hole.outer_entity is not None:
                entity_ids.add(id(hole.outer_entity))

        # inners
        for inner in inners:
            if inner.entity is not None:
                entity_ids.add(id(inner.entity))

        part = ForgePart(
            outer=outer,
            holes=holes,
            inners=inners,
            label=label,
            source_file=source_file,
            custom={},
            geometry_hints=GeometryHints(),
            entity_ids=entity_ids,
        )

        # registra il VS padre in _vs_to_part per lo swap in write()
        if father_tipo == "VIRTUAL":
            result._vs_to_part[id(father_obj)] = part

        # registra anche i VS inner in _vs_to_part
        for child in children:
            child_obj, _, child_tipo, grandchildren = child
            if child_tipo == "VIRTUAL":
                result._vs_to_part[id(child_obj)] = part
            for gc in grandchildren:
                gc_obj, _, gc_tipo, _ = gc
                if gc_tipo == "VIRTUAL":
                    result._vs_to_part[id(gc_obj)] = part

        result.parts.append(part)

    # ------------------------------------------------------------------
    # Trash — tutto ciò che non è strutturale
    # ------------------------------------------------------------------
    result.trash_entities += [
        e for e in msp
        if id(e) not in classified_entity_ids
        and id(e) not in classified_virtual_ids
        and id(e) not in entities_in_loops
        and e.dxf.hasattr("layer")
        and e.dxf.layer.upper() not in STRUCTURAL_LAYERS
    ]

    return result