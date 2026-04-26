import ezdxf
import math

# Parametri principali
startx_1 = -200
startx_2 = 200
y = 0

# Cerchi principali
diametro_cerchio_grande_1 = 100
diametro_cerchio_grande_2 = 150

# Cerchi interni (ciambella)
diametro_cerchio_interno = 60

# Piccoli cerchi per array circolare
diametro_piccolo_cerchio = 5
numero_piccoli_cerchi = 4
diametro_array = 80  # diametro del cerchio immaginario su cui sono centrati i piccoli cerchi

# Creazione nuovo documento DXF
doc = ezdxf.new(dxfversion='R2010')
msp = doc.modelspace()

# Funzione per aggiungere array circolare di cerchi
def add_circular_array(center_x, center_y, diam_array, num, diam_cerchio):
    r = diam_array / 2
    for i in range(num):
        angle = 2 * math.pi * i / num
        x = center_x + r * math.cos(angle)
        y = center_y + r * math.sin(angle)
        msp.add_circle(center=(x, y), radius=diam_cerchio/2)

# Cerchi principali e interni
msp.add_circle(center=(startx_1, y), radius=diametro_cerchio_grande_1/2)
msp.add_circle(center=(startx_1, y), radius=diametro_cerchio_interno/2)

msp.add_circle(center=(startx_2, y), radius=diametro_cerchio_grande_2/2)
msp.add_circle(center=(startx_2, y), radius=diametro_cerchio_interno/2)

# Array circolare di piccoli cerchi solo per il cerchio da 100mm
add_circular_array(startx_1, y, diametro_array, numero_piccoli_cerchi, diametro_piccolo_cerchio)

# Salvataggio file DXF
doc.saveas("examples/cerchi_ciambella.dxf")
print("DXF generato: examples/cerchi_ciambella.dxf")