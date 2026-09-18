"""
tools/manufacturing_role.py
----------------------------
Vocabolario manifatturiero — foro, foro filettato, svasatura, piega,
incisione, marcatura. Prima viveva in ``model/role.py`` (motore); non è
topologia, è detect che gli dà significato — quindi sta qui, a fianco di
``detect.py``, non nel motore (MAP.md, "roles out of core").

``core``/``model`` non importano mai questo modulo. È ``detect()`` che lo usa
per classificare, ed è ``heal(doc, is_structural=...)`` che riceve
``is_structural`` da chi lo chiama (tipicamente ``heal_and_detect()``, che
passa proprio questa funzione) — mai il contrario: il motore non sa cosa sia
un foro, sa solo eseguire un predicato che gli viene passato.

Chi chiama ``heal()`` da solo, senza passare ``is_structural``, non ha questo
vocabolario a disposizione: i ruoli qui sotto sono trattati come qualunque
altro ruolo di consumatore, non strutturali di default (heal() lo segnala con
un warning — vedi ``core/heal.py::_split_labeled``). ``heal_and_detect()``
inietta questo modulo automaticamente.
"""

from __future__ import annotations

from typing import Dict

from ..model.role import ContourRole, is_structural_role as _core_is_structural

# ---------------------------------------------------------------------------
# I ruoli manifatturieri — stringhe semplici, non un ContourRole: il motore
# non deve poterli importare per nome. Confrontabili con `==` come qualunque
# altro ruolo (tutto in forge lo confronta per valore, mai per identità/tipo
# — vedi model/role.py::role_str).
# ---------------------------------------------------------------------------
HOLE          = "hole"
COUNTERSINK   = "countersink"
THREADED_HOLE = "threaded_hole"
BEND          = "bending"
ENGRAVE       = "engrave"
MARKING       = "marking"

# Quali di questi sono topologia di contorno di pezzo (un foro è un vero
# contorno interno, una piega/incisione/marcatura non lo è) — la stessa
# domanda che `model.role.STRUCTURAL_ROLES` risponde per outer/inner, qui
# estesa al vocabolario che il motore non conosce.
STRUCTURAL_MANUFACTURING_ROLES = frozenset({HOLE, COUNTERSINK, THREADED_HOLE})

# I ruoli che detect() sa collocare come feature di un cluster (usato da
# detect.py per distinguere "proxy già classificato da label_map" da "proxy
# ancora da inferire").
ALL_MANUFACTURING_ROLES = frozenset({HOLE, COUNTERSINK, THREADED_HOLE, BEND, ENGRAVE, MARKING})

# work_type stringa (label_map/linetype_map/color_map) → ruolo. Estende
# model.role.WORK_TYPE_TO_ROLE (che qui non tocchiamo) con i nomi
# manifatturieri — usata da detect/adapter quando serve il nome canonico.
WORK_TYPE_TO_ROLE: Dict[str, str] = {
    "hole":          HOLE,
    "bending":       BEND,
    "bend":          BEND,
    "countersink":   COUNTERSINK,
    "threaded_hole": THREADED_HOLE,
    "engrave":       ENGRAVE,
    "marking":       MARKING,
}


# Nomi layer DXF di default per l'output — registrati sotto via
# register_role_style, e la fonte di verità per chi (tipicamente i test)
# deve confrontare un layer scritto in output senza reinventare la stringa.
LAYER_HOLE          = "Hole"
LAYER_COUNTERSINK   = "Countersink"
LAYER_THREADED_HOLE = "ThreadHole"
LAYER_BENDING       = "Bending"
LAYER_ENGRAVE       = "Engrave"
LAYER_MARKING       = "Marking"


def is_structural(role) -> bool:
    """
    Predicato strutturale COMPLETO: outer/inner (motore) + hole/countersink/
    threaded_hole (manifatturiero). Questo è quello che `heal_and_detect()`
    passa a `heal(doc, is_structural=...)` — il motore da solo conosce solo
    la metà `model.role.is_structural_role`.
    """
    return _core_is_structural(role) or role in STRUCTURAL_MANUFACTURING_ROLES


def _register_default_styles() -> None:
    """
    Registra colore + nome layer di default per i ruoli manifatturieri —
    stessi valori che stavano hardcoded in rules/palette.py e
    adapters/dxf/layers.py prima del refactor. Gira all'import di questo
    modulo (quindi automaticamente quando forge viene importato, dato che
    forge/__init__.py importa detect): zero regressione sull'output di
    default, zero sapere manifatturiero fuori da qui — detect si registra
    con lo stesso meccanismo pubblico (`register_role_style`) che userebbe
    un consumatore esterno, nessun trattamento privilegiato.
    """
    from ..rules.palette import register_role_style, RoleStyle

    # Valori copiati da rules.palette.ACI_TO_HEX (mai dal commento accanto a
    # COLOR_BENDING — diceva "bianco" ma ACI 11 è "#ff7f7f", rosa: il
    # commento era sbagliato, il valore vero è quello della tabella hex).
    register_role_style(HOLE,          RoleStyle(color=(255, 0, 255),   layer_name=LAYER_HOLE))          # magenta, ACI 6
    register_role_style(COUNTERSINK,   RoleStyle(color=(0, 0, 255),     layer_name=LAYER_COUNTERSINK))   # blu, ACI 5
    register_role_style(THREADED_HOLE, RoleStyle(color=(0, 255, 255),   layer_name=LAYER_THREADED_HOLE)) # ciano, ACI 4
    register_role_style(BEND,          RoleStyle(color=(255, 127, 127), layer_name=LAYER_BENDING))       # rosa, ACI 11
    register_role_style(ENGRAVE,       RoleStyle(color=(192, 192, 192), layer_name=LAYER_ENGRAVE))       # grigio chiaro, ACI 9
    register_role_style(MARKING,       RoleStyle(color=(128, 128, 128), layer_name=LAYER_MARKING))       # grigio scuro, ACI 8


_register_default_styles()
