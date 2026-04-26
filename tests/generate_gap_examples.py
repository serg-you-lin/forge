"""
generate_gap_examples.py
------------------------
Genera DXF di esempio per testare la gestione dei gap.

    python tests/generate_gap_examples.py
"""

import ezdxf
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"
EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def save(doc, name):
    path = EXAMPLES_DIR / name
    doc.saveas(str(path))
    print(f"Generato: {path.name}")


GAP     =  0.1   # linee troppo corte — endpoint distanti 0.1mm
OVERLAP =  0.1   # linee troppo lunghe — endpoint che si sovrappongono di 0.1mm

W, H = 100.0, 50.0


# ---------------------------------------------------------------------------
# Rettangolo con GAP negli angoli (linee troppo corte)
#
#   Ogni lato finisce 0.1mm prima dell'angolo reale.
#   Il loop non si chiude → il grafo non trova loop → fallback attuale.
#   Con la nuova logica: extend al punto di intersezione reale.
#
#   Angoli reali: (0,0) (100,0) (100,50) (0,50)
#   Con gap 0.1:
#     bottom: (0.1, 0)  → (99.9, 0)
#     right:  (100, 0.1) → (100, 49.9)
#     top:    (99.9, 50) → (0.1, 50)
#     left:   (0, 49.9)  → (0, 0.1)
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
g = GAP
msp.add_line((0,   0),   (W, 0))    # bottom
msp.add_line((W,   0),   (W,   H-g))  # right
msp.add_line((W-g, H),   (g,   H))    # top
msp.add_line((0,   H), (0,   0))    # left
save(doc, "rect_gap.dxf")


# ---------------------------------------------------------------------------
# Rettangolo con OVERLAP negli angoli (linee troppo lunghe)
#
#   Ogni lato supera l'angolo reale di 0.1mm.
#   Gli endpoint si intersecano → il grafo trova loop ma la forma
#   ha i corners sbagliati (angoli arrotondati o tagliati).
#   Con la nuova logica: trim al punto di intersezione reale.
#
#   Con overlap 0.1:
#     bottom: (-0.1, 0)   → (100.1, 0)
#     right:  (100, -0.1) → (100,   50.1)
#     top:    (100.1, 50) → (-0.1,  50)
#     left:   (0,  50.1)  → (0,    -0.1)
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
o = OVERLAP
msp.add_line((0,  0),   (W, 0))    # bottom
msp.add_line((W,   0),  (W,   H+o))  # right
msp.add_line((W+o, H),   (-o,  H))    # top
msp.add_line((0,   H), (0,   0))   # left
save(doc, "rect_overlap.dxf")


print(f"\nGAP={GAP}mm  OVERLAP={OVERLAP}mm")
print(f"Rettangolo atteso: {W}x{H}mm  area={W*H}mm²")



import math

# ---------------------------------------------------------------------------
# Gap tra ARC e LINE (un solo lato)
#
#   Rettangolo con angolo in alto a destra arrotondato da un arco.
#   L'arco finisce 0.1mm prima della LINE top → gap arc/line.
#
#   Geometria:
#     bottom:  LINE (0,0) → (100,0)
#     right:   LINE (100,0) → (100,40)         termina 0.1mm prima del tangent point
#     corner:  ARC  centro=(90,40) r=10        da 0° a 90°, tangent points (100,40) e (90,50)
#     top:     LINE (90,50+gap) → (0,50)       inizia 0.1mm dopo il tangent point
#     left:    LINE (0,50) → (0,0)
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
R = 20.0
cx, cy = W - R, H - R  # (90, 40)
g = GAP

msp.add_line((0, 0),      (W, 0))           # bottom
msp.add_line((W, 0),      (W, cy - g))      # right — finisce g prima del tangent
msp.add_arc(center=(cx, cy, 0), radius=R,
            start_angle=0, end_angle=90)    # arco 0°→90°
msp.add_line((cx - g, H), (0, H))           # top — inizia g dopo il tangent
msp.add_line((0, H),      (0, 0))           # left
save(doc, "arc_line_gap.dxf")


