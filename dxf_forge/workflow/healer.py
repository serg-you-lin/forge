"""
healer.py
---------
Ripara geometrie DXF rotte: riconnette LINE e ARC sparsi
in LWPOLYLINE chiuse, classificando outer contour e fori.

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

Entità su special_layers → escluse dal grafo, misurate separatamente.

Architettura interna:
  - Pre-processing: close_gaps solo su endpoint liberi (grado < 2)
  - Passo 1: costruisce geometria in memoria (VirtualShape)
  - Passo 3: gerarchia da VirtualShape + entità esistenti
  - Scrittura msp: effetto collaterale separato, solo se write_to_msp=True
"""

import math
import numpy as np
from typing import Callable, List, Optional, Set
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union, snap

from ..models import ForgeContour, ForgePart, ForgeResult
from ..rules.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    LAYER_BENDING, LAYER_MARKING, LAYER_ENGRAVE,
    COLOR_OUTER, COLOR_INNER, COLOR_HOLE,
    COLOR_BENDING, COLOR_MARKING, COLOR_ENGRAVE, COLOR_TRASH,
    HOLE_DIAMETER_THRESHOLD, STRUCTURAL_LAYERS, TRASH_LAYER,
    WORK_TYPE_TO_LAYER,
)
from ..core.geometry import (arc_to_linestrings, pline_to_polygon,
                       circle_to_polygon, entity_length, arc_endpoints)
from ..core.graph import (build_node_graph, find_closed_loops,
                    check_loop_ambiguity, classify_loops,
                    spline_to_points, spline_endpoints,
                    round_point)
from ..core.virtual import VirtualShape, _loop_to_virtual_shape, _write_virtual_shape
from ..core.gap import close_gaps
from ..io.text_utils import extract_texts_from_msp


# ---------------------------------------------------------------------------
# Helper privati
# ---------------------------------------------------------------------------

def _special_layer_names(special_layers: dict) -> Set[str]:
    if not special_layers:
        return set()
    return {k.lower() for k in special_layers}


def _is_special(entity, special_names: Set[str]) -> bool:
    if not special_names:
        return False
    layer = entity.dxf.layer.lower() if entity.dxf.hasattr("layer") else ""
    return any(sl in layer for sl in special_names)


def _free_endpoints(graph, msp, node_decimals: int = 1,
                    special_names: Set[str] = None) -> list:
    """
    Restituisce gli endpoint di LINE, ARC e SPLINE con grado < 2 nel grafo.
    Esclude le entità su special_layers.
    """
    if special_names is None:
        special_names = set()
    free = []

    for line in msp.query('LINE'):
        if _is_special(line, special_names):
            continue
        s = round_point((line.dxf.start.x, line.dxf.start.y), node_decimals)
        e = round_point((line.dxf.end.x,   line.dxf.end.y),   node_decimals)
        if len(graph.get(s, [])) < 2:
            free.append(((line.dxf.start.x, line.dxf.start.y), line, 'start'))
        if len(graph.get(e, [])) < 2:
            free.append(((line.dxf.end.x, line.dxf.end.y), line, 'end'))

    for arc in msp.query('ARC'):
        if _is_special(arc, special_names):
            continue
        s, e = arc_endpoints(arc)
        s_r = round_point(s, node_decimals)
        e_r = round_point(e, node_decimals)
        if len(graph.get(s_r, [])) < 2:
            free.append((s, arc, 'start'))
        if len(graph.get(e_r, [])) < 2:
            free.append((e, arc, 'end'))

    for spline in msp.query('SPLINE'):
        if _is_special(spline, special_names):
            continue
        s, e = spline_endpoints(spline)
        if s is None or e is None:
            continue
        s_r = round_point(s, node_decimals)
        e_r = round_point(e, node_decimals)
        if len(graph.get(s_r, [])) < 2:
            free.append((s, spline, 'start'))
        if len(graph.get(e_r, [])) < 2:
            free.append((e, spline, 'end'))

    return free


def _spline_is_closed(spline, tolerance: float = 0.01) -> bool:
    """Restituisce True se la SPLINE è chiusa (start ≈ end)."""
    s, e = spline_endpoints(spline)
    if s is None or e is None:
        return False
    return math.sqrt((e[0] - s[0])**2 + (e[1] - s[1])**2) < tolerance


