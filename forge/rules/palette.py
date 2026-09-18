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

Solo outer/inner/trash/annotation/consumer hanno un colore semantico fisso
qui — sono gli unici ruoli che il motore conosce. Il colore di un ruolo
manifatturiero (hole, bending, ...) o di un altro consumatore si ottiene con
``register_role_style`` qui sotto, non aggiungendo voci a questo file (MAP.md,
"roles out of core"): ``tools/manufacturing_role.py`` lo fa per i ruoli di
``detect()`` allo stesso modo in cui lo farebbe un consumatore esterno.

``RoleStyle`` (D37) è l'override esplicito di questa palette: un ruolo — noto
al motore o assegnato da chiunque altro — non è più per forza grigio/fisso.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from ..model.role import ContourRole, role_str  # noqa: F401 — ContourRole importato per comodità dei consumer

# ---------------------------------------------------------------------------
# Colori semantici per ruolo — solo quelli che il motore conosce
# ---------------------------------------------------------------------------
COLOR_OUTER      = 3    # verde
COLOR_INNER      = 2    # giallo
COLOR_TRASH      = 1    # rosso
COLOR_ANNOTATION = 7    # bianco/nero (foreground) — testi e quote
COLOR_CONSUMER   = 8    # grigio scuro — ruolo che il motore non conosce
                        # (manifatturiero o di un consumatore esterno):
                        # forge non sa cosa sia, non è spazzatura

# ---------------------------------------------------------------------------
# ContourRole → colore semantico
# Unica fonte di verità per outer/inner — gli adapter la leggono per
# costruire la propria rappresentazione cromatica nel formato target.
# ---------------------------------------------------------------------------
ROLE_TO_COLOR: dict = {
    ContourRole.OUTER:   COLOR_OUTER,
    ContourRole.INNER:   COLOR_INNER,
    ContourRole.UNKNOWN: COLOR_TRASH,
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
    """
    Colore hex CSS di un ruolo. Un colore registrato (`register_role_style`)
    vince, in hex diretto — evita il giro per la palette ACI a 10 colori, che
    non ha spazio per il colore RGB pieno che un consumatore può registrare.
    Altrimenti passa per role_to_color (palette del motore) + ACI_TO_HEX.
    """
    style = _REGISTERED_ROLE_STYLES.get(role_str(role))
    if style is not None and style.color is not None:
        r, g, b = style.color
        return f"#{r:02x}{g:02x}{b:02x}"
    return ACI_TO_HEX.get(role_to_color(role), fallback)


# ---------------------------------------------------------------------------
# RoleStyle — override esplicito della palette per ruolo (D37)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoleStyle:
    """
    Override, indipendente dal formato, dell'aspetto visivo di un ruolo in
    output. Ogni campo è opzionale: quello lasciato a ``None`` resta il
    default di forge per quel ruolo (colore semantico di ``ROLE_TO_COLOR``,
    linetype/lineweight del layer di destinazione).

    Il chiamante ne assembla un dizionario ``{ruolo: RoleStyle}`` una volta
    sola e lo passa a qualunque renderer lo supporti (oggi ``to_dxf``, domani
    ``to_svg``) — stesso idioma di ``label_map``/``linetype_map``: dizionario
    esplicito del chiamante, nessuno stato globale mutabile.

    Pensato per crescere per aggiunta, non per modifica: un futuro campo
    (fill, trasparenza, ...) si aggiunge qui senza toccare la firma di
    ``to_dxf``/``to_svg`` né rompere chi già passa un ``RoleStyle`` con meno
    campi — ogni adapter interpreta solo i campi che sa gestire e ignora gli
    altri.

    Args:
        color:      RGB canonico (0-255 per canale). Ogni adapter lo traduce
                     nella propria codifica (``layer.rgb`` per DXF, hex CSS
                     per SVG).
        linetype:    nome di un linetype standard riconosciuto dall'adapter
                     (per DXF: uno dei nomi di ``ezdxf.tools.standards``, es.
                     ``"DASHED"``). Un nome non standard è responsabilità del
                     chiamante.
        lineweight:  spessore linea in millimetri.
        layer_name:  nome di output (layer DXF, `data-role`/gruppo SVG, ...)
                     per questo ruolo, al posto dello slug grezzo. Un ruolo
                     che il motore non conosce va altrimenti su un layer col
                     nome dello slug (D31) — questo campo gli dà un nome
                     leggibile senza bisogno che il motore lo conosca.
    """
    color:      Optional[Tuple[int, int, int]] = None
    linetype:   Optional[str] = None
    lineweight: Optional[float] = None
    layer_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Registro globale di RoleStyle — stesso idioma di set_schema() in
# io/exporter.py per i metadati: un consumatore (framer, bendly, ...)
# registra UNA VOLTA come vuole che appaia un suo ruolo, e ogni to_dxf/split
# successivo lo applica senza doverlo ripassare a ogni chiamata. Il
# `role_styles=` esplicito passato a una singola chiamata resta possibile e
# vince comunque su quanto registrato qui (override puntuale, una tantum).
# ---------------------------------------------------------------------------
_REGISTERED_ROLE_STYLES: dict = {}


def register_role_style(role, style: RoleStyle) -> None:
    """
    Registra uno `RoleStyle` per `role`, valido per ogni render successivo
    (`to_dxf`, `split`, ...) finché non lo si ri-registra o il processo
    termina. `role` può essere una costante `ContourRole` o lo slug stringa
    di un ruolo di consumatore (`normalize_role`) — viene normalizzato a
    stringa qui, così il lookup nei renderer non deve saperne la provenienza.
    """
    _REGISTERED_ROLE_STYLES[role_str(role)] = style


def registered_role_styles() -> dict:
    """Copia del registro attivo — letta dai renderer, mai mutata da loro."""
    return dict(_REGISTERED_ROLE_STYLES)
