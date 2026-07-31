"""
inject.py
-----------
Inietta dati nei ForgePart di un ForgeResult già prodotto da heal().

Responsabilità:
    - Calcola metriche per label_map (bending_lines, engrave_length)
      cercando sulle entità già routate da heal() sui layer forge corretti.
    - Estrae testi dal msp e li passa al data_injector del chiamante.
    - Popola part.custom con i risultati.

Contratto:
    - Opera SEMPRE su un ForgeResult già prodotto da heal().
    - I fori (countersink, threaded, plain) si leggono da part.holes —
      non da classified_entities, che contiene solo entità non-Hole
      (bending, engrave, marking, ecc.).
    - È indipendente da split() — si può usare con o senza split.
    - Non modifica il msp.
    - Il data_injector è opzionale.

Flusso tipico:

    result = forge.heal(msp, label_map={"Bend": "bending"})
    forge.detect(result)
    forge.inject(msp, result)
    forge.save_json(result, ...)
"""

from shapely.geometry import Point
from typing import Callable, Optional
from ..model.text import ForgeText
from ..core.geometry import group_collinear_lines
from ..io.text_utils import extract_texts_from_msp
from ..adapters.dxf.layers import (
    LAYER_BENDING, LAYER_ENGRAVE, LAYER_MARKING, LAYER_COUNTERSINK, LAYER_THREADED_HOLE,
)
from ..model import HOLE_TYPE_COUNTERSINK, HOLE_TYPE_THREADED, HOLE_TYPE_PLAIN

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
    result,
    data_injector: Optional[Callable] = None,
    texts: Optional[list[ForgeText]] = None,
    tolerance: float = 0.1,
) -> None:
    """
    Inietta dati nei ForgePart di un ForgeResult.

    Modifica result.parts[i].custom in-place.
    Non restituisce nulla — il ForgeResult viene aggiornato direttamente.

    Fonti di verità:
        - part.holes                    → fori (countersink, threaded, plain)
        - part.geometry_hints           → bending lines
        - result.classified_entities    → engrave, marking

    È indipendente da write() — può essere chiamato senza che write()
    abbia spostato le entità sui layer forge.

    Args:
        result:         ForgeResult prodotto da heal() + detect()
        data_injector:  funzione (ForgePart, testi) -> dict per dati custom
        texts:          lista di ForgeText estratti da extract_forge_texts()
        tolerance:      tolleranza mm per group_collinear_lines
    """
    if not result.parts:
        return

    for part in result.parts:
        outer_poly = part.outer.polygon
        if outer_poly is None or outer_poly.is_empty:
            continue

        # Fori — fonte di verità: part.holes
        _inject_holes(part)

        # Bending — fonte di verità: part.geometry_hints.bend_line_ids
        _inject_bending(part, tolerance)

        # Engrave, marking — fonte di verità: classified_entities
        if result.classified_entities:
            _inject_classified(part, result.classified_entities, outer_poly)

        # Data injector esterno (codice, spessore, materiale, ecc.)
        if data_injector is not None:
            testi = _filter_texts_for_part(texts or [], outer_poly)
            try:
                injected = data_injector(part, testi)
                if injected:
                    part.custom.update(injected)
            except Exception as ex:
                result.warnings.append(
                    f"data_injector fallito su {part.label}: {ex}"
                )


def _inject_holes(part) -> None:
    """
    Conta i fori per tipo e scrive in part.custom.

    Fonte di verità: part.holes — mai classified_entities.
    Scrive solo le chiavi con count > 0.
    """
    countersink_count   = 0
    threaded_hole_count = 0
    plain_hole_count    = 0

    for hole in part.holes:
        if hole.hole_type == HOLE_TYPE_COUNTERSINK:
            countersink_count += 1
        elif hole.hole_type == HOLE_TYPE_THREADED:
            threaded_hole_count += 1
        elif hole.hole_type == HOLE_TYPE_PLAIN:
            plain_hole_count += 1

    if countersink_count:
        part.custom["countersink_count"]   = countersink_count
    if threaded_hole_count:
        part.custom["threaded_holes_count"] = threaded_hole_count
    if plain_hole_count:
        part.custom["plain_holes_count"]   = plain_hole_count


def _inject_bending(part, tolerance: float) -> None:
    """
    Conta le pieghe da part.bending_lines.
    Fonte di verità: detect() — indipendente da write().
    """
    if not part.bending_lines:
        return
    geometries = [bl.geometry for bl in part.bending_lines]
    groups = group_collinear_lines(geometries, tolerance=tolerance)
    part.custom["bending_lines"] = len(groups)
    

def _inject_classified(part, classified_entities, outer_poly) -> None:
    total_engrave = 0.0
    total_marking = 0.0

    for ce in classified_entities:
        if ce.representative_point is not None:
            pt = Point(ce.representative_point)
        elif ce.polygon is not None and not ce.polygon.is_empty:
            pt = ce.polygon.centroid
        else:
            continue
 
        if pt is None or not outer_poly.covers(pt):
            continue

        wt = ce.work_type.lower()
        if wt == "engrave":
            total_engrave += ce.data.get("length") or 0.0
        elif wt == "marking":
            total_marking += ce.data.get("length") or 0.0

    if total_engrave:
        part.custom["total_engrave_length"] = round(total_engrave, 4)
    if total_marking:
        part.custom["total_marking_length"] = round(total_marking, 4)


def _filter_texts_for_part(texts: list[ForgeText], outer_poly) -> list[str]:
    """
    Filtra i ForgeText che ricadono dentro l'outer_poly del part.
    Restituisce list[str] per compatibilità con data_injector esistenti.
    """
    return [
        t.content for t in texts
        if outer_poly.covers(t.position)
    ]