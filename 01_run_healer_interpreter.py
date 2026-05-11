"""
run_healer.py
-------------
Testa l'healer su un file DXF reale.
Produce un file healed.dxf nella cartella di output.

"""

import ezdxf
import dxf_forge as forge
from dxf_forge.dxf_inspect import DxfInspector
from dxf_forge.rules.classifier import GeometricInterpreter
import os

# ← CAMBIA QUI
input_dxf = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\Tutorial\healer_int\single.dxf"

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

# inspector = DxfInspector(
#     summary=False,
#     lines=False,
#     arcs=False,
#     polylines=True,
#     circles=False,
#     splines=True,
#     graph=False,
# )

# ---------------------------------------------------------------------------

print(f"Apertura: {input_dxf}")

doc = ezdxf.readfile(input_dxf)
msp = doc.modelspace()

#inspector.analyze(msp, title=input_dxf)

# ---------------------------------------------------------------------------
# VALIDAZIONE
# ---------------------------------------------------------------------------

print("\n--- VALIDAZIONE ---")

check = forge.validate_msp(msp)

for w in check.warnings:
    print(f"  WARN: {w}")

for e in check.errors:
    print(f"  ERROR: {e}")

if not check.errors:
    print("  OK: nessun errore bloccante")

# HEAL — genera i part e scrive i layer speciali su msp
result = forge.heal(
    msp,
    tolerance=tolerance,
    explode_inserts=True,
    write_to_msp=True,
    label=base_name,
    source_file=file_name,
    interpreter = GeometricInterpreter(),  # ← classe che intepreta la geometria per classificare fori, contorni, ecc. (opzionale, ma se presente arricchisce le metriche)
)

# INJECT — inserisce dati custom e metriche da classified_entities 
forge.inject(
    msp,
    result,
)

# ---------------------------------------------------------------------------
# REPORT
# ---------------------------------------------------------------------------

print(f"\n  Pezzi trovati : {result.part_count}")

for i, part in enumerate(result.parts):
    print(f"\n  Pezzo {i+1}:")
    print(f"    Area outer : {part.outer.area:.1f}")
    print(f"    Fori       : {len(part.inners)}")
    print(f"    Bbox       : {part.bbox}")

    # DEBUG SPECIAL LAYERS
    if part.custom:
        print(f"    Custom      : {part.custom}")

# ---------------------------------------------------------------------------
# SAVE JSON
# ---------------------------------------------------------------------------

output_json = os.path.join(base_dir, f"{base_name}_healed.json")

forge.save_json(result, output_json)

# ---------------------------------------------------------------------------
# SAVE DXF
# ---------------------------------------------------------------------------

if not result.is_valid:
    print(f"\nFile non valido — non salvato.")
    raise SystemExit(1)

doc.saveas(output_dxf)

print(f"\nSalvato: {output_dxf}")
