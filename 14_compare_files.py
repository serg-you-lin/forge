

"""
compare_dxf.py
--------------
Compara due file DXF (tipicamente: healato vs splittato)
e stampa le differenze per tipo di entità, layer e geometria.

Uso:
    python compare_dxf.py file_a.dxf file_b.dxf
    python compare_dxf.py              (usa i DEFAULT sotto)
"""

import sys
import os
import ezdxf
from collections import Counter, defaultdict
import dxf_forge as forge

# ← CAMBIA QUI se vuoi lanciare senza argomenti
DEFAULT_A = r"tests/examples/scritta_healed.dxf"
DEFAULT_B = r"tests/examples/files_multipli/6200002991Sviluppo/6200002991Sviluppo_PART5.dxf"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load(path: str):
    path = os.path.abspath(path)
    try:
        doc = ezdxf.readfile(path)
    except IOError:
        print(f"  ERRORE: file non trovato — {path}")
        sys.exit(1)
    except ezdxf.DXFStructureError:
        print(f"  ERRORE: DXF non valido — {path}")
        sys.exit(1)
    if doc.dxfversion < 'AC1015':
        doc = forge.upgrade_to_r2010(doc)
    return doc, doc.modelspace()


def entity_summary(msp) -> dict:
    by_type  = Counter()
    by_layer = defaultdict(Counter)
    for e in msp:
        t     = e.dxftype()
        layer = e.dxf.layer if e.dxf.hasattr('layer') else '??'
        by_type[t] += 1
        by_layer[layer][t] += 1
    return {"by_type": by_type, "by_layer": dict(by_layer)}


def spline_details(msp) -> list:
    rows = []
    for s in msp.query('SPLINE'):
        try:
            from dxf_forge.graph import spline_endpoints
            start, end = spline_endpoints(s)
        except Exception:
            start = end = None
        rows.append({
            "degree" : s.dxf.get('degree', '?'),
            "closed" : s.closed,
            "n_ctrl" : len(s.control_points),
            "n_knots": len(s.knots) if s.knots else 0,
            "layer"  : s.dxf.layer if s.dxf.hasattr('layer') else '??',
            "start"  : start,
            "end"    : end,
        })
    return rows


def pline_details(msp) -> list:
    rows = []
    for p in msp.query('LWPOLYLINE'):
        pts = list(p.get_points())
        rows.append({
            "n_pts" : len(pts),
            "closed": p.closed,
            "layer" : p.dxf.layer if p.dxf.hasattr('layer') else '??',
        })
    return rows


def circle_details(msp) -> list:
    rows = []
    for c in msp.query('CIRCLE'):
        rows.append({
            "radius": round(c.dxf.radius, 4),
            "layer" : c.dxf.layer if c.dxf.hasattr('layer') else '??',
            "center": (round(c.dxf.center.x, 2), round(c.dxf.center.y, 2)),
        })
    return rows


def approx_bbox(msp):
    xs, ys = [], []
    for e in msp:
        t = e.dxftype()
        try:
            if t == 'LINE':
                xs += [e.dxf.start.x, e.dxf.end.x]
                ys += [e.dxf.start.y, e.dxf.end.y]
            elif t in ('CIRCLE', 'ARC'):
                xs.append(e.dxf.center.x)
                ys.append(e.dxf.center.y)
            elif t == 'LWPOLYLINE':
                for pt in e.get_points():
                    xs.append(pt[0]); ys.append(pt[1])
            elif t == 'SPLINE':
                for cp in e.control_points:
                    xs.append(cp[0]); ys.append(cp[1])
        except Exception:
            pass
    if not xs:
        return None
    return (round(min(xs), 2), round(min(ys), 2),
            round(max(xs), 2), round(max(ys), 2))


# ---------------------------------------------------------------------------
# Stampa
# ---------------------------------------------------------------------------

