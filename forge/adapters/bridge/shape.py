"""
bridge/shape.py

Due tipi distinti per due concetti distinti:
  - ClosedShape : contorno chiuso → ha un Polygon shapely
  - OpenShape   : traccia aperta  → ha pts e length

L'adapter popola `role` prima di consegnare le shape al core.
`origin` è deprecato — rimane temporaneamente per backward compat
durante il refactor, ma detect.py non deve leggerlo.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Any
from shapely.geometry import Polygon

from ...model.role import ContourRole


@dataclass
class ClosedShape:
    """
    Forma chiusa pronta per la hierarchy.

    Prodotta dall'adapter (DXF, PDF, …) — il core la tratta come opaca
    rispetto al formato.

    Campi:
        polygon    : Polygon shapely — forma chiusa già calcolata
        role       : ruolo semantico — impostato dall'adapter prima del core
        shape_type : categoria geometrica — "circle" | "polyline" |
                     "spline" | "ellipse"
        diameter   : diametro in unità documento — solo per cerchi, None altrimenti
        center     : centro (x, y) — solo per cerchi, None altrimenti
    """
    polygon:    Polygon
    role:       ContourRole                   = field(default=ContourRole.UNKNOWN)
    shape_type: str                           = ""
    diameter:   Optional[float]               = None
    center:     Optional[Tuple[float, float]] = None
    segments:   List                          = field(default_factory=list)
    origin:     str                           = ""


@dataclass
class OpenShape:
    """
    Traccia aperta — tipicamente una bending line o un segmento non chiuso.

    Non ha Polygon: la gerarchia non la tocca, serve a detect() e inject().

    Campi:
        pts        : lista di vertici (x, y) nell'ordine della traccia
        length     : lunghezza totale in unità documento
        role       : ruolo semantico — impostato dall'adapter prima del core
        shape_type : categoria geometrica — "line" | "arc" | "polyline" | …
        segments   : primitive native (LineSeg/ArcSeg/SplineSeg) da cui la
                     traccia è stata discretizzata — servono a write()/to_dxf()
                     per materializzare la geometria senza perdere fedeltà
                     (es. engrave line su layer speciale)
    """
    pts:        List[Tuple[float, float]]
    length:     float
    role:       ContourRole                   = field(default=ContourRole.UNKNOWN)
    shape_type: str                           = ""
    diameter:   Optional[float]               = None
    center:     Optional[Tuple[float, float]] = None
    segments:   List                          = field(default_factory=list)
