"""
model/role.py

Ruolo semantico di una forma nel contesto manifatturiero.

``ContourRole`` NON è un universo chiuso: è la raccolta dei ruoli che forge
conosce e sa classificare. Un consumatore (un layer sopra forge, l'interprete,
un agente) può assegnare un ruolo che forge non conosce — ``"title_block"``,
``"section"``, ``"nesting_region"`` — e forge lo conserva, lo tratta come non
strutturale e lo manda su ``Trash`` in output, senza sollevare. Vedi MAP.md D27.

``normalize_role()`` è l'unico punto in cui una stringa-ruolo che arriva dal
chiamante entra nel modello: la ripulisce una volta sola in uno slug sicuro,
così tutto il codice a valle (nomi layer DXF, chiavi/valori serializzati,
attributi SVG) se ne può fidare senza ri-validarla.

``layer_to_role()`` è la mappatura pura nome-layer → ruolo via ``label_map`` —
nessuna dipendenza da ezdxf o dal formato, usata dal core e dagli adapter per
tradurre ``label_map`` senza mai toccare l'entità sorgente.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict

# Slug ruolo: minuscole, cifre, _ e -. Tutto il resto viene collassato in "_"
# da normalize_role — è quello che neutralizza i payload di injection
# (`"</cluster>"`, newline, caratteri vietati nei nomi layer DXF).
_MAX_ROLE_LEN = 64
_ROLE_SLUG_RE = re.compile(r"[^a-z0-9_-]+")


class ContourRole(str, Enum):
    """
    I ruoli che forge conosce e sa classificare. **Non esaustivo** — un
    consumatore può assegnare altre stringhe (vedi ``normalize_role``).

    Eredita da str: il valore è già una stringa normale, quindi JSON/repr
    scrivono ``"outer"`` invece di ``<ContourRole.OUTER: 'outer'>`` e le
    comparazioni con stringhe funzionano senza ``.value``.
    """
    UNKNOWN = "unknown"   # default — l'adapter non sa / non mappato
    OUTER   = "outer"     # profilo esterno della parte
    HOLE    = "hole"      # foro (confermato da detect o da label_map)
    COUNTERSINK   = "countersink"     # foro svasato
    THREADED_HOLE = "threaded_hole"   # foro filettato
    BEND    = "bending"      # linea / contorno di piega
    FRAME   = "frame"     # cornice / riferimento di lavorazione
    INNER   = "inner"     # loop interno non ancora classificato
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


def normalize_role(value) -> str:
    """
    Ripulisce una stringa-ruolo che arriva dal chiamante (``label_map``,
    ``linetype_map``, ``load_geometry``) e la restituisce come slug sicuro.

    È l'unico punto d'ingresso: da qui in poi ``feature.role`` è sempre o una
    costante di ``ContourRole`` o uno slug ``[a-z0-9_-]`` corto, di cui il
    resto di forge si fida senza ri-controllarlo.

    - non-stringa o vuota → ``"unknown"``
    - minuscole, ``_``/``-`` esterni rimossi
    - caratteri fuori da ``[a-z0-9_-]`` collassati in ``_``
    - troncata a 64 caratteri
    - se è un ruolo noto → la costante canonica di ``ContourRole``
    - altrimenti → lo slug così com'è (ruolo di un layer sopra forge)

    Non fare mai lookup dinamici sull'enum (``ContourRole[s]``, ``getattr``,
    ``ContourRole(s)``): sollevano o raggiungono attributi di classe. Qui si
    passa sempre per un dict.
    """
    if not isinstance(value, str):
        return ContourRole.UNKNOWN.value
    slug = _ROLE_SLUG_RE.sub("_", value.strip().lower()).strip("_-")
    slug = slug[:_MAX_ROLE_LEN]
    if not slug:
        return ContourRole.UNKNOWN.value
    known = WORK_TYPE_TO_ROLE.get(slug)
    return known if known is not None else slug


def role_str(role) -> str:
    """
    Valore stringa di un ruolo, che sia una costante ``ContourRole`` o una
    stringa già pura. Da usare al posto di ``role.value``, che esplode su una
    ``str`` semplice.
    """
    return role.value if isinstance(role, ContourRole) else str(role)


def layer_to_role(layer: str, label_map: Dict[str, str]) -> str:
    """
    Traduce un nome layer nel ruolo corrispondente via ``label_map``.

    Pura — non tocca mai un'entità sorgente. ``label_map`` è
    ``{nome_layer: work_type}``, chiavi case-insensitive. Un ``work_type`` che
    forge non conosce viene conservato (passa per ``normalize_role``), non
    schiacciato a ``UNKNOWN``.
    """
    layer = layer or ""
    work_type = label_map.get(layer, label_map.get(layer.lower(), ""))
    if not work_type:
        return ContourRole.UNKNOWN.value
    return normalize_role(work_type)
