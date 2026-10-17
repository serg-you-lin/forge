"""
topo/core/geometry/__init__.py
-------------------------------
La geometria di topo, un posto solo: `topo.geometry.<nome>` (MAP.md D95).
Fatti con nomi geometrici — "cerchio", mai "foro": cosa significano lo
decide il consumatore.

Pubblici (qui sotto):
    build.py          costruire forme come segmenti: polygon, rectangle, regular_polygon, circle, stadium
    shape.py          forma di un contorno chiuso; cerchi concentrici; archi attorno a un cerchio
    lines.py          una corda che divide un poligono; file di tratti collineari unite attraverso dei poligoni; tratteggio di un segmento
    regions.py        punto su un contorno (vertice, raccordo, lato); tratto tagliato da una regione; contorno meno regione
    axis.py           rettangoli coperti da tratti, linee che li attraversano, lati sul bordo di un altro, quota sugli assi

Mattoni (si importano dal sottomodulo):
    measure.py        arrotondamento dei nodi, lunghezza e angolo di un segmento, tracce aperte, "è circolare?"
    points.py         sequenze di punti: spigoli, doppioni, fit di cerchio, b-spline
    intersections.py  retta/retta, cerchio/retta, cerchio/cerchio, polilinea/retta
                      (pubblica: `intersections(a, b)` fra due primitive qualunque)
    lines.py, axis.py anche: distanza da una retta, collinearità, intervalli, tratti dentro un riquadro
"""

from .build import polygon, rectangle, regular_polygon, circle, stadium
from .shape import (
    contour_shape, ContourShape,
    concentric_groups, ConcentricGroup,
    arcs_around, ArcAround,
)
from .lines import splits_polygon, bridged_runs, CollinearRun, dash_line
from .regions import point_on_contour, ContourPoint, cut_by, contour_minus
from .intersections import intersections
from .axis import covered_rectangles, CoveredRectangle, spanning_lines, sides_on_border, axis_aligned_share

__all__ = [
    "polygon", "rectangle", "regular_polygon", "circle", "stadium",
    "contour_shape", "ContourShape",
    "concentric_groups", "ConcentricGroup",
    "arcs_around", "ArcAround",
    "splits_polygon", "bridged_runs", "CollinearRun", "dash_line",
    "point_on_contour", "ContourPoint", "cut_by", "contour_minus", "intersections",
    "covered_rectangles", "CoveredRectangle", "spanning_lines", "sides_on_border", "axis_aligned_share",
]
