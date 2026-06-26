"""
generate_examples.py
--------------------
Genera i DXF di esempio usati nei test.
Lancia questo script una volta sola per creare i file in tests/examples/.

    python tests/generate_examples.py
"""

import ezdxf
import numpy as np
import os
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"
EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def save(doc, name):
    path = EXAMPLES_DIR / name
    doc.saveas(str(path))
    print(f"Generato: {path.name}")


# ---------------------------------------------------------------------------
# Esempio 1: rettangolo fatto di 4 LINE separate
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
msp.add_line((0, 0, 0),    (100, 0, 0))
msp.add_line((100, 0, 0),  (100, 50, 0))
msp.add_line((100, 50, 0), (0, 50, 0))
msp.add_line((0, 50, 0),   (0, 0, 0))
save(doc, "rect_lines.dxf")


# ---------------------------------------------------------------------------
# Esempio 2: rettangolo con foro (LINE + foro approssimato con LINE)
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
msp.add_line((0, 0, 0),     (200, 0, 0))
msp.add_line((200, 0, 0),   (200, 100, 0))
msp.add_line((200, 100, 0), (0, 100, 0))
msp.add_line((0, 100, 0),   (0, 0, 0))
cx, cy, r = 100, 50, 20
angles = np.linspace(0, 2*np.pi, 9)
pts = [(cx + r*np.cos(a), cy + r*np.sin(a)) for a in angles]
for i in range(len(pts)-1):
    msp.add_line((*pts[i], 0), (*pts[i+1], 0))
save(doc, "rect_with_hole_lines.dxf")


# ---------------------------------------------------------------------------
# Esempio 3: due LWPOLYLINE separate (multi-pezzo)
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
msp.add_lwpolyline([(0,0),(80,0),(80,60),(0,60)],   close=True, dxfattribs={'layer': '0'})
msp.add_lwpolyline([(120,0),(220,0),(220,80),(120,80)], close=True, dxfattribs={'layer': '0'})
save(doc, "two_parts.dxf")


# ---------------------------------------------------------------------------
# Esempio 4: LWPOLYLINE già chiusa con foro (file già pulito)
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
msp.add_lwpolyline([(0,0),(150,0),(150,100),(0,100)],  close=True, dxfattribs={'layer': '0'})
msp.add_lwpolyline([(50,30),(100,30),(100,70),(50,70)], close=True, dxfattribs={'layer': '0'})
save(doc, "pline_with_hole.dxf")


# ---------------------------------------------------------------------------
# Esempio 5: CIRCLE outer (flangia tonda) con foro circolare
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
msp.add_circle((0, 0, 0), radius=50)   # outer
msp.add_circle((0, 0, 0), radius=10)   # foro interno
save(doc, "circle_outer_with_hole.dxf")


# ---------------------------------------------------------------------------
# Esempio 6: rettangolo con layer MARK e BEND (special layers)
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
# Contorno esterno
msp.add_lwpolyline([(0,0),(200,0),(200,100),(0,100)], close=True, dxfattribs={'layer': '0'})
# 2 linee di piegatura su layer BEND
msp.add_line((0, 33, 0), (200, 33, 0), dxfattribs={'layer': 'BEND'})
msp.add_line((0, 66, 0), (200, 66, 0), dxfattribs={'layer': 'BEND'})
# 1 linea di marcatura su layer MARK
msp.add_line((50, 0, 0), (150, 100, 0), dxfattribs={'layer': 'MARK'})
save(doc, "rect_with_special_layers.dxf")


# ---------------------------------------------------------------------------
# Esempio 7: rettangolo con entità trash (layer sconosciuto)
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
msp.add_lwpolyline([(0,0),(100,0),(100,80),(0,80)], close=True, dxfattribs={'layer': '0'})
# Entità su layer sconosciuto — finisce in Trash
msp.add_line((10, 10, 0), (90, 70, 0), dxfattribs={'layer': 'QUOTA'})
msp.add_text("REF_001", dxfattribs={'layer': 'TESTO', 'height': 5})
save(doc, "rect_with_trash.dxf")


# ---------------------------------------------------------------------------
# Esempio 8: rettangolo con foro CIRCLE piccolo (< soglia HOLE)
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
msp.add_lwpolyline([(0,0),(150,0),(150,100),(0,100)], close=True, dxfattribs={'layer': '0'})
msp.add_circle((75, 50, 0), radius=8)   # diametro 16 < 32.1 → LAYER_HOLE
save(doc, "rect_with_circle_hole.dxf")


# ---------------------------------------------------------------------------
# Esempio 9: rettangolo con CIRCLE grande (>= soglia → LAYER_INNER)
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
msp.add_lwpolyline([(0,0),(300,0),(300,200),(0,200)], close=True, dxfattribs={'layer': '0'})
msp.add_circle((150, 100, 0), radius=40)  # diametro 80 >= 32.1 → LAYER_INNER
save(doc, "rect_with_circle_inner.dxf")


# ---------------------------------------------------------------------------
# Esempio 10: rettangolo con loop LINE interno (marcatura/inner)
# LWPOLYLINE outer già presente + 4 LINE che formano un loop contenuto
# Verifica che il loop venga classificato INNER e non OUTER
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
msp.add_lwpolyline([(0,0),(200,0),(200,100),(0,100)], close=True, dxfattribs={'layer': '0'})
msp.add_line((80, 40), (120, 40))  # loop interno 40x20
msp.add_line((120, 40), (120, 60))
msp.add_line((120, 60), (80, 60))
msp.add_line((80, 60), (80, 40))
save(doc, "rect_with_inner_mark.dxf")


# ---------------------------------------------------------------------------
# Esempio 11: rettangolo con LINE duplicate
# Simula duplicati dopo explode INSERT
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()

segments = [
    ((0, 0, 0),   (100, 0, 0)),
    ((100, 0, 0), (100, 50, 0)),
    ((100, 50, 0), (0, 50, 0)),
    ((0, 50, 0),  (0, 0, 0)),
]

for start, end in segments:
    # Segmento originale
    msp.add_line(start, end)

    # Duplicato identico
    msp.add_line(start, end)

save(doc, "rect_lines_duplicated.dxf")


print(f"\nTutti i file generati in {EXAMPLES_DIR}")


# ---------------------------------------------------------------------------
# Esempio 12: rettangolo con coppia di cerchi concentrici (svasatura)
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()
# outer rettangolo
msp.add_line((0, 0, 0),    (200, 0, 0))
msp.add_line((200, 0, 0),  (200, 100, 0))
msp.add_line((200, 100, 0),(0, 100, 0))
msp.add_line((0, 100, 0),  (0, 0, 0))
# coppia concentrica: cerchio grande (svasatura) + cerchio piccolo (foro)
cx, cy = 100, 50
msp.add_circle((cx, cy, 0), radius=15)   # grande → Layer Countersink
msp.add_circle((cx, cy, 0), radius=5)    # piccolo → resta come hole
save(doc, "rect_with_countersink.dxf")


# ---------------------------------------------------------------------------
# Esempio 14: rettangolo + linea di mezzeria verticale dal lato orizzontale
# ---------------------------------------------------------------------------
doc = ezdxf.new('R2010')
msp = doc.modelspace()

# Rettangolo 100 x 50 (LINE separate)
msp.add_line((0, 0, 0),    (100, 0, 0))
msp.add_line((100, 0, 0),  (100, 50, 0))
msp.add_line((100, 50, 0), (0, 50, 0))
msp.add_line((0, 50, 0),   (0, 0, 0))

# Linea di mezzeria: parte dal punto medio del lato orizzontale inferiore
# e sale fino a metà altezza, parallela ai lati verticali
msp.add_line((50, 0, 0), (50, 25, 0))

save(doc, "rect_centerline.dxf")


# ---------------------------------------------------------------------------
# Esempio 15: test flattener (Z non uniforme + geometria mista)
# ---------------------------------------------------------------------------

doc = ezdxf.new('R2010')
msp = doc.modelspace()

# LINE con Z diverso (deve essere appiattita)
msp.add_line((0, 0, 5), (100, 0, -3))
msp.add_line((100, 0, -3), (100, 50, 2))
msp.add_line((100, 50, 2), (0, 50, 0))
msp.add_line((0, 50, 0), (0, 0, 5))

# # ARC con Z diverso (stress flattener)
# msp.add_arc(
#     center=(50, 25, 10),
#     radius=20,
#     start_angle=0,
#     end_angle=180,
#     dxfattribs={"layer": "0"}
# )

# # poligono semplice a quota mista
# msp.add_lwpolyline(
#     [(150, 0, 1), (250, 0, -2), (250, 60, 3), (150, 60, 0)],
#     close=True
# )

save(doc, "example_15_flattener.dxf")


def generate_rect_with_threaded_holes():
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0,0),(200,0),(200,100),(0,100),(0,0)], close=True)
    for cx in [40, 100, 160]:
        msp.add_circle((cx, 50), radius=2.5, dxfattribs={"layer": "THREADED"})
    doc.saveas(EXAMPLES_DIR / "rect_with_threaded_holes.dxf")



def generate_two_rects_with_bend():
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0,0),(200,0),(200,100),(0,100),(0,0)], close=True)
    msp.add_lwpolyline([(300,0),(500,0),(500,100),(300,100),(300,0)], close=True)
    msp.add_line((10,50),(190,50), dxfattribs={"layer": "BEND"})
    doc.saveas(EXAMPLES_DIR / "two_rects_with_bend.dxf")


# add this in generate_examples.py

doc = ezdxf.new('R2010')
msp = doc.modelspace()

msp.add_lwpolyline([(0,0),(200,0),(200,100),(0,100)], close=True)
msp.add_line((0,33),(200,33), dxfattribs={"layer":"BEND"})
msp.add_line((0,66),(200,66), dxfattribs={"layer":"BEND"})
msp.add_line((50,0),(150,100), dxfattribs={"layer":"MARK"})

save(doc, "rect_with_special_layers.dxf")


generate_rect_with_threaded_holes()
generate_two_rects_with_bend()