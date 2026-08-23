

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
from shapely.geometry import Point

from ..model import ForgeResult, ForgePart, Hole, HOLE_TYPE_COUNTERSINK, HOLE_TYPE_THREADED
from ..adapters.dxf.copy_adapter import copy_entity
from ..adapters.dxf.geometry_adapter import get_representative_point
from ..adapters.dxf.virtual_adapter import _write_virtual_shape
from ..model.role import ContourRole

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

        # Le primitive chiuse durevoli (CIRCLE, POLYLINE/LWPOLYLINE/SPLINE)
        # sono già presenti nel documento nella loro entità sorgente e devono
        # rimanere tali. Non le riscriviamo come LWPOLYLINE: altrimenti si
        # genera una copia di fallback con layer di default InnerContour/Hole
        # che non rispetta la classificazione finale.
        if len(ctx.loop) == 1:
            edge, _ = ctx.loop[0]
            source_ref = getattr(edge, "source_ref", None)
            if source_ref is not None and source_ref.dxftype() not in ("LINE", "ARC"):
                continue

        lwpoly = _write_virtual_shape(msp, ctx)
        if lwpoly is not None:
            part = result._vs_to_part.get(id(ctx))
            if part is not None:
                part.entity_ids.discard(id(ctx))
                part.entity_ids.add(id(lwpoly))
                matched = False
                for contour in [part.outer] + part.inners:
                    if contour.vs_id == id(ctx):
                        layer = ROLE_TO_LAYER.get(contour.role, LAYER_INNER)
                        lwpoly.dxf.layer = layer
                        lwpoly.dxf.color = 256
                        if contour.role not in (ContourRole.OUTER, ContourRole.INNER, ContourRole.UNKNOWN):
                            entity_to_work[id(lwpoly)] = contour.role.value.lower()
                        matched = True
                        break
                if not matched:
                    for hole in part.holes:
                        if hole.vs_id == id(ctx):
                            hole.source_ref = lwpoly
                            layer = ROLE_TO_LAYER.get(hole.role, LAYER_HOLE)
                            lwpoly.dxf.layer = layer
                            lwpoly.dxf.color = 256
                            if hole.hole_type == HOLE_TYPE_COUNTERSINK:
                                entity_to_work[id(lwpoly)] = "countersink"
                            elif hole.hole_type == HOLE_TYPE_THREADED:
                                entity_to_work[id(lwpoly)] = "threaded_hole"
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

    for part in result.parts:
        _materialize_derived_bending_lines(msp, part)

    
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
        vs_passthrough_structural = _collect_vs_passthrough_structural(result, part)
        consumed_source_ids = _collect_consumed_virtual_source_ids(result, part, vs_swap)

        effective_ids = set()
        for eid in part.entity_ids:
            swapped = vs_swap.get(eid, eid)
            if isinstance(swapped, list):
                effective_ids.update(swapped)
            else:
                effective_ids.add(swapped)

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
                if pt is None:
                    continue
                # Converti tupla (x, y) in Point Shapely
                pt_geom = Point(pt)
                if not part.outer.polygon.covers(pt_geom):
                    continue
            else:
                if id(entity) not in effective_ids:
                    continue
                if id(entity) in consumed_source_ids:
                    # Questo source_ref è già stato materializzato come
                    # VirtualShape nel file figlio: non duplicarlo col layer
                    # originale del DXF sorgente.
                    continue

            new_entity = copy_entity(entity, msp_out)
            if new_entity is None:
                continue

            entity_id = id(entity)
            layer     = entity.dxf.layer
            work_type = entity_to_work.get(entity_id) or special_map.get(layer.lower())

            structural_layer = (
                entity_to_structural.get(entity_id)
                or vs_passthrough_structural.get(entity_id)
            )
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

        _materialize_derived_bending_lines(msp_out, part)

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
            ref = contour.source_ref
            if ref is not None and getattr(ref, "is_alive", True):
                ref.dxf.layer = ROLE_TO_LAYER.get(contour.role, LAYER_OUTER)
                ref.dxf.color = 256

        for hole in part.holes:
            ref = hole.source_ref
            if ref is not None and getattr(ref, "is_alive", True):
                ref.dxf.layer = ROLE_TO_LAYER.get(hole.role, LAYER_HOLE)
                ref.dxf.color = 256


