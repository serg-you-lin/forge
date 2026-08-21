DEFAULT_FILE = r"tests/examples/quadro_fori_spline.DXF"

import sys
import os
import ezdxf
import forge

def analyze_splines(input_file: str):
    input_file = os.path.abspath(input_file)
    try:
        doc = ezdxf.readfile(input_file)
    except IOError:
        print(f"Errore: file non trovato — {input_file}")
        return
    except ezdxf.DXFStructureError:
        print(f"Errore: DXF non valido — {input_file}")
        return

    if doc.dxfversion < 'AC1015':
        doc = forge.upgrade_to_r2010(doc)
    msp = doc.modelspace()

    splines = [e for e in msp if e.dxftype() == "SPLINE"]
    print(f"\n--- SPLINES ({len(splines)}) ---")
    for i, s in enumerate(splines):
        print(f"\nSPLINE [{i}]")
        print(f"  layer        : {s.dxf.layer}")
        print(f"  degree       : {s.dxf.degree}")
        print(f"  closed       : {s.closed}")
        print(f"  n_knots      : {s.dxf.n_knots}")
        print(f"  n_control_pts: {s.dxf.n_control_points}")
        print(f"  control_pts  : {list(s.control_points)}")
        print(f"  knots        : {list(s.knots)}")
        try:
            print(f"  weights      : {list(s.weights)}")
        except Exception:
            print(f"  weights      : n/a")

if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILE
    analyze_splines(filepath)