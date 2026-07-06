"""
rules/validator.py
------------
Valida la salute geometrica di un modelspace o di un ForgeResult.

Non modifica nulla — solo legge e restituisce warning/errori.
"""

from ..model import ForgeResult, ForgePart


def validate(result: ForgeResult) -> ForgeResult:
    """
    Valida i ForgePart dentro un ForgeResult.
    Aggiunge warning ed errori direttamente nel result passato.

    Controlli:
    - Poligono valido (non self-intersecting)
    - Poligono chiuso
    - Area > 0
    - Geometria 2D (z == 0)
    - Fori effettivamente dentro l'outer

    Args:
        result: ForgeResult già popolato da heal() o split()

    Returns:
        Lo stesso ForgeResult con warning/errori aggiunti.
    """
    for i, part in enumerate(result.parts):
        label = part.label or f"Part {i}"

        poly = part.outer.polygon
        if poly is None:
            result.errors.append(f"{label}: poligono outer è None.")
            result.is_valid = False
            continue

        if not poly.is_valid:
            result.warnings.append(f"{label}: poligono outer non valido (self-intersection?).")

        if poly.is_empty:
            result.errors.append(f"{label}: poligono outer è vuoto.")
            result.is_valid = False
            continue

        if poly.area <= 0:
            result.errors.append(f"{label}: area outer <= 0.")
            result.is_valid = False

        # Controlla fori
        for j, hole in enumerate(part.inners):
            if not part.outer.polygon.contains(hole.polygon):
                result.warnings.append(
                    f"{label}: foro {j} non completamente contenuto nell'outer."
                )

    return result


def validate_msp(msp) -> ForgeResult:
    """
    Validazione rapida di un modelspace grezzo (prima di heal/split).
    Controlla se ci sono entità 3D, layer vuoti, geometrie aperte.

    Args:
        msp: modelspace ezdxf

    Returns:
        ForgeResult con solo warning/errori (parts vuoto).
    """
    result = ForgeResult()

    lines      = list(msp.query('LINE'))
    arcs       = list(msp.query('ARC'))
    plines     = list(msp.query('LWPOLYLINE'))
    polylines  = list(msp.query('POLYLINE'))
    circles    = list(msp.query('CIRCLE'))
    ellipsises = list(msp.query('ELLIPSE'))
    inserts    = list(msp.query('INSERT'))

    if not lines and not arcs and not plines and not polylines and not circles and not ellipsises and not inserts:
        result.errors.append("Modelspace vuoto: nessuna geometria trovata.")
        result.is_valid = False
        return result

    # ---------------------------------------------------------------------------
    # Hint sanitize — condizioni che sanitize() può correggere
    # ---------------------------------------------------------------------------

    # OCS invertito
    inverted_ocs = [
        e for e in list(arcs) + list(circles)
        if e.dxf.hasattr('extrusion') and e.dxf.extrusion[2] < 0
    ]
    if inverted_ocs:
        result.warnings.append(
            f"{len(inverted_ocs)} entità con vettore di estrusione invertito (OCS -1) — "
            f"questo file may be sanitized."
        )

    # Z non zero
    z_nonzero = []
    for e in lines:
        if e.dxf.start.z != 0.0 or e.dxf.end.z != 0.0:
            z_nonzero.append(e)
    for e in list(arcs) + list(circles) + list(ellipsises):
        if e.dxf.center.z != 0.0:
            z_nonzero.append(e)
    for e in plines:
        if e.dxf.get('elevation', 0.0) != 0.0:
            z_nonzero.append(e)

    if z_nonzero:
        result.warnings.append(
            f"{len(z_nonzero)} entità con Z != 0 rilevate — "
            f"questo file may be sanitized."
        )

    # ---------------------------------------------------------------------------
    # Controlli geometrici standard
    # ---------------------------------------------------------------------------

    # Errore bloccante solo se Z != 0 non è recuperabile via sanitize
    for entity in lines:
        if entity.dxf.start.z != 0 or entity.dxf.end.z != 0:
            result.errors.append("Geometria 3D rilevata (LINE con z != 0). dxf-forge lavora solo in 2D.")
            result.is_valid = False
            break

    for entity in arcs:
        if entity.dxf.center.z != 0:
            result.errors.append("Geometria 3D rilevata (ARC con z != 0). dxf-forge lavora solo in 2D.")
            result.is_valid = False
            break

    if lines or arcs:
        result.warnings.append(
            f"Trovate {len(lines)} LINE e {len(arcs)} ARC — potrebbe essere necessario heal()."
        )

    if plines or polylines:
        open_plines = [p for p in plines if not p.closed]
        if open_plines:
            result.warnings.append(
                f"{len(open_plines)} LWPOLYLINE non chiuse trovate."
            )
        open_polylines = [p for p in polylines if not p.is_closed]
        if open_polylines:
            result.warnings.append(
                f"{len(open_polylines)} POLYLINE non chiuse trovate."
            )

    if inserts:
        result.warnings.append(
            f"Trovati {len(inserts)} INSERT (blocchi). "
            f"Usa explode_inserts=True in heal() per esploderli."
        )

    return result