# ---------------------------------------------------------------------------
# Gap tra due ARC
#
#   Due semicerchi che insieme formano un cerchio, con gap di 0.1mm
#   tra i loro endpoint.
#
#   ARC1: centro=(0,0) r=50  da 0° a 175°   (termina g prima di 180°)
#   ARC2: centro=(0,0) r=50  da 185° a 360° (inizia g dopo 180°)
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
R2 = 50.0
gap_deg = math.degrees(GAP / R2)  # gap in gradi corrispondente a 0.1mm

msp.add_arc(center=(0, 0, 0), radius=R2,
            start_angle=0,             end_angle=180 - gap_deg)
msp.add_arc(center=(0, 0, 0), radius=R2,
            start_angle=180 + gap_deg, end_angle=360)
save(doc, "arc_arc_gap.dxf")


# ---------------------------------------------------------------------------
# Rettangolo con 3 lati (lato destro mancante) — rette parallele
#
#   bottom: LINE (0,0) → (100,0)
#   top:    LINE (0,50) → (100,50)
#   left:   LINE (0,0) → (0,50)
#   lato destro: MANCANTE
#
#   Gli endpoint di bottom e top sul lato destro sono vicini
#   ma le loro rette sono parallele → non c'è intersezione.
#   Soluzione attesa: aggiunge una LINE di chiusura (100,0)→(100,50).
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
msp.add_line((0,  0),  (W, 0))   # bottom
msp.add_line((0,  H),  (W, H))   # top
msp.add_line((0,  0),  (0, H))   # left
# lato destro mancante — endpoint vicini ma rette parallele
save(doc, "rect_3sides.dxf")


# ---------------------------------------------------------------------------
# Trapezio con 3 lati (base superiore + due lati divergenti)
#
#   base_sup:  LINE (25,50) → (75,50)
#   left:      LINE (0,0)   → (25,50)   diverge verso sinistra
#   right:     LINE (75,50) → (100,0)   diverge verso destra
#   base_inf:  MANCANTE
#
#   Gli endpoint in basso (0,0) e (100,0) sono lontani (100mm) —
#   non devono essere colmati dalla tolerance.
#   Ma gli endpoint in alto (25,50)-(75,50) sono connessi tramite base_sup.
#   Il gap da chiudere è la base inferiore.
#   Soluzione attesa: aggiunge LINE (0,0)→(100,0).
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
msp.add_line((25, H),  (75, H))   # base superiore
msp.add_line((0,  0),  (25, H))   # lato sinistro
msp.add_line((75, H),  (W,  0))   # lato destro
# base inferiore mancante
save(doc, "trapezio_3sides.dxf")


# ---------------------------------------------------------------------------
# Gap tra SPLINE e LINE (0.2mm)
#
#   Rettangolo dove il lato sinistro è una SPLINE leggermente curva
#   che termina 0.2mm prima dell'angolo in alto a sinistra.
#   La LINE top inizia dall'angolo reale (0,50).
#
#   close_gaps non gestisce questo caso (lavora solo su LINE).
#   Risultato atteso oggi: fallback polygonize o loop non chiuso.
# ---------------------------------------------------------------------------
SPLINE_GAP = 0.2
doc = ezdxf.new('R2010')
msp = doc.modelspace()
msp.add_line((0, 0),  (W, 0))    # bottom
msp.add_line((W, 0),  (W, H))    # right
msp.add_line((W, H),  (0, H))    # top — endpoint reale (0,50)
spline = msp.add_spline()
spline.fit_points = [
    (0,    0,                0),
    (0.5,  H * 0.25,         0),
    (-0.5, H * 0.5,          0),
    (0.5,  H * 0.75,         0),
    (0,    H - SPLINE_GAP,   0),
]
save(doc, "spline_line_gap.dxf")


print(f"\nGAP={GAP}mm  OVERLAP={OVERLAP}mm")
print(f"Rettangolo atteso: {W}x{H}mm  area={W*H}mm²")
