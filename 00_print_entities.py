
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
import math


DEFAULT_FILE = r"tests/examples/la_104.DXF"

# ← CONFIGURA COSA VUOI VEDERE
inspector = DxfInspector(
    summary   = False,
    lines     = True,
    arcs      = True,
    polylines = True,
    circles   = False,
    splines   = False,
    graph     = True,
    dimensions = False,
    text      = False,
)

def debug_point_on_arc(msp, tolerance=2.0):
    all_lines = list(msp.query("LINE"))
    all_arcs  = list(msp.query("ARC"))

    # linee con entrambi gli endpoint scollegati (degree=1 nel grafo)
    # le identifichiamo come quelle che NON condividono coordinate con altre entità
    # approssimazione: le stampiamo tutte e per ognuna testiamo tutti gli archi
    print(f"\n--- DEBUG POINT ON ARC ---")
    print(f"  tolerance={tolerance}")
    print(f"  LINE totali: {len(all_lines)}")
    print(f"  ARC totali:  {len(all_arcs)}\n")

    for line in all_lines:
        s_raw = (line.dxf.start.x, line.dxf.start.y)
        e_raw = (line.dxf.end.x,   line.dxf.end.y)

        for arc in all_arcs:
            cx = arc.dxf.center.x
            cy = arc.dxf.center.y
            r  = arc.dxf.radius

            for label, (px, py) in [("S", s_raw), ("E", e_raw)]:
                dist  = math.sqrt((px - cx)**2 + (py - cy)**2)
                diff  = abs(dist - r)
                angle = math.degrees(math.atan2(py - cy, px - cx)) % 360

                if diff < tolerance * 10:   # stampa solo i casi vicini
                    print(
                        f"  LINE {s_raw} → {e_raw}  pt={label}\n"
                        f"    ARC center=({cx:.2f},{cy:.2f}) r={r:.3f} "
                        f"angles={arc.dxf.start_angle:.1f}→{arc.dxf.end_angle:.1f}\n"
                        f"    dist={dist:.4f}  diff={diff:.4f}  angle={angle:.2f}  "
                        f"tolerance={tolerance}\n"
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

    mark_lines = [
        e for e in msp
        if e.dxftype() == "LINE" and e.dxf.layer == "MARK"
    ]

    print(f"\n--- MARK LINES ---")
    print(f"Totale LINE su layer MARK: {len(mark_lines)}")


    # from collections import defaultdict
    # import math

    # def round_pt(p, d=1):
    #     return (round(p[0], d), round(p[1], d))
    
    # graph = defaultdict(list)
    # for e in msp:
    #     if e.dxftype() == 'LINE':
    #         s = round_pt((e.dxf.start.x, e.dxf.start.y))
    #         en = round_pt((e.dxf.end.x, e.dxf.end.y))
    #     elif e.dxftype() == 'ARC':
    #         import ezdxf.math as emath
    #         sa = math.radians(e.dxf.start_angle)
    #         ea = math.radians(e.dxf.end_angle)
    #         s  = round_pt((e.dxf.center.x + e.dxf.radius * math.cos(sa),
    #                        e.dxf.center.y + e.dxf.radius * math.sin(sa)))
    #         en = round_pt((e.dxf.center.x + e.dxf.radius * math.cos(ea),
    #                        e.dxf.center.y + e.dxf.radius * math.sin(ea)))
    #     else:
    #         continue
    #     graph[s].append((e, en))
    #     graph[en].append((e, s))

    # print(f"\n--- DEBUG GRAPH ---")
    # print(f"  Nodi totali: {len(graph)}")
    # for node, neighbors in graph.items():
    #     if len(neighbors) > 2:
    #         print(f"  BRANCHING NODE {node}: degree={len(neighbors)}")
    #         for ent, nbr in neighbors:
    #             print(f"    → {ent.dxftype()} layer={ent.dxf.layer}")

    # inspector.analyze(msp, title=input_file, doc=doc)
    # debug_point_on_arc(msp, tolerance=2.0)
    # for e in msp:
    #   print(e.dxftype())
    # for e in msp:
    #     if e.dxftype() == 'INSERT':
    #         try:
    #             block = doc.blocks.get(e.dxf.name)
    #             inner = Counter(sub.dxftype() for sub in block)
    #             print(f"  INSERT '{e.dxf.name}' contiene: {dict(inner)}")
    #         except Exception as ex:
    #             print(f"  INSERT error: {ex}")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILE
    analyze_dxf(filepath)