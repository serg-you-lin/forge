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