"""
rules/palette.py
----------------
Palette cromatica semantica di forge — indipendente dal formato.

I colori qui sono decisioni di dominio: "un outer è verde, un hole è magenta".
Questo vale sia che tu scriva un DXF, un SVG, o un PDF.

Chi li usa:
    adapters/dxf/layers.py  — li traduce in interi colore DXF (ACI)
    adapters/svg/layers.py  — li tradurrà in hex CSS (#rrggbb)
    adapters/pdf/layers.py  — li tradurrà in RGB float

I valori qui sono interi ACI DXF per ragioni storiche — quando arriva
un adapter SVG/PDF andrà aggiunto un mapping ACI→hex in quel modulo.
"""

from ..model.role import ContourRole  # noqa: F401 — importato per comodità dei consumer

# ---------------------------------------------------------------------------
# Colori semantici per ruolo
# ---------------------------------------------------------------------------
COLOR_OUTER         = 3    # verde
COLOR_INNER         = 2    # giallo
COLOR_HOLE          = 6    # magenta
COLOR_BENDING       = 11   # bianco
COLOR_ENGRAVE       = 9    # grigio chiaro
COLOR_MARKING       = 8    # grigio scuro
COLOR_COUNTERSINK   = 5    # blu
COLOR_THREADED_HOLE = 4    # ciano
COLOR_TRASH         = 1    # rosso
COLOR_ANNOTATION    = 7    # bianco/nero (foreground) — testi e quote
COLOR_CONSUMER      = 8    # grigio scuro — ruolo assegnato da un consumatore
                           # (frame, title_block, section, ...): forge non sa
                           # cosa sia, non è spazzatura, non è di taglio

# ---------------------------------------------------------------------------
# ContourRole → colore semantico
# Unica fonte di verità — gli adapter la leggono per costruire la propria
# rappresentazione cromatica nel formato target.
# ---------------------------------------------------------------------------
ROLE_TO_COLOR: dict = {
    ContourRole.OUTER:         COLOR_OUTER,
    ContourRole.INNER:         COLOR_INNER,
    ContourRole.HOLE:          COLOR_HOLE,
    ContourRole.COUNTERSINK:   COLOR_COUNTERSINK,
    ContourRole.THREADED_HOLE: COLOR_THREADED_HOLE,
    ContourRole.BEND:          COLOR_BENDING,
    ContourRole.ENGRAVE:       COLOR_ENGRAVE,
    ContourRole.MARKING:       COLOR_MARKING,
    ContourRole.UNKNOWN:       COLOR_TRASH,
}

# ---------------------------------------------------------------------------
# ACI (intero colore DXF) → hex CSS.
# I 10 colori ACI che forge usa, con i valori RGB canonici AutoCAD. Serve a
# ogni renderer non-DXF (SVG, HTML, PDF) senza dover dipendere da ezdxf o dal
# formato. Se aggiungi un COLOR_* qui sopra, aggiungi la riga corrispondente.
# ---------------------------------------------------------------------------
ACI_TO_HEX: dict = {
    1:  "#ff0000",   # rosso
    2:  "#ffff00",   # giallo
    3:  "#00ff00",   # verde
    4:  "#00ffff",   # ciano
    5:  "#0000ff",   # blu
    6:  "#ff00ff",   # magenta
    7:  "#ffffff",   # foreground (bianco su fondo scuro)
    8:  "#808080",   # grigio scuro
    9:  "#c0c0c0",   # grigio chiaro
    11: "#ff7f7f",   # rosa
}


def role_to_color(role) -> int:
    """
    Colore ACI di un ruolo. Ruolo noto → il suo colore semantico;
    ``unknown`` → rosso trash; slug di un consumatore (``frame``, ...) →
    ``COLOR_CONSUMER`` (grigio scuro, non spazzatura).
    """
    aci = ROLE_TO_COLOR.get(role)
    if aci is not None:
        return aci
    if role and role != ContourRole.UNKNOWN.value:
        return COLOR_CONSUMER
    return COLOR_TRASH


def role_to_hex(role, fallback: str = "#ff0000") -> str:
    """ContourRole → colore hex CSS. Passa per role_to_color + ACI_TO_HEX."""
    return ACI_TO_HEX.get(role_to_color(role), fallback)
