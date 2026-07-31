

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

from ..adapters.dxf.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    TRASH_LAYER,
    WORK_TYPE_TO_LAYER,
    ALL_FORGE_LAYERS,
    ROLE_TO_LAYER,       # ← non più definito localmente
    color_for_layer,
)
from ..rules.palette import COLOR_OUTER, COLOR_INNER, COLOR_HOLE, COLOR_TRASH

# STRUCTURAL_LAYERS → sostituisci con:
_STRUCTURAL_LAYER_NAMES = {LAYER_OUTER.upper(), LAYER_INNER.upper(), LAYER_HOLE.upper()}

# WORK_LAYERS → se usi solo il check, sostituisci con:
_WORK_LAYER_NAMES = set(n.upper() for n, _ in WORK_TYPE_TO_LAYER.values())

_HOLE_TYPE_TO_WORK_TYPE = {
    HOLE_TYPE_COUNTERSINK: "countersink",
    HOLE_TYPE_THREADED:    "threaded_hole",
}

ROLE_TO_LAYER = {
    "outer": LAYER_OUTER,
    "inner": LAYER_INNER,
    "hole":  LAYER_HOLE,
}

# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def write(
    msp,
    result:     ForgeResult,
    keep_trash: bool = True,
) -> None:
    entity_to_work = _build_work_index(result)
    special_map    = _build_special_map(result)

    for ctx in result._virtual_shapes:
        if id(ctx) in result._suppressed_vs_ids:
            continue

        lwpoly = _write_virtual_shape(msp, ctx)
        if lwpoly is not None:
            part = result._vs_to_part.get(id(ctx))
            if part is not None:
                part.entity_ids.discard(id(ctx))
                part.entity_ids.add(id(lwpoly))
                for contour in [part.outer] + part.inners:
                    if contour.vs_id == id(ctx):
                        layer = ROLE_TO_LAYER.get(contour.role, LAYER_INNER)
                        lwpoly.dxf.layer = layer
                        lwpoly.dxf.color = 256
                        if contour.role not in (ContourRole.OUTER, ContourRole.INNER, ContourRole.UNKNOWN):
                            entity_to_work[id(lwpoly)] = contour.role.value.lower()
                        break
        else:
            part = result._vs_to_part.get(id(ctx))
            if part is not None:
                part.entity_ids.discard(id(ctx))
                for entity, _ in ctx.loop:
                    part.entity_ids.add(id(entity))

    _remove_superseded_line_arc(msp, result)
    _assign_structural_layers(msp, result)

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
        elif layer.upper() in _STRUCTURAL_LAYER_NAMES:
            entity.dxf.color = 256
            continue
        elif keep_trash:
            entity.dxf.layer = TRASH_LAYER
            entity.dxf.color = 256
        else:
            msp.delete_entity(entity)

# def write(
#     msp,
#     result:     ForgeResult,
#     keep_trash: bool = True,
# ) -> None:
#     """
#     Materializza il ForgeResult sul msp originale.

#     Deve essere chiamato DOPO heal() — e opzionalmente dopo detect()
#     se si vogliono anche i layer di lavorazione.

#     Fase 1 — strutturale (sempre):
#         - scrive i Contour come LWPOLYLINE nel msp
#         - aggiorna part.entity_ids: swap id(ctx) → id(LWPOLYLINE) per i non-spline
#         - assegna layer/colori strutturali (outer, inner, hole) alle entità reali
#         - rimuove le LINE/ARC originali sostituite dai Contour

#     Fase 2 — lavorazioni (solo se detect() è stato chiamato):
#         - assegna layer lavorazioni (bending, countersink, engrave...)
#           leggendo geometry_hints e Hole.hole_type da result
#     """
    
#     for ctx in result._virtual_shapes:
#         if id(ctx) in result._suppressed_vs_ids:
#             continue

#         lwpoly = _write_virtual_shape(msp, ctx)
#         if lwpoly is not None:
#             part = result._vs_to_part.get(id(ctx))
#             if part is not None:
#                 part.entity_ids.discard(id(ctx))
#                 part.entity_ids.add(id(lwpoly))
#                 # propaga il role del ForgeContour sulla LWPOLYLINE
#                 for contour in [part.outer] + part.inners:
#                     if contour.vs_id == id(ctx):
#                         layer = ROLE_TO_LAYER.get(contour.role, LAYER_INNER)
#                         lwpoly.dxf.layer = layer
#                         lwpoly.dxf.color = 256
#                         print(f"DEBUG vs check: contour.vs_id={contour.vs_id}, id(ctx)={id(ctx)}, role={contour.role}")
#                         break
#         else:
#             # has_spline=True: le entità originali restano nel msp
#             part = result._vs_to_part.get(id(ctx))
#             if part is not None:
#                 part.entity_ids.discard(id(ctx))
#                 for entity, _ in ctx.loop:
#                     part.entity_ids.add(id(entity))

