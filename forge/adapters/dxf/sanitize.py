"""
adapters/dxf/sanitize.py
-------------------------
Corregge dati DXF corrotti prima di qualsiasi processing geometrico.

Questo modulo opera su entità ezdxf grezze — non conosce il core.
Il chiamante è responsabile di aprire il documento e passare msp.
Le funzioni lavorano in-place e stampano messaggi per ogni fix applicato.

Funzioni pubbliche:
    sanitize — esegue tutti i sanitizer in sequenza
"""

from ezdxf import upright as _upright

_FLATTENABLE_TYPES = frozenset({'LINE', 'ARC', 'CIRCLE', 'LWPOLYLINE', 'ELLIPSE'})


def normalize_ocs(msp, verbose: bool = False) -> None:
    """
    Normalizza il vettore di estrusione di tutte le entità OCS nel modelspace.
    Converte (0,0,-1) → (0,0,1) senza alterare la geometria in WCS.
    """
    _upright.upright_all(msp)
    if verbose:
        print("[sanitize] normalize_ocs: vettori di estrusione normalizzati")


def flatten_z(msp, verbose: bool = False) -> None:
    """
    Porta a 0 tutte le coordinate Z != 0 per LINE, ARC, CIRCLE,
    LWPOLYLINE e ELLIPSE.
    """
    fixed = 0
    skipped_types = set()

    for entity in msp:
        t = entity.dxftype()
        if t not in _FLATTENABLE_TYPES:
            skipped_types.add(t)
            continue

        if t == 'LINE':
            changed = False
            if entity.dxf.start.z != 0.0:
                entity.dxf.start = (entity.dxf.start.x, entity.dxf.start.y, 0.0)
                changed = True
            if entity.dxf.end.z != 0.0:
                entity.dxf.end = (entity.dxf.end.x, entity.dxf.end.y, 0.0)
                changed = True
            if changed:
                fixed += 1
                if verbose:
                    print(f"  [sanitize] LINE Z!=0 corretta su layer '{entity.dxf.layer}'")

        elif t in ('ARC', 'CIRCLE'):
            if entity.dxf.center.z != 0.0:
                entity.dxf.center = (entity.dxf.center.x, entity.dxf.center.y, 0.0)
                fixed += 1
                if verbose:
                    print(f"  [sanitize] {t} Z!=0 corretta su layer '{entity.dxf.layer}'")

        elif t == 'LWPOLYLINE':
            elev = entity.dxf.get('elevation', 0.0)
            if elev != 0.0:
                entity.dxf.elevation = 0.0
                fixed += 1
                if verbose:
                    print(f"  [sanitize] LWPOLYLINE elevation={elev:.3f} → 0 su layer '{entity.dxf.layer}'")

        elif t == 'ELLIPSE':
            center = entity.dxf.center
            if center.z != 0.0:
                entity.dxf.center = (center.x, center.y, 0.0)
                fixed += 1
                if verbose:
                    print(f"  [sanitize] ELLIPSE Z!=0 corretta su layer '{entity.dxf.layer}'")

    # sempre — summary compatto
    if fixed:
        print(f"[sanitize] flatten_z: {fixed} entità corrette")
    if skipped_types and verbose:
        print(f"[sanitize] flatten_z: tipi ignorati — {sorted(skipped_types)}")


def sanitize(msp, flatten_z_flag: bool = True, verbose: bool = False) -> None:
    """
    Esegue tutti i sanitizer in sequenza sul modelspace ricevuto.
    Il chiamante è responsabile di aprire e salvare il documento.

    Args:
        msp:            modelspace ezdxf
        flatten_z_flag: se True, esegue flatten_z
        verbose:        se True, stampa dettaglio per ogni entità corretta
    """
    normalize_ocs(msp, verbose=verbose)
    if flatten_z_flag:
        flatten_z(msp, verbose=verbose)

def _explode_inserts(msp) -> int:
    """
    Esplode tutti gli INSERT (blocchi) nel modelspace in entità primitive.
    Restituisce il numero di INSERT esplosi.
    """
    inserts = list(msp.query('INSERT'))
    if not inserts:
        return 0

    for insert in inserts:
        try:
            insert.explode()
        except Exception as ex:
            print(f"  [WARN] Esplosione INSERT fallita: {ex}")

    return len(inserts)


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