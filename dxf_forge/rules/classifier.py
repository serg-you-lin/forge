"""
classifier.py
-------------
Classifica le entità extra di un DXF e arricchisce i ForgePart con metadati.

Lavora DOPO heal() — non tocca la geometria strutturale.
Riceve un msp, una lista di ForgePart, e una config, e popola part.custom.

Entità riconosciute (per layer, colore, o tipo):
  - fold_lines  : linee di piegatura
  - punch       : bulinatura / punching
  - mark        : marcature
  - trash       : entità non riconosciute (warning)

Metadati pezzo (materiale, spessore) arrivano dall esterno:
  - da distinta (dict passato a mano)
  - da filename (parsing automatico)
  - se mancano → warning nel ForgeResult

Config di default — sovrascrivibile per ogni officina:
    DEFAULT_ENTITY_MAP = {
        "fold_lines": {"layers": ["BEND", "PIEGA", "FOLD"], "colors": []},
        "punch":      {"layers": ["PUNCH", "BULIN"],          "colors": []},
        "mark":       {"layers": ["MARK", "MARCA"],           "colors": []},
    }
"""

from shapely.geometry import Point, MultiPoint
import numpy as np
import math
from typing import Optional
from ..models import ForgePart, ForgeResult, BaseInterpreter, ClassifiedEntity
from ..core.geometry import get_representative_point

# ---------------------------------------------------------------------------
# Config di default
# ---------------------------------------------------------------------------

DEFAULT_ENTITY_MAP = {
    "fold_lines": {"layers": ["BEND", "PIEGA", "FOLD", "PIEGATURA"], "colors": []},
    "punch":      {"layers": ["PUNCH", "BULIN", "PUNCHING"],           "colors": []},
    "mark":       {"layers": ["MARK", "MARCA", "MARKING"],             "colors": []},
}

# Tipi geometria strutturale — ignorati dal classifier (gestiti da healer/splitter)
STRUCTURAL_TYPES = {"LWPOLYLINE", "POLYLINE"}

# Layer strutturali — entità su questi layer sono contorni, non entità extra
STRUCTURAL_LAYERS = {"OUTERCONTOUR", "INNERCONTOUR", "HEALED_HOLE"}


# ---------------------------------------------------------------------------
# Utilità
# ---------------------------------------------------------------------------

def _classify_entity(entity, entity_map: dict) -> Optional[str]:
    """
    Classifica una singola entità in base a layer e colore.
    Restituisce la categoria o None se non riconosciuta.
    """
    layer = entity.dxf.layer.upper() if entity.dxf.hasattr("layer") else ""
    color = entity.dxf.color if entity.dxf.hasattr("color") else None

    for category, rules in entity_map.items():
        if layer in [l.upper() for l in rules.get("layers", [])]:
            return category
        if color is not None and color in rules.get("colors", []):
            return category
    return None


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def classify(
    msp,
    parts: list,
    entity_map: dict = None,
    extra_metadata: dict = None,
    result: ForgeResult = None,
) -> list:
    """
    Classifica le entità extra del msp e arricchisce i ForgePart con metadati.

    Args:
        msp: modelspace ezdxf già healato
        parts: lista di ForgePart da arricchire (result.parts)
        entity_map: mappa di classificazione custom — sovrascrive DEFAULT_ENTITY_MAP.
                    Es: {"fold_lines": {"layers": ["PIEGA"], "colors": [1]}}
        extra_metadata: metadati aggiuntivi da aggiungere a tutti i part.
                        Es: {"material": "S235", "thickness": 2.0}
        result: ForgeResult opzionale — se passato, i warning vengono aggiunti lì

    Returns:
        La stessa lista di parts, con part.custom popolato.

    Esempio:
        result = forge.heal(msp, label="pezzo", source_file="pezzo.dxf")
        forge.classify(
            msp,
            result.parts,
            entity_map={"fold_lines": {"layers": ["PIEGA"]}},
            extra_metadata={"material": "S235", "thickness": 2.0},
            result=result,
        )
        forge.write_metadata_to_dxf(doc, result.parts[0])
    """
    emap = {**DEFAULT_ENTITY_MAP, **(entity_map or {})}
    warnings = []

    # Inizializza custom per ogni part
    for part in parts:
        if "fold_lines" not in part.custom:
            part.custom["fold_lines"] = []
        if "punch" not in part.custom:
            part.custom["punch"] = []
        if "mark" not in part.custom:
            part.custom["mark"] = []
        if "trash" not in part.custom:
            part.custom["trash"] = []

        # Metadati esterni — warning se mancano
        if extra_metadata:
            part.custom.update(extra_metadata)
        else:
            if "material" not in part.custom:
                warnings.append(f"{part.label}: materiale non specificato.")
            if "thickness" not in part.custom:
                warnings.append(f"{part.label}: spessore non specificato.")

    # Classifica entità non strutturali
    for entity in msp:
        if entity.dxftype() in STRUCTURAL_TYPES:
            continue

        # Skippa entità su layer strutturali (contorni già gestiti dall healer)
        layer = entity.dxf.layer.upper() if entity.dxf.hasattr("layer") else ""
        if layer in STRUCTURAL_LAYERS:
            continue

        category = _classify_entity(entity, emap)
        pt = get_representative_point(entity)

        # Assegna al part che contiene l entità
        assigned = False
        for part in parts:
            if pt is not None and part.outer.polygon.contains(pt):
                key = category if category else "trash"
                if key not in part.custom:
                    part.custom[key] = []
                part.custom[key].append({
                    "type":  entity.dxftype(),
                    "layer": entity.dxf.layer if entity.dxf.hasattr("layer") else "",
                    "color": entity.dxf.color if entity.dxf.hasattr("color") else None,
                })
                assigned = True
                break

        if not assigned:
            # Entità non contenuta in nessun part — va in trash globale
            # Questo cattura LINE/ARC orfane rimaste dopo un healing parziale
            if parts:
                key = category if category else "trash"
                if key not in parts[0].custom:
                    parts[0].custom[key] = []
                parts[0].custom[key].append({
                    "type":  entity.dxftype(),
                    "layer": entity.dxf.layer if entity.dxf.hasattr("layer") else "",
                    "color": entity.dxf.color if entity.dxf.hasattr("color") else None,
                    "orphan": True,  # non contenuta in nessun part
                })
            if category:
                warnings.append(
                    f"Entità {entity.dxftype()} su layer {entity.dxf.layer!r} "
                    f"classificata come {category!r} ma non contenuta in nessun part."
                )

    # Conta il trash e avvisa
    for part in parts:
        trash_count = len(part.custom.get("trash", []))
        if trash_count > 0:
            warnings.append(
                f"{part.label}: {trash_count} entità non riconosciute in trash. "
                f"Verificare layer e colori."
            )

    # Propaga i warning
    if result is not None:
        result.warnings.extend(warnings)
    else:
        for w in warnings:
            print(f"  [WARN] {w}")

    return parts


