


"""DXF write helpers for ForgeResult materialization."""

from __future__ import annotations

import os
from typing import Callable, Optional, Set

import ezdxf
from shapely.geometry import Point

from ..model import ForgeResult, ForgePart, Hole, HOLE_TYPE_COUNTERSINK, HOLE_TYPE_THREADED
from ..adapters.dxf.geometry_adapter import get_representative_point
from ..adapters.dxf.exporter import write_contour_to_msp
from ..adapters.dxf.adapter import entity_to_primitive
from ..model.role import ContourRole
from ..core.primitives import CircleSeg, SplineSeg

from ..adapters.dxf.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    TRASH_LAYER,
    WORK_TYPE_TO_LAYER,
    ALL_FORGE_LAYERS,
    ROLE_TO_LAYER,
    color_for_layer,
)
from ..rules.palette import COLOR_OUTER, COLOR_INNER, COLOR_HOLE, COLOR_TRASH

_STRUCTURAL_LAYER_NAMES = {LAYER_OUTER.upper(), LAYER_INNER.upper(), LAYER_HOLE.upper()}
_WORK_LAYER_NAMES = set(n.upper() for n, _ in WORK_TYPE_TO_LAYER.values())

_HOLE_TYPE_TO_WORK_TYPE = {
    HOLE_TYPE_COUNTERSINK: "countersink",
    HOLE_TYPE_THREADED:    "threaded_hole",
}

ANNOTATION_TYPES = frozenset({"TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER"})
DEFAULT_MIN_PART_AREA = 50.0  # mm²


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def write(
    msp,
    result: ForgeResult,
    keep_trash: bool = True,
    filter_part: Optional[Callable[[ForgePart], bool]] = None,
    include_annotations: bool = True,
) -> None:
    """
    Scrive un ForgeResult in un modelspace DXF.
    
    Args:
        msp: Modelspace di destinazione
        result: Risultato da materializzare
        keep_trash: Se True mantiene le entità non classificate su TRASH_LAYER
        filter_part: Callable opzionale per filtrare quali parti scrivere
        include_annotations: Se True include annotazioni (testi, quote, ecc.)
    """
    entity_to_work = _build_work_index(result)

    # --- Materializza contorni e fori ---
    for part in result.parts:
        # Applica il filtro se presente
        if filter_part is not None and not filter_part(part):
            continue

        for contour in [part.outer] + part.inners:
            _write_or_assign_contour(msp, contour, part, entity_to_work)

        for hole in part.holes:
            _write_or_assign_hole(msp, hole, part, entity_to_work)

    _remove_superseded_line_arc(msp, result)
    _assign_structural_layers(msp, result)
    _setup_layers(msp.doc)

    # --- Assegna layer lavorazioni e trash ---
    for entity in list(msp):
        if not entity.dxf.hasattr("layer"):
            continue

        entity_id = id(entity)
        layer = entity.dxf.layer
        work_type = entity_to_work.get(entity_id)

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

    # --- Materializza linee derivate e annotazioni ---
    for part in result.parts:
        if filter_part is not None and not filter_part(part):
            continue
        _materialize_derived_bending_lines(msp, part)

    # --- Annotazioni (solo se richieste) ---
    if include_annotations:
        _materialize_annotations(msp, result, filter_part)


