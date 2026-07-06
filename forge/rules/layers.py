
"""
layers.py
---------
Unica fonte di verità per i nomi dei layer DXF usati da dxf-forge.

STRUTTURALI — prodotti da heal(), certezza assoluta
    Rappresentano la geometria del pezzo — contorni e fori semplici.
    heal() li assegna autonomamente, nessun input esterno necessario.

    LAYER_OUTER : contorno esterno del pezzo
    LAYER_INNER : contorno interno (cave, asole, aperture grandi)
    LAYER_HOLE  : foro circolare (CIRCLE diametro < HOLE_DIAMETER_THRESHOLD)

LAVORAZIONI — prodotti da detect(), certezza variabile
    Rappresentano operazioni di lavorazione — non geometria strutturale.
    detect() li assegna via special_layers (certezza 1.0) o via
    detection geometrica/agente (certezza < 1.0).

    LAYER_BENDING       : linee di piega
    LAYER_ENGRAVE       : bulinature, riferimenti
    LAYER_MARKING       : marcatura nome pezzo
    LAYER_COUNTERSINK   : foro svasato (due cerchi concentrici, o layer noto)
    LAYER_THREADED_HOLE : foro filettato (arco 270° concentrico, o layer noto)

RESIDUO
    TRASH_LAYER : tutto ciò che detect() non classifica
                  quote, note, misure, linee di centro → non vanno a CAM

REGOLA FORI
    CIRCLE diametro <  HOLE_DIAMETER_THRESHOLD → LAYER_HOLE      (heal)
    CIRCLE diametro >= HOLE_DIAMETER_THRESHOLD → LAYER_INNER     (heal)
    CIRCLE con geometria svasatura             → LAYER_COUNTERSINK (detect)
    CIRCLE con geometria filettatura           → LAYER_THREADED_HOLE (detect)

    Nota: countersink e threaded_hole partono come LAYER_HOLE da heal(),
    poi detect() li riclassifica sul layer corretto.

WORK_TYPE_TO_LAYER
    Mappa work_type → (layer canonico, colore DXF).
    Usato da detect() e da _apply_to_msp() per assegnare layer e colore
    alle entità classificate.
    Solo lavorazioni — i layer strutturali non hanno work_type.

    special_layers in input:  {'LAYER_A': 'bending', 'LAYER_B': 'countersink'}
    WORK_TYPE_TO_LAYER risolve: 'bending' → (LAYER_BENDING, COLOR_BENDING)
"""

# ---------------------------------------------------------------------------
# Layer strutturali — heal()
# ---------------------------------------------------------------------------
LAYER_OUTER = "OuterContour"
LAYER_INNER = "InnerContour"
LAYER_HOLE  = "Hole"

# ---------------------------------------------------------------------------
# Layer lavorazioni — detect()
# ---------------------------------------------------------------------------
LAYER_BENDING       = "Bending"
LAYER_ENGRAVE       = "Engrave"
LAYER_MARKING       = "Marking"
LAYER_COUNTERSINK   = "Countersink"
LAYER_THREADED_HOLE = "ThreadHole"

# ---------------------------------------------------------------------------
# Layer residuo
# ---------------------------------------------------------------------------
TRASH_LAYER = "Trash"

# ---------------------------------------------------------------------------
# Colori DXF
# ---------------------------------------------------------------------------
COLOR_OUTER         = 3   # verde
COLOR_INNER         = 2   # giallo
COLOR_HOLE          = 6   # magenta
COLOR_BENDING       = 11  # bianco
COLOR_ENGRAVE       = 9   # grigio chiaro
COLOR_MARKING       = 8   # grigio scuro
COLOR_COUNTERSINK   = 5   # blu
COLOR_THREADED_HOLE = 4   # ciano
COLOR_TRASH         = 1   # rosso

# ---------------------------------------------------------------------------
# Soglia diametro fori — heal()
# ---------------------------------------------------------------------------
HOLE_DIAMETER_THRESHOLD = 32.1  # mm

# ---------------------------------------------------------------------------
# Set layer strutturali
# Usato da heal() per skippare entità già classificate nella raccolta trash.
# NON include lavorazioni — countersink e threaded sono lavorazioni, non struttura.
# ---------------------------------------------------------------------------
STRUCTURAL_LAYERS = {
    LAYER_OUTER.upper(),
    LAYER_INNER.upper(),
    LAYER_HOLE.upper(),
}

# ---------------------------------------------------------------------------
# Set layer lavorazioni
# Usato da detect() e _apply_to_msp() per riconoscere entità già classificate.
# ---------------------------------------------------------------------------
WORK_LAYERS = {
    LAYER_BENDING.upper(),
    LAYER_ENGRAVE.upper(),
    LAYER_MARKING.upper(),
    LAYER_COUNTERSINK.upper(),
    LAYER_THREADED_HOLE.upper(),
}

# ---------------------------------------------------------------------------
# Mapping work_type → (layer canonico, colore)
# Chiavi: stringhe lowercase — confronto sempre via .lower()
# ---------------------------------------------------------------------------
WORK_TYPE_TO_LAYER = {
    "bending":       (LAYER_BENDING,       COLOR_BENDING),
    "engrave":       (LAYER_ENGRAVE,       COLOR_ENGRAVE),
    "marking":       (LAYER_MARKING,       COLOR_MARKING),
    "countersink":   (LAYER_COUNTERSINK,   COLOR_COUNTERSINK),
    "threaded_hole": (LAYER_THREADED_HOLE, COLOR_THREADED_HOLE),
}

# ---------------------------------------------------------------------------
# Work type validi — per validazione in detect() e nei test
# ---------------------------------------------------------------------------
VALID_WORK_TYPES = frozenset(WORK_TYPE_TO_LAYER.keys())


# ---------------------------------------------------------------------------
# Tutti i layer forge → colore canonico
# Single source of truth per exporter e test.
# ---------------------------------------------------------------------------
ALL_FORGE_LAYERS = {
    LAYER_OUTER:         COLOR_OUTER,
    LAYER_INNER:         COLOR_INNER,
    LAYER_HOLE:          COLOR_HOLE,
    LAYER_BENDING:       COLOR_BENDING,
    LAYER_ENGRAVE:       COLOR_ENGRAVE,
    LAYER_MARKING:       COLOR_MARKING,
    LAYER_COUNTERSINK:   COLOR_COUNTERSINK,
    LAYER_THREADED_HOLE: COLOR_THREADED_HOLE,
    TRASH_LAYER:         COLOR_TRASH,
}


# ---------------------------------------------------------------------------
# Helper — risoluzione layer → colore
# Single point of truth: evita dict inline sparsi nel codice.
# ---------------------------------------------------------------------------
def color_for_layer(layer_name: str) -> int:
    """Restituisce il colore DXF canonico per un layer forge.
    
    Se il layer non è riconosciuto, restituisce COLOR_TRASH (rosso).
    """
    return ALL_FORGE_LAYERS.get(layer_name, COLOR_TRASH)