def is_threaded_arc(arc, angle_tolerance: float = 20.0) -> bool:
    if arc.dxftype() != 'ARC':
        return False
    cx, cy = arc.dxf.center.x, arc.dxf.center.y
    r = arc.dxf.radius
    start_rad = math.radians(arc.dxf.start_angle)
    end_rad = math.radians(arc.dxf.end_angle)
    p_start = (cx + r * math.cos(start_rad), cy + r * math.sin(start_rad))
    p_end   = (cx + r * math.cos(end_rad),   cy + r * math.sin(end_rad))
    a1 = math.atan2(p_start[1] - cy, p_start[0] - cx)
    a2 = math.atan2(p_end[1] - cy,   p_end[0] - cx)
    gap = math.degrees(abs(a1 - a2)) % 360
    swept = 360 - gap
    return abs(swept - 270) < angle_tolerance

def is_threaded_hole(circle, all_arcs, tolerance_center: float = 1.0) -> bool:
    cx = circle.dxf.center.x
    cy = circle.dxf.center.y
    for arc in all_arcs:
        dist = np.hypot(cx - arc.dxf.center.x, cy - arc.dxf.center.y)
        if dist < tolerance_center \
           and arc.dxf.radius > circle.dxf.radius \
           and is_threaded_arc(arc):
            return True
    return False


def is_countersink_outer(circle, children, tolerance=1.0):
    cx = circle.dxf.center.x
    cy = circle.dxf.center.y
    cr = circle.dxf.radius

    for other_obj, _, other_tipo in children:
        if other_tipo != 'CIRCLE':
            continue
        ox = other_obj.dxf.center.x
        oy = other_obj.dxf.center.y
        or_ = other_obj.dxf.radius
        if or_ >= cr:         
            continue
        dist = np.hypot(cx - ox, cy - oy)
        if dist < tolerance:
            return True
    return False


class GeometricInterpreter(BaseInterpreter):
    """
    Interpreter geometrico — non usa nomi layer, solo geometria.
    Classifica le entità in Trash basandosi su forma e posizione.
    heal() passa gli hints con le classificazioni già calcolate.
    """

    def classify(self, entities, outer_poly, inner_polys, msp, hints=None):
        classified = []
        hints = hints or {}
        countersink_ids = hints.get("countersink_ids", set())

        for entity in entities:
            if id(entity) in countersink_ids:
                classified.append(ClassifiedEntity(
                    entity=entity,
                    work_type="countersink",
                    confidence=1.0,
                    source="geometric",
                ))

        return classified