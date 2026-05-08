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
from typing import Optional
from ..models import ForgePart, ForgeResult
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
