"""
adapters/dxf/layers.py
----------------------
Nomi layer DXF e mapping semantica→DXF per il formato DXF.

Appartiene all'adapter DXF — NON al core.
I colori vengono da rules/palette.py — qui li mappiamo solo ai layer DXF.

Se domani scrivi un SvgAdapter, avrà il suo svg/layers.py con
data-role, classi CSS, colori fill hex — indipendente da questo file.
"""

from ...model.role import ContourRole, role_str
from ...rules.palette import (
    COLOR_OUTER, COLOR_INNER, COLOR_HOLE,
    COLOR_BENDING, COLOR_ENGRAVE, COLOR_MARKING,
    COLOR_COUNTERSINK, COLOR_THREADED_HOLE, COLOR_TRASH,
    COLOR_ANNOTATION, COLOR_CONSUMER,
)

# ---------------------------------------------------------------------------
# Nomi layer DXF — prodotti da forge in output
# ---------------------------------------------------------------------------
LAYER_OUTER         = "OuterContour"
LAYER_INNER         = "InnerContour"
LAYER_HOLE          = "Hole"
LAYER_BENDING       = "Bending"
LAYER_ENGRAVE       = "Engrave"
LAYER_MARKING       = "Marking"
LAYER_COUNTERSINK   = "Countersink"
LAYER_THREADED_HOLE = "ThreadHole"
LAYER_ANNOTATION    = "Annotation"
TRASH_LAYER         = "Trash"

# ---------------------------------------------------------------------------
# Tutti i layer DXF forge → colore canonico
# Single source of truth per write.py, split.py, test.
# ---------------------------------------------------------------------------
ALL_FORGE_LAYERS: dict[str, int] = {
    LAYER_OUTER:         COLOR_OUTER,
    LAYER_INNER:         COLOR_INNER,
    LAYER_HOLE:          COLOR_HOLE,
    LAYER_BENDING:       COLOR_BENDING,
    LAYER_ENGRAVE:       COLOR_ENGRAVE,
    LAYER_MARKING:       COLOR_MARKING,
    LAYER_COUNTERSINK:   COLOR_COUNTERSINK,
    LAYER_THREADED_HOLE: COLOR_THREADED_HOLE,
    LAYER_ANNOTATION:    COLOR_ANNOTATION,
    TRASH_LAYER:         COLOR_TRASH,
}

# ---------------------------------------------------------------------------
# ContourRole → nome layer DXF
# Usato da write.py e hierarchy.py per assegnare layer alle entità in output.
# ---------------------------------------------------------------------------
ROLE_TO_LAYER: dict[ContourRole, str] = {
    ContourRole.OUTER:        LAYER_OUTER,
    ContourRole.INNER:        LAYER_INNER,
    ContourRole.HOLE:         LAYER_HOLE,
    ContourRole.COUNTERSINK:  LAYER_COUNTERSINK,
    ContourRole.THREADED_HOLE: LAYER_THREADED_HOLE,
    ContourRole.BEND:         LAYER_BENDING,
    ContourRole.ENGRAVE:      LAYER_ENGRAVE,
    ContourRole.MARKING:      LAYER_MARKING,
}

# ---------------------------------------------------------------------------
# work_type stringa → (layer DXF, colore)
# Usato da detect() → write() per le ClassifiedEntity.
# Chiavi lowercase.
# ---------------------------------------------------------------------------
WORK_TYPE_TO_LAYER: dict[str, tuple[str, int]] = {
    "bending":       (LAYER_BENDING,       COLOR_BENDING),
    "bend":          (LAYER_BENDING,       COLOR_BENDING),
    "engrave":       (LAYER_ENGRAVE,       COLOR_ENGRAVE),
    "marking":       (LAYER_MARKING,       COLOR_MARKING),
    "countersink":   (LAYER_COUNTERSINK,   COLOR_COUNTERSINK),
    "threaded_hole": (LAYER_THREADED_HOLE, COLOR_THREADED_HOLE),
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

    Ruolo noto a forge → il suo layer dedicato. Ruolo assegnato da un
    consumatore (slug già sanificato da `normalize_role`, es. `frame`) → un
    layer **col nome dello slug**: la sua geometria non è spazzatura e va
    tenuta distinta (D31). `unknown` → `Trash`.
    """
    if role in ROLE_TO_LAYER:
        return ROLE_TO_LAYER[role]
    slug = role_str(role)
    if slug and slug != ContourRole.UNKNOWN.value:
        return slug
    return TRASH_LAYER
