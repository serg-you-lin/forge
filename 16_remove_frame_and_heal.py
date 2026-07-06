import os
import ezdxf
import sys
sys.path.insert(0, r"C:\Users\FEDERICO\Documents\Python_Scripts\Projects\GitHub\dxf-forge")

import forge
from forge.adapters.dxf.frame_adapter_dxf import extract_frame_handles

# ── CONFIG ──────────────────────────────────────────────────────────────────
INPUT_DXF = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_02_07_2026\U07010Z21.dxf"

tolerance = .02
special_layers = {
    "MARK"      : "engrave",
    "Filettati" : "threaded_hole",
    "Svasati"   : "countersink",
    "Piega"     : "bending",
}
# ────────────────────────────────────────────────────────────────────────────

base_dir   = os.path.dirname(INPUT_DXF)
base_name  = os.path.splitext(os.path.basename(INPUT_DXF))[0]
output_dxf = os.path.join(base_dir, f"{base_name}_noframe_healed.dxf")

doc, msp = forge.load_dxf(INPUT_DXF)

# --- Frame detection --------------------------------------------------------
print("Rilevamento cornice...")
frame_result = extract_frame_handles(msp)
print(f"Found: {frame_result.found}  Confidence: {frame_result.confidence}  Containment: {frame_result.containment:.1%}")

if frame_result.found:
    for entity in list(msp):
        if entity.dxf.handle in frame_result.excluded_handles:
            msp.delete_entity(entity)
    print(f"Rimossi {len(frame_result.excluded_handles)} handle cornice")

# --- Pipeline ---------------------------------------------------------------
result = forge.heal(
    msp,
    tolerance=tolerance,
    explode_inserts=True,
    special_layers=special_layers,
    label=base_name,
    source_file=os.path.basename(INPUT_DXF),
)

forge.detect(result, msp, bending_tolerance=0.2)
forge.write(msp, result)
forge.inject(msp, result)

doc.saveas(output_dxf)
print(f"\nSalvato: {output_dxf}")