"""
workflow/classifier.py
----------------------
Classifica le entità extra di un DXF e arricchisce i ForgePart con metadati.

Lavora DOPO heal() — non tocca la geometria strutturale.
È l'unico posto dove vivono: special_layers, interpreter, bending_lines_data.

Flusso interno:
    1. BendingLine — da special_layers OPPURE da interpreter (mai entrambi)
    2. GeometricInterpreter — countersink, threaded_hole, e BL se non coperte da special
    3. Extra entities — fold_lines, punch, mark da layer/colore
    4. Scrittura su part.custom

API pubblica:
    classify(result, msp, special_layers, interpreter, entity_map, extra_metadata)
"""

from __future__ import annotations

from typing import Optional, List
from shapely.geometry import Point

from ..models import (
    ForgeResult,
    ForgePart,
    BendingLine,
    ClassifiedEntity,
    BaseInterpreter,
)
from ..core.geometry import get_representative_point
from ..rules.interpreter import bending_line_from_entity

# ---------------------------------------------------------------------------
# Config default entità extra — sovrascrivibile per ogni officina
# ---------------------------------------------------------------------------

DEFAULT_ENTITY_MAP = {
    "fold_lines": {"layers": ["BEND", "PIEGA", "FOLD", "PIEGATURA"], "colors": []},
    "punch":      {"layers": ["PUNCH", "BULIN", "PUNCHING"],         "colors": []},
    "mark":       {"layers": ["MARK", "MARCA", "MARKING"],           "colors": []},
}

# Layer strutturali — ignorati dal classifier
STRUCTURAL_LAYERS = {"OUTERCONTOUR", "INNERCONTOUR", "HEALED_HOLE", "FORGE_TRASH"}
STRUCTURAL_TYPES  = {"LWPOLYLINE", "POLYLINE"}


# ---------------------------------------------------------------------------
# Helpers interni
# ---------------------------------------------------------------------------

def _has_bending_in_special(special_layers: dict) -> bool:
    if not special_layers:
        return False
    return any(v == "bending" for v in special_layers.values())


def _bending_lines_from_special(msp, part: ForgePart) -> List[BendingLine]:
    """
    Costruisce BendingLine dalle entità LINE i cui id() sono in
    part.geometry_hints.bend_line_ids, filtrate per appartenenza all'outer del part.
    """
    result = []
    bend_ids = part.geometry_hints.bend_line_ids
    if not bend_ids:
        return result

    for entity in msp.query("LINE"):
        if id(entity) not in bend_ids:
            continue
        s = entity.dxf.start
        e = entity.dxf.end
        midpoint = Point((s.x + e.x) / 2, (s.y + e.y) / 2)
        if part.outer.polygon.contains(midpoint) or \
           part.outer.polygon.boundary.distance(midpoint) < 1.0:
            bl = bending_line_from_entity(entity, part_label=part.label)
            result.append(bl)
    return result


def _classify_entity_by_map(entity, entity_map: dict) -> Optional[str]:
    """Classifica una singola entità per layer o colore. Restituisce categoria o None."""
    layer = entity.dxf.layer.upper() if entity.dxf.hasattr("layer") else ""
    color = entity.dxf.color        if entity.dxf.hasattr("color") else None

    for category, rules in entity_map.items():
        if layer in [l.upper() for l in rules.get("layers", [])]:
            return category
        if color is not None and color in rules.get("colors", []):
            return category
    return None


