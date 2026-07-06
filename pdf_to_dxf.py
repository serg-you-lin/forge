

import fitz  # PyMuPDF
import ezdxf

pdf_file = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_02_07_2026\U07010Z21.pdf"
dxf_file = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_02_07_2026\U07010Z21.dxf"

# FATTORE DI CONVERSIONE: da PDF punti (pt) a Millimetri (mm)
# 1 pollice = 72 punti = 25.4 mm -> 25.4 / 72
PT_TO_MM = 25.4 / 72.0

doc = fitz.open(pdf_file)
dxf = ezdxf.new("R2010")

# Forza le unità del documento DXF in Millimetri (codice 4)
dxf.header['$INSUNITS'] = 4 

msp = dxf.modelspace()

for page in doc:
    drawings = page.get_drawings()

    for drawing in drawings:
        for item in drawing["items"]:
            cmd = item[0]

            if cmd == "l":  # linea
                p1, p2 = item[1], item[2]
                msp.add_line(
                    (p1.x * PT_TO_MM, -p1.y * PT_TO_MM), 
                    (p2.x * PT_TO_MM, -p2.y * PT_TO_MM)
                )

            elif cmd == "re":  # rettangolo
                rect = item[1]
                msp.add_lwpolyline([
                    (rect.x0 * PT_TO_MM, -rect.y0 * PT_TO_MM),
                    (rect.x1 * PT_TO_MM, -rect.y0 * PT_TO_MM),
                    (rect.x1 * PT_TO_MM, -rect.y1 * PT_TO_MM),
                    (rect.x0 * PT_TO_MM, -rect.y1 * PT_TO_MM),
                ], close=True)

            elif cmd == "qu":  # quadrilatero
                quad = item[1]
                pts = [(p.x * PT_TO_MM, -p.y * PT_TO_MM) for p in quad]
                msp.add_lwpolyline(pts, close=True)

            elif cmd == "c":  # curva Bezier
                p1, p2, p3, p4 = item[1:]
                msp.add_spline([
                    (p1.x * PT_TO_MM, -p1.y * PT_TO_MM),
                    (p2.x * PT_TO_MM, -p2.y * PT_TO_MM),
                    (p3.x * PT_TO_MM, -p3.y * PT_TO_MM),
                    (p4.x * PT_TO_MM, -p4.y * PT_TO_MM),
                ])

dxf.saveas(dxf_file)
print(f"DXF salvato in scala reale (mm) in: {dxf_file}")