
"""
analyze_dxf.py
--------------
Analisi di un file DXF — usa DxfInspector, niente healing.

Uso:
    python analyze_dxf.py path/al/file.dxf
    python analyze_dxf.py   (usa DEFAULT_FILE)
"""

import sys
import os
import ezdxf
from dxf_forge.dxf_inspect import DxfInspector
from collections import Counter
import dxf_forge as forge

DEFAULT_FILE = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_06_05_2026\6200012914 Sviluppo\6200012914_1.dxf"

# ← CONFIGURA COSA VUOI VEDERE
inspector = DxfInspector(
    summary   = False,
    lines     = True,
    arcs      = True,
    polylines = True,
    circles   = True,
    splines   = True,
    graph     = True,  # ← il più utile per debug ambiguità
    dimensions = True,
    text      = True,
)


def analyze_dxf(input_file: str):
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
    inspector.analyze(msp, title=input_file, doc=doc)
    # for e in msp:
    #   print(e.dxftype())
    for e in msp:
        if e.dxftype() == 'INSERT':
            try:
                block = doc.blocks.get(e.dxf.name)
                inner = Counter(sub.dxftype() for sub in block)
                print(f"  INSERT '{e.dxf.name}' contiene: {dict(inner)}")
            except Exception as ex:
                print(f"  INSERT error: {ex}")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILE
    analyze_dxf(filepath)