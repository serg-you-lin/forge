"""
injector.py
-----------
Inietta dati nei ForgePart di un ForgeResult già prodotto da heal().

Responsabilità:
    - Calcola metriche per special_layers (bending_lines, engrave_length)
      cercando sulle entità già routate da heal() sui layer forge corretti.
      heal() deve aver ricevuto special_layers per spostare le entità
      da trash a LAYER_BENDING, LAYER_ENGRAVE, LAYER_MARKING.
    - Estrae testi dal msp e li passa al data_injector del chiamante.
    - Popola part.custom con i risultati.

Contratto:
    - Opera SEMPRE su un ForgeResult già prodotto da heal().
    - heal() deve ricevere special_layers per preservare le entità speciali
      da trash — inject() le trova sui layer forge corrispondenti.
    - È indipendente da split() — si può usare con o senza split.
    - Non modifica il msp.
    - Il data_injector è opzionale.

Flusso tipico:

    result = forge.heal(msp, special_layers={"Bend": "bending"}, ...)
    forge.inject(msp, result)
    forge.save_json(result, ...)

    # oppure con data_injector esterno
    result = forge.heal(msp, special_layers={"Bend": "bending"}, ...)
    forge.inject(msp, result, data_injector=my_fn)

    # split opzionale dopo
    forge.split_to_files(msp, output_dir, heal_result=result, ...)
"""

from typing import Callable, Optional
from ..core.geometry import get_representative_point, group_collinear_lines, entity_length
from ..io.text_utils import extract_texts_from_msp
from ..rules.layers import (
    LAYER_BENDING, LAYER_ENGRAVE, LAYER_MARKING,
)

ANNOTATION_TYPES = {'TEXT', 'MTEXT', 'DIMENSION', 'LEADER', 'MULTILEADER'}

# Mappa work_type → layer forge dove heal() ha già spostato le entità
WORK_TYPE_TO_FORGE_LAYER = {
    "bending": LAYER_BENDING,
    "engrave": LAYER_ENGRAVE,
    "marking": LAYER_MARKING,
}

# Mappa work_type → chiave in part.custom
WORK_TYPE_TO_KEY = {
    "bending": "bending_lines",
    "engrave": "total_engrave_length",
    "marking": "total_marking_length",
}


def inject(
    msp,
    result,
    data_injector: Optional[Callable] = None,
    tolerance: float = 0.1,
) -> None:
    """
    Inietta dati nei ForgePart di un ForgeResult.

    Modifica result.parts[i].custom in-place.
    Non restituisce nulla — il ForgeResult viene aggiornato direttamente.

    Prerequisito: heal() deve essere stato chiamato con special_layers
    per preservare le entità speciali su LAYER_BENDING, LAYER_ENGRAVE, ecc.
    inject() le cerca direttamente su quei layer forge.

    Args:
        msp:            modelspace ezdxf (già healato)
        result:         ForgeResult prodotto da heal()
        data_injector:  funzione (ForgePart, testi) -> dict per dati custom
        tolerance:      tolleranza mm per group_collinear_lines
    """
    if not result.parts:
        return

    for part in result.parts:
        outer_poly = part.outer.polygon
        if outer_poly is None or outer_poly.is_empty:
            continue

        # Metriche layer forge (bending, engrave, marking)
        _inject_forge_layers(msp, part, outer_poly, tolerance, result)

        # Data injector esterno (codice, spessore, materiale, ecc.)
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


def _inject_forge_layers(
    msp, part, outer_poly,
    tolerance: float, result,
) -> None:
    """
    Calcola metriche per ogni work_type cercando sui layer forge
    dove heal() ha già spostato le entità speciali.
    Filtra per outer_poly del part corrente.
    """
    for work_type, forge_layer in WORK_TYPE_TO_FORGE_LAYER.items():
        entities = [
            e for e in msp
            if e.dxf.hasattr("layer")
            and e.dxf.layer == forge_layer
            and (pt := get_representative_point(e)) is not None
            and outer_poly.covers(pt)
        ]

        if not entities:
            continue

        key = WORK_TYPE_TO_KEY[work_type]

        if work_type == "bending":
            lines_only = [e for e in entities if e.dxftype() == 'LINE']
            groups = group_collinear_lines(lines_only, tolerance=tolerance)
            part.custom[key] = len(groups)
        else:
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