

"""
workflow/write.py
---------------------
Materializza un ForgeResult su uno o più documenti ezdxf.

Posizione nella pipeline:
    heal()      → geometria pura (ForgeResult con parts, trash, _virtual_shapes)
    detect()    → semantica (geometry_hints, part.custom)
    write()     → materializza LWPOLYLINE + assegna layer/colori sul msp    ← qui
    split()     → produce un documento separato per ogni part               ← qui
    inject()    → serializza metriche nel JSON/XDATA

Responsabilità:
    write()  → materializza i VirtualShape come LWPOLYLINE nel msp
               assegna layer strutturali (outer, inner, hole)
               assegna layer lavorazioni (bending, countersink, engrave...)
               rimuove LINE/ARC originali sostituite da LWPOLYLINE
               aggiorna part.entity_ids: swap id(VS) → id(LWPOLYLINE) materializzata

    split()  → crea un nuovo documento ezdxf per ogni ForgePart
               copia le entità usando part.entity_ids — nessun calcolo geometrico

NON è responsabilità di questo modulo:
    - decidere cosa è countersink o threaded     → detect()
    - serializzare metriche                      → inject()
    - aprire o salvare file su disco             → il chiamante
"""

from __future__ import annotations

import os
from typing import Callable, Optional

import ezdxf

from ..model import ForgeResult, ForgePart, Hole, HOLE_TYPE_COUNTERSINK, HOLE_TYPE_THREADED
from ..adapters.dxf.copy_adapter import copy_entity
from ..adapters.dxf.geometry_adapter import get_representative_point
from ..adapters.dxf.virtual_adapter import _write_virtual_shape
from ..rules.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    COLOR_OUTER, COLOR_INNER, COLOR_HOLE,
    STRUCTURAL_LAYERS, WORK_LAYERS,
    TRASH_LAYER, COLOR_TRASH,
    WORK_TYPE_TO_LAYER,
    HOLE_DIAMETER_THRESHOLD,
    ALL_FORGE_LAYERS,
    color_for_layer,
)

_HOLE_TYPE_TO_WORK_TYPE = {
    HOLE_TYPE_COUNTERSINK: "countersink",
    HOLE_TYPE_THREADED:    "threaded_hole",
}


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def write(
    msp,
    result:     ForgeResult,
    keep_trash: bool = True,
) -> None:
    """
    Materializza il ForgeResult sul msp originale.

    Deve essere chiamato DOPO heal() — e opzionalmente dopo detect()
    se si vogliono anche i layer di lavorazione.

    Fase 1 — strutturale (sempre):
        - scrive i Contour come LWPOLYLINE nel msp
        - aggiorna part.entity_ids: swap id(ctx) → id(LWPOLYLINE) per i non-spline
        - assegna layer/colori strutturali (outer, inner, hole) alle entità reali
        - rimuove le LINE/ARC originali sostituite dai Contour

    Fase 2 — lavorazioni (solo se detect() è stato chiamato):
        - assegna layer lavorazioni (bending, countersink, engrave...)
          leggendo geometry_hints e Hole.hole_type da result
    """
    for ctx in result._virtual_shapes:
        if id(ctx) in result._suppressed_vs_ids:
            continue
        lwpoly = _write_virtual_shape(msp, ctx)
        if lwpoly is not None:
            part = result._vs_to_part.get(id(ctx))
            if part is not None:
                part.entity_ids.discard(id(ctx))
                part.entity_ids.add(id(lwpoly))
        else:
            # has_spline=True: le entità originali restano nel msp
            part = result._vs_to_part.get(id(ctx))
            if part is not None:
                part.entity_ids.discard(id(ctx))
                for entity, _ in ctx.loop:
                    part.entity_ids.add(id(entity))

    _remove_superseded_line_arc(msp, result)
    _assign_structural_layers(msp, result)

    entity_to_work = _build_work_index(result)
    special_map    = _build_special_map(result)

    _setup_layers(msp.doc)

    for entity in list(msp):
        if not entity.dxf.hasattr("layer"):
            continue

        entity_id = id(entity)
        layer     = entity.dxf.layer
        work_type = entity_to_work.get(entity_id) or special_map.get(layer.lower())

        if work_type is not None:
            target_layer, _ = WORK_TYPE_TO_LAYER.get(
                work_type, (TRASH_LAYER, COLOR_TRASH)
            )
            entity.dxf.layer = target_layer
            entity.dxf.color = 256
        elif layer.upper() in STRUCTURAL_LAYERS:
            entity.dxf.color = 256
            continue
        elif keep_trash:
            entity.dxf.layer = TRASH_LAYER
            entity.dxf.color = 256
        else:
            msp.delete_entity(entity)


ANNOTATION_TYPES = frozenset({"TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER"})
DEFAULT_MIN_PART_AREA = 50.0  # mm²