def _remove_superseded_line_arc(msp, result: ForgeResult) -> None:
    """
    Rimuove dal msp solo le LINE e ARC originali assorbite da un loop in heal().

    Le primitive chiuse durevoli (CIRCLE, POLYLINE/LWPOLYLINE chiusa, SPLINE)
    devono invece rimanere sul documento come entità originali e poi ricevere
    il layer strutturale corretto in _assign_structural_layers().

    Usa result._entities_in_loops_ids — fonte di verità immutabile prodotta
    da heal(). Non dipende da trash_entities o classified_entities.
    """
    special_layer_names = {k.lower() for k in result.label_map} if result.label_map else set()
    superseded_types = ("LINE", "ARC")

    to_delete = [
        e for e in list(msp)
        if e.dxftype() in superseded_types
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
            if (
                bl.source_ref is not None
                and hasattr(bl.source_ref, "dxftype")
                and bl.source_ref.dxftype() == "LINE"
            ):
                eid = id(bl.source_ref)
                index[eid] = "bending"
                part.entity_ids.add(eid)

        for eng in part.engrave_lines:
            if eng.source_ref is not None:
                eid = id(eng.source_ref)
                index[eid] = "engrave"
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
    id(VS) → id(lwpoly) oppure id(VS) → list[id(entity)] per passthrough.
    """
    vs_swap = {}  # id(VS) → id(lwpoly) locale al figlio
    
    for vs in result._virtual_shapes:
        if result._vs_to_part.get(id(vs)) is not part:
            continue
        if id(vs) in result._suppressed_vs_ids:
            continue
        if id(vs) not in part.entity_ids:
            # Già materializzato da write() sul documento sorgente: write()
            # ha rimpiazzato id(vs) con id(lwpoly) in part.entity_ids, che
            # verrà copiato nel figlio dal loop principale di split() —
            # non ri-materializzare qui, altrimenti si duplica l'entità.
            continue
        
        lwpoly = _write_virtual_shape(msp_out, vs)
        if lwpoly is not None:
            vs_swap[id(vs)] = id(lwpoly)
        else:
            # has_spline=True: registra tutte le entità originali del loop.
            vs_swap[id(vs)] = [id(entity) for entity, _ in vs.loop]
    
    return vs_swap


def _materialize_derived_bending_lines(msp_out, part: ForgePart) -> None:
    """Scrive bending line derivate da edge non-LINE come primitive Forge."""
    layer_name, _ = WORK_TYPE_TO_LAYER.get("bending", (TRASH_LAYER, COLOR_TRASH))
    seen = set()
    for bl in part.bending_lines:
        src = bl.source_ref
        if src is not None and hasattr(src, "dxftype") and src.dxftype() == "LINE":
            continue
        coords = list(bl.geometry.coords) if bl.geometry is not None else []
        if len(coords) < 2:
            continue
        start = coords[0]
        end = coords[-1]
        key = (round(start[0], 6), round(start[1], 6), round(end[0], 6), round(end[1], 6))
        if key in seen:
            continue
        seen.add(key)
        msp_out.add_line(start, end, dxfattribs={"layer": layer_name, "color": 256})


def _collect_vs_passthrough_structural(result: ForgeResult, part: ForgePart) -> dict:
    """Mappa id(entità originale) -> layer strutturale per VS con spline."""
    mapping = {}
    for vs in result._virtual_shapes:
        if result._vs_to_part.get(id(vs)) is not part:
            continue
        if id(vs) in result._suppressed_vs_ids:
            continue
        if not getattr(vs, "has_spline", False):
            continue
        target_layer = vs.layer if getattr(vs, "layer", "") else LAYER_OUTER
        for entity, _ in vs.loop:
            mapping[id(entity)] = target_layer
    return mapping


def _collect_consumed_virtual_source_ids(result: ForgeResult, part: ForgePart, vs_swap: dict) -> set:
    """
    Restituisce gli id(entità sorgente) dei loop virtuali già materializzati
    nel figlio come nuova entità (id(vs) -> id(lwpoly)).

    Queste entità non vanno ricopiate da msp sorgente per evitare duplicati
    su layer originali non-forge.
    """
    consumed = set()
    for vs in result._virtual_shapes:
        if result._vs_to_part.get(id(vs)) is not part:
            continue
        swap = vs_swap.get(id(vs))
        if swap is None or isinstance(swap, list):
            continue
        for edge, _ in getattr(vs, "loop", []):
            source_ref = getattr(edge, "source_ref", None)
            if source_ref is not None:
                consumed.add(id(source_ref))
    return consumed