def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def compare(path_a: str, path_b: str):
    name_a = os.path.basename(path_a)
    name_b = os.path.basename(path_b)

    print(f"\nA: {path_a}")
    print(f"B: {path_b}")

    doc_a, msp_a = load(path_a)
    doc_b, msp_b = load(path_b)

    sum_a = entity_summary(msp_a)
    sum_b = entity_summary(msp_b)

    # ------------------------------------------------------------------
    section("ENTITÀ PER TIPO")
    all_types = sorted(set(sum_a["by_type"]) | set(sum_b["by_type"]))
    col = 20
    print(f"  {'Tipo':<{col}}  {'A':>6}  {'B':>6}  {'Δ':>6}")
    print(f"  {'-'*col}  {'------'}  {'------'}  {'------'}")
    for t in all_types:
        a = sum_a["by_type"].get(t, 0)
        b = sum_b["by_type"].get(t, 0)
        delta = b - a
        flag = "  ←" if delta != 0 else ""
        print(f"  {t:<{col}}  {a:>6}  {b:>6}  {delta:>+6}{flag}")

    # ------------------------------------------------------------------
    section("ENTITÀ PER LAYER")
    all_layers = sorted(set(sum_a["by_layer"]) | set(sum_b["by_layer"]))
    for layer in all_layers:
        ca = sum_a["by_layer"].get(layer, Counter())
        cb = sum_b["by_layer"].get(layer, Counter())
        all_t = sorted(set(ca) | set(cb))
        diffs = [(t, ca.get(t, 0), cb.get(t, 0)) for t in all_t
                 if ca.get(t, 0) != cb.get(t, 0)]
        if diffs:
            print(f"\n  Layer '{layer}':")
            for t, a, b in diffs:
                delta = b - a
                flag = "  ←" if delta != 0 else ""
                print(f"    {t:<{col}}  {a:>6}  {b:>6}  {delta:>+6}{flag}")


# ------------------------------------------------------------------
    section("BOUNDING BOX APPROSSIMATA")
    bbox_a = approx_bbox(msp_a)
    bbox_b = approx_bbox(msp_b)
    
    print(f"  A: {bbox_a}")
    print(f"  B: {bbox_b}")
    
    if bbox_a != bbox_b:
        print("\n  [!] ATTENZIONE: Le Bounding Box differiscono!")
        if bbox_a and bbox_b:
            dx = round(bbox_b[2] - bbox_b[0], 2) - round(bbox_a[2] - bbox_a[0], 2)
            dy = round(bbox_b[3] - bbox_b[1], 2) - round(bbox_a[3] - bbox_a[1], 2)
            print(f"      Differenza Dimensioni: DeltaX: {dx:>+6} | DeltaY: {dy:>+6}")

    # ------------------------------------------------------------------
    section("DETTAGLI GEOMETRICI (SAMPLED)")
    # Comparazione rapida dei cerchi come esempio
    c_a = circle_details(msp_a)
    c_b = circle_details(msp_b)
    if len(c_a) != len(c_b):
        print(f"  [!] Numero di cerchi variato: A={len(c_a)}, B={len(c_b)}")
    
    # Esempio: Controlla se le Spline sono state "esplose" o alterate
    s_a = spline_details(msp_a)
    s_b = spline_details(msp_b)
    if len(s_a) != len(s_b):
        print(f"  [!] Numero di Spline variato: A={len(s_a)}, B={len(s_b)}")
        if len(s_b) == 0 and len(s_a) > 0:
            print("      HINT: Lo splitter potrebbe aver convertito le SPLINE in polilinee!")

    print("\n--- Fine Comparazione ---")

# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Gestione argomenti da riga di comando
    if len(sys.argv) == 3:
        file_a = sys.argv[1]
        file_b = sys.argv[2]
    else:
        file_a = DEFAULT_A
        file_b = DEFAULT_B

    # Verifica esistenza file prima di iniziare
    if not os.path.exists(file_a) or not os.path.exists(file_b):
        print(f"ERRORE: Uno dei file non esiste.\nA: {file_a}\nB: {file_b}")
        print("\nUso: python compare_dxf.py file1.dxf file2.dxf")
    else:
        compare(file_a, file_b)