"""
layers.py
---------
Unica fonte di verità per i nomi dei layer DXF usati da dxf-forge.

Layer strutturali (contorni chiusi):
    LAYER_OUTER : contorno esterno del pezzo
    LAYER_INNER : contorno interno (cave, asole, aperture grandi)
    LAYER_HOLE  : foro circolare piccolo (diametro < HOLE_DIAMETER_THRESHOLD)

Layer lavorazioni (entità aperte):
    LAYER_BENDING : linee di piega     → conta pieghe + lunghezza
    LAYER_MARKING : numerazione pezzo  → lunghezza
    LAYER_ENGRAVE : bulinature, refer. → lunghezza

Layer residuo:
    TRASH_LAYER : tutto ciò che l'healer non classifica

Regola fori:
    CIRCLE diametro <  HOLE_DIAMETER_THRESHOLD → LAYER_HOLE
    CIRCLE diametro >= HOLE_DIAMETER_THRESHOLD → LAYER_INNER

WORK_TYPE_TO_LAYER:
    L'utente passa special_layers = {'MARCATURA': 'bending', 'LINEA_PIEGA': 'bending'}
    Il work_type risolve il layer canonico e il colore da assegnare nel DXF healed.
    Più layer sorgente possono puntare allo stesso work_type.
"""

# ---------------------------------------------------------------------------
# Layer strutturali
# ---------------------------------------------------------------------------
LAYER_OUTER   = "OuterContour"
LAYER_INNER   = "InnerContour"
LAYER_HOLE    = "Hole"

# ---------------------------------------------------------------------------
# Layer lavorazioni
# ---------------------------------------------------------------------------
LAYER_BENDING = "Bending"
LAYER_MARKING = "Mark"
LAYER_ENGRAVE = "Engrave"
LAYER_COUNTERSINK = "Countersink"
LAYER_THREADED_HOLE = "ThreadHole"

# ---------------------------------------------------------------------------
# Layer residuo
# ---------------------------------------------------------------------------
TRASH_LAYER   = "Trash"

# ---------------------------------------------------------------------------
# Colori DXF
# ---------------------------------------------------------------------------
COLOR_OUTER   = 3   # verde
COLOR_INNER   = 2   # giallo
COLOR_HOLE    = 6   # magenta
COLOR_BENDING = 7   # bianco
COLOR_MARKING = 8   # grigio scuro
COLOR_ENGRAVE = 9   # grigio chiaro
COLOR_TRASH   = 1   # rosso
COLOR_COUNTERSINK = 5  # blu
COLOR_THREADED_HOLE = 4  # ciano

# ---------------------------------------------------------------------------
# Soglia diametro fori
# ---------------------------------------------------------------------------
HOLE_DIAMETER_THRESHOLD = 32.1  # mm

# ---------------------------------------------------------------------------
# Set layer strutturali — usato dall'healer per skippare entità già classificate
# ---------------------------------------------------------------------------
STRUCTURAL_LAYERS = {LAYER_OUTER.upper(), LAYER_INNER.upper(), LAYER_HOLE.upper()}

# ---------------------------------------------------------------------------
# Mapping work_type → (layer canonico, colore)
#
# L'utente decide il work_type in special_layers a runtime.
# Questo mapping decide dove finisce l'entità nel DXF healed.
#
# Tutti e tre alimentano total_engrave_length nei metadati.
# Solo 'bending' incrementa anche bending_lines.
# ---------------------------------------------------------------------------
WORK_TYPE_TO_LAYER = {
    'bending' : (LAYER_BENDING, COLOR_BENDING),
    'marking' : (LAYER_MARKING, COLOR_MARKING),
    'engrave' : (LAYER_ENGRAVE, COLOR_ENGRAVE),
    'countersink' : (LAYER_COUNTERSINK, COLOR_COUNTERSINK),
    'threaded_hole' : (LAYER_THREADED_HOLE, COLOR_THREADED_HOLE),
}