#     _remove_superseded_line_arc(msp, result)
#     _assign_structural_layers(msp, result)

#     entity_to_work = _build_work_index(result)
#     special_map    = _build_special_map(result)

#     _setup_layers(msp.doc)

#     for entity in list(msp):
#         print(f"DEBUG write loop: id={id(entity)}, layer={entity.dxf.layer}, in_work={id(entity) in entity_to_work}, in_special={entity.dxf.layer.lower() in special_map}")
#         if not entity.dxf.hasattr("layer"):
#             continue

#         entity_id = id(entity)
#         layer     = entity.dxf.layer
#         work_type = entity_to_work.get(entity_id) or special_map.get(layer.lower())

#         if work_type is not None:
#             target_layer, _ = WORK_TYPE_TO_LAYER.get(
#                 work_type, (TRASH_LAYER, COLOR_TRASH)
#             )
#             entity.dxf.layer = target_layer
#             entity.dxf.color = 256
#         elif layer.upper() in _STRUCTURAL_LAYER_NAMES:
#             entity.dxf.color = 256
#             continue
#         elif keep_trash:
#             entity.dxf.layer = TRASH_LAYER
#             entity.dxf.color = 256
#         else:
#             msp.delete_entity(entity)

    
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
        if p.outer.source_ref is not None:
            entity_to_structural[id(p.outer.source_ref)] = ROLE_TO_LAYER.get(p.outer.role, LAYER_OUTER)
        for inner in p.inners:
            if inner.source_ref is not None:
                entity_to_structural[id(inner.source_ref)] = ROLE_TO_LAYER.get(inner.role, LAYER_INNER)
        for hole in p.holes:
            if hole.source_ref is not None:
                entity_to_structural[id(hole.source_ref)] = ROLE_TO_LAYER.get(hole.role, LAYER_HOLE)

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
            elif layer.upper() in _STRUCTURAL_LAYER_NAMES or layer.upper() in _WORK_LAYER_NAMES:
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
    for part in result.parts:
        for contour in [part.outer] + part.inners:
            print(f"DEBUG assign: role={contour.role}, source_ref={contour.source_ref is not None}, vs_id={contour.vs_id}")
            if contour.source_ref is not None:
                contour.source_ref.dxf.layer = ROLE_TO_LAYER.get(contour.role, LAYER_OUTER)
                contour.source_ref.dxf.color = 256

        for hole in part.holes:
            if hole.source_ref is not None:
                hole.source_ref.dxf.layer = ROLE_TO_LAYER.get(hole.role, LAYER_HOLE)
                hole.source_ref.dxf.color = 256


def _remove_superseded_line_arc(msp, result: ForgeResult) -> None:
    """
    Rimuove dal msp le LINE e ARC originali assorbite da un loop in heal().

    Usa result._entities_in_loops_ids — fonte di verità immutabile prodotta
    da heal(). Non dipende da trash_entities o classified_entities.
    """
    special_layer_names = {k.lower() for k in result.label_map} if result.label_map else set()
    to_delete = [
        e for e in list(msp)
        if e.dxftype() in ("LINE", "ARC")
        and id(e) in result._entities_in_loops_ids
        and (not e.dxf.hasattr("layer") or e.dxf.layer.lower() not in special_layer_names)
    ]

    for e in to_delete:
        msp.delete_entity(e)



def _build_work_index(result: ForgeResult) -> dict:
    index = {}
    
    # entità classificate da detect() (engrave, marking, ecc.)
    for ce in result.classified_entities:
        if ce.source_ref is not None:
            index[id(ce.source_ref)] = ce.work_type.lower()

    for part in result.parts:
        for hole in part.holes:
            if hole.hole_type == HOLE_TYPE_COUNTERSINK and hole.outer_source_ref is not None:
                index[id(hole.outer_source_ref)] = "countersink"
            elif hole.hole_type == HOLE_TYPE_THREADED and hole.source_ref is not None:
                index[id(hole.source_ref)] = "threaded_hole"

        for bl in part.bending_lines:
            eid = id(bl.source_ref)
            index[eid] = "bending"
            part.entity_ids.add(eid)

    return index


def _build_special_map(result: ForgeResult) -> dict:
    return {}   # label_map non esiste più nel core — l'adapter ha già tradotto in role

            
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
    return {id(ce.source_ref) for ce in result.classified_entities if ce.source_ref is not None}


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