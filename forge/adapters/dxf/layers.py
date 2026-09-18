"""
adapters/dxf/layers.py
----------------------
Nomi layer DXF e mapping semantica→DXF per il formato DXF.

Appartiene all'adapter DXF — NON al core. Conosce solo i tre ruoli del
motore (outer/inner/unknown); qualunque altro ruolo — manifatturiero
(`tools/manufacturing_role.py`) o di un consumatore esterno — prende nome e
colore dal registro di `rules/palette.py` (`register_role_style`) se
qualcuno l'ha registrato, altrimenti dallo slug grezzo e dal grigio
"consumatore" (D31). Questo file non distingue i due casi: stesso
trattamento, nessuna eccezione (MAP.md, "roles out of core").

I colori vengono da rules/palette.py — qui li mappiamo solo ai layer DXF.

Se domani scrivi un SvgAdapter, avrà il suo svg/layers.py con
data-role, classi CSS, colori fill hex — indipendente da questo file.
"""

from ...model.role import ContourRole, role_str
from ...rules.palette import (
    COLOR_OUTER, COLOR_INNER, COLOR_TRASH,
    COLOR_ANNOTATION, COLOR_CONSUMER,
    registered_role_styles,
)

# ---------------------------------------------------------------------------
# Nomi layer DXF — prodotti da forge in output
# ---------------------------------------------------------------------------
LAYER_OUTER      = "OuterContour"
LAYER_INNER      = "InnerContour"
LAYER_ANNOTATION = "Annotation"
TRASH_LAYER      = "Trash"

# ---------------------------------------------------------------------------
# Tutti i layer DXF forge → colore canonico
# Single source of truth per write.py, split.py, test.
# ---------------------------------------------------------------------------
ALL_FORGE_LAYERS: dict[str, int] = {
    LAYER_OUTER:      COLOR_OUTER,
    LAYER_INNER:      COLOR_INNER,
    LAYER_ANNOTATION: COLOR_ANNOTATION,
    TRASH_LAYER:      COLOR_TRASH,
}

# ---------------------------------------------------------------------------
# ContourRole → nome layer DXF — solo i ruoli che il motore conosce.
# Usato da write.py e hierarchy.py per assegnare layer alle entità in output.
# ---------------------------------------------------------------------------
ROLE_TO_LAYER: dict[ContourRole, str] = {
    ContourRole.OUTER: LAYER_OUTER,
    ContourRole.INNER: LAYER_INNER,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def color_for_layer(layer_name: str) -> int:
    """
    Colore DXF canonico per un layer.

    Layer forge → il suo colore semantico. Layer col nome di uno slug di un
    consumatore (`frame`, `title_block`, ...) → `COLOR_CONSUMER` (grigio scuro).
    Fallback: `COLOR_TRASH` (rosso).
    """
    if layer_name in ALL_FORGE_LAYERS:
        return ALL_FORGE_LAYERS[layer_name]
    if layer_name and layer_name != TRASH_LAYER:
        return COLOR_CONSUMER
    return COLOR_TRASH


def role_to_dxf_layer(role) -> str:
    """
    Nome layer DXF per un ruolo.

    Ruolo noto al motore → il suo layer dedicato (`OuterContour`/
    `InnerContour`). Ruolo registrato (`register_role_style(role,
    RoleStyle(layer_name=...))` — detect lo fa per i suoi, un consumatore
    esterno può fare lo stesso) → il nome registrato. Altrimenti: un layer
    **col nome dello slug** stesso (`normalize_role`) — la sua geometria non
    è spazzatura e va tenuta distinta (D31). `unknown` → `Trash`.
    """
    if role in ROLE_TO_LAYER:
        return ROLE_TO_LAYER[role]
    slug = role_str(role)
    style = registered_role_styles().get(slug)
    if style is not None and style.layer_name:
        return style.layer_name
    if slug and slug != ContourRole.UNKNOWN.value:
        return slug
    return TRASH_LAYER
