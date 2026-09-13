"""
16_cut_tabs_on_fixture.py — linguette sul file reale di Federico
===================================================================

Carica `cerchi_concentrici_detect_is_counter_tabs_join.dxf` (rettangolo +
2 cerchi concentrici, r=9 e r~4.12) e taglia le linguette sull'anello
esterno (r=9) — quello che oggi `detect()` fonderebbe in una svasatura
insieme al cerchio interno (vedi MAP.md, discussione disambiguazione
countersink/join). Qui NON si passa da `detect()`: cut_tabs e detect non
convivono sullo stesso contorno (o linguette, o classificazione hole).

Il cerchio bersaglio si identifica per **raggio** — nessun layer coinvolto,
nessun label_map: `cut_tabs` lavora su punti grezzi, non su ruoli.

    python scripts/16_cut_tabs_on_fixture.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import math
import os

import ezdxf

import forge
from forge.core.primitives.segments import LineSeg, ArcSeg, CircleSeg
from forge.tools.tabs import cut_tabs

# --- CONFIG ------------------------------------------------------------
INPUT = r"tests/examples/cerchi_concentrici_detect_is_counter_tabs_join.dxf"
TAB_RING_RADIUS     = 9.0    # quale cerchio riceve le linguette
RADIUS_TOLERANCE    = 0.01
TAB_COUNT           = 4
TAB_WIDTH           = 2.0    # mm, lunghezza del ponticello lungo il perimetro
ARC_FIT_TOLERANCE   = 0.05
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

targets = [
    e for e in doc.edges
    if isinstance(e.segment, CircleSeg)
    and abs(e.segment.radius - TAB_RING_RADIUS) <= RADIUS_TOLERANCE
]
if not targets:
    raise SystemExit(f"nessun cerchio di raggio ~{TAB_RING_RADIUS} in {INPUT}")
target = targets[0]
other_edges = [e for e in doc.edges if e is not target]
print(f"anello con linguette: centro={target.segment.center}  raggio={target.segment.radius}")
print(f"resto del disegno intatto: {len(other_edges)} edge (rettangolo + altro cerchio)")

raw_points = target.segment.discretize(DISCRETIZE_TOLERANCE)[:-1]  # chiuso -> apro
n = len(raw_points)
tab_positions = [round(i * n / TAB_COUNT) for i in range(TAB_COUNT)]

stretches = cut_tabs(raw_points, closed=True, tab_positions=tab_positions, tab_width=TAB_WIDTH)
print(f"{len(stretches)} stretch aperti dopo {TAB_COUNT} linguette")

doc_out = ezdxf.new(dxfversion="R2010")
msp = doc_out.modelspace()

for e in other_edges:
    write_native(msp, e.segment)

for stretch in stretches:
    segments = forge.simplify_points(stretch, closed=False, arc_fit_tolerance=ARC_FIT_TOLERANCE)
    print(f"  stretch di {len(stretch)} punti -> {[type(s).__name__ for s in segments]}")
    for seg in segments:
        write_native(msp, seg)

os.makedirs(OUTDIR, exist_ok=True)
path = os.path.join(OUTDIR, "cerchi_concentrici_con_linguette.dxf")
doc_out.saveas(path)
print(f"scritto {path}")