def _spline_to_polygon(spline) -> Optional[Polygon]:
    """
    Converte una SPLINE chiusa in Polygon Shapely via discretizzazione.
    Usato solo internamente per la gerarchia.
    """
    pts = spline_to_points(spline)
    if len(pts) < 3:
        return None
    try:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.geom_type == 'MultiPolygon':
            poly = max(poly.geoms, key=lambda p: p.area)
        return poly if not poly.is_empty else None
    except Exception:
        return None

def _deduplicate_loops(loops):
    """Per ogni coppia diretta/inversa, tieni solo quella con area maggiore."""
    from shapely.geometry import Polygon
    from dxf_forge.core.graph import spline_to_points
    from dxf_forge.core.geometry import arc_to_bulge

    seen = {}  # frozenset(id) -> (loop, area)
    for loop in loops:
        key = frozenset(id(e) for e, _ in loop)
        pts = []
        for entity, rev in loop:
            if entity.dxftype() == 'LINE':
                pts.append(
                    (entity.dxf.end.x, entity.dxf.end.y) if rev
                    else (entity.dxf.start.x, entity.dxf.start.y)
                )
            elif entity.dxftype() == 'ARC':
                entry_pt, _, _ = arc_to_bulge(entity, reversed=rev)
                pts.append(entry_pt)
            elif entity.dxftype() == 'SPLINE':
                spline_pts = spline_to_points(entity)
                if rev:
                    spline_pts = list(reversed(spline_pts))
                pts.extend(spline_pts)
        poly = Polygon(pts) if len(pts) >= 3 else None
        area = poly.area if poly and poly.is_valid else 0.0
        if key not in seen or area > seen[key][1]:
            seen[key] = (loop, area)
    return [loop for loop, _ in seen.values()]

def _deduplicate_entities(msp, tolerance: float = 0.01) -> int:
    """
    Rimuove entità geometricamente identiche dal msp.
    Va chiamata subito dopo _explode_inserts, prima del grafo.
    Restituisce il numero di entità rimosse.
    """
    def entity_key(e):
        t = e.dxftype()
        layer = e.dxf.get("layer", "0")
        try:
            if t == "LINE":
                s = (round(e.dxf.start.x, 2), round(e.dxf.start.y, 2))
                end = (round(e.dxf.end.x, 2), round(e.dxf.end.y, 2))
                pts = tuple(sorted([s, end]))  # normalizza direzione A→B == B→A
                return (t, layer, pts)
            elif t in ("LWPOLYLINE", "POLYLINE"):
                pts = tuple((round(p[0], 2), round(p[1], 2)) for p in e.get_points())
                return (t, layer, pts)
            elif t == "CIRCLE":
                c = e.dxf.center
                return (t, layer, round(c.x, 2), round(c.y, 2), round(e.dxf.radius, 2))
            elif t == "ARC":
                c = e.dxf.center
                return (t, layer, round(c.x, 2), round(c.y, 2),
                        round(e.dxf.radius, 2),
                        round(e.dxf.start_angle, 1),
                        round(e.dxf.end_angle, 1))
        except Exception:
            return None
        return None

    seen = set()
    to_delete = []
    for entity in msp:
        key = entity_key(entity)
        if key is None:
            continue
        if key in seen:
            to_delete.append(entity)
        else:
            seen.add(key)

    for entity in to_delete:
        msp.delete_entity(entity)

    return len(to_delete)