def _classify_extra_entities(msp, parts: list, entity_map: dict, warnings: list):
    """
    Classifica entità extra (fold_lines, punch, mark, trash) per layer/colore
    e le assegna al part che le contiene geometricamente.

    Modifica part.custom in place.
    """
    # Inizializza le chiavi su ogni part
    for part in parts:
        for key in ("fold_lines", "punch", "mark", "trash"):
            part.custom.setdefault(key, [])

    special_layer_names = set()
    for part in parts:
        # Recupera i layer speciali dai hints per non riclassificarli
        # (le BL sono già in bending_lines_data)
        pass

    for entity in msp:
        if entity.dxftype() in STRUCTURAL_TYPES:
            continue
        layer = entity.dxf.layer.upper() if entity.dxf.hasattr("layer") else ""
        if layer in STRUCTURAL_LAYERS:
            continue

        category = _classify_entity_by_map(entity, entity_map)
        pt       = get_representative_point(entity)

        assigned = False
        for part in parts:
            if pt is not None and part.outer.polygon.contains(pt):
                key = category if category else "trash"
                part.custom.setdefault(key, [])
                part.custom[key].append({
                    "type":  entity.dxftype(),
                    "layer": entity.dxf.layer if entity.dxf.hasattr("layer") else "",
                    "color": entity.dxf.color if entity.dxf.hasattr("color") else None,
                })
                assigned = True
                break

        if not assigned and parts:
            key = category if category else "trash"
            parts[0].custom.setdefault(key, [])
            parts[0].custom[key].append({
                "type":    entity.dxftype(),
                "layer":   entity.dxf.layer if entity.dxf.hasattr("layer") else "",
                "color":   entity.dxf.color if entity.dxf.hasattr("color") else None,
                "orphan":  True,
            })
            if category:
                warnings.append(
                    f"Entità {entity.dxftype()} su layer {entity.dxf.layer!r} "
                    f"classificata come {category!r} ma non contenuta in nessun part."
                )

    for part in parts:
        trash_count = len(part.custom.get("trash", []))
        if trash_count > 0:
            warnings.append(
                f"{part.label}: {trash_count} entità non riconosciute in trash. "
                f"Verificare layer e colori."
            )


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def classify(
    result:          ForgeResult,
    msp,
    interpreter:     BaseInterpreter   = None,
    entity_map:      dict              = None,
    extra_metadata:  dict              = None,
) -> ForgeResult:
    """
    Arricchisce i ForgePart con metadati di classificazione.

    Deve essere chiamata dopo heal() e prima di inject().

    Le special_layers vengono lette da result.special_layers,
    popolato da heal().

    Responsabilità:
        - BendingLine: da special_layers OPPURE da interpreter (mai entrambi)
        - ClassifiedEntity: countersink, threaded_hole via interpreter
        - Extra entities: fold_lines, punch, mark via entity_map
        - Scrittura di part.custom['bending_lines_data']
        - Scrittura di part.custom['countersink_data'], ['threaded_hole_data']

    Args:
        result:         ForgeResult prodotto da heal()
        msp:            modelspace ezdxf (stesso passato a heal())
        interpreter:    implementazione di BaseInterpreter — opzionale
        entity_map:     mappa layer/colore per fold_lines, punch, mark
                        se None usa DEFAULT_ENTITY_MAP
        extra_metadata: metadati da aggiungere a tutti i part (material, thickness, ecc.)

    Returns:
        Il ForgeResult ricevuto, con part.custom popolato.
    """
    emap     = {**DEFAULT_ENTITY_MAP, **(entity_map or {})}
    warnings = []

    special_layers = result.special_layers

    use_special_bending = _has_bending_in_special(special_layers)

    for part in result.parts:
        hints = part.geometry_hints

        # ----------------------------------------------------------------
        # Step 1 — BendingLine
        # Regola: special_layers con bending → solo quelle, interpreter tace.
        #         Nessun bending in special → interpreter libero.
        # ----------------------------------------------------------------
        if use_special_bending:
            bending_lines = _bending_lines_from_special(msp, part)
        else:
            bending_lines = []

        # ----------------------------------------------------------------
        # Step 2 — Interpreter (countersink, threaded_hole, BL se libero)
        # ----------------------------------------------------------------
        if interpreter is not None:
            classified: List[ClassifiedEntity] = interpreter.classify(
                entities=result.trash_entities,
                outer_poly=part.outer.polygon,
                inner_polys=[i.polygon for i in part.inners],
                msp=msp,
                hints={
                    "countersink_ids":   hints.countersink_ids,
                    "threaded_hole_ids": hints.threaded_hole_ids,
                    "bend_line_ids":     hints.bend_line_ids,
                },
            )
            result.classified_entities.extend(classified)

            # BL dall'interpreter — solo se special non le ha già coperte
            if not use_special_bending:
                bending_lines = getattr(interpreter, "bend_lines", [])

        # ----------------------------------------------------------------
        # Step 3 — Scrivi bending_lines_data su part.custom
        # ----------------------------------------------------------------
        part.custom["bending_lines_data"] = [
            bl.to_dict() for bl in bending_lines
        ]

        # ----------------------------------------------------------------
        # Step 4 — countersink_data e threaded_hole_data da classified
        # ----------------------------------------------------------------
        part.custom.setdefault("countersink_data",   [])
        part.custom.setdefault("threaded_hole_data", [])

        for ce in result.classified_entities:
            if not part.outer.polygon.contains(
                _entity_midpoint(ce.entity)
            ):
                continue
            if ce.work_type == "countersink":
                part.custom["countersink_data"].append({
                    "layer":      ce.entity.dxf.layer if ce.entity.dxf.hasattr("layer") else "",
                    "confidence": ce.confidence,
                    "source":     ce.source,
                })
            elif ce.work_type == "threaded_hole":
                part.custom["threaded_hole_data"].append({
                    "layer":      ce.entity.dxf.layer if ce.entity.dxf.hasattr("layer") else "",
                    "confidence": ce.confidence,
                    "source":     ce.source,
                })

        # ----------------------------------------------------------------
        # Step 5 — extra_metadata (material, thickness, ecc.)
        # ----------------------------------------------------------------
        if extra_metadata:
            part.custom.update(extra_metadata)
        else:
            if "material" not in part.custom:
                warnings.append(f"{part.label}: materiale non specificato.")
            if "thickness" not in part.custom:
                warnings.append(f"{part.label}: spessore non specificato.")

    # ----------------------------------------------------------------
    # Step 6 — entità extra (fold_lines, punch, mark, trash)
    # ----------------------------------------------------------------
    _classify_extra_entities(msp, result.parts, emap, warnings)

    # Propaga i warning
    result.warnings.extend(warnings)

    return result


# ---------------------------------------------------------------------------
# Utility interna
# ---------------------------------------------------------------------------

def _entity_midpoint(entity) -> Point:
    """Punto medio di un'entità — usato per il containment check."""
    try:
        s = entity.dxf.start
        e = entity.dxf.end
        return Point((s.x + e.x) / 2, (s.y + e.y) / 2)
    except Exception:
        try:
            c = entity.dxf.center
            return Point(c.x, c.y)
        except Exception:
            return Point(0, 0)
