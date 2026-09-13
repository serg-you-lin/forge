"""
15_cut_tabs.py — linguette su un anello, per vedere l'import giusto
====================================================================

`cut_tabs` NON è nel contratto pubblico flat (`forge.*`): si importa
esplicitamente da `forge.tools.tabs`, come `detect_corners`/`fit_primitives`
prima di loro — un utente che si aspetta `forge.*` sempre puramente
ricostruttivo non deve incappare per caso in qualcosa che aggiunge un gap che
nel disegno sorgente non c'era (MAP.md D39).

Pipeline dimostrata (un anello, 4 linguette — il caso concreto da cui è nata
la funzione: un cerchio che deve restare attaccato al resto della lamiera):

    punti grezzi del cerchio
        -> cut_tabs()                  4 stretch aperti (i ponticelli)
        -> simplify_points() per stretch, con arc_fit_tolerance   ArcSeg puliti
        -> load_geometry("arc"/"line")  Edge di forge
        -> to_dxf()                     DXF con 4 archi + i micro-segmenti di raccordo

Apri il DXF risultante in un viewer: si devono vedere 4 interruzioni nette
sul cerchio, non una spline che le smussa via.

    python scripts/15_cut_tabs.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import math
import os

import ezdxf

import forge
from forge.tools.tabs import cut_tabs

# --- CONFIG ------------------------------------------------------------
RADIUS      = 20.0
N_POINTS    = 200      # densità del cerchio grezzo, come da un contorno reale
TAB_COUNT   = 4
TAB_WIDTH   = 2.0       # mm, lunghezza del ponticello lungo il perimetro
ARC_FIT_TOLERANCE = 0.05
OUTDIR = "pipeline_output"
# -------------------------------------------------------------------------


def circle_points(radius, n):
    return [
        (radius * math.cos(2 * math.pi * i / n), radius * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def write_segment(msp, seg):
    """LineSeg/ArcSeg -> entità DXF nativa (script, non libreria: un anello con
    linguette è aperto per costruzione, non passa da heal()/to_dxf(), che si
    aspettano un contorno chiuso)."""
    from forge.core.primitives.segments import LineSeg, ArcSeg

    if isinstance(seg, LineSeg):
        msp.add_line(seg.start, seg.end)
    elif isinstance(seg, ArcSeg):
        msp.add_arc(
            center=seg.center, radius=seg.radius,
            start_angle=math.degrees(seg.start_angle),
            end_angle=math.degrees(seg.end_angle),
        )
    else:
        raise TypeError(f"tipo non gestito in questo script: {type(seg)}")


raw_points = circle_points(RADIUS, N_POINTS)
tab_positions = [round(i * N_POINTS / TAB_COUNT) for i in range(TAB_COUNT)]

stretches = cut_tabs(raw_points, closed=True, tab_positions=tab_positions, tab_width=TAB_WIDTH)
print(f"{len(stretches)} stretch aperti dopo {TAB_COUNT} linguette")

doc_out = ezdxf.new(dxfversion="R2010")
msp = doc_out.modelspace()

for stretch in stretches:
    segments = forge.simplify_points(stretch, closed=False, arc_fit_tolerance=ARC_FIT_TOLERANCE)
    print(f"  stretch di {len(stretch)} punti -> {[type(s).__name__ for s in segments]}")
    for seg in segments:
        write_segment(msp, seg)

os.makedirs(OUTDIR, exist_ok=True)
path = os.path.join(OUTDIR, "cut_tabs_ring.dxf")
doc_out.saveas(path)
print(f"scritto {path}")