def _explode_inserts(msp) -> int:
    """
    Esplode tutti gli INSERT (blocchi) nel modelspace in entità primitive.
    Restituisce il numero di INSERT esplosi.
 
    Chiamato come primo pre-processing in heal() se explode_inserts=True.
    Le entità risultanti vengono aggiunte al msp e l'INSERT originale rimosso.
    """
    inserts = list(msp.query('INSERT'))
    if not inserts:
        return 0
 
    for insert in inserts:
        try:
            insert.explode()   # ezdxf aggiunge le entità al msp e rimuove l'INSERT
        except Exception as ex:
            print(f"  [WARN] Esplosione INSERT fallita: {ex}")
 
    return len(inserts)


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def heal(
    msp,
    tolerance: float = 0.05,
    write_to_msp: bool = True,
    label: str = "",
    source_file: str = "",
    special_layers: dict = None,
    keep_trash: bool = True,
    explode_inserts: bool = False,
    data_injector: Optional[Callable] = None,
) -> ForgeResult:
    """
    Ripara la geometria del modelspace in 3 passi sequenziali.

    Args:
        msp:            modelspace ezdxf già aperto dal chiamante
        tolerance:      tolleranza per chiudere gap tra segmenti (mm)
        write_to_msp:   se True modifica il msp, se False solo ForgeResult
        label:          etichetta del pezzo
        source_file:    percorso del DXF originale
        special_layers: dict {nome_layer: tipo_lavorazione} per entità speciali
        keep_trash:     se True entità non classificate → layer Trash
        explode_inserts: se True esplode gli INSERT prima dell'healing
    Returns:
        ForgeResult con i ForgePart trovati.
    """
    result = ForgeResult(source_file=source_file)

    # Se explode_inserts=False e ci sono INSERT, aggiungi un warning.
    inserts_found = list(msp.query('INSERT'))
    if inserts_found:
        if explode_inserts:
            n = _explode_inserts(msp)
            result.warnings.append(
                f"{n} INSERT esplosi prima dell'healing."
            )
        else:
            result.warnings.append(
                f"Trovati {len(inserts_found)} INSERT (blocchi) non esplosi — "
                f"usa explode_inserts=True in heal() per includerli."
            )

    removed = _deduplicate_entities(msp, tolerance=tolerance)
    if removed > 0:
        result.warnings.append(f"Rimosse {removed} entità duplicate dal msp.")

    special_names = _special_layer_names(special_layers)

    all_lines   = [e for e in msp.query('LINE')
                   if not _is_special(e, special_names)]
    all_arcs    = [e for e in msp.query('ARC')
                   if not _is_special(e, special_names)]
    all_plines  = [e for e in msp.query('LWPOLYLINE POLYLINE')
                   if not _is_special(e, special_names)]
    all_circles = [e for e in msp.query('CIRCLE')
                   if not _is_special(e, special_names)]
    all_splines = [e for e in msp.query('SPLINE')
                   if not _is_special(e, special_names)]
    all_ellipses = [e for e in msp.query('ELLIPSE')
                   if not _is_special(e, special_names)]

    if not all_lines and not all_arcs and not all_plines \
            and not all_circles and not all_splines and not all_ellipses:
        result.errors.append("Modelspace vuoto: nessuna geometria trovata.")
        result.is_valid = False
        return result

    # Separa spline chiuse (passo 3) da spline aperte (grafo passo 1)
    closed_splines = [s for s in all_splines if _spline_is_closed(s, tolerance)]
    open_splines   = [s for s in all_splines if not _spline_is_closed(s, tolerance)]

    # -------------------------------------------------------------------
    # PRE-PROCESSING: close_gaps solo su endpoint liberi
    # -------------------------------------------------------------------

    graph_pre = None
    node_decimals = max(round(-np.log10(tolerance * 2)), 1)

    if all_lines or all_arcs:
        graph_pre = build_node_graph(msp, decimals=node_decimals,
                                     exclude_layers=special_names)
        free = _free_endpoints(graph_pre, msp, node_decimals, special_names)
        
        if free:
            fixed = close_gaps(msp, free, tolerance)
            if fixed:
                all_lines = [e for e in msp.query('LINE')
                             if not _is_special(e, special_names)]
                all_arcs  = [e for e in msp.query('ARC')
                             if not _is_special(e, special_names)]
                graph_pre = None

    # Warning: spline aperte con endpoint liberi
    if open_splines:
        if graph_pre is None:
            graph_pre = build_node_graph(msp, decimals=node_decimals,
                                         exclude_layers=special_names)
        for spline in open_splines:
            s, e = spline_endpoints(spline)
            if s is None or e is None:
                continue
            s_r = round_point(s)
            e_r = round_point(e)
            if len(graph_pre.get(s_r, [])) < 2 or \
               len(graph_pre.get(e_r, [])) < 2:
                result.warnings.append(
                    "SPLINE con endpoint non connesso trovata — "
                    "gap tra SPLINE e altre entità gestito con una linea di congiunzione. "
                    "Verificare manualmente la correttezza del file."
                )
                break

    # -------------------------------------------------------------------
    # PASSO 1: LINE/ARC/SPLINE → grafo → loop → VirtualShape in memoria
    # -------------------------------------------------------------------
    virtual_shapes: List[VirtualShape] = []
    entities_in_loops: set = set()

    if all_lines or all_arcs or open_splines:
        graph = build_node_graph(msp, decimals=node_decimals,
                                 exclude_layers=special_names)
        loops = find_closed_loops(graph)
        # print(f"  [DEBUG] loop trovati nel grafo globale: {len(loops)}")
        # for i, loop in enumerate(loops):
        #     entities = [e.dxftype() for e, _ in loop]
        #     from .graph import spline_to_points
        #     from .geometry import arc_to_bulge
        #     print(f"    loop {i}: {len(loop)} entità → {entities}")
        loops = _deduplicate_loops(loops)
        
        if loops:
            branching_nodes = check_loop_ambiguity(loops, graph)
            if branching_nodes:
                result.warnings.append(
                    f"Geometria ambigua: {len(branching_nodes)} nodi con più di 2 "
                    f"connessioni all'interno dei loop chiusi. Verificare il risultato."
                )

            outer_loops, inner_loops = classify_loops(loops)
            
            entities_in_loops = {id(e) for loop in (outer_loops + inner_loops)
                                  for e, _ in loop}

            for loop in outer_loops:
                vs = _loop_to_virtual_shape(loop, LAYER_OUTER, COLOR_OUTER)
                if vs is not None:
                    virtual_shapes.append(vs)
            for loop in inner_loops:
                vs = _loop_to_virtual_shape(loop, LAYER_INNER, COLOR_INNER)
                if vs is not None:
                    virtual_shapes.append(vs)

        else:
            result.warnings.append(
                "Nessun loop trovato via grafo, uso polygonize come fallback.")
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

    # -------------------------------------------------------------------
    # PASSO 2: gerarchia — VirtualShape + LWPOLYLINE + CIRCLE + SPLINE chiuse
    # -------------------------------------------------------------------
    shapes = []

    for vs in virtual_shapes:
        shapes.append((vs, vs.polygon, 'VIRTUAL'))

    for pline in all_plines:
        poly = pline_to_polygon(pline)
        if poly is not None:
            shapes.append((pline, poly, 'LWPOLYLINE'))

    for circle in all_circles:
        poly = circle_to_polygon(circle)
        if poly is not None:
            shapes.append((circle, poly, 'CIRCLE'))

    for spline in closed_splines:
        poly = _spline_to_polygon(spline)
        if poly is not None:
            shapes.append((spline, poly, 'SPLINE'))

    if not shapes:
        result.errors.append("Nessuna geometria chiusa trovata dopo healing.")
        result.is_valid = False
        return result

    shapes.sort(key=lambda x: x[1].area, reverse=True)

    # print(f"  [DEBUG] shapes totali: {len(shapes)}")
    # for i, (obj, poly, tipo) in enumerate(shapes):
    #     print(f"    shape {i}: tipo={tipo} area={poly.area:.1f}")

    # Gerarchia padre-figlio
    classified_entity_ids: set = set()
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

        # print(f"  [DEBUG] shapes totali: {len(shapes)}")
        # for i, (obj, poly, tipo) in enumerate(shapes):
        #     print(f"    shape {i}: tipo={tipo} area={poly.area:.1f}")
        # print(f"  [DEBUG] fathers: {len(fathers)}")
        # for f_obj, f_poly, f_tipo, f_children in fathers:
        #     print(f"    father area={f_poly.area:.1f} tipo={f_tipo} children={len(f_children)}")

    # Corregge layer delle VirtualShape finite come children:
    # nel passo 1 erano outer (il grafo non vedeva le LWPOLYLINE),
    # la gerarchia le ha riclassificate, ora aggiorniamo layer e color.
    for _, _, _, children in fathers:
        for child_obj, child_poly, child_tipo in children:
            if child_tipo == 'VIRTUAL':
                child_obj.layer = LAYER_INNER
                child_obj.color = COLOR_INNER

    # Costruisce ForgeResult
    for father_obj, father_poly, father_tipo, children in fathers:
        outer = ForgeContour(polygon=father_poly, is_inner=False, layer=LAYER_OUTER)

        if father_tipo == 'VIRTUAL':
            classified_virtual_ids.add(id(father_obj))
        else:
            classified_entity_ids.add(id(father_obj))

        inners = []
        for child_obj, child_poly, child_tipo in children:
            if child_tipo == 'CIRCLE':
                diameter = child_obj.dxf.radius * 2
                layer = LAYER_HOLE if diameter < HOLE_DIAMETER_THRESHOLD else LAYER_INNER
            else:
                layer = LAYER_INNER

            inners.append(ForgeContour(polygon=child_poly, is_inner=True, layer=layer))

            if child_tipo == 'VIRTUAL':
                classified_virtual_ids.add(id(child_obj))
            else:
                classified_entity_ids.add(id(child_obj))

        # print(f"  fathers costruiti: {len(fathers)}")
        # for f_obj, f_poly, f_tipo, f_children in fathers:
        #     print(f"    father area={f_poly.area:.1f} tipo={f_tipo} children={len(f_children)}")

        custom = {}
        if special_layers:
            custom = _collect_special_entities(
                msp, special_layers,
                classified_entity_ids | entities_in_loops
            )

        result.parts.append(ForgePart(
            outer=outer, inners=inners,
            label=label, source_file=source_file,
            custom=custom,
        ))

        if data_injector is not None:
            try:
                testi = extract_texts_from_msp(msp)
                injected = data_injector(result.parts[-1], testi)
                if injected:
                    result.parts[-1].custom.update(injected)
            except Exception as ex:
                result.warnings.append(
                    f"data_injector fallito su {label}: {ex}"
                )

    # -------------------------------------------------------------------
    # SCRITTURA MSP — solo se write_to_msp=True
    # -------------------------------------------------------------------
    if write_to_msp:
        # Entità nei loop con spline — NON vengono cancellate
        spline_loop_entity_ids: set = set()
        for vs in virtual_shapes:
            if vs.has_spline:
                for entity, _ in vs.loop:
                    spline_loop_entity_ids.add(id(entity))

        # Materializza VirtualShape nel msp
        for vs in virtual_shapes:
            entity = _write_virtual_shape(msp, vs)
            if entity is not None:
                print(f"  [WRITE] {entity.dxftype()} layer={entity.dxf.layer} area={vs.polygon.area:.1f}")
            if entity is not None:
                vs.entity = entity
                classified_entity_ids.add(id(entity))
            else:
                for orig_entity, _ in vs.loop:
                    classified_entity_ids.add(id(orig_entity))

        # Cancella LINE/ARC/SPLINE originali usati nei loop
        # MA NON quelli nei loop con spline
        for entity in list(msp.query('LINE ARC SPLINE')):
            if id(entity) in entities_in_loops \
               and id(entity) not in spline_loop_entity_ids:
                msp.delete_entity(entity)

        # Assegna layer/colori alle entità reali
        for father_obj, father_poly, father_tipo, children in fathers:
            if father_tipo not in ('VIRTUAL',):
                father_obj.dxf.layer = LAYER_OUTER
                father_obj.dxf.color = COLOR_OUTER

            for child_obj, child_poly, child_tipo in children:
                if child_tipo == 'VIRTUAL':
                    continue
                if child_tipo == 'CIRCLE':
                    diameter = child_obj.dxf.radius * 2
                    layer = LAYER_HOLE if diameter < HOLE_DIAMETER_THRESHOLD else LAYER_INNER
                    color = COLOR_HOLE if diameter < HOLE_DIAMETER_THRESHOLD else COLOR_INNER
                else:
                    layer = LAYER_INNER
                    color = COLOR_INNER
                child_obj.dxf.layer = layer
                child_obj.dxf.color = color

        # Trash
        for entity in list(msp):
            if id(entity) in classified_entity_ids:
                continue
            layer = entity.dxf.layer if entity.dxf.hasattr("layer") else ""
            if layer.upper() in STRUCTURAL_LAYERS:
                continue
            # if special_layers and layer.lower() in {k.lower() for k in special_layers}:
                #continue
            if special_layers and layer.lower() in {k.lower() for k in special_layers}:
                # trova il work_type per questo layer
                work_type = next(
                    v for k, v in special_layers.items()
                    if k.lower() == layer.lower()
                )
                target_layer, target_color = WORK_TYPE_TO_LAYER.get(
                    work_type, (TRASH_LAYER, COLOR_TRASH)
                )
                entity.dxf.layer = target_layer
                entity.dxf.color = target_color
                continue

            if keep_trash:
                entity.dxf.layer = TRASH_LAYER
                entity.dxf.color = COLOR_TRASH
            else:
                msp.delete_entity(entity)

    return result


# ---------------------------------------------------------------------------
# Raccolta entità speciali
# ---------------------------------------------------------------------------

def _collect_special_entities(msp, special_layers: dict,
                               classified_ids: set) -> dict:
    """
    Raccoglie e misura le entità su layer speciali.
    Non tocca le entità già classificate.
    """
    totals = {}

    for entity in msp:
        if id(entity) in classified_ids:
            continue
        layer = entity.dxf.layer.lower() if entity.dxf.hasattr("layer") else ""
        for layer_key, work_type in special_layers.items():
            if layer_key.lower() in layer:
                length = entity_length(entity)
                totals["total_engrave_length"] = (
                    totals.get("total_engrave_length", 0.0) + length
                )
                if work_type == "bending":
                    totals["bending_lines"] = totals.get("bending_lines", 0) + 1
                break

    for k, v in totals.items():
        if isinstance(v, float):
            totals[k] = round(v, 4)

    return totals