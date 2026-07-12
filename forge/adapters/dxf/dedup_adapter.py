"""
adapters/dxf/dedup_adapter.py
------------------------------
Normalizzazione entità DXF — traduzione formato → normalizer.

Unico punto che conosce sia ezdxf che find_duplicates.
Il core (normalizer) non importa mai ezdxf.

Funzioni pubbliche:
    extract_keyed_entities — msp → List[(key, entity)]
    delete_entities        — elimina entità dal msp
    deduplicate            — shortcut: extract + find + delete → int
"""

from __future__ import annotations
from typing import Any, Hashable, List, Optional, Tuple

from ...core.healing.normalizer import find_duplicates


# ---------------------------------------------------------------------------
# Calcolo chiave geometrica per tipo DXF
# ---------------------------------------------------------------------------

def _key_for(entity) -> Optional[Hashable]:
    """
    Restituisce una chiave hashable che identifica univocamente
    la geometria dell'entità, indipendente dall'handle DXF.
    Restituisce None per tipi non gestiti o in caso di errore.
    """
    t     = entity.dxftype()
    layer = entity.dxf.get('layer', '0')

    try:
        if t == 'LINE':
            s   = (round(entity.dxf.start.x, 2), round(entity.dxf.start.y, 2))
            e   = (round(entity.dxf.end.x,   2), round(entity.dxf.end.y,   2))
            pts = tuple(sorted([s, e]))          # ordine canonico: A→B == B→A
            return (t, layer, pts)

        if t in ('LWPOLYLINE', 'POLYLINE'):
            pts = tuple(
                (round(p[0], 2), round(p[1], 2))
                for p in entity.get_points()
            )
            return (t, layer, pts)

        if t == 'CIRCLE':
            c = entity.dxf.center
            return (t, layer,
                    round(c.x, 2), round(c.y, 2),
                    round(entity.dxf.radius, 2))

        if t == 'ARC':
            c = entity.dxf.center
            return (t, layer,
                    round(c.x, 2), round(c.y, 2),
                    round(entity.dxf.radius,      2),
                    round(entity.dxf.start_angle, 1),
                    round(entity.dxf.end_angle,   1))

    except Exception:
        return None

    return None


# ---------------------------------------------------------------------------
# Funzioni pubbliche
# ---------------------------------------------------------------------------

def extract_keyed_entities(msp) -> List[Tuple[Hashable, Any]]:
    """
    Produce la lista (key, entity) per tutte le entità del msp.
    Le entità con tipo non gestito producono key=None e vengono
    ignorate da find_duplicates.
    """
    return [(_key_for(entity), entity) for entity in msp]


def delete_entities(refs: List[Any], msp) -> None:
    """Elimina le entità dal msp in-place."""
    for entity in refs:
        msp.delete_entity(entity)


def deduplicate(msp, tolerance: float = 0.01) -> int:
    """
    Shortcut: estrae chiavi, trova duplicati, li elimina.

    Il parametro tolerance è mantenuto per compatibilità con il
    chiamante attuale (heal.py) ma non è usato nella chiave —
    l'arrotondamento fisso a 2 decimali è la soglia di dedup.
    Da rivedere se serve una dedup tolerance-driven.

    Restituisce il numero di entità eliminate.
    """
    keyed    = extract_keyed_entities(msp)
    to_delete = find_duplicates(keyed)
    delete_entities(to_delete, msp)
    return len(to_delete)
