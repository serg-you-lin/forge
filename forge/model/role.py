"""
model/role.py

Ruolo topologico di una forma — il minimo che il motore (core/) deve sapere
per costruire l'albero di contenimento: è un contorno esterno, un contorno
interno, o non ha ancora un ruolo deciso. Punto. **Non vive qui nessuna
tassonomia manifatturiera** (foro, foro filettato, svasatura, piega,
incisione, marcatura, ...) — quella è vocabolario di ``tools/detect.py``
(``forge/tools/manufacturing_role.py``), non del motore: core non sa cosa sia
un foro, sa solo distinguere un contorno da un altro (MAP.md, "roles out of
core").

``ContourRole`` NON è un universo chiuso: un consumatore (un layer sopra
forge, l'interprete, un agente, o lo stesso ``detect()`` di forge — nessuno
dei due è privilegiato) può assegnare un ruolo che core non conosce —
``"hole"``, ``"frame"``, ``"title_block"``, qualunque slug — e forge lo
conserva, lo tratta come non strutturale di default e in output lo scrive su
un layer col nome dello slug (non su ``Trash``: quella geometria non è
spazzatura). Chi vuole che un ruolo che core non conosce sia trattato come
strutturale (un foro è un vero contorno di pezzo, non decorazione) passa il
proprio predicato a ``heal(doc, is_structural=...)`` — vedi
``tools.manufacturing_role.is_structural``, usato di default da
``heal_and_detect()``. Vedi MAP.md D27 e D31.

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
    I tre ruoli che il motore topologico conosce. **Non esaustivo** — un
    consumatore (``tools/detect.py`` incluso: non è privilegiato) assegna
    qualunque altra stringa a un edge/contorno, vedi ``normalize_role``.

    Eredita da str: il valore è già una stringa normale, quindi JSON/repr
    scrivono ``"outer"`` invece di ``<ContourRole.OUTER: 'outer'>`` e le
    comparazioni con stringhe funzionano senza ``.value``.
    """
    UNKNOWN = "unknown"   # default — nessun ruolo deciso
    OUTER   = "outer"     # profilo esterno della parte, trovato da heal()
    INNER   = "inner"     # loop interno, trovato da heal()
    # Non c'è altro qui. `hole`/`countersink`/`threaded_hole`/`bending`/
    # `engrave`/`marking` sono vocabolario manifatturiero — vive in
    # `tools/manufacturing_role.py`, a fianco di `detect()`, che è l'unico a
    # saperne il significato. `frame`/`title_block`/... sono slug di un
    # consumatore esterno (framer, ...) — stesso trattamento, nessuna
    # eccezione: core non distingue "il ruolo di detect" da "il ruolo di un
    # consumatore qualunque", sono entrambi fuori da questo enum.


# ---------------------------------------------------------------------------
# Tassonomia: quali ruoli sono topologia di contorno (motore puro)
# ---------------------------------------------------------------------------
# Unico punto di verità per la domanda "questo edge/loop/proxy è OUTER o INNER
# per come l'ha costruito heal(), a prescindere da qualunque significato
# manifatturiero?". Chi vuole che heal() tratti come strutturale anche un
# ruolo che core non conosce (un foro etichettato da label_map, per esempio)
# passa il proprio predicato a `heal(doc, is_structural=...)` — vedi
# `tools.manufacturing_role.is_structural`. Senza quel predicato, heal()
# tratta qualunque ruolo fuori da qui come non strutturale di default (esce
# dal grafo, resta in trash col ruolo intatto — MAP.md, "roles out of core").
STRUCTURAL_ROLES = frozenset({
    ContourRole.OUTER,
    ContourRole.INNER,
})


def is_structural_role(role) -> bool:
    """
    True se ``role`` è OUTER o INNER per il motore (vedi ``STRUCTURAL_ROLES``).

    Predicato minimo del motore — non sa nulla di fori/pieghe/incisioni.
    Test di appartenenza puro — accetta sia una costante ``ContourRole`` sia lo
    slug stringa equivalente (``ContourRole`` eredita da ``str``). Nessun
    reverse-lookup sull'enum (D27 regola A).
    """
    return role in STRUCTURAL_ROLES


# ---------------------------------------------------------------------------
# work_type stringa → ContourRole — mappatura pura, zero dipendenze di formato
# ---------------------------------------------------------------------------
WORK_TYPE_TO_ROLE: Dict[str, ContourRole] = {
    "outer": ContourRole.OUTER,
    "inner": ContourRole.INNER,
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
