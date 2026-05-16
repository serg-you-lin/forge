"""
workflow/healer/__init__.py
---------------------------
API pubblica di healing geometrico.

IMPORTANTE: questo modulo non apre né salva file.
Riceve un msp (modelspace ezdxf) e lo modifica in memoria.
Chi chiama decide quando salvare.

Casi gestiti:
  1. FILE SPORCO: LINE + ARC sparsi → ricostruisce LWPOLYLINE con bulge reali
  2. FILE GIÀ PULITO: LWPOLYLINE già chiuse → classifica outer/hole, assegna layer
  3. MISTO: LINE/ARC + LWPOLYLINE → gestisce entrambi
  4. SPLINE chiusa solitaria → resta SPLINE nel msp, riceve layer corretto
  5. SPLINE aperta connessa a LINE/ARC → loop resta come entità separate
                                         con layer/colore assegnati (no LWPOLYLINE)
  6. Gap SPLINE+LINE → chiude con LINE aggiuntiva (warning esplicito)


Architettura interna:
  - Pre-processing: close_gaps solo su endpoint liberi (grado < 2)
  - Passo 1: costruisce geometria in memoria (VirtualShape)
  - Passo 2: gerarchia da VirtualShape + entità esistenti
  - Passo 3: Scrittura msp, effetto collaterale separato, solo se write_to_msp=True

heal() è un orchestratore — costruisce la geometria strutturale e
popola GeometryHints su ogni ForgePart. Non sa cosa significa
"bending" o "countersink" per il business: sa solo dove si trovano
quelle entità rispetto alla geometria strutturale.

Flusso:
    heal()      → ForgeResult con ForgePart e GeometryHints popolati
    classify()  → legge GeometryHints, scrive part.custom
    inject()    → scrive metriche e dati custom nel JSON
"""

from __future__ import annotations

from typing import List

import numpy as np
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union, snap, polygonize

from ...models import (
    ForgeResult,
    ForgePart,
    ForgeContour,
    GeometryHints,
)
from ...core.geometry import (
    pline_to_polygon,
    circle_to_polygon,
    is_countersink_outer,
    is_threaded_hole,
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
    _special_layer_names,
    _is_special,
    _free_endpoints,
    _spline_is_closed,
    _spline_to_polygon,
)

from ._utils import (
    _deduplicate_entities,
    _deduplicate_loops,
    _explode_inserts,
)

from ._writer import _apply_to_msp
from ...core.gap import close_gaps
from ...core.graph import spline_endpoints
from ...core.geometry import round_point

# ---------------------------------------------------------------------------
# Costanti layer / colori — fonte di verità per tutto il package
# ---------------------------------------------------------------------------

