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

# ---------------------------------------------------------------------------
# Tipi con coordinate 3D da controllare per Z != 0
# ---------------------------------------------------------------------------

_FLATTENABLE_TYPES = frozenset({'LINE', 'ARC', 'CIRCLE', 'LWPOLYLINE', 'ELLIPSE'})


# ---------------------------------------------------------------------------
# normalize_ocs
# ---------------------------------------------------------------------------

def normalize_ocs(msp) -> None:
    """
    Normalizza il vettore di estrusione di tutte le entità OCS nel modelspace.
    Converte (0,0,-1) → (0,0,1) senza alterare la geometria in WCS.
    """
    _upright.upright_all(msp)
    print("[sanitize] normalize_ocs: vettori di estrusione normalizzati")


# ---------------------------------------------------------------------------
# flatten_z
# ---------------------------------------------------------------------------

def flatten_z(msp) -> None:
    """
    Porta a 0 tutte le coordinate Z != 0 per LINE, ARC, CIRCLE,
    LWPOLYLINE e ELLIPSE.

    LINE/ARC/CIRCLE/ELLIPSE: corregge i singoli attributi dxf.
    LWPOLYLINE: elevation → 0.
    """
    fixed = 0

    for entity in msp:
        t = entity.dxftype()
        if t not in _FLATTENABLE_TYPES:
            print(f"[sanitize] flatten_z: entità {t} su layer '{entity.dxf.layer}' non supportata, ignorata")
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
                print(f"[sanitize] LINE Z!=0 corretta su layer '{entity.dxf.layer}'")

        elif t in ('ARC', 'CIRCLE'):
            if entity.dxf.center.z != 0.0:
                entity.dxf.center = (entity.dxf.center.x, entity.dxf.center.y, 0.0)
                fixed += 1
                print(f"[sanitize] {t} Z!=0 corretta su layer '{entity.dxf.layer}'")

        elif t == 'LWPOLYLINE':
            elev = entity.dxf.get('elevation', 0.0)
            if elev != 0.0:
                entity.dxf.elevation = 0.0
                fixed += 1
                print(f"[sanitize] LWPOLYLINE elevation={elev:.3f} → 0 su layer '{entity.dxf.layer}'")

        elif t == 'ELLIPSE':
            center = entity.dxf.center
            if center.z != 0.0:
                entity.dxf.center = (center.x, center.y, 0.0)
                fixed += 1
                print(f"[sanitize] ELLIPSE Z!=0 corretta su layer '{entity.dxf.layer}'")

    if fixed:
        print(f"[sanitize] flatten_z: {fixed} entità corrette")


# ---------------------------------------------------------------------------
# Entry point pubblico
# ---------------------------------------------------------------------------

def sanitize(msp, flatten_z_flag: bool = True) -> None:
    """
    Esegue tutti i sanitizer in sequenza sul modelspace ricevuto.
    Il chiamante è responsabile di aprire e salvare il documento.
    """
    normalize_ocs(msp)
    if flatten_z_flag:
        flatten_z(msp)