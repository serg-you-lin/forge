"""
run_frame_detector.py — script di test manuale

Carica un DXF, esegue il frame detector, stampa il risultato.
"""

import ezdxf
import sys
sys.path.insert(0, r"C:\Users\FEDERICO\Documents\Python_Scripts\Projects\GitHub\dxf-forge")

from dxf_forge.adapters.dxf.frame_adapter_dxf import extract_frame_handles

# ── CONFIG ──────────────────────────────────────────────────────────────────
INPUT_DXF = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_27_05_2026\disegni\271004g13.dxf"
# ────────────────────────────────────────────────────────────────────────────

def main():
    print(f"Caricamento: {INPUT_DXF}")
    doc = ezdxf.readfile(INPUT_DXF)
    msp = doc.modelspace()

    result = extract_frame_handles(msp)

    print()
    print(f"Found:      {result.found}")
    print(f"Confidence: {result.confidence}")
    print(f"Containment: {result.containment:.1%}")

    if result.frame_bbox:
        fb = result.frame_bbox
        print(f"Frame bbox: ({fb.xmin:.1f}, {fb.ymin:.1f}) → ({fb.xmax:.1f}, {fb.ymax:.1f})")
        print(f"Frame size: {fb.width:.1f} x {fb.height:.1f}  ratio: {fb.ratio:.4f}")

    if result.excluded_handles:
        print(f"Handle esclusi ({len(result.excluded_handles)}):")
        for h in sorted(result.excluded_handles):
            print(f"  {h}")
    else:
        print("Nessun handle escluso.")

    if result.found and result.excluded_handles:
        for entity in list(msp):
            if entity.dxf.handle in result.excluded_handles:
                msp.delete_entity(entity)
        
        OUTPUT_DXF = INPUT_DXF.replace(".dxf", "_noframe.dxf")
        doc.saveas(OUTPUT_DXF)
        print(f"\nSalvato: {OUTPUT_DXF}")
        

if __name__ == "__main__":
    main()