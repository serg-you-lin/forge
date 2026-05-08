"""
run_healer.py
-------------
Testa l'healer su un file DXF reale.
Produce un file healed.dxf nella cartella di output.

Lancia:
    python run_healer.py

Modifica input_dxf con il percorso del tuo file.
"""

import ezdxf
import dxf_forge as forge
from dxf_forge.dxf_inspect import DxfInspector
import os

# ← CAMBIA QUI
input_dxf = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_23_04_2026\BAR2.00079-ZN 42D025Z00I.dxf"

# percorso assoluto
input_dxf = os.path.abspath(input_dxf)

# cartella del file
base_dir = os.path.dirname(input_dxf)

file_name = os.path.basename(input_dxf)

# nome senza estensione
base_name = os.path.splitext(file_name)[0]

# output nella stessa cartella
output_dxf = os.path.join(base_dir, f"{base_name}_healed.dxf")


tolerance = 2
print("tolleranza:", tolerance)

# Configura cosa vuoi vedere — commenta/decommenta
inspector = DxfInspector(
    summary   = False,
    lines     = True,
    arcs      = True,
    polylines = True,
    circles   = True,
    splines   = True,
    graph     = False,   # ← il più utile per debug ambiguità
)

# ---------------------------------------------------------------------------

print(f"Apertura: {input_dxf}")
doc = ezdxf.readfile(input_dxf)
msp = doc.modelspace()

inspector.analyze(msp, title=input_dxf)

# Validazione
print("\n--- VALIDAZIONE ---")
check = forge.validate_msp(msp)
for w in check.warnings:
    print(f"  WARN: {w}")
for e in check.errors:
    print(f"  ERROR: {e}")
if not check.errors:
    print("  OK: nessun errore bloccante")

# Healing
# for entity in msp:
#     layer = entity.dxf.layer if entity.dxf.hasattr("layer") else ""
#     if layer.upper() in ("MARK", "MARCATURA"):
#         print(f"  Entità speciale: {entity.dxftype()} layer={layer}")
print("\n--- HEALING ---")
result = forge.heal(msp, tolerance=tolerance, 
                    explode_inserts=True,
                    write_to_msp=True, 
                    label=base_name, 
                    source_file=file_name,
                    special_layers={
                        "MARK": "engrave",                
                        "Bend": "bending",
                        "MBend": "bending",
                    })

print(f"\n  Pezzi trovati : {result.part_count}")
# print(f"  Valido        : {result.is_valid}")
# for w in result.warnings:
#     print(f"  WARN: {w}")
# for e in result.errors:
#     print(f"  ERROR: {e}")

for i, part in enumerate(result.parts):
    print(f"\n  Pezzo {i+1}:")
    print(f"    Area outer : {part.outer.area:.1f}")
    print(f"    Fori       : {len(part.inners)}")
    print(f"    Bbox       : {part.bbox}")

# Salva
output_json = os.path.join(base_dir, f"{base_name}_healed.json")
forge.save_json(result, output_json)

if not result.is_valid:
    print(f"\nFile non valido — non salvato.")
    raise SystemExit(1)

doc.saveas(output_dxf)
print(f"\nSalvato: {output_dxf}")

# Debug LWPOLYLINE risultanti
print("\n--- LWPOLYLINE RISULTANTI ---")
inspector_out = DxfInspector(polylines=True, summary=False)
saved_doc = ezdxf.readfile(output_dxf)
inspector_out.analyze(saved_doc.modelspace(), title=output_dxf)