# """
# injector.py
# -----------
# Inietta dati nei ForgePart di un ForgeResult già prodotto da heal().

# Responsabilità:
#     - Calcola metriche per special_layers (bending_lines, engrave_length)
#       cercando sulle entità già routate da heal() sui layer forge corretti.
#       heal() deve aver ricevuto special_layers per spostare le entità
#       da trash a LAYER_BENDING, LAYER_ENGRAVE, LAYER_MARKING.
#     - Estrae testi dal msp e li passa al data_injector del chiamante.
#     - Popola part.custom con i risultati.

# Contratto:
#     - Opera SEMPRE su un ForgeResult già prodotto da heal().
#     - heal() deve ricevere special_layers per preservare le entità speciali
#       da trash — inject() le trova sui layer forge corrispondenti.
#     - È indipendente da split() — si può usare con o senza split.
#     - Non modifica il msp.
#     - Il data_injector è opzionale.

# Flusso tipico:

#     result = forge.heal(msp, special_layers={"Bend": "bending"}, ...)
#     forge.inject(msp, result)
#     forge.save_json(result, ...)

#     # oppure con data_injector esterno
#     result = forge.heal(msp, special_layers={"Bend": "bending"}, ...)
#     forge.inject(msp, result, data_injector=my_fn)

#     # split opzionale dopo
#     forge.split_to_files(msp, output_dir, heal_result=result, ...)
# """

# from shapely.geometry import Point
# from typing import Callable, Optional
# from ..core.geometry import get_representative_point, group_collinear_lines, entity_length
# from ..io.text_utils import extract_texts_from_msp
# from ..rules.layers import (
#     LAYER_BENDING, LAYER_ENGRAVE, LAYER_MARKING, LAYER_COUNTERSINK, LAYER_THREADED_HOLE,
# )

# ANNOTATION_TYPES = {'TEXT', 'MTEXT', 'DIMENSION', 'LEADER', 'MULTILEADER'}

# # Mappa work_type → layer forge dove heal() ha già spostato le entità
# WORK_TYPE_TO_FORGE_LAYER = {
#     "bending": LAYER_BENDING,
#     "engrave": LAYER_ENGRAVE,
#     "marking": LAYER_MARKING,
#     "threaded_hole": LAYER_THREADED_HOLE,
# }

# # Mappa work_type → chiave in part.custom
# WORK_TYPE_TO_KEY = {
#     "bending": "bending_lines",
#     "engrave": "total_engrave_length",
#     "marking": "total_marking_length",
#     "threaded_hole": "threaded_holes_count",
# }


# def inject(
#     msp,
#     result,
#     data_injector: Optional[Callable] = None,
#     tolerance: float = 0.1,
# ) -> None:
#     """
#     Inietta dati nei ForgePart di un ForgeResult.

#     Modifica result.parts[i].custom in-place.
#     Non restituisce nulla — il ForgeResult viene aggiornato direttamente.

#     Prerequisito: heal() deve essere stato chiamato con special_layers
#     per preservare le entità speciali su LAYER_BENDING, LAYER_ENGRAVE, ecc.
#     inject() le cerca direttamente su quei layer forge.

#     Args:
#         msp:            modelspace ezdxf (già healato)
#         result:         ForgeResult prodotto da heal()
#         data_injector:  funzione (ForgePart, testi) -> dict per dati custom
#         tolerance:      tolleranza mm per group_collinear_lines
#     """
#     if not result.parts:
#         return

#     for part in result.parts:
#         outer_poly = part.outer.polygon
#         if outer_poly is None or outer_poly.is_empty:
#             continue

#         # Metriche layer forge (bending, engrave, marking)
#         _inject_forge_layers(msp, part, outer_poly, tolerance, result)

#         # Metriche da classified_entities (interpreter geometrico)
#         # print(f"classified_entities: {len(result.classified_entities)}")
#         if result.classified_entities:
#             _inject_classified(part, result.classified_entities, outer_poly)

#         # Data injector esterno (codice, spessore, materiale, ecc.)
#         if data_injector is not None:
#             testi = _extract_texts_for_part(msp, outer_poly)
#             try:
#                 injected = data_injector(part, testi)
#                 if injected:
#                     part.custom.update(injected)
#             except Exception as ex:
#                 result.warnings.append(
#                     f"data_injector fallito su {part.label}: {ex}"
#                 )


# def _inject_forge_layers(
#     msp, part, outer_poly,
#     tolerance: float, result,
# ) -> None:
#     """
#     Calcola metriche per ogni work_type cercando sui layer forge
#     dove heal() ha già spostato le entità speciali.
#     Filtra per outer_poly del part corrente.
#     """
#     for work_type, forge_layer in WORK_TYPE_TO_FORGE_LAYER.items():
#         entities = [
#             e for e in msp
#             if e.dxf.hasattr("layer")
#             and e.dxf.layer == forge_layer
#             and (pt := get_representative_point(e)) is not None
#             and outer_poly.covers(pt)
#         ]

#         if not entities:
#             continue

#         key = WORK_TYPE_TO_KEY[work_type]

#         if work_type == "bending":
#             lines_only = [e for e in entities if e.dxftype() == 'LINE']
#             groups = group_collinear_lines(lines_only, tolerance=tolerance)
#             part.custom[key] = len(groups)
#         elif work_type == "threaded_hole":
#             part.custom[key] = len(entities) 
#         else:
#             total = sum(entity_length(e) for e in entities)
#             part.custom[key] = round(total, 4)


