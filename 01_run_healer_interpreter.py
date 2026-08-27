"""
run_healer.py
-------------
Testa l'healer su un file DXF reale.
Produce un file healed.dxf nella cartella di output.
"""

import forge
# from forge.dxf_inspect import DxfInspector
import os

# ---------------------------------------------------------------------------
# CAMBIA QUI
# ---------------------------------------------------------------------------

input_dxf = r"tests/examples/spline_line_gap.dxf"

tolerance = .2

special_layers = {
    "MARK"      : "engrave",
    "Signature"      : "engrave",
    "Filettati" : "threaded_hole",
    "Svasati"   : "countersink",
    "Piega"     : "bending",
}

# ---------------------------------------------------------------------------

input_dxf  = os.path.abspath(input_dxf)
base_dir   = os.path.dirname(input_dxf)
file_name  = os.path.basename(input_dxf)
base_name  = os.path.splitext(file_name)[0]
output_dxf = os.path.join(base_dir, f"{base_name}_healed.dxf")
output_json = os.path.join(base_dir, f"{base_name}_healed.json")

# ---------------------------------------------------------------------------
# Apertura
# ---------------------------------------------------------------------------

print(f"Apertura: {input_dxf}")
print(f"Tolleranza: {tolerance}")

doc, msp = forge.load_dxf(input_dxf, explode_inserts=True, flatten_z_flag=True, verbose=False)

# inspector = DxfInspector(summary=False, lines=True, arcs=False,
#                          polylines=True, circles=False, splines=True, graph=False)
# inspector.analyze(msp, title=input_dxf)

# ---------------------------------------------------------------------------
# Validazione
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
# Pipeline
# ---------------------------------------------------------------------------

result = forge.heal(
    msp,
    tolerance=tolerance,
    label_map=special_layers,
    label=base_name,
    source_file=file_name,
)

forge.detect(result, bending_tolerance=0.2)
forge.write(msp, result)
forge.inject(result)

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

print(f"\n  Pezzi trovati : {result.part_count}")
for i, part in enumerate(result.parts):
    print(f"\n  Pezzo {i+1}:")
    print(f"    Area outer : {part.outer.area:.1f}")
    print(f"    Fori       : {len(part.inners)}")
    print(f"    Bbox       : {part.bbox}")
    # if part.custom:
    #     print(f"    Custom     : {part.custom}")

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

forge.save_json(result, output_json)
print(f"\nJSON salvato: {output_json}")

if not result.is_valid:
    print("\nFile non valido — non salvato.")
    raise SystemExit(1)

doc.saveas(output_dxf)
print(f"DXF salvato : {output_dxf}")