def split(
    msp,
    result:              ForgeResult,
    output_folder:       str,
    namer:               Optional[Callable] = None,
    keep_trash:          bool               = False,
    include_annotations: bool               = True,
    min_area:            float              = DEFAULT_MIN_PART_AREA,
    exclude_types:       set                = None,
    on_part:             Optional[Callable] = None,
) -> list:
    """
    Produce un documento ezdxf separato per ogni ForgePart.
    ...
    """
    os.makedirs(output_folder, exist_ok=True)

    entity_to_work     = _build_work_index(result)
    special_map        = _build_special_map(result)
    entity_to_structural = {}
    for p in result.parts:
        if p.outer.entity is not None:
            entity_to_structural[id(p.outer.entity)] = p.outer.layer
        for inner in p.inners:
            if inner.entity is not None:
                entity_to_structural[id(inner.entity)] = inner.layer
        for hole in p.holes:
            if hole.entity is not None:
                entity_to_structural[id(hole.entity)] = hole.layer

    generated = []
    src_doc   = msp.doc

    for i, part in enumerate(result.parts):
        if min_area > 0 and part.outer.polygon.area < min_area:
            result.warnings.append(
                f"Part {i} scartato: area {part.outer.polygon.area:.2f} mm² "
                f"sotto soglia {min_area} mm²"
            )
            continue

        name     = namer(i, part) if namer else f"{part.label}_P{i + 1}"
        out_path = os.path.join(output_folder, f"{name}.dxf")

        doc_out = ezdxf.new(dxfversion="R2010")
        doc_out.header['$INSUNITS']    = src_doc.header.get('$INSUNITS', 4)
        doc_out.header['$MEASUREMENT'] = src_doc.header.get('$MEASUREMENT', 1)
        _setup_layers(doc_out)
        msp_out = doc_out.modelspace()

        vs_swap = _write_virtual_shapes_to_msp(msp_out, result, part)

        effective_ids = set()
        for eid in part.entity_ids:
            effective_ids.add(vs_swap.get(eid, eid))

        for entity in msp:
            if not entity.dxf.hasattr("layer"):
                continue
            if exclude_types and entity.dxftype() in exclude_types:
                continue

            is_annotation = entity.dxftype() in ANNOTATION_TYPES
            if is_annotation:
                if not include_annotations:
                    continue
                pt = get_representative_point(entity)
                if pt is None or not part.outer.polygon.covers(pt):
                    continue
            else:
                if id(entity) not in effective_ids:
                    continue

            new_entity = copy_entity(entity, msp_out)
            if new_entity is None:
                continue

            entity_id = id(entity)
            layer     = entity.dxf.layer
            work_type = entity_to_work.get(entity_id) or special_map.get(layer.lower())

            structural_layer = entity_to_structural.get(entity_id)
            if structural_layer is not None:
                new_entity.dxf.layer = structural_layer
                new_entity.dxf.color = 256
            elif work_type is not None:
                target_layer, _ = WORK_TYPE_TO_LAYER.get(work_type, (TRASH_LAYER, COLOR_TRASH))
                new_entity.dxf.layer = target_layer
                new_entity.dxf.color = 256
            elif layer.upper() in STRUCTURAL_LAYERS or layer.upper() in WORK_LAYERS:
                new_entity.dxf.color = 256
            elif keep_trash:
                new_entity.dxf.layer = TRASH_LAYER
                new_entity.dxf.color = 256

        if on_part is not None:
            on_part(part, doc_out, out_path)

        doc_out.saveas(out_path)
        generated.append(out_path)
        part.label = name

    return generated


# ---------------------------------------------------------------------------
# Helpers interni
# ---------------------------------------------------------------------------

def _assign_structural_layers(msp, result: ForgeResult) -> None:
    """ Assegna i layer strutturali e imposta il colore a BYLAYER (256). """
    for part in result.parts:
        for contour in [part.outer] + part.inners:
            if contour.entity is not None:
                contour.entity.dxf.layer = contour.layer
                contour.entity.dxf.color = 256  # BYLAYER

        for hole in part.holes:
            if hole.entity is not None:
                hole.entity.dxf.layer = hole.layer
                hole.entity.dxf.color = 256  # BYLAYER


def _remove_superseded_line_arc(msp, result: ForgeResult) -> None:
    """
    Rimuove dal msp le LINE e ARC originali assorbite da un loop in heal().

    Usa result._entities_in_loops_ids — fonte di verità immutabile prodotta
    da heal(). Non dipende da trash_entities o classified_entities.
    """
    special_layer_names = {k.lower() for k in result.special_layers} if result.special_layers else set()
    to_delete = [
        e for e in list(msp)
        if e.dxftype() in ("LINE", "ARC")
        and id(e) in result._entities_in_loops_ids
        and (not e.dxf.hasattr("layer") or e.dxf.layer.lower() not in special_layer_names)
    ]
    # to_delete = [
    #     e for e in list(msp)
    #     if e.dxftype() in ("LINE", "ARC")
    #     and id(e) in result._entities_in_loops_ids
    # ]
    for e in to_delete:
        msp.delete_entity(e)