def split(
    msp,
    result: ForgeResult,
    output_folder: str,
    namer: Optional[Callable] = None,
    keep_trash: bool = False,
    include_annotations: bool = True,
    min_area: float = DEFAULT_MIN_PART_AREA,
    exclude_types: Set[str] = None,
    on_part: Optional[Callable] = None,
) -> list:
    """
    Divide un ForgeResult in file DXF separati, uno per parte.
    
    Args:
        msp: Modelspace sorgente
        result: Risultato da suddividere
        output_folder: Cartella di destinazione
        namer: Callable per generare il nome del file (i, part) -> str
        keep_trash: Se True mantiene le entità non classificate
        include_annotations: Se True include annotazioni
        min_area: Area minima delle parti da includere (mm²)
        exclude_types: Set di tipi DXF da escludere (es. {"SPLINE", "CIRCLE"})
        on_part: Callable chiamata per ogni parte prima del salvataggio (part, doc, path)
    
    Returns:
        Lista dei percorsi dei file generati
    """
    os.makedirs(output_folder, exist_ok=True)
    generated = []
    src_doc = msp.doc
    exclude_types = exclude_types or set()
    excluded_upper = {t.upper() for t in exclude_types}

    for i, part in enumerate(result.parts):
        # Verifica area minima
        if min_area > 0 and part.outer.polygon.area < min_area:
            result.warnings.append(
                f"Part {i} scartato: area {part.outer.polygon.area:.2f} mm² "
                f"sotto soglia {min_area} mm²"
            )
            continue

        # Genera nome e percorso
        name = namer(i, part) if namer else f"{part.label}_P{i + 1}"
        out_path = os.path.join(output_folder, f"{name}.dxf")

        # Crea nuovo documento
        doc_out = ezdxf.new(dxfversion="R2010")
        doc_out.header['$INSUNITS'] = src_doc.header.get('$INSUNITS', 4)
        doc_out.header['$MEASUREMENT'] = src_doc.header.get('$MEASUREMENT', 1)
        _setup_layers(doc_out)
        msp_out = doc_out.modelspace()

        # Filtro per scrivere solo la parte corrente
        def filter_current_part(part_to_check: ForgePart) -> bool:
            # Confronto per identità (o per ID se disponibile)
            return part_to_check is part

        # Riutilizza il writer principale con il filtro
        write(
            msp_out,
            result,
            keep_trash=keep_trash,
            filter_part=filter_current_part,
            include_annotations=include_annotations
        )

        # Ricostruisce le entità del part dal modello sorgente senza usare la
        # copia globale: i cerchi e le spline vengono rigenerati come primitive,
        # mentre le annotazioni sono riscritte in modo dedicato.
        _materialize_part_entities(
            msp,
            msp_out,
            part,
            include_annotations=include_annotations,
            excluded_upper=excluded_upper,
        )

        # Rimuovi entità di tipo escluso (opzionale)
        if exclude_types:
            _remove_excluded_entities(msp_out, excluded_upper)

        # Callback opzionale
        if on_part is not None:
            on_part(part, doc_out, out_path)

        doc_out.saveas(out_path)
        generated.append(out_path)
        part.label = name

    return generated


# ---------------------------------------------------------------------------
# Helpers interni — materializzazione
# ---------------------------------------------------------------------------

def _materialize_annotation_entity(entity, msp_out, layer: str):
    """Riscrive un'annotazione come entità DXF dedicata, senza clone/copy."""
    kind = entity.dxftype()
    attribs = {"layer": layer, "color": 256}
    if kind == "TEXT":
        return msp_out.add_text(entity.dxf.text, dxfattribs=attribs)
    if kind == "MTEXT":
        return msp_out.add_mtext(entity.text, dxfattribs=attribs)
    # Unsupported: MULTILEADER/DIMENSION non sono rigenerabili in modo sicuro
    # senza usare una logica di dumping esplicita; per ora non vengono esportati.
    return None


def _materialize_part_entities(msp, msp_out, part: ForgePart,
                              include_annotations: bool = True,
                              excluded_upper: Set[str] | None = None) -> None:
    """Rigenera le entità del part da sorgente, senza usare il vecchio copy adapter."""
    excluded_upper = excluded_upper or set()
    for entity in msp:
        ent_type = entity.dxftype().upper()
        if ent_type in excluded_upper:
            continue

        rep = get_representative_point(entity)
        if rep is None:
            continue
        if not part.outer.polygon.covers(Point(rep)):
            continue

        if ent_type in ANNOTATION_TYPES:
            if not include_annotations:
                continue
            layer = entity.dxf.layer if entity.dxf.hasattr("layer") else LAYER_OUTER
            _materialize_annotation_entity(entity, msp_out, layer)
            continue

        if ent_type == "CIRCLE":
            prim = entity_to_primitive(entity)
            if not isinstance(prim, CircleSeg):
                continue
            layer = entity.dxf.layer if entity.dxf.hasattr("layer") else LAYER_OUTER
            proxy = type("_P", (), {"segments": [prim]})()
            write_contour_to_msp(msp_out, proxy, layer)
            continue

        if ent_type == "SPLINE":
            prim = entity_to_primitive(entity)
            if not isinstance(prim, SplineSeg):
                continue
            layer = entity.dxf.layer if entity.dxf.hasattr("layer") else LAYER_OUTER
            proxy = type("_P", (), {"segments": [prim]})()
            write_contour_to_msp(msp_out, proxy, layer)


def _write_or_assign_contour(msp, contour, part: ForgePart, entity_to_work: dict) -> None:
    """
    Forma durevole (source_ref non None, segments vuoti): assegna layer/color.
    Loop multi-entità (source_ref None, segments popolati): materializza LWPOLYLINE.
    """
    layer = ROLE_TO_LAYER.get(contour.role, LAYER_OUTER)

    if contour.source_ref is not None:
        ref = contour.source_ref
        if getattr(ref, "is_alive", True):
            ref.dxf.layer = layer
            ref.dxf.color = 256
        return

    lwpoly = write_contour_to_msp(msp, contour, layer)
    if lwpoly is not None:
        part.entity_ids.add(id(lwpoly))
        if contour.role not in (ContourRole.OUTER, ContourRole.INNER, ContourRole.UNKNOWN):
            entity_to_work[id(lwpoly)] = contour.role.value.lower()


