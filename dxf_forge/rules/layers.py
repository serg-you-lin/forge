# """
# layers.py
# ---------
# Unica fonte di verità per i nomi dei layer DXF usati da dxf-forge.

# Layer strutturali (contorni chiusi):
#     LAYER_OUTER : contorno esterno del pezzo
#     LAYER_INNER : contorno interno (cave, asole, aperture grandi)
#     LAYER_HOLE  : foro circolare piccolo (diametro < HOLE_DIAMETER_THRESHOLD)

# Layer lavorazioni (entità aperte):
#     LAYER_BENDING : linee di piega     → conta pieghe + lunghezza
#     LAYER_MARKING : numerazione pezzo  → lunghezza
#     LAYER_ENGRAVE : bulinature, refer. → lunghezza

# Layer residuo:
#     TRASH_LAYER : tutto ciò che l'healer non classifica

# Regola fori:
#     CIRCLE diametro <  HOLE_DIAMETER_THRESHOLD → LAYER_HOLE
#     CIRCLE diametro >= HOLE_DIAMETER_THRESHOLD → LAYER_INNER

# WORK_TYPE_TO_LAYER:
#     L'utente passa special_layers = {'MARCATURA': 'bending', 'LINEA_PIEGA': 'bending'}
#     Il work_type risolve il layer canonico e il colore da assegnare nel DXF healed.
#     Più layer sorgente possono puntare allo stesso work_type.
# """

# # ---------------------------------------------------------------------------
# # Layer strutturali
# # ---------------------------------------------------------------------------
# LAYER_OUTER   = "OuterContour"
# LAYER_INNER   = "InnerContour"
# LAYER_HOLE    = "Hole"

# # ---------------------------------------------------------------------------
# # Layer lavorazioni
# # ---------------------------------------------------------------------------
# LAYER_BENDING = "Bending"
# LAYER_MARKING = "Mark"
# LAYER_ENGRAVE = "Engrave"
# LAYER_COUNTERSINK = "Countersink"
# LAYER_THREADED_HOLE = "ThreadHole"

# # ---------------------------------------------------------------------------
# # Layer residuo
# # ---------------------------------------------------------------------------
# TRASH_LAYER   = "Trash"

# # ---------------------------------------------------------------------------
# # Colori DXF
# # ---------------------------------------------------------------------------
# COLOR_OUTER   = 3   # verde
# COLOR_INNER   = 2   # giallo
# COLOR_HOLE    = 6   # magenta
# COLOR_BENDING = 7   # bianco
# COLOR_MARKING = 8   # grigio scuro
# COLOR_ENGRAVE = 9   # grigio chiaro
# COLOR_TRASH   = 1   # rosso
# COLOR_COUNTERSINK = 5  # blu
# COLOR_THREADED_HOLE = 4  # ciano

# # ---------------------------------------------------------------------------
# # Soglia diametro fori
# # ---------------------------------------------------------------------------
# HOLE_DIAMETER_THRESHOLD = 32.1  # mm

# # ---------------------------------------------------------------------------
# # Set layer strutturali — usato dall'healer per skippare entità già classificate
# # ---------------------------------------------------------------------------
# STRUCTURAL_LAYERS = {LAYER_OUTER.upper(), LAYER_INNER.upper(), LAYER_HOLE.upper()}

# # ---------------------------------------------------------------------------
# # Mapping work_type → (layer canonico, colore)
# #
# # L'utente decide il work_type in special_layers a runtime.
# # Questo mapping decide dove finisce l'entità nel DXF healed.
# #
# # Tutti e tre alimentano total_engrave_length nei metadati.
# # Solo 'bending' incrementa anche bending_lines.
# # ---------------------------------------------------------------------------
# WORK_TYPE_TO_LAYER = {
#     'bending' : (LAYER_BENDING, COLOR_BENDING),
#     'marking' : (LAYER_MARKING, COLOR_MARKING),
#     'engrave' : (LAYER_ENGRAVE, COLOR_ENGRAVE),
#     'countersink' : (LAYER_COUNTERSINK, COLOR_COUNTERSINK),
#     'threaded_hole' : (LAYER_THREADED_HOLE, COLOR_THREADED_HOLE),
# }



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
LAYER_MARKING       = "Mark"
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
COLOR_BENDING       = 7   # bianco
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
#
# Unica fonte di verità per la risoluzione work_type → layer DXF.
# detect() lo usa per sapere su quale layer spostare l'entità classificata.
# _apply_to_msp() lo usa per assegnare layer e colore nel DXF in output.
#
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