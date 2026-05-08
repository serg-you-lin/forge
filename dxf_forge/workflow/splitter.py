"""
splitter.py
-----------
Divide un DXF con più pezzi in file separati.

Contratto:
    - split_to_files() heala il msp, usa il ForgeResult in memoria
      per la gerarchia, e usa il msp solo per l'export fisico delle entità.
      NON scrive metadata — quella è responsabilità del chiamante.

    Il namer è una funzione (int, ForgePart) -> str decisa dal chiamante.

Workflow utente tipico:

    # Caso A — pipeline completa
    result = forge.split_to_files(msp, output_folder, label="pezzo")
    for part in result.parts:
        forge.write_metadata_to_dxf(doc_figlio, part)

    # Caso B — heal separato + split_to_files
    heal_result = forge.heal(msp, write_to_msp=True)
    if forge.is_multi(heal_result):
        forge.split_to_files(msp, output_folder, heal_result=heal_result,
                             namer=lambda i, p: f"custom_{i}")

    # Caso C — namer con dati esterni
    def mio_namer(i, part):
        return lookup_codice(part.label, i)

    forge.split_to_files(msp, output_folder, namer=mio_namer)

Tipi geometrici supportati come outer/inner:
    LWPOLYLINE, POLYLINE, CIRCLE, SPLINE, ELLIPSE, LINE, ARC
    (inclusi loop LINE+SPLINE che non producono LWPOLYLINE)
"""

import os
from typing import Callable, Optional, Set
from shapely.geometry import Point
import ezdxf

from ..models import ForgeContour, ForgePart, ForgeResult
from ..core.geometry import entity_to_polygon, get_representative_point, copy_entity
from ..rules.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    LAYER_BENDING, LAYER_MARKING, LAYER_ENGRAVE, TRASH_LAYER,
    COLOR_OUTER, COLOR_INNER, COLOR_HOLE,
    COLOR_BENDING, COLOR_MARKING, COLOR_ENGRAVE, COLOR_TRASH,
)

# Tutti i layer forge con il loro colore canonico — fonte di verità: layers.py
ALL_FORGE_LAYERS = {
    LAYER_OUTER:   COLOR_OUTER,
    LAYER_INNER:   COLOR_INNER,
    LAYER_HOLE:    COLOR_HOLE,
    LAYER_BENDING: COLOR_BENDING,
    LAYER_MARKING: COLOR_MARKING,
    LAYER_ENGRAVE: COLOR_ENGRAVE,
    TRASH_LAYER:   COLOR_TRASH,
}
from .healer import heal
from ..io.text_utils import extract_texts_from_msp

ANNOTATION_TYPES = {'TEXT', 'MTEXT', 'DIMENSION', 'LEADER', 'MULTILEADER'}
STRUCTURAL_LAYER_NAMES = {LAYER_OUTER, LAYER_INNER, LAYER_HOLE}
STRUCTURAL_ENTITY_TYPES = {'LWPOLYLINE', 'POLYLINE', 'CIRCLE', 'SPLINE', 'ELLIPSE', 'LINE', 'ARC'}


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def is_multi(result: ForgeResult) -> bool:
    """
    Restituisce True se il ForgeResult contiene più di un pezzo.
    Usato per decidere se splittare o salvare direttamente.
    """
    return result.part_count > 1


def split_to_files(
    msp,
    output_folder: str,
    label: str = "",
    source_file: str = "",
    tolerance: float = 0.05,
    explode_inserts: bool = False,
    namer: Optional[Callable] = None,
    exclude_types: Optional[Set[str]] = None,
    include_annotations: bool = True,
    special_layers: dict = None,
    heal_result: ForgeResult = None,
    data_injector: Optional[Callable] = None,
    preserve_original_layers: bool = False,
) -> ForgeResult:
    """
    Pipeline completa: heala, usa ForgeResult in memoria, salva un DXF per ogni pezzo.
    Non scrive metadata — quella è responsabilità del chiamante.

    Args:
        msp:               modelspace ezdxf (anche non healato)
        output_folder:     cartella dove salvare i file figli
        label:             nome base per i file (es. stem del file sorgente)
        source_file:       percorso del file originale (per tracciabilità)
        tolerance:         tolleranza healing in mm
        explode_inserts:   se True esplode gli INSERT prima dell'healing
        namer:             funzione (int, ForgePart) -> str per il nome file.
                           Default: "{label}_{i}"
        exclude_types:     tipi DXF da non copiare nei file figli
        include_annotations: se False esclude TEXT, MTEXT, DIMENSION, ecc.
        special_layers:    dict {nome_layer: tipo} passato all'healer
        heal_result:       ForgeResult già prodotto da heal() — se fornito
                           salta l'healing interno (evita doppio lavoro)
        data_injector:     funzione (ForgePart, testi) -> dict per dati custom

    Returns:
        ForgeResult con tutti i ForgePart trovati.
    """
    os.makedirs(output_folder, exist_ok=True)

    # 1. Healing — salta se il chiamante ha già healato
    if heal_result is None:
        heal_result = heal(
            msp,
            tolerance=tolerance,
            write_to_msp=True,
            label=label,
            source_file=source_file,
            explode_inserts=explode_inserts,
            special_layers=special_layers,
        )
        for w in heal_result.warnings:
            print(f"  [heal] {w}")
        for e in heal_result.errors:
            print(f"  [heal ERROR] {e}")

    if not heal_result.is_valid or not heal_result.parts:
        return heal_result

    # 2. Il ForgeResult viene usato direttamente dalla memoria —
    #    non si rilegge dal msp. Questo risolve il problema dei loop
    #    con SPLINE che non producono LWPOLYLINE nel msp.
    result = heal_result

    # 3. Namer — default se non fornito
    if namer is None:
        namer = lambda i, part: f"{label}_{i}" if label else f"P_{i}"

    # 4. Filtri entità
    skip_types = set(exclude_types or [])
    if not include_annotations:
        skip_types |= ANNOTATION_TYPES

    # Entità su layer strutturali nel msp — usate per l'export fisico
    structural_entities = [e for e in msp
                           if e.dxf.layer in STRUCTURAL_LAYER_NAMES
                           and e.dxftype() in STRUCTURAL_ENTITY_TYPES]

    inner_entities = [e for e in structural_entities
                      if e.dxf.layer in (LAYER_INNER, LAYER_HOLE)]

    # Entità su layer NON strutturali (testi, quote, extra)
    all_extras = [e for e in msp
                  if e.dxf.layer not in STRUCTURAL_LAYER_NAMES]

    # 5. Export — un file per ogni ForgePart
    for i, part in enumerate(result.parts, start=1):
        outer_poly = part.outer.polygon
        if outer_poly is None or outer_poly.is_empty:
            continue

        new_doc = ezdxf.new('R2010')
        new_msp = new_doc.modelspace()

        if preserve_original_layers:
            # --- Modalità RAW ---
            # Copia i layer dall'originale così come sono (colori, linetype, ecc.)
            source_doc = msp.doc
            for layer in source_doc.layers:
                if layer.dxf.name not in new_doc.layers:
                    raw_color = layer.dxf.get("color", 7)
                    is_off = raw_color < 0
                    abs_color = abs(raw_color)
                    new_layer = new_doc.layers.add(
                        layer.dxf.name,
                        color=abs_color,
                        linetype=layer.dxf.get("linetype", "Continuous"),
                    )
                    if is_off:
                        new_layer.off()

            # Copia TUTTE le entità del msp originale contenute nel polygon
            for entity in msp:
                if entity.dxftype() in skip_types:
                    continue
                pt = get_representative_point(entity)
                if pt is not None and outer_poly.covers(pt):
                    copy_entity(entity, new_msp)

        else:
            # --- Modalità FORGE (comportamento attuale) ---
            for layer_name, color in ALL_FORGE_LAYERS.items():
                new_doc.layers.add(layer_name, color=color)

            outer_written = False
            for e in structural_entities:
                if e.dxf.layer != LAYER_OUTER:
                    continue
                e_poly = entity_to_polygon(e)
                if e_poly is not None and abs(e_poly.area - outer_poly.area) < 1.0:
                    copy_entity(e, new_msp)
                    outer_written = True
                    break

            if not outer_written:
                for e in msp:
                    if e.dxf.layer == LAYER_OUTER and e.dxftype() in STRUCTURAL_ENTITY_TYPES:
                        pt = get_representative_point(e)
                        if pt is not None and outer_poly.covers(pt):
                            copy_entity(e, new_msp)

            for inner_e in inner_entities:
                inner_poly = entity_to_polygon(inner_e)
                if inner_poly is not None:
                    if outer_poly.contains(inner_poly):
                        copy_entity(inner_e, new_msp)
                else:
                    pt = get_representative_point(inner_e)
                    if pt is not None and outer_poly.covers(pt):
                        copy_entity(inner_e, new_msp)

            # Estrai testi dal msp originale PRIMA di copiare
            # (se copy avviene con skip_types, new_msp potrebbe non averli)
        text_to_be_injected = []
        if data_injector is not None:
            text_to_be_injected = extract_texts_from_msp([
                e for e in msp
                if e.dxftype() in ANNOTATION_TYPES
                and (pt := get_representative_point(e)) is not None
                and outer_poly.covers(pt)
            ])

        # Copia extras SOLO in modalità FORGE (non raw)
        if not preserve_original_layers:
            for entity in all_extras:
                if entity.dxftype() in skip_types:
                    continue
                pt = get_representative_point(entity)
                if pt is not None and outer_poly.contains(pt):
                    copy_entity(entity, new_msp)
                    
        # for entity in all_extras:
        #     if entity.dxftype() in skip_types:
        #         continue
        #     pt = get_representative_point(entity)
        #     if pt is not None and outer_poly.contains(pt):
        #         copy_entity(entity, new_msp)

        # Data injection con testi già estratti
        if data_injector is not None:
            try:
                injected = data_injector(part, text_to_be_injected)
                if injected:
                    part.custom.update(injected)
            except Exception as ex:
                result.warnings.append(
                    f"data_injector fallito su {part.label}: {ex}"
                )

        # Namer DOPO injection
        file_label = namer(i, part)
        part.label = file_label

        filename = os.path.join(output_folder, f"{file_label}.dxf")
        new_doc.saveas(filename)

    return result