def _write_or_assign_hole(msp, hole: Hole, part: ForgePart, entity_to_work: dict) -> None:
    layer = ROLE_TO_LAYER.get(hole.role, LAYER_HOLE)

    if hole.source_ref is not None:
        ref = hole.source_ref
        if getattr(ref, "is_alive", True):
            ref.dxf.layer = layer
            ref.dxf.color = 256

        if hole.outer_source_ref is not None:
            outer_ref = hole.outer_source_ref
            if getattr(outer_ref, "is_alive", True):
                outer_ref.dxf.layer = layer
                outer_ref.dxf.color = 256

        if hole.hole_type == HOLE_TYPE_COUNTERSINK:
            target_ref = hole.outer_source_ref or hole.source_ref
            if target_ref is not None:
                entity_to_work[id(target_ref)] = "countersink"
        elif hole.hole_type == HOLE_TYPE_THREADED:
            if hole.source_ref is not None:
                entity_to_work[id(hole.source_ref)] = "threaded_hole"
        return

    if hole.outer_source_ref is not None:
        outer_ref = hole.outer_source_ref
        if getattr(outer_ref, "is_alive", True):
            outer_ref.dxf.layer = layer
            outer_ref.dxf.color = 256

    lwpoly = write_contour_to_msp(msp, hole, layer)
    if lwpoly is not None:
        part.entity_ids.add(id(lwpoly))
        if hole.hole_type == HOLE_TYPE_COUNTERSINK:
            entity_to_work[id(lwpoly)] = "countersink"
        elif hole.hole_type == HOLE_TYPE_THREADED:
            entity_to_work[id(lwpoly)] = "threaded_hole"


def _materialize_annotations(msp, result: ForgeResult, filter_part: Optional[Callable]) -> None:
    """Materializza le annotazioni (testi, quote, ecc.) nel modelspace."""
    # Questa è un'implementazione di base; puoi estenderla secondo le tue esigenze
    for part in result.parts:
        if filter_part is not None and not filter_part(part):
            continue
        # Qui la logica per gestire le annotazioni specifiche della parte
        # Per ora è un placeholder
        pass


def _remove_excluded_entities(msp, excluded_upper: Set[str]) -> None:
    """Rimuove le entità di tipo escluso dal modelspace."""
    to_delete = []
    for entity in msp:
        if entity.dxftype().upper() in excluded_upper:
            to_delete.append(entity)
    for entity in to_delete:
        msp.delete_entity(entity)


# ---------------------------------------------------------------------------
# Helpers interni — layer e rimozione
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
    Le primitive chiuse durevoli restano sul documento.
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


def _build_structural_index(result: ForgeResult) -> dict:
    """Mappa id(source_ref) → layer strutturale per tutte le forme durevoli."""
    index = {}
    for part in result.parts:
        for contour in [part.outer] + part.inners:
            if contour.source_ref is not None:
                index[id(contour.source_ref)] = ROLE_TO_LAYER.get(contour.role, LAYER_OUTER)
        for hole in part.holes:
            if hole.source_ref is not None:
                index[id(hole.source_ref)] = ROLE_TO_LAYER.get(hole.role, LAYER_HOLE)
            if hole.outer_source_ref is not None:
                index[id(hole.outer_source_ref)] = ROLE_TO_LAYER.get(hole.role, LAYER_HOLE)
    return index


def _build_work_index(result: ForgeResult) -> dict:
    index = {}

    for ce in result.classified_entities:
        if ce.source_ref is not None:
            index[id(ce.source_ref)] = ce.work_type.lower()

    for part in result.parts:
        for hole in part.holes:
            if hole.hole_type == HOLE_TYPE_COUNTERSINK:
                target_ref = hole.outer_source_ref or hole.source_ref
                if target_ref is not None:
                    index[id(target_ref)] = "countersink"
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


def _collect_structural_source_ids(part: ForgePart) -> set[int]:
    ids = set()
    for contour in [part.outer] + part.inners:
        if contour.source_ref is not None:
            ids.add(id(contour.source_ref))
    for hole in part.holes:
        if hole.source_ref is not None:
            ids.add(id(hole.source_ref))
        if hole.outer_source_ref is not None:
            ids.add(id(hole.outer_source_ref))
    return ids


def _setup_layers(doc) -> None:
    for name, color in ALL_FORGE_LAYERS.items():
        if name not in doc.layers:
            layer = doc.layers.new(name)
        else:
            layer = doc.layers.get(name)
        layer.color = color


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
