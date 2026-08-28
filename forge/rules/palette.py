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

# ---------------------------------------------------------------------------
# ContourRole → colore semantico
# Unica fonte di verità — gli adapter la leggono per costruire la propria
# rappresentazione cromatica nel formato target.
# ---------------------------------------------------------------------------
ROLE_TO_COLOR: dict = {
    ContourRole.OUTER:   COLOR_OUTER,
    ContourRole.INNER:   COLOR_INNER,
    ContourRole.HOLE:    COLOR_HOLE,
    ContourRole.BEND:    COLOR_BENDING,
    ContourRole.FRAME:   COLOR_OUTER,    # frame → stesso colore outer per ora
    ContourRole.UNKNOWN: COLOR_TRASH,
}
