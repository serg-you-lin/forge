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
        source_ref : oggetto originale (entità ezdxf, DxfWriteContext, …)
                     — serve per traceability e writeback; se None la forma è
                     stata ricostruita dal core e non corrisponde ad una singola
                     entità sorgente
        shape_type : categoria geometrica — "circle" | "polyline" |
                     "spline" | "ellipse"
        diameter   : diametro in unità documento — solo per cerchi, None altrimenti
        center     : centro (x, y) — solo per cerchi, None altrimenti
    """
    polygon:    Polygon
    source_ref: Any
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
        source_ref : oggetto originale — serve per traceability e writeback
        shape_type : categoria geometrica — "line" | "arc" | "polyline" | …
    """
    pts:        List[Tuple[float, float]]
    length:     float
    source_ref: Any
    role:       ContourRole                   = field(default=ContourRole.UNKNOWN)
    shape_type: str                           = ""
    diameter:   Optional[float]               = None
    center:     Optional[Tuple[float, float]] = None