# def _build_work_index(result: ForgeResult) -> dict:
#     """
#     Costruisce un indice id(entity) → work_type da:
#         - part.holes con hole_type classificato da detect()
#         - part.geometry_hints.bend_line_ids (linee di piega)

#     I fori plain non entrano nell'indice — rimangono su LAYER_HOLE.
#     I fori unknown (detect() non chiamato) non entrano — nessuna diagnosi.
#     """
#     index = {}
#     for part in result.parts:
#         for hole in part.holes:
#             # print(f"[work_index] hole_type={hole.hole_type} entity={hole.entity} outer_entity={hole.outer_entity}")
#             if hole.hole_type == HOLE_TYPE_COUNTERSINK and hole.outer_entity is not None:
#                 index[id(hole.outer_entity)] = "countersink"
#             elif hole.hole_type == HOLE_TYPE_THREADED and hole.entity is not None:
#                 index[id(hole.entity)] = "threaded_hole"
#                 # print(f"  → indicizzato id={id(hole.entity)} come threaded_hole")

#         for eid in part.geometry_hints.bend_line_ids:
#             index[eid] = "bending"
#             part.entity_ids.add(eid)

#     # print(f"[work_index] totale: {len(index)} entità")
#     return index

def _build_work_index(result: ForgeResult) -> dict:
    """
    Costruisce un indice id(entity) → work_type da:
        - part.holes con hole_type classificato da detect()
        - part.bending_lines (linee di piega)

    I fori plain non entrano nell'indice — rimangono su LAYER_HOLE.
    I fori unknown (detect() non chiamato) non entrano — nessuna diagnosi.
    """
    index = {}
    for part in result.parts:
        for hole in part.holes:
            if hole.hole_type == HOLE_TYPE_COUNTERSINK and hole.outer_entity is not None:
                index[id(hole.outer_entity)] = "countersink"
            elif hole.hole_type == HOLE_TYPE_THREADED and hole.entity is not None:
                index[id(hole.entity)] = "threaded_hole"

        for bl in part.bending_lines:
            eid = id(bl.entity)
            index[eid] = "bending"
            part.entity_ids.add(eid)

    return index


def _build_special_map(result: ForgeResult) -> dict:
    """
    Costruisce un indice layer_name → work_type da result.special_layers.
    """
    if not result.special_layers:
        return {}
    return {k.lower(): v.lower() for k, v in result.special_layers.items()}


# def _setup_layers(doc) -> None:
#     """
#     Crea i layer forge standard nel documento di output.
#     """
#     for name, color in ALL_FORGE_LAYERS.items():
#         if name not in doc.layers:
#             layer = doc.layers.new(name)
#             layer.color = color
            
def _setup_layers(doc) -> None:
    """
    Crea o aggiorna i layer forge standard nel documento, 
    garantendo che il colore del layer sia quello stabilito.
    """
    for name, color in ALL_FORGE_LAYERS.items():
        if name not in doc.layers:
            layer = doc.layers.new(name)
        else:
            layer = doc.layers.get(name)
        
        layer.color = color  # Fissa il colore a livello di Layer nella tabella DXF


def _all_classified_ids(result: ForgeResult) -> set:
    """
    Restituisce gli id() di tutte le entità già classificate da detect().
    Se detect() non è stato chiamato, restituisce un insieme vuoto.
    """
    return {id(ce.entity) for ce in result.classified_entities if ce.entity is not None}


def _write_virtual_shapes_to_msp(msp_out, result: ForgeResult, part: ForgePart) -> dict:
    """
    Materializza i VirtualShape del part corrente nel msp_out figlio.
    
    Non tocca result né part.entity_ids — restituisce uno swap dict
    id(VS) → id(lwpoly) che split() usa localmente per filtrare le entità.
    """
    vs_swap = {}  # id(VS) → id(lwpoly) locale al figlio
    
    for vs in result._virtual_shapes:
        if result._vs_to_part.get(id(vs)) is not part:
            continue
        if id(vs) in result._suppressed_vs_ids:
            continue
        
        lwpoly = _write_virtual_shape(msp_out, vs)
        if lwpoly is not None:
            vs_swap[id(vs)] = id(lwpoly)
        else:
            # has_spline=True: registra le entità originali
            for entity, _ in vs.loop:
                vs_swap[id(vs)] = id(entity)  # placeholder
    
    return vs_swap