# def _inject_classified(part, classified_entities, outer_poly) -> None:
#     countersink_count   = 0
#     total_engrave       = 0.0
#     total_marking       = 0.0
#     threaded_hole_count = 0
#     bending_count       = 0

#     for ce in classified_entities:
#         if ce.entity is not None:
#             pt = get_representative_point(ce.entity)
#             if pt is None or not outer_poly.covers(pt):
#                 continue

#         wt = ce.work_type.lower()

#         if wt == "countersink":
#             countersink_count += 1
#         elif wt == "engrave":
#             total_engrave += ce.data.get("length") or 0.0
#         elif wt == "marking":
#             total_marking += ce.data.get("length") or 0.0
#         elif wt == "threaded_hole":
#             threaded_hole_count += 1
#         elif wt == "bending":
#             bending_count += 1

#     if countersink_count:
#         part.custom["countersink_count"]    = countersink_count
#     if total_engrave:
#         part.custom["total_engrave_length"] = round(total_engrave, 4)
#     if total_marking:
#         part.custom["total_marking_length"] = round(total_marking, 4)
#     if threaded_hole_count:
#         part.custom["threaded_holes_count"] = threaded_hole_count
#     if bending_count:
#         part.custom["bending_lines"]        = bending_count


# def _extract_texts_for_part(msp, outer_poly) -> list:
#     """
#     Estrae i testi dal msp che ricadono dentro l'outer_poly del part.
#     """
#     candidates = [
#         e for e in msp
#         if e.dxftype() in ANNOTATION_TYPES
#         and (pt := get_representative_point(e)) is not None
#         and outer_poly.covers(pt)
#     ]
#     return extract_texts_from_msp(candidates)



"""
injector.py
-----------
Inietta dati nei ForgePart di un ForgeResult già prodotto da heal().

Responsabilità:
    - Calcola metriche per special_layers (bending_lines, engrave_length)
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

    result = forge.heal(msp, ...)
    forge.detect(result, msp, special_layers={"Bend": "bending"})
    forge.inject(msp, result)
    forge.save_json(result, ...)
"""

from shapely.geometry import Point
from typing import Callable, Optional
from ..core.geometry import get_representative_point, group_collinear_lines, entity_length
from ..io.text_utils import extract_texts_from_msp
from ..rules.layers import (
    LAYER_BENDING, LAYER_ENGRAVE, LAYER_MARKING, LAYER_COUNTERSINK, LAYER_THREADED_HOLE,
)
from ..models import HOLE_TYPE_COUNTERSINK, HOLE_TYPE_THREADED, HOLE_TYPE_PLAIN

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

    I dati dei fori vengono letti da part.holes (fonte di verità unica):
        - countersink_count    → fori con hole_type == COUNTERSINK
        - threaded_holes_count → fori con hole_type == THREADED
        - plain_holes_count    → fori con hole_type == PLAIN

    Le entità non-foro (bending, engrave, marking) vengono lette dai
    layer forge corrispondenti nel msp o da classified_entities.

    Args:
        msp:            modelspace ezdxf (già healato)
        result:         ForgeResult prodotto da heal() + detect()
        data_injector:  funzione (ForgePart, testi) -> dict per dati custom
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

        # Metriche layer forge (bending, engrave, marking)
        _inject_forge_layers(msp, part, outer_poly, tolerance, result)

        # Metriche da classified_entities (bending/engrave/marking da interpreter)
        if result.classified_entities:
            _inject_classified(part, result.classified_entities, outer_poly)

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
        # UNKNOWN: detect() non chiamato — non contiamo, non è una diagnosi

    if countersink_count:
        part.custom["countersink_count"]   = countersink_count
    if threaded_hole_count:
        part.custom["threaded_holes_count"] = threaded_hole_count
    if plain_hole_count:
        part.custom["plain_holes_count"]   = plain_hole_count


def _inject_forge_layers(
    msp, part, outer_poly,
    tolerance: float, result,
) -> None:
    """
    Calcola metriche per bending, engrave, marking cercando sui layer forge.

    Nota: countersink e threaded_hole non sono più in WORK_TYPE_TO_FORGE_LAYER —
    i loro dati vengono da _inject_holes() che legge part.holes.
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


def _inject_classified(part, classified_entities, outer_poly) -> None:
    """
    Conta metriche da classified_entities per entità non-foro.

    Nota: countersink e threaded_hole NON vengono contati qui —
    vivono su part.holes e vengono contati da _inject_holes().
    Questo evita il doppio conteggio che rompeva i golden test.
    """
    total_engrave = 0.0
    total_marking = 0.0
    bending_count = 0

    for ce in classified_entities:
        if ce.entity is not None:
            pt = get_representative_point(ce.entity)
            if pt is None or not outer_poly.covers(pt):
                continue

        wt = ce.work_type.lower()

        if wt == "engrave":
            total_engrave += ce.data.get("length") or 0.0
        elif wt == "marking":
            total_marking += ce.data.get("length") or 0.0
        elif wt == "bending":
            bending_count += 1
        # countersink e threaded_hole: ignorati qui — vedi _inject_holes()

    if total_engrave:
        part.custom["total_engrave_length"] = round(total_engrave, 4)
    if total_marking:
        part.custom["total_marking_length"] = round(total_marking, 4)
    if bending_count:
        part.custom["bending_lines"] = bending_count


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