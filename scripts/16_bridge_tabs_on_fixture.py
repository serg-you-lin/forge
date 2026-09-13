"""
16_bridge_tabs_on_fixture.py — linguette sul file reale di Federico
=====================================================================

Carica `cerchi_concentrici_detect_is_counter_tabs_join.dxf` (rettangolo +
2 cerchi concentrici, r=9 e r~4.12) e collega il cerchio interno (nipote,
depth 2) al suo genitore diretto (l'anello r=9, depth 1) con 4 linguette —
un ponte fra i due contorni, non un gap in uno solo (MAP.md D40).

Il resto del disegno (il rettangolo) resta intatto.

    python scripts/16_bridge_tabs_on_fixture.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import math
import os

import ezdxf

import forge
from forge.core.primitives.segments import LineSeg, ArcSeg, CircleSeg
from forge.tools.tabs import bridge_nested_tabs

# --- CONFIG ------------------------------------------------------------
INPUT = r"tests/examples/cerchi_concentrici_detect_is_counter_tabs_join.dxf"
TAB_COUNT = 4
TAB_WIDTH = 2.0    # mm, larghezza reale (perpendicolare) della linguetta
ARC_FIT_TOLERANCE = 0.05
DISCRETIZE_TOLERANCE = 0.05
OUTDIR = "pipeline_output"
# -------------------------------------------------------------------------


def write_native(msp, seg):
    if isinstance(seg, LineSeg):
        msp.add_line(seg.start, seg.end)
    elif isinstance(seg, ArcSeg):
        msp.add_arc(
            center=seg.center, radius=seg.radius,
            start_angle=math.degrees(seg.start_angle),
            end_angle=math.degrees(seg.end_angle),
        )
    elif isinstance(seg, CircleSeg):
        msp.add_circle(center=seg.center, radius=seg.radius)
    else:
        raise TypeError(f"tipo non gestito in questo script: {type(seg)}")


doc = forge.load_dxf(INPUT)
result = forge.heal(doc)
cluster = result.clusters[0]

bridges = bridge_nested_tabs(cluster, tab_width=TAB_WIDTH, tab_count=TAB_COUNT,
                              discretize_tolerance=DISCRETIZE_TOLERANCE)
if not bridges:
    raise SystemExit("nessuna coppia isola/genitore trovata nel fixture")
bridge = bridges[0]
print(f"figlio depth={bridge.child_contour.depth}  genitore depth={bridge.parent_contour.depth}")
print(f"{len(bridge.tab_edges)} fianchi di linguetta ({TAB_COUNT} linguette)")

bridged_contours = {id(bridge.child_contour), id(bridge.parent_contour)}

doc_out = ezdxf.new(dxfversion="R2010")
msp = doc_out.modelspace()

# outer e ogni altro inner non coinvolto nel ponte: intatti
for seg in cluster.outer.segments:
    write_native(msp, seg)
for other in cluster.inners:
    if id(other) not in bridged_contours:
        for seg in other.segments:
            write_native(msp, seg)

# i due contorni ponteggiati: ogni stretch rifittato, i fianchi come LINE native
for stretch in bridge.child_stretches + bridge.parent_stretches:
    segments = forge.simplify_points(stretch, closed=False, arc_fit_tolerance=ARC_FIT_TOLERANCE)
    print(f"  stretch di {len(stretch)} punti -> {[type(s).__name__ for s in segments]}")
    for seg in segments:
        write_native(msp, seg)

for edge in bridge.tab_edges:
    write_native(msp, edge)

os.makedirs(OUTDIR, exist_ok=True)
path = os.path.join(OUTDIR, "cerchi_concentrici_con_linguette.dxf")
doc_out.saveas(path)
print(f"scritto {path}")
