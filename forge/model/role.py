"""
model/role.py

Ruolo semantico di una forma nel contesto manifatturiero.
Unica fonte di verità — usato da ClosedShape, OpenShape, detect.py.

layer_to_role() è la mappatura pura stringa→ruolo (nessuna dipendenza
da ezdxf o altro formato) — usata dal core (loop_finder, hierarchy)
per tradurre label_map senza mai toccare l'entità sorgente.
"""

from enum import Enum
from typing import Dict


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


# ---------------------------------------------------------------------------
# work_type stringa → ContourRole — mappatura pura, zero dipendenze di formato
# ---------------------------------------------------------------------------
WORK_TYPE_TO_ROLE: Dict[str, ContourRole] = {
    "outer":         ContourRole.OUTER,
    "hole":          ContourRole.HOLE,
    "bending":       ContourRole.BEND,
    "bend":          ContourRole.BEND,
    "frame":         ContourRole.FRAME,
    "inner":         ContourRole.INNER,
    "countersink":   ContourRole.COUNTERSINK,
    "threaded_hole": ContourRole.THREADED_HOLE,
    "engrave":       ContourRole.ENGRAVE,
    "marking":       ContourRole.MARKING,
}


def layer_to_role(layer: str, label_map: Dict[str, str]) -> ContourRole:
    """
    Traduce un nome layer nel ContourRole corrispondente via label_map.

    Pura — non tocca mai un'entità sorgente. label_map è
    {nome_layer: work_type}, chiavi case-insensitive.
    """
    layer = layer or ""
    work_type = label_map.get(layer, label_map.get(layer.lower(), ""))
    return WORK_TYPE_TO_ROLE.get(work_type.lower(), ContourRole.UNKNOWN)