from ...rules.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    LAYER_BENDING, LAYER_MARKING, LAYER_ENGRAVE, LAYER_COUNTERSINK, LAYER_THREADED_HOLE,
    COLOR_OUTER, COLOR_INNER, COLOR_HOLE,
    COLOR_BENDING, COLOR_MARKING, COLOR_ENGRAVE, COLOR_COUNTERSINK, COLOR_TRASH, COLOR_THREADED_HOLE,
    HOLE_DIAMETER_THRESHOLD, STRUCTURAL_LAYERS, TRASH_LAYER,
    WORK_TYPE_TO_LAYER,
)
# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def heal(
    msp,
    tolerance:       float = 0.05,
    write_to_msp:    bool  = True,
    label:           str   = "",
    source_file:     str   = "",
    special_layers:  dict  = None,
    keep_trash:      bool  = True,
    explode_inserts: bool  = False,
) -> ForgeResult:
    """
    Ripara la geometria del modelspace e restituisce un ForgeResult.

    Responsabilità di heal():
        - loop chiusi da LINE/ARC/SPLINE → VirtualShape
        - gerarchia padre-figlio → ForgePart con ForgeContour
        - rilevamento geometrico puro di countersink, threaded holes, bend lines
          → scritto in part.geometry_hints (NON in part.custom)
        - scrittura opzionale nel msp via _apply_to_msp()

    Non è responsabilità di heal():
        - interpretare cosa significa "bending" per il business  → classify()
        - scrivere bending_lines_data, countersink_data, ecc.    → classify()
        - iniettare metriche e dati custom nel JSON              → inject()

    Args:
        msp:             modelspace ezdxf già aperto dal chiamante
        tolerance:       tolleranza per chiudere gap tra segmenti (mm)
        write_to_msp:    se True modifica il msp, se False solo ForgeResult
        label:           etichetta del pezzo
        source_file:     percorso del DXF originale
        special_layers:  dict {nome_layer: tipo_lavorazione}
                         usato solo per escludere entità dalla geometria strutturale
                         e per popolare geometry_hints.bend_line_ids
        keep_trash:      se True entità non classificate → layer Trash
        explode_inserts: se True esplode gli INSERT prima dell'healing

    Returns:
        ForgeResult con ForgePart già costruiti.
        Ogni ForgePart ha:
            - custom={}              → da popolare con classify() e inject()
            - geometry_hints popolato → letto da classify() e snapmark
    """
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
    # Raccolta entità — special_layers esclusi dalla geometria strutturale
    # ------------------------------------------------------------------
    special_names = _special_layer_names(special_layers)

    all_lines    = [e for e in msp.query("LINE")              if not _is_special(e, special_names)]
    all_arcs     = [e for e in msp.query("ARC")               if not _is_special(e, special_names)]
    all_plines   = [e for e in msp.query("LWPOLYLINE POLYLINE") if not _is_special(e, special_names)]
    all_circles  = [e for e in msp.query("CIRCLE")            if not _is_special(e, special_names)]
    all_splines  = [e for e in msp.query("SPLINE")            if not _is_special(e, special_names)]
    all_ellipses = [e for e in msp.query("ELLIPSE")           if not _is_special(e, special_names)]

    if not any([all_lines, all_arcs, all_plines, all_circles, all_splines, all_ellipses]):
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
        graph_pre = build_node_graph(msp, decimals=node_decimals, exclude_layers=special_names)
        free = _free_endpoints(graph_pre, msp, node_decimals, special_names)
        if free:
            fixed = close_gaps(msp, free, tolerance)
            if fixed:
                all_lines = [e for e in msp.query("LINE") if not _is_special(e, special_names)]
                all_arcs  = [e for e in msp.query("ARC")  if not _is_special(e, special_names)]
                graph_pre = None

    if open_splines:
        if graph_pre is None:
            graph_pre = build_node_graph(msp, decimals=node_decimals, exclude_layers=special_names)
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
    virtual_shapes:    List[VirtualShape] = []
    entities_in_loops: set                = set()

    if all_lines or all_arcs or open_splines:
        graph = build_node_graph(msp, decimals=node_decimals, exclude_layers=special_names)
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

            for loop in outer_loops:
                vs = _loop_to_virtual_shape(loop, LAYER_OUTER, COLOR_OUTER)
                if vs is not None:
                    virtual_shapes.append(vs)
            for loop in inner_loops:
                vs = _loop_to_virtual_shape(loop, LAYER_INNER, COLOR_INNER)
                if vs is not None:
                    virtual_shapes.append(vs)

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
                for poly in polygons:
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    pts = [(x, y, 0.0, 0.0, 0.0) for x, y in poly.exterior.coords]
                    virtual_shapes.append(VirtualShape(
                        pts_with_bulge=pts, polygon=poly,
                        layer=LAYER_OUTER, color=COLOR_OUTER,
                    ))
                    for interior in poly.interiors:
                        pts_i = [(x, y, 0.0, 0.0, 0.0) for x, y in interior.coords]
                        virtual_shapes.append(VirtualShape(
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
    for vs     in virtual_shapes: shapes.append((vs,     vs.polygon,                "VIRTUAL"))
    for pline  in all_plines:
        poly = pline_to_polygon(pline)
        if poly: shapes.append((pline,  poly, "LWPOLYLINE"))
    for circle in all_circles:
        poly = circle_to_polygon(circle)
        if poly: shapes.append((circle, poly, "CIRCLE"))
    for spline in closed_splines:
        poly = _spline_to_polygon(spline)
        if poly: shapes.append((spline, poly, "SPLINE"))

    if not shapes:
        result.errors.append("Nessuna geometria chiusa trovata dopo healing.")
        result.is_valid = False
        return result

    shapes.sort(key=lambda x: x[1].area, reverse=True)

    # Gerarchia padre-figlio
    classified_entity_ids:  set = set()
    classified_virtual_ids: set = set()
    fathers = []

    for obj, poly, tipo in shapes:
        placed = False
        for _, father_poly, _, children in fathers:
            if father_poly.contains(poly):
                children.append((obj, poly, tipo))
                placed = True
                break
        if not placed:
            fathers.append((obj, poly, tipo, []))

    for _, _, _, children in fathers:
        for child_obj, child_poly, child_tipo in children:
            if child_tipo == "VIRTUAL":
                child_obj.layer = LAYER_INNER
                child_obj.color = COLOR_INNER

    # ------------------------------------------------------------------
    # Raccolta geometry_hints — geometria pura, nessuna semantica business
    #
    # heal() sa dove si trovano queste entità rispetto alla struttura
    # geometrica. Non sa (e non gli interessa) cosa significano per
    # il processo di lavorazione — quello è compito di classify().
    # ------------------------------------------------------------------
    hints_countersink:   set = set()
    hints_threaded_hole: set = set()
    hints_bend_line:     set = set()

    # Bend lines — entità LINE su layer marcati come "bending" in special_layers.
    # heal() le identifica per escluderle dalla geometria strutturale e per
    # passarle a classify() via geometry_hints. Nient'altro.
    if special_layers:
        bending_layer_names = {
            k.lower() for k, v in special_layers.items() if v == "bending"
        }
        for entity in msp.query("LINE"):
            layer = entity.dxf.layer.lower() if entity.dxf.hasattr("layer") else ""
            if layer in bending_layer_names:
                hints_bend_line.add(id(entity))

    # ------------------------------------------------------------------
    # Costruzione ForgeResult — un ForgePart per ogni father
    # ------------------------------------------------------------------
    for father_obj, father_poly, father_tipo, children in fathers:
        outer = ForgeContour(polygon=father_poly, is_inner=False, layer=LAYER_OUTER)

        if father_tipo == "VIRTUAL":
            classified_virtual_ids.add(id(father_obj))
        else:
            classified_entity_ids.add(id(father_obj))

        inners          = []
        part_countersink   = set()
        part_threaded_hole = set()

        for child_obj, child_poly, child_tipo in children:
            if child_tipo == "CIRCLE":
                if is_countersink_outer(child_obj, children):
                    part_countersink.add(id(child_obj))
                    hints_countersink.add(id(child_obj))
                    continue
                diameter = child_obj.dxf.radius * 2
                layer = LAYER_HOLE if diameter < HOLE_DIAMETER_THRESHOLD else LAYER_INNER
                if layer == LAYER_HOLE:
                    if is_threaded_hole(child_obj, all_arcs):
                        part_threaded_hole.add(id(child_obj))
                        hints_threaded_hole.add(id(child_obj))
            else:
                layer = LAYER_INNER

            inners.append(ForgeContour(
                polygon=child_poly,
                is_inner=True,
                layer=layer,
                is_hole=(layer == LAYER_HOLE),
            ))

            if child_tipo == "VIRTUAL":
                classified_virtual_ids.add(id(child_obj))
            else:
                classified_entity_ids.add(id(child_obj))

        # GeometryHints per questo part — id() validi finché il msp è in memoria
        hints = GeometryHints(
            countersink_ids=part_countersink,
            threaded_hole_ids=part_threaded_hole,
            bend_line_ids=hints_bend_line,   # per ora globali, classify() filtra per poly
        )

        result.parts.append(ForgePart(
            outer=outer,
            inners=inners,
            label=label,
            source_file=source_file,
            custom={},
            geometry_hints=hints,
        ))

    # Trash — entità non classificate, non su layer strutturali o special
    special_names_set = {k.lower() for k in special_layers} if special_layers else set()
    result.trash_entities = [
        e for e in msp
        if id(e) not in classified_entity_ids
        and id(e) not in classified_virtual_ids
        and id(e) not in entities_in_loops
        and e.dxf.hasattr("layer")
        and e.dxf.layer.upper() not in STRUCTURAL_LAYERS
        and e.dxf.layer.lower() not in special_names_set
    ]

    # ------------------------------------------------------------------
    # Passo 3: scrittura MSP — delegata a _apply_to_msp
    # ------------------------------------------------------------------
    if write_to_msp:
        _apply_to_msp(
            msp=msp,
            virtual_shapes=virtual_shapes,
            fathers=fathers,
            entities_in_loops=entities_in_loops,
            classified_entity_ids=classified_entity_ids,
            special_layers=special_layers,
            keep_trash=keep_trash,
            countersink_ids=hints_countersink,
            threaded_hole_ids=hints_threaded_hole,
            bend_line_ids=hints_bend_line,
        )

    return result