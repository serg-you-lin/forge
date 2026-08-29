"""
run_healer_pdf.py
-----------------
Testa l'healer su un file PDF reale, convertendolo al volo in strutture compatibili.
"""

import forge
from forge.dxf_inspect import DxfInspector
import os
import ezdxf  # Ci serve per creare il documento fasullo

# ---------------------------------------------------------------------------
# CAMBIA QUI
# ---------------------------------------------------------------------------

input_pdf = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_02_07_2026\U07010Z21.pdf"

tolerance = 1

special_layers = {
    "MARK"      : "engrave",
    "Filettati" : "threaded_hole",
    "Svasati"   : "countersink",
    "Piega"     : "bending",
}

# ---------------------------------------------------------------------------

input_pdf  = os.path.abspath(input_pdf)
base_dir   = os.path.dirname(input_pdf)
file_name  = os.path.basename(input_pdf)
base_name  = os.path.splitext(file_name)[0]

# L'output finale sarà comunque un DXF elaborato partendo dal PDF!
output_dxf = os.path.join(base_dir, f"{base_name}_from_pdf_healed.dxf")
output_json = os.path.join(base_dir, f"{base_name}_from_pdf_healed.json")

# ---------------------------------------------------------------------------
# Apertura e Conversione al volo in DXF Virtuale
# ---------------------------------------------------------------------------

print(f"Apertura PDF: {input_pdf}")
print(f"Tolleranza: {tolerance}")

# 1. Carichiamo gli Edge dal PDF tramite il loader che abbiamo scritto
edges = forge.load_pdf(input_pdf, node_decimals=3)

# 2. Creiamo il documento DXF fasullo (virtuale)
doc = ezdxf.new("R2010")
doc.header['$INSUNITS'] = 4  # Millimetri
msp = doc.modelspace()

# 3. Travasiamo gli Edge del PDF nel Modelspace fasullo usando il copy_adapter del DXF!
# Visto che hai già un copy_adapter che sa come scrivere su msp partendo dalle entità,
# oppure puoi scriverle direttamente usando la geometria delle LineString degli Edge:
for edge in edges:
    # Se l'edge arriva da una linea vettoriale
    if edge.geometry.geom_type == 'LineString':
        coords = list(edge.geometry.coords)
        if len(coords) == 2:
            # È una linea semplice
            msp.add_line(coords[0], coords[1], dxfattribs={"layer": edge.layer})
        else:
            # È una poligonale o una curva discretizzata
            msp.add_lwpolyline(coords, dxfattribs={"layer": edge.layer})

print(f"[Fasullo] Generato Modelspace virtuale con {len(msp)} entità provenienti dal PDF.")

# ---------------------------------------------------------------------------
# Validazione (Uguale a prima!)
# ---------------------------------------------------------------------------

print("\n--- VALIDAZIONE ---")
check = forge.validate_msp(msp)
for w in check.warnings:
    print(f"  WARN: {w}")
for e in check.errors:
    print(f"  ERROR: {e}")
if not check.errors:
    print("  OK")

# ---------------------------------------------------------------------------
# Pipeline (Identica, non tochi una virgola!)
# ---------------------------------------------------------------------------

result = forge.heal(
    msp,
    tolerance=tolerance,
    explode_inserts=True,
    special_layers=special_layers,
    label=base_name,
    source_file=file_name,
)

forge.detect(result, msp, bending_tolerance=0.2)
forge.write(msp, result)
forge.inject(msp, result)

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

print(f"\n  Pezzi trovati : {result.part_count}")
for i, part in enumerate(result.parts):
    print(f"\n  Pezzo {i+1}:")
    print(f"    Area outer : {part.outer.area:.1f}")
    print(f"    Fori       : {len(part.inners)}")
    print(f"    Bbox       : {part.bbox}")

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

forge.save_json(result, output_json)
print(f"\nJSON salvato: {output_json}")

if not result.is_valid:
    print("\nFile non valido — non salvato.")
    raise SystemExit(1)

doc.saveas(output_dxf)
print(f"DXF salvato da sorgente PDF : {output_dxf}")