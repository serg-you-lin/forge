"""
injector.py
-----------
Inietta dati nei ForgePart di un ForgeResult già prodotto da heal().

Responsabilità:
    - Calcola metriche per special_layers (bending_lines, engrave_length)
      filtrate per outer_poly di ogni part — corretto anche per multi-pezzo.
    - Estrae testi dal msp e li passa al data_injector del chiamante.
    - Popola part.custom con i risultati.

Contratto:
    - Opera SEMPRE su un ForgeResult già prodotto da heal().
    - È indipendente da split() — si può usare con o senza split.
    - Non modifica il msp.
    - Il data_injector è opzionale — si può usare inject() solo per
      le special_layers senza fornire un data_injector esterno.

Flusso tipico:

    result = forge.heal(msp, ...)
    forge.inject(msp, result, special_layers={"BEND": "bending"})
    forge.save_json(result, ...)

    # split opzionale
    forge.split(msp, result, output_dir)

    # oppure con data_injector esterno
    forge.inject(msp, result,
                 special_layers={"BEND": "bending"},
                 data_injector=my_fn)
"""

from typing import Callable, Optional
from .splitter import ANNOTATION_TYPES
from ..core.geometry import get_representative_point, group_collinear_lines, entity_length
from ..io.text_utils import extract_texts_from_msp
from ..rules.layers import (
    LAYER_BENDING, COLOR_BENDING,
    LAYER_MARKING, COLOR_MARKING,
    LAYER_ENGRAVE, COLOR_ENGRAVE,
)

# Mappa work_type → chiave in part.custom
WORK_TYPE_COUNTER = {
    "bending": "bending_lines",
    "engrave": "total_engrave_length",
    "marking": "total_marking_length",
}


def inject(
    msp,
    result,
    special_layers: Optional[dict] = None,
    data_injector: Optional[Callable] = None,
    tolerance: float = 0.1,
) -> None:
    """
    Inietta dati nei ForgePart di un ForgeResult.

    Modifica result.parts[i].custom in-place.
    Non restituisce nulla — il ForgeResult viene aggiornato direttamente.

    Args:
        msp:            modelspace ezdxf (già healato)
        result:         ForgeResult prodotto da heal()
        special_layers: dict {nome_layer: work_type} es. {"BEND": "bending"}
                        work_type supportati: "bending", "engrave", "marking"
        data_injector:  funzione (ForgePart, testi) -> dict per dati custom
                        es. estrazione codice/spessore/quantità da testi nel msp
        tolerance:      tolleranza mm per group_collinear_lines
    """
    if not result.parts:
        return

    for part in result.parts:
        outer_poly = part.outer.polygon
        if outer_poly is None or outer_poly.is_empty:
            continue

        # --- Special layers ---
        if special_layers:
            _inject_special_layers(
                msp, part, outer_poly, special_layers, tolerance, result
            )

        # --- Data injector esterno ---
        if data_injector is not None:
            testi = _extract_texts_for_part(msp, outer_poly)
            try:
                injected = data_injector(part, testi)
                if injected:
                    part.custom.update(injected)
            except Exception as ex:
                result.warnings.append(
                    f"data_injector fallito su {part.label}: {ex}"
                )


def _inject_special_layers(
    msp, part, outer_poly, special_layers: dict,
    tolerance: float, result
) -> None:
    """
    Calcola metriche per ogni work_type nelle special_layers,
    filtrate per outer_poly del part corrente.
    """
    # Raggruppa entità per work_type, filtrate per outer
    by_work_type: dict[str, list] = {}

    for entity in msp:
        if not entity.dxf.hasattr("layer"):
            continue
        layer = entity.dxf.layer.lower()
        for layer_key, work_type in special_layers.items():
            if layer_key.lower() not in layer:
                continue
            pt = get_representative_point(entity)
            if pt is None or not outer_poly.covers(pt):
                continue
            by_work_type.setdefault(work_type, []).append(entity)
            break

    # Calcola metriche per work_type
    for work_type, entities in by_work_type.items():
        if work_type == "bending":
            lines_only = [e for e in entities if e.dxftype() == 'LINE']
            groups = group_collinear_lines(lines_only, tolerance=tolerance)
            part.custom["bending_lines"] = len(groups)

        elif work_type in ("engrave", "marking"):
            key = WORK_TYPE_COUNTER.get(work_type, f"total_{work_type}_length")
            total = sum(entity_length(e) for e in entities)
            part.custom[key] = round(total, 4)


def _extract_texts_for_part(msp, outer_poly) -> list:
    """
    Estrae i testi dal msp che ricadono dentro l'outer_poly del part.
    """
    candidates = [
        e for e in msp
        if e.dxftype() in ANNOTATION_TYPES
        and (pt := get_representative_point(e)) is not None
        and outer_poly.covers(pt)
    ]
    return extract_texts_from_msp(candidates)
