"""
model/role.py

Ruolo semantico di una forma nel contesto manifatturiero.
Unica fonte di verità — usato da ClosedShape, OpenShape, detect.py.

L'adapter DXF traduce label_map (layer → role) prima di consegnare
le shape al core.  detect.py non tocca mai layer o origin.
"""

from enum import Enum


class ContourRole(str, Enum):
    """
    Ruolo semantico di un contorno.

    Eredita da str: il valore è già una stringa normale, quindi
    JSON/repr scrivono "outer" invece di <ContourRole.OUTER: 'outer'>.
    I golden file non si rompono e le comparazioni con stringhe vecchie
    funzionano ancora durante il refactor.
    """
    UNKNOWN = "unknown"   # default — l'adapter non sa / non mappato
    OUTER   = "outer"     # profilo esterno della parte
    HOLE    = "hole"      # foro (confermato da detect o da label_map)
    COUNTERSINK  = "countersink"
    THREADED_HOLE = "threaded_hole"
    BEND    = "bending"      # linea / contorno di piega
    FRAME   = "frame"     # cornice / riferimento di lavorazione
    INNER   = "inner"     # loop interno non ancora classificato come hole
    ENGRAVE = "engrave"
    MARKING = "marking" 