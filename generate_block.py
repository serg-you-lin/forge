import ezdxf

# Crea un nuovo documento DXF
doc = ezdxf.new(dxfversion='R2010')
msp = doc.modelspace()

# Crea un blocco
block = doc.blocks.new(name='RECT_BLOCK')

# Disegna un rettangolo nel blocco (polyline chiusa)
points = [(0, 0), (100, 0), (100, 50), (0, 50), (0, 0)]
block.add_lwpolyline(points)

# Inserisci il blocco nel modelspace
msp.add_blockref('RECT_BLOCK', insert=(0, 0))

# Salva il file
doc.saveas("blocco_singolo.dxf")


doc = ezdxf.new(dxfversion='R2010')
msp = doc.modelspace()

# --- BLOCCO 1: rettangolo ---
b1 = doc.blocks.new(name='RECT')
b1.add_lwpolyline([(0,0), (100,0), (100,50), (0,50), (0,0)])

# --- BLOCCO 2: quadrato ---
b2 = doc.blocks.new(name='SQUARE')
b2.add_lwpolyline([(0,0), (50,0), (50,50), (0,50), (0,0)])

# --- BLOCCO 3: cerchio ---
b3 = doc.blocks.new(name='CIRCLE')
b3.add_circle(center=(0,0), radius=25)

# --- BLOCCO 4: triangolo ---
b4 = doc.blocks.new(name='TRIANGLE')
b4.add_lwpolyline([(0,0), (50,0), (25,40), (0,0)])

# Inserimento distanziato (NO sovrapposizione)
msp.add_blockref('RECT', insert=(0, 0))
msp.add_blockref('SQUARE', insert=(200, 0))
msp.add_blockref('CIRCLE', insert=(0, 150))
msp.add_blockref('TRIANGLE', insert=(200, 150))

# Salva
doc.saveas("4_blocchi.dxf")