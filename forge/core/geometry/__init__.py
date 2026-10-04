"""
forge/core/geometry/__init__.py
-------------------------------
La geometria di forge, un posto solo: `forge.geometry.<nome>` (MAP.md D95).
Fatti con nomi geometrici — "cerchio", mai "foro": cosa significano lo
decide il consumatore.

Pubblici (qui sotto):
    shape.py          forma di un contorno chiuso; cerchi concentrici; archi attorno a un cerchio
    lines.py          una corda che divide un poligono; file di tratti collineari unite attraverso dei poligoni
    axis.py           rettangoli coperti da tratti, linee che li attraversano, quota sugli assi

Mattoni (si importano dal sottomodulo):
    measure.py        arrotondamento dei nodi, lunghezza e angolo di un segmento, tracce aperte, "è circolare?"
    points.py         sequenze di punti: spigoli, doppioni, fit di cerchio, b-spline
    intersections.py  retta/retta, cerchio/retta, cerchio/cerchio, polilinea/retta
    lines.py, axis.py anche: distanza da una retta, collinearità, intervalli, tratti dentro un riquadro
"""

from .shape import (
    contour_shape, ContourShape,
    concentric_groups, ConcentricGroup,
    arcs_around, ArcAround,
)
from .lines import splits_polygon, bridged_runs, CollinearRun
from .axis import covered_rectangles, CoveredRectangle, spanning_lines, axis_aligned_share

__all__ = [
    "contour_shape", "ContourShape",
    "concentric_groups", "ConcentricGroup",
    "arcs_around", "ArcAround",
    "splits_polygon", "bridged_runs", "CollinearRun",
    "covered_rectangles", "CoveredRectangle", "spanning_lines", "axis_aligned